import httpx

from onefetch.adapters.base import BaseAdapter
from onefetch.pipeline import IngestionPipeline
from onefetch.router import Router


class TimeoutAdapter(BaseAdapter):
    id = "timeout"

    def supports(self, url: str) -> bool:
        return True

    async def crawl(self, url: str):
        raise httpx.TimeoutException("timeout")


async def test_pipeline_classifies_timeout_error() -> None:
    pipeline = IngestionPipeline(router=Router([TimeoutAdapter()]))
    report = await pipeline.ingest_urls(["https://example.com/a"])

    assert report.failed_count == 1
    result = report.results[0]
    assert result.error_code == "network.timeout"
    assert result.error_type == "network"
    assert result.retryable is True
