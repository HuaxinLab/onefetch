from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from onefetch.config import Paths
from onefetch.models import Capture, FeedEntry


class StorageService:
    def __init__(self, paths: Paths) -> None:
        self._paths = paths
        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        self._paths.raw_dir.mkdir(parents=True, exist_ok=True)
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

    def save_capture(self, capture: Capture) -> str:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        filename = f"{stamp}-{capture.id[:8]}.json"
        path = self._paths.raw_dir / filename
        path.write_text(capture.model_dump_json(indent=2), encoding="utf-8")
        return str(path)

    def save_feed(self, feed: FeedEntry) -> str:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        filename = f"{stamp}-{feed.id[:8]}.json"
        path = self._paths.feed_dir / filename
        path.write_text(feed.model_dump_json(indent=2), encoding="utf-8")
        return str(path)

    def save_note(self, feed: FeedEntry) -> str:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        filename = f"{stamp}-{feed.id[:8]}.md"
        path = self._paths.notes_dir / filename
        title = feed.title or "Untitled"
        lines = [
            f"# {title}",
            "",
            f"- Source: {feed.source_url}",
            f"- Canonical: {feed.canonical_url}",
            f"- Crawler: {feed.crawler_id}",
            f"- Author: {feed.author or '-'}",
            f"- Published: {feed.published_at.isoformat() if feed.published_at else '-'}",
            "",
            "## Content",
            "",
            feed.body or "",
        ]
        path.write_text("\n".join(lines), encoding="utf-8")
        return str(path)

    def append_catalog(self, feed: FeedEntry, raw_path: str, feed_path: str, note_path: str) -> None:
        record = {
            "canonical_url": feed.canonical_url,
            "content_hash": feed.content_hash,
            "crawler_id": feed.crawler_id,
            "title": feed.title,
            "raw_path": raw_path,
            "feed_path": feed_path,
            "note_path": note_path,
            "stored_at": datetime.now(timezone.utc).isoformat(),
        }
        with self._paths.catalog_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
