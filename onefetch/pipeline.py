from __future__ import annotations

import httpx

from onefetch.models import BatchIngestReport, IngestResult
from onefetch.router import Router


class IngestionPipeline:
    def __init__(self, router: Router) -> None:
        self._router = router

    async def ingest_urls(
        self,
        urls: list[str],
        forced_adapter: str | None = None,
    ) -> BatchIngestReport:
        unique_urls = list(dict.fromkeys(urls))
        report = BatchIngestReport(requested_urls=unique_urls)

        for source_url in unique_urls:
            try:
                adapter = self._router.route(source_url, forced_adapter=forced_adapter)
                feed = await adapter.crawl(source_url)
                feed.compute_content_hash()

                comment_fetch = (feed.metadata or {}).get("comment_fetch") or {}
                comment_source = str(comment_fetch.get("source") or "none")
                api_reason = (comment_fetch.get("api") or {}).get("reason")
                risk_controlled = api_reason in {"risk_controlled", "risk_cooldown"}

                report.fetched_count += 1
                report.results.append(
                    IngestResult(
                        source_url=source_url,
                        canonical_url=feed.canonical_url,
                        crawler_id=adapter.id,
                        status="fetched",
                        content_hash=feed.content_hash,
                        title=feed.title,
                        comment_count=len(feed.comments),
                        comment_source=comment_source,
                        body_preview=self._preview(feed.body, limit=280),
                        body_excerpt=self._preview(feed.body, limit=1600),
                        body_full=(feed.body or "").strip(),
                        images=feed.images,
                        risk_controlled=risk_controlled,
                    )
                )
            except Exception as exc:
                code, err_type, retryable, action_hint = self._classify_error(exc)
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
                        action_hint=action_hint,
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
    def _classify_error(exc: Exception) -> tuple[str, str, bool, str]:
        """Return (error_code, error_type, retryable, action_hint)."""
        if isinstance(exc, LookupError):
            return "route.not_found", "route", False, ""
        if isinstance(exc, httpx.TimeoutException):
            return "network.timeout", "network", True, ""
        if isinstance(exc, httpx.HTTPStatusError):
            status = exc.response.status_code if exc.response else 0
            if status in {429, 461}:
                return "risk.rate_limited", "risk", True, ""
            if status >= 500:
                return f"network.http_{status}", "network", True, ""
            return f"network.http_{status}", "network", False, ""
        message = str(exc).lower()
        if "playwright is not installed" in message:
            return (
                "dep.playwright_missing",
                "dependency",
                False,
                "pip install 'onefetch[browser]' && python -m playwright install chromium",
            )
        if "risk" in message or "captcha" in message or "风控" in message:
            return "risk.blocked", "risk", True, ""
        if "parse" in message or "json" in message:
            return "parse.failed", "parse", False, ""
        return "unknown", "unknown", False, ""
