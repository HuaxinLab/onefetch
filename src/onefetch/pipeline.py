from __future__ import annotations

from onefetch.models import BatchIngestReport, IngestResult
from onefetch.router import Router
from onefetch.storage import StorageService


class IngestionPipeline:
    def __init__(self, router: Router, storage: StorageService) -> None:
        self._router = router
        self._storage = storage

    async def ingest_urls(self, urls: list[str], forced_adapter: str | None = None) -> BatchIngestReport:
        unique_urls = list(dict.fromkeys(urls))
        report = BatchIngestReport(requested_urls=unique_urls)

        for source_url in unique_urls:
            try:
                adapter = self._router.route(source_url, forced_adapter=forced_adapter)
                output = await adapter.crawl(source_url)
                output.feed.compute_content_hash()

                duplicate = self._storage.find_duplicate(output.feed.canonical_url, output.feed.content_hash)
                if duplicate:
                    report.duplicate_count += 1
                    report.results.append(
                        IngestResult(
                            source_url=source_url,
                            canonical_url=output.feed.canonical_url,
                            crawler_id=adapter.id,
                            status="duplicate",
                            title=output.feed.title,
                            raw_path=duplicate.get("raw_path", ""),
                            feed_path=duplicate.get("feed_path", ""),
                            note_path=duplicate.get("note_path", ""),
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
                        source_url=source_url,
                        canonical_url=output.feed.canonical_url,
                        crawler_id=adapter.id,
                        status="stored",
                        title=output.feed.title,
                        raw_path=raw_path,
                        feed_path=feed_path,
                        note_path=note_path,
                    )
                )
            except Exception as exc:
                report.failed_count += 1
                report.results.append(
                    IngestResult(
                        source_url=source_url,
                        canonical_url=source_url,
                        crawler_id=forced_adapter or "auto",
                        status="failed",
                        error=str(exc),
                    )
                )

        return report
