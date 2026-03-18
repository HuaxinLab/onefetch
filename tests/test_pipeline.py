from onefetch.adapters.base import BaseAdapter
from onefetch.models import FeedEntry
from onefetch.pipeline import IngestionPipeline
from onefetch.router import Router


class FakeAdapter(BaseAdapter):
    id = "fake"
    register = False

    def supports(self, url: str) -> bool:
        return True

    async def crawl(self, url: str) -> FeedEntry:
        return FeedEntry(
            source_url=url,
            canonical_url=url,
            crawler_id=self.id,
            title="ok",
            body="payload",
        )


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
