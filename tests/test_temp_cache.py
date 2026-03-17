from pathlib import Path

from onefetch.cache import TempCacheService
from onefetch.config import OneFetchConfig
from onefetch.models import IngestResult


def _make_result(url: str, content_hash: str) -> IngestResult:
    return IngestResult(
        source_url=url,
        canonical_url=url,
        crawler_id="generic_html",
        status="fetched",
        content_hash=content_hash,
        title="t",
        body_full=f"body-{content_hash}",
    )


def test_temp_cache_prunes_old_entries(tmp_path: Path) -> None:
    paths = OneFetchConfig.from_project_root(tmp_path).paths()
    cache = TempCacheService(paths, max_entries=2)

    p1 = Path(cache.save_result(_make_result("https://example.com/a", "h1")))
    p2 = Path(cache.save_result(_make_result("https://example.com/b", "h2")))
    p3 = Path(cache.save_result(_make_result("https://example.com/c", "h3")))

    existing = sorted(paths.temp_cache_dir.glob("*.json"))
    assert len(existing) == 2
    assert not p1.exists()
    assert p2.exists()
    assert p3.exists()

