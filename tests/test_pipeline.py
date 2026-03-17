from pathlib import Path

from onefetch.adapters.base import BaseAdapter
from onefetch.config import OneFetchConfig
from onefetch.models import Capture, CrawlOutput, FeedEntry
from onefetch.pipeline import IngestionPipeline
from onefetch.router import Router
from onefetch.storage import StorageService


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


async def test_pipeline_fetch_only(tmp_path: Path) -> None:
    router = Router([FakeAdapter()])
    pipeline = IngestionPipeline(router=router, storage=None)

    report = await pipeline.ingest_urls(["https://example.com/a"])
    assert report.fetched_count == 1
    assert report.stored_count == 0
    assert report.duplicate_count == 0


async def test_pipeline_stored_then_duplicate(tmp_path: Path) -> None:
    config = OneFetchConfig.from_project_root(tmp_path)
    storage = StorageService(config.paths())
    router = Router([FakeAdapter()])
    pipeline = IngestionPipeline(router=router, storage=storage)

    first = await pipeline.ingest_urls(["https://example.com/a"], store=True)
    assert first.stored_count == 1
    assert first.duplicate_count == 0

    second = await pipeline.ingest_urls(["https://example.com/a"], store=True)
    assert second.stored_count == 0
    assert second.duplicate_count == 1
