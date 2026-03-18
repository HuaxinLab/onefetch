from onefetch.adapters.base import BaseAdapter
from onefetch.models import Capture, CrawlOutput, FeedEntry
from onefetch.pipeline import IngestionPipeline
from onefetch.router import Router


class FakeAdapter(BaseAdapter):
    id = "fake"
    register = False

    def supports(self, url: str) -> bool:
        return True

    async def crawl(self, url: str) -> CrawlOutput:
        capture = Capture(
            source_url=url,
            canonical_url=url,
            final_url=url,
            status_code=200,
            body="<html>ok</html>",
        )
        feed = FeedEntry(
            source_url=url,
            canonical_url=url,
            crawler_id=self.id,
            title="ok",
            body="payload",
        )
        return CrawlOutput(capture=capture, feed=feed)


async def test_pipeline_fetch_only() -> None:
    router = Router([FakeAdapter()])
    pipeline = IngestionPipeline(router=router)

    report = await pipeline.ingest_urls(["https://example.com/a"])
    assert report.fetched_count == 1
    assert report.failed_count == 0
    assert len(report.results) == 1
    assert report.results[0].status == "fetched"


async def test_pipeline_deduplicates_urls() -> None:
    router = Router([FakeAdapter()])
    pipeline = IngestionPipeline(router=router)

    report = await pipeline.ingest_urls([
        "https://example.com/a",
        "https://example.com/a",
    ])
    assert report.fetched_count == 1
    assert len(report.results) == 1
