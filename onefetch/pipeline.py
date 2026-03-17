from __future__ import annotations

import httpx

from onefetch.models import BatchIngestReport, IngestResult
from onefetch.router import Router
from onefetch.storage import StorageService


class IngestionPipeline:
    def __init__(self, router: Router, storage: StorageService | None = None) -> None:
        self._router = router
        self._storage = storage

    async def ingest_urls(
        self,
        urls: list[str],
        forced_adapter: str | None = None,
        *,
        store: bool = False,
    ) -> BatchIngestReport:
        unique_urls = list(dict.fromkeys(urls))
        report = BatchIngestReport(requested_urls=unique_urls)

        for source_url in unique_urls:
            try:
                adapter = self._router.route(source_url, forced_adapter=forced_adapter)
                output = await adapter.crawl(source_url)
                output.feed.compute_content_hash()

                comment_fetch = (output.feed.metadata or {}).get("comment_fetch") or {}
                comment_source = str(comment_fetch.get("source") or "none")
                api_reason = (comment_fetch.get("api") or {}).get("reason")
                risk_controlled = api_reason in {"risk_controlled", "risk_cooldown"}

                common_result = {
                    "source_url": source_url,
                    "canonical_url": output.feed.canonical_url,
                    "crawler_id": adapter.id,
                    "title": output.feed.title,
                    "comment_count": len(output.feed.comments),
                    "comment_source": comment_source,
                    "body_preview": self._preview(output.feed.body, limit=280),
                    "body_excerpt": self._preview(output.feed.body, limit=1600),
                    "risk_controlled": risk_controlled,
                }

                if not store:
                    report.fetched_count += 1
                    report.results.append(IngestResult(status="fetched", **common_result))
                    continue

                if self._storage is None:
                    raise RuntimeError("Storage is not initialized but store=True was requested.")

                duplicate = self._storage.find_duplicate(output.feed.canonical_url, output.feed.content_hash)
                if duplicate:
                    report.duplicate_count += 1
                    report.results.append(
                        IngestResult(
                            status="duplicate",
                            raw_path=duplicate.get("raw_path", ""),
                            feed_path=duplicate.get("feed_path", ""),
                            note_path=duplicate.get("note_path", ""),
                            **common_result,
                        )
                    )
                    continue

                raw_path = self._storage.save_capture(output.capture)
                feed_path = self._storage.save_feed(output.feed)
                note_path = self._storage.save_note(output.feed)
                self._storage.append_catalog(output.feed, raw_path, feed_path, note_path)

                report.stored_count += 1
                report.results.append(
                    IngestResult(
                        status="stored",
                        raw_path=raw_path,
                        feed_path=feed_path,
                        note_path=note_path,
                        **common_result,
                    )
                )
            except Exception as exc:
                code, err_type, retryable = self._classify_error(exc)
                report.failed_count += 1
                report.results.append(
                    IngestResult(
                        source_url=source_url,
                        canonical_url=source_url,
                        crawler_id=forced_adapter or "auto",
                        status="failed",
                        error=str(exc),
                        error_code=code,
                        error_type=err_type,
                        retryable=retryable,
                    )
                )

        return report

    @staticmethod
    def _preview(body: str, limit: int = 280) -> str:
        text = " ".join((body or "").split())
        if len(text) <= limit:
            return text
        return text[: limit - 1] + "…"

    @staticmethod
    def _classify_error(exc: Exception) -> tuple[str, str, bool]:
        if isinstance(exc, LookupError):
            return "route.not_found", "route", False
        if isinstance(exc, httpx.TimeoutException):
            return "network.timeout", "network", True
        if isinstance(exc, httpx.HTTPStatusError):
            status = exc.response.status_code if exc.response else 0
            if status in {429, 461}:
                return "risk.rate_limited", "risk", True
            if status >= 500:
                return f"network.http_{status}", "network", True
            return f"network.http_{status}", "network", False
        message = str(exc).lower()
        if "risk" in message or "captcha" in message or "风控" in message:
            return "risk.blocked", "risk", True
        if "parse" in message or "json" in message:
            return "parse.failed", "parse", False
        return "unknown", "unknown", False
