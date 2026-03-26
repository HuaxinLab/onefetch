import json
from pathlib import Path
import re

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
    feed_payload = json.loads((article_path / "feed.json").read_text(encoding="utf-8"))
    assert "llm_outputs_state" not in feed_payload
    assert feed_payload["llm_outputs"]["summary"] == "test summary"
    assert feed_payload["llm_outputs"]["key_points"] == ["p1"]
    assert feed_payload["llm_outputs"]["tags"] == ["t1"]

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

    # Duplicate detection — catalog stores relative path
    dup = storage.find_duplicate("https://example.com/", "abc123")
    assert dup is not None
    assert article_dir.endswith(dup["article_dir"])

    # Second store should return existing dir (duplicate)
    article_dir2, is_dup2, _ = storage.store_result(result)
    assert article_dir2 == article_dir
    assert is_dup2 is True


def test_storage_heuristic_outputs_not_written_to_note(tmp_path: Path) -> None:
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
    assert "## 摘要" not in note_content
    assert "## 要点" not in note_content
    assert "## 标签" not in note_content
    assert "## 正文" in note_content
    assert "content" in note_content
    feed_payload = json.loads((Path(article_dir) / "feed.json").read_text(encoding="utf-8"))
    assert feed_payload["llm_outputs"] == {"summary": "", "key_points": [], "tags": [], "extras": {}}


def test_storage_stale_duplicate_path_falls_back_to_new_store(tmp_path: Path) -> None:
    config = OneFetchConfig.from_project_root(tmp_path)
    storage = StorageService(config.paths())

    result = IngestResult(
        source_url="https://example.com/a",
        canonical_url="https://example.com/a",
        crawler_id="generic_html",
        status="fetched",
        content_hash="samehash",
        title="A",
        body_full="body",
        llm_outputs_state="missing",
    )

    article_dir, is_dup, _ = storage.store_result(result)
    assert is_dup is False
    Path(article_dir).rename(Path(article_dir + "-moved"))

    article_dir2, is_dup2, _ = storage.store_result(result)
    assert is_dup2 is False
    assert Path(article_dir2).is_dir()
    assert (Path(article_dir2) / "feed.json").exists()
    assert Path(article_dir + "-moved").is_dir()


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
    feed_payload = json.loads((Path(article_dir) / "feed.json").read_text(encoding="utf-8"))
    assert feed_payload["images"] == [
        {"index": 1, "src": "https://example.com/img1.jpg", "alt": "", "href": ""},
        {"index": 2, "src": "https://example.com/img2.png", "alt": "", "href": ""},
    ]


def test_storage_caption_markers_are_normalized(monkeypatch, tmp_path: Path) -> None:
    config = OneFetchConfig.from_project_root(tmp_path)
    storage = StorageService(config.paths())

    # Mock image download to avoid network and force deterministic extension.
    monkeypatch.setattr("onefetch.storage._try_download_image", lambda _url: (b"img", "image/png"))

    result = IngestResult(
        source_url="https://example.com/article",
        canonical_url="https://example.com/article",
        crawler_id="generic_html",
        status="fetched",
        content_hash="cap123",
        title="Caption Test",
        body_full="段落A\n[IMG:1]\n[IMG_CAPTION:1] 这是一段图片说明。\n段落B",
        images=["https://example.com/1.png"],
        llm_outputs_state="missing",
    )

    article_dir, _, _ = storage.store_result(result, with_images=True)
    note_with_images = (Path(article_dir) / "note.md").read_text(encoding="utf-8")
    assert "![1](images/001.png)" in note_with_images
    assert "图片说明：这是一段图片说明。" in note_with_images
    assert re.search(r"\[IMG(_CAPTION)?:\d+\]", note_with_images) is None

    # Duplicate save without images should also not expose markers.
    article_dir2, is_dup, _ = storage.store_result(result, with_images=False)
    assert is_dup is True
    assert article_dir2 == article_dir
    note_without_images = (Path(article_dir2) / "note.md").read_text(encoding="utf-8")
    assert "图片说明：这是一段图片说明。" in note_without_images
    assert re.search(r"\[IMG(_CAPTION)?:\d+\]", note_without_images) is None


def test_storage_duplicate_with_images_rewrites_note_and_backfills(monkeypatch, tmp_path: Path) -> None:
    config = OneFetchConfig.from_project_root(tmp_path)
    storage = StorageService(config.paths())
    monkeypatch.setattr("onefetch.storage._try_download_image", lambda _url: (b"img", "image/jpeg"))

    result = IngestResult(
        source_url="https://example.com/item",
        canonical_url="https://example.com/item",
        crawler_id="generic_html",
        status="fetched",
        content_hash="dupimg1",
        title="Dup Image",
        body_full="A\n[IMG:1]\n[IMG_CAPTION:1] 说明文本",
        images=["https://example.com/x.jpg"],
        llm_outputs_state="missing",
    )

    article_dir, is_dup, _ = storage.store_result(result, with_images=False)
    assert is_dup is False
    note_before = (Path(article_dir) / "note.md").read_text(encoding="utf-8")
    assert "![1](" not in note_before
    assert "[IMG_CAPTION:1]" not in note_before

    article_dir2, is_dup2, _ = storage.store_result(result, with_images=True)
    assert is_dup2 is True
    assert article_dir2 == article_dir
    assert list((Path(article_dir2) / "images").glob("001.*")), "expected backfilled image file"
    note_after = (Path(article_dir2) / "note.md").read_text(encoding="utf-8")
    assert "![1](images/001.jpg)" in note_after
    assert "图片说明：说明文本" in note_after
    assert re.search(r"\[IMG(_CAPTION)?:\d+\]", note_after) is None


def test_storage_note_cleans_img_markers_in_llm_outputs(tmp_path: Path) -> None:
    config = OneFetchConfig.from_project_root(tmp_path)
    storage = StorageService(config.paths())

    result = IngestResult(
        source_url="https://example.com/l",
        canonical_url="https://example.com/l",
        crawler_id="generic_html",
        status="fetched",
        content_hash="llmimg1",
        title="LLM Marker",
        body_full="正文",
        llm_outputs=LLMOutputs(
            summary="摘要 [IMG_CAPTION:1] 说明",
            key_points=["要点A [IMG:1]", "要点B [IMG_CAPTION:2] xxx"],
            tags=["t1"],
        ),
        llm_outputs_state="ok",
    )
    article_dir, _, _ = storage.store_result(result, with_images=False)
    note = (Path(article_dir) / "note.md").read_text(encoding="utf-8")
    assert "[IMG:" not in note
    assert "[IMG_CAPTION:" not in note
    assert "摘要 说明" in note
    assert "- 要点A" in note
    assert "- 要点B xxx" in note


def test_relocate_articles_to_collection_keeps_single_order_prefix(tmp_path: Path) -> None:
    config = OneFetchConfig.from_project_root(tmp_path)
    storage = StorageService(config.paths())

    # Simulate two stored article dirs under data/
    a = config.paths().data_dir / "20260320-aaaa1111"
    b = config.paths().data_dir / "20260320-bbbb2222"
    a.mkdir(parents=True, exist_ok=True)
    b.mkdir(parents=True, exist_ok=True)
    (a / "feed.json").write_text("{}", encoding="utf-8")
    (b / "feed.json").write_text("{}", encoding="utf-8")

    _, moved1 = storage.relocate_articles_to_collection(
        collection_key="seed-test",
        article_dirs_in_order=[str(a), str(b)],
    )
    first_paths = [Path(v).name for _, v in sorted(moved1.items())]
    assert all(name.startswith(("001-", "002-")) for name in first_paths)

    # Re-run relocation with already-prefixed collection paths.
    _, moved2 = storage.relocate_articles_to_collection(
        collection_key="seed-test",
        article_dirs_in_order=[*moved1.values()],
    )
    second_paths = [Path(v).name for _, v in sorted(moved2.items())]
    assert second_paths == ["001-20260320-aaaa1111", "002-20260320-bbbb2222"]
