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

    article_dir, is_dup, _ = storage.store_result(result)
    assert is_dup is False
    article_path = Path(article_dir)
    assert (article_path / "feed.json").exists()
    assert (article_path / "note.md").exists()

    # Read note and verify LLM outputs are included
    note_content = (article_path / "note.md").read_text(encoding="utf-8")
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
    assert dup["article_dir"] == article_dir

    # Second store should return existing dir (duplicate)
    article_dir2, is_dup2, _ = storage.store_result(result)
    assert article_dir2 == article_dir
    assert is_dup2 is True


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

    article_dir, _, _ = storage.store_result(result)
    note_content = (Path(article_dir) / "note.md").read_text(encoding="utf-8")
    assert "规则自动提取" in note_content


def test_storage_with_images(tmp_path: Path) -> None:
    config = OneFetchConfig.from_project_root(tmp_path)
    storage = StorageService(config.paths())

    result = IngestResult(
        source_url="https://example.com",
        canonical_url="https://example.com/",
        crawler_id="generic_html",
        status="fetched",
        content_hash="img789",
        title="With Images",
        body_full="content with images",
        images=["https://example.com/img1.jpg", "https://example.com/img2.png"],
        llm_outputs_state="missing",
    )

    # Without --with-images: no images dir
    article_dir, _, _ = storage.store_result(result, with_images=False)
    assert not (Path(article_dir) / "images").exists()
    note_content = (Path(article_dir) / "note.md").read_text(encoding="utf-8")
    assert "## 图片" not in note_content
