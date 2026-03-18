from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from onefetch.config import Paths
from onefetch.models import IngestResult


class StorageService:
    def __init__(self, paths: Paths) -> None:
        self._paths = paths
        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        self._paths.feed_dir.mkdir(parents=True, exist_ok=True)
        self._paths.notes_dir.mkdir(parents=True, exist_ok=True)
        self._paths.catalog_file.parent.mkdir(parents=True, exist_ok=True)
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

    def store_result(self, result: IngestResult) -> tuple[str, str, bool]:
        """Store an IngestResult to data/. Returns (feed_path, note_path, is_duplicate)."""
        duplicate = self.find_duplicate(result.canonical_url, result.content_hash)
        if duplicate:
            return duplicate.get("feed_path", ""), duplicate.get("note_path", ""), True

        feed_path = self._save_feed(result)
        note_path = self._save_note(result)
        self._append_catalog(result, feed_path, note_path)
        return feed_path, note_path, False

    def _save_feed(self, result: IngestResult) -> str:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        filename = f"{stamp}-{result.content_hash[:8] or 'unknown'}.json"
        path = self._paths.feed_dir / filename
        payload = {
            "source_url": result.source_url,
            "canonical_url": result.canonical_url,
            "crawler_id": result.crawler_id,
            "title": result.title,
            "content_hash": result.content_hash,
            "body": result.body_full or result.body_excerpt or "",
            "comment_count": result.comment_count,
            "comment_source": result.comment_source,
            "llm_outputs": result.llm_outputs.model_dump(),
            "llm_outputs_state": result.llm_outputs_state,
            "stored_at": datetime.now(timezone.utc).isoformat(),
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(path)

    def _save_note(self, result: IngestResult) -> str:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        filename = f"{stamp}-{result.content_hash[:8] or 'unknown'}.md"
        path = self._paths.notes_dir / filename
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

        # Body
        body = result.body_full or result.body_excerpt or ""
        if body:
            lines.extend(["## 正文", "", body])

        path.write_text("\n".join(lines), encoding="utf-8")
        return str(path)

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

    def _append_catalog(self, result: IngestResult, feed_path: str, note_path: str) -> None:
        record = {
            "canonical_url": result.canonical_url,
            "content_hash": result.content_hash,
            "crawler_id": result.crawler_id,
            "title": result.title,
            "feed_path": feed_path,
            "note_path": note_path,
            "stored_at": datetime.now(timezone.utc).isoformat(),
        }
        with self._paths.catalog_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
