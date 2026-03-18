from pathlib import Path

from onefetch.config import OneFetchConfig
from onefetch.models import IngestResult, LLMOutputs
from onefetch.storage import StorageService


def test_storage_store_and_duplicate_lookup(tmp_path: Path) -> None:
    config = OneFetchConfig.from_project_root(tmp_path)
    storage = StorageService(config.paths())

    result = IngestResult(
        source_url="https://example.com",
        canonical_url="https://example.com/",
        crawler_id="generic_html",
        status="fetched",
        content_hash="abc123",
        title="Example",
        body_full="hello world",
        llm_outputs=LLMOutputs(summary="test summary", key_points=["p1"], tags=["t1"]),
        llm_outputs_state="ok",
    )

    feed_path, note_path = storage.store_result(result)
    assert feed_path.endswith(".json")
    assert note_path.endswith(".md")

    # Read note and verify LLM outputs are included
    note_content = Path(note_path).read_text(encoding="utf-8")
    assert "# Example" in note_content
    assert "## 摘要" in note_content
    assert "test summary" in note_content
    assert "## 要点" in note_content
    assert "- p1" in note_content
    assert "## 标签" in note_content
    assert "t1" in note_content
    assert "## 正文" in note_content
    assert "hello world" in note_content

    # Duplicate detection
    dup = storage.find_duplicate("https://example.com/", "abc123")
    assert dup is not None
    assert dup["feed_path"] == feed_path

    # Second store should return existing paths (duplicate)
    feed_path2, note_path2 = storage.store_result(result)
    assert feed_path2 == feed_path
    assert note_path2 == note_path


def test_storage_note_labels_heuristic_source(tmp_path: Path) -> None:
    config = OneFetchConfig.from_project_root(tmp_path)
    storage = StorageService(config.paths())

    result = IngestResult(
        source_url="https://example.com",
        canonical_url="https://example.com/",
        crawler_id="generic_html",
        status="fetched",
        content_hash="def456",
        title="Test",
        body_full="content",
        llm_outputs=LLMOutputs(
            summary="auto summary",
            extras={"regenerated_by": "heuristic_rules"},
        ),
        llm_outputs_state="ok",
    )

    _, note_path = storage.store_result(result)
    note_content = Path(note_path).read_text(encoding="utf-8")
    assert "规则自动提取" in note_content
