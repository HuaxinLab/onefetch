from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from onefetch.config import Paths
from onefetch.models import IngestResult


class StorageService:
    def __init__(self, paths: Paths) -> None:
        self._paths = paths
        self._paths.data_dir.mkdir(parents=True, exist_ok=True)
        if not self._paths.catalog_file.exists():
            self._paths.catalog_file.touch()

    def find_duplicate(self, canonical_url: str, content_hash: str) -> dict | None:
        with self._paths.catalog_file.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                if record.get("canonical_url") == canonical_url and record.get("content_hash") == content_hash:
                    return record
        return None

    def store_result(self, result: IngestResult, *, with_images: bool = False) -> tuple[str, bool]:
        """Store an IngestResult to data/. Returns (article_dir, is_duplicate)."""
        duplicate = self.find_duplicate(result.canonical_url, result.content_hash)
        if duplicate:
            return duplicate.get("article_dir", ""), True

        article_dir = self._create_article_dir(result)
        self._save_feed(article_dir, result)
        self._save_note(article_dir, result, with_images=with_images)
        if with_images and result.images:
            self._download_images(article_dir, result.images)
        self._append_catalog(result, str(article_dir))
        return str(article_dir), False

    def _create_article_dir(self, result: IngestResult) -> Path:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        short_hash = result.content_hash[:8] if result.content_hash else "unknown"
        dirname = f"{stamp}-{short_hash}"
        article_dir = self._paths.data_dir / dirname
        article_dir.mkdir(parents=True, exist_ok=True)
        return article_dir

    def _save_feed(self, article_dir: Path, result: IngestResult) -> None:
        payload = {
            "source_url": result.source_url,
            "canonical_url": result.canonical_url,
            "crawler_id": result.crawler_id,
            "title": result.title,
            "content_hash": result.content_hash,
            "body": result.body_full or result.body_excerpt or "",
            "images": result.images,
            "comment_count": result.comment_count,
            "comment_source": result.comment_source,
            "llm_outputs": result.llm_outputs.model_dump(),
            "llm_outputs_state": result.llm_outputs_state,
            "stored_at": datetime.now(timezone.utc).isoformat(),
        }
        path = article_dir / "feed.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _save_note(self, article_dir: Path, result: IngestResult, *, with_images: bool = False) -> None:
        title = result.title or "Untitled"
        lines = [
            f"# {title}",
            "",
            f"- 来源: {result.source_url}",
            f"- 平台: {result.crawler_id}",
        ]
        if result.comment_count:
            lines.append(f"- 评论: {result.comment_count} ({result.comment_source})")
        lines.append("")

        # LLM outputs
        llm = result.llm_outputs
        source_label = self._llm_source_label(result)

        if llm.summary:
            lines.extend([f"## 摘要{source_label}", "", llm.summary, ""])
        if llm.key_points:
            lines.extend([f"## 要点{source_label}", ""])
            for point in llm.key_points:
                lines.append(f"- {point}")
            lines.append("")
        if llm.tags:
            lines.extend(["## 标签", "", ", ".join(llm.tags), ""])

        # Body — replace [IMG:N] with local image paths or strip them
        body = result.body_full or result.body_excerpt or ""
        if with_images and result.images:
            import re
            for i in range(len(result.images)):
                body = body.replace(f"[IMG:{i + 1}]", f"![{i + 1}](images/{i + 1:03d}.jpg)")
            # Strip any remaining placeholders
            body = re.sub(r"\[IMG:\d+\]", "", body)
        else:
            import re
            body = re.sub(r"\[IMG:\d+\]\n?", "", body)
        if body.strip():
            lines.extend(["## 正文", "", body.strip()])

        path = article_dir / "note.md"
        path.write_text("\n".join(lines), encoding="utf-8")

    @staticmethod
    def _download_images(article_dir: Path, images: list[str]) -> None:
        import urllib.request
        images_dir = article_dir / "images"
        images_dir.mkdir(exist_ok=True)
        for i, url in enumerate(images):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = resp.read()
                ct = resp.headers.get("Content-Type", "image/jpeg")
                ext = ".webp" if "webp" in ct else ".png" if "png" in ct else ".gif" if "gif" in ct else ".jpg"
                path = images_dir / f"{i + 1:03d}{ext}"
                path.write_bytes(data)
            except Exception:
                continue

    @staticmethod
    def _llm_source_label(result: IngestResult) -> str:
        extras = result.llm_outputs.extras or {}
        regen_by = extras.get("regenerated_by", "")
        if regen_by == "heuristic_rules":
            return "（规则自动提取，可能不够准确）"
        if regen_by == "llm_command":
            return "（AI 整理）"
        if result.llm_outputs_state == "ok":
            return "（AI 整理）"
        return ""

    def _append_catalog(self, result: IngestResult, article_dir: str) -> None:
        record = {
            "canonical_url": result.canonical_url,
            "content_hash": result.content_hash,
            "crawler_id": result.crawler_id,
            "title": result.title,
            "article_dir": article_dir,
            "stored_at": datetime.now(timezone.utc).isoformat(),
        }
        with self._paths.catalog_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
