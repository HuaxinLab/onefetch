from pathlib import Path

from onefetch.config import OneFetchConfig
from onefetch.models import Capture, FeedEntry
from onefetch.storage import StorageService


def test_storage_write_and_duplicate_lookup(tmp_path: Path) -> None:
    config = OneFetchConfig.from_project_root(tmp_path)
    storage = StorageService(config.paths())

    capture = Capture(
        source_url="https://example.com",
        canonical_url="https://example.com/",
        final_url="https://example.com/",
        status_code=200,
        body="<html>hello</html>",
    )
    feed = FeedEntry(
        source_url="https://example.com",
        canonical_url="https://example.com/",
        crawler_id="generic_html",
        title="Example",
        body="hello",
    )
    feed.compute_content_hash()

    raw_path = storage.save_capture(capture)
    feed_path = storage.save_feed(feed)
    note_path = storage.save_note(feed)
    storage.append_catalog(feed, raw_path, feed_path, note_path)

    dup = storage.find_duplicate(feed.canonical_url, feed.content_hash)
    assert dup is not None
    assert dup["feed_path"].endswith(".json")
