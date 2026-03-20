from __future__ import annotations

import json
import re
import shutil
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from onefetch.config import Paths
from onefetch.models import IngestResult

_IMG_PLACEHOLDER_RE = re.compile(r"\[IMG:\d+\]\n?")
_IMG_CAPTION_LINE_RE = re.compile(r"^\[IMG_CAPTION:(\d+)\]\s*(.*)$")
_IMG_CAPTION_INLINE_RE = re.compile(r"\[IMG_CAPTION:(\d+)\]\s*")
_IMG_MARKERS_INLINE_RE = re.compile(r"\[(?:IMG|IMG_CAPTION):\d+\]\s*")
_ITEM_PREFIX_RE = re.compile(r"^(?:\d{3}-)+")


def _try_download_image(url: str) -> tuple[bytes | None, str]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
        return data, resp.headers.get("Content-Type", "image/jpeg")
    except Exception:
        return None, ""


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

    def store_result(self, result: IngestResult, *, with_images: bool = False) -> tuple[str, bool, list[str]]:
        """Store an IngestResult to data/. Returns (article_dir, is_duplicate, image_failures)."""
        duplicate = self.find_duplicate(result.canonical_url, result.content_hash)
        if duplicate:
            article_dir = str(duplicate.get("article_dir", "") or "")
            article_path = Path(article_dir) if article_dir else None
            if article_path is None or not article_path.is_dir():
                # Catalog can contain stale paths after historical collection swaps.
                # If duplicate target no longer exists, treat it as a fresh store.
                duplicate = None
            else:
                if with_images and article_dir:
                    if result.images:
                        image_failures = self._download_images(article_path, result.images)
                    else:
                        image_failures = []
                    # Refresh note/feed on demand so existing duplicates can be "补图 + 清理标记".
                    self._save_feed(article_path, result)
                    self._save_note(article_path, result, with_images=True, image_failures=image_failures)
                    return article_dir, True, image_failures
                return article_dir, True, []

        article_dir = self._create_article_dir(result)
        image_failures: list[str] = []
        if with_images and result.images:
            image_failures = self._download_images(article_dir, result.images)
        self._save_feed(article_dir, result)
        self._save_note(article_dir, result, with_images=with_images, image_failures=image_failures)
        self._append_catalog(result, str(article_dir))
        return str(article_dir), False, image_failures

    def _create_article_dir(self, result: IngestResult) -> Path:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        short_hash = result.content_hash[:8] if result.content_hash else "unknown"
        dirname = f"{stamp}-{short_hash}"
        article_dir = self._paths.data_dir / dirname
        article_dir.mkdir(parents=True, exist_ok=True)
        return article_dir

    def _save_feed(self, article_dir: Path, result: IngestResult) -> None:
        llm_outputs = self._feed_llm_outputs(result)
        images = self._normalize_images(result.images)
        payload = {
            "source_url": result.source_url,
            "canonical_url": result.canonical_url,
            "crawler_id": result.crawler_id,
            "title": result.title,
            "author": result.author,
            "published_at": result.published_at,
            "content_hash": result.content_hash,
            "body": result.body_full or "",
            "images": images,
            "comment_count": result.comment_count,
            "comment_source": result.comment_source,
            "llm_outputs": llm_outputs,
            "stored_at": datetime.now(timezone.utc).isoformat(),
        }
        path = article_dir / "feed.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _save_note(self, article_dir: Path, result: IngestResult, *, with_images: bool = False, image_failures: list[str] | None = None) -> None:
        title = result.title or "Untitled"
        lines = [
            f"# {title}",
            "",
            f"- 来源: {result.source_url}",
            f"- 平台: {result.crawler_id}",
        ]
        if result.author:
            lines.append(f"- 作者: {result.author}")
        if result.published_at:
            lines.append(f"- 发布时间: {result.published_at}")
        if result.comment_count:
            lines.append(f"- 评论: {result.comment_count} ({result.comment_source})")
        lines.append("")

        # LLM outputs: only persist to note.md when they are model-derived.
        if self._should_include_llm_sections(result):
            llm = result.llm_outputs
            source_label = self._llm_source_label(result)

            summary = self._clean_text_for_note(llm.summary)
            key_points = [self._clean_text_for_note(point) for point in llm.key_points]
            key_points = [point for point in key_points if point]
            tags = [self._clean_text_for_note(tag) for tag in llm.tags]
            tags = [tag for tag in tags if tag]

            if summary:
                lines.extend([f"## 摘要{source_label}", "", summary, ""])
            if key_points:
                lines.extend([f"## 要点{source_label}", ""])
                for point in key_points:
                    lines.append(f"- {point}")
                lines.append("")
            if tags:
                lines.extend(["## 标签", "", ", ".join(tags), ""])

        # Image download failures
        if image_failures:
            lines.extend(["## 图片下载失败", ""])
            lines.append("以下图片无法下载（直接请求和 wsrv.nl 代理均失败），仅根据正文整理：")
            for msg in image_failures:
                lines.append(f"- {msg}")
            lines.append("")

        # Body — normalize image/caption markers for readable note output
        body = self._render_body_for_note(article_dir=article_dir, body=(result.body_full or ""), with_images=with_images)
        if body.strip():
            lines.extend(["## 正文", "", body.strip()])

        path = article_dir / "note.md"
        path.write_text("\n".join(lines), encoding="utf-8")

    def _download_images(self, article_dir: Path, images: list) -> list[str]:
        """Download images with wsrv.nl fallback. Returns failure messages."""
        images_dir = article_dir / "images"
        images_dir.mkdir(exist_ok=True)
        failures: list[str] = []
        for image in self._normalize_images(images):
            i = int(image.get("index") or 0)
            url = str(image.get("src") or "").strip()
            if i <= 0 or not url:
                continue
            # Keep idempotent behavior for "补下载图片" workflow.
            if list(images_dir.glob(f"{i:03d}.*")):
                continue
            data, ct = _try_download_image(url)
            if data is None:
                proxy_url = f"https://wsrv.nl/?url={urllib.parse.quote(url, safe='')}"
                data, ct = _try_download_image(proxy_url)
            if data is None:
                failures.append(f"[IMG:{i}] download failed: {url}")
                continue
            ext = ".webp" if "webp" in ct else ".png" if "png" in ct else ".gif" if "gif" in ct else ".jpg"
            path = images_dir / f"{i:03d}{ext}"
            path.write_bytes(data)
        return failures

    @staticmethod
    def _normalize_images(images: list) -> list[dict]:
        rows: list[dict] = []
        for i, raw in enumerate(images or [], start=1):
            if isinstance(raw, dict):
                src = str(raw.get("src") or "").strip()
                alt = str(raw.get("alt") or "").strip()
                href = str(raw.get("href") or "").strip()
            else:
                src = str(raw or "").strip()
                alt = ""
                href = ""
            if not src:
                continue
            rows.append(
                {
                    "index": i,
                    "src": src,
                    "alt": alt,
                    "href": href,
                }
            )
        return rows

    @staticmethod
    def _resolve_local_image_path(article_dir: Path, index: int) -> str:
        images_dir = article_dir / "images"
        candidates = sorted(images_dir.glob(f"{index:03d}.*"))
        if candidates:
            return f"images/{candidates[0].name}"
        return f"images/{index:03d}.jpg"

    def _render_body_for_note(self, *, article_dir: Path, body: str, with_images: bool) -> str:
        lines = []
        for raw in (body or "").splitlines():
            line = raw.strip()
            if not line:
                lines.append("")
                continue

            if line.startswith("[IMG:") and line.endswith("]"):
                if with_images:
                    try:
                        idx = int(line[5:-1])
                    except Exception:
                        continue
                    img_rel = self._resolve_local_image_path(article_dir, idx)
                    lines.append(f"![{idx}]({img_rel})")
                continue

            cap_match = _IMG_CAPTION_LINE_RE.match(line)
            if cap_match:
                caption = cap_match.group(2).strip()
                if caption:
                    lines.append(f"图片说明：{caption}")
                continue

            # Handle any inline caption token fallback.
            line = _IMG_CAPTION_INLINE_RE.sub("", line).strip()
            if line:
                lines.append(line)

        normalized = "\n".join(lines).strip()
        normalized = re.sub(r"\n{3,}", "\n\n", normalized)
        return normalized

    @staticmethod
    def _clean_text_for_note(value: str) -> str:
        text = (value or "").strip()
        if not text:
            return ""
        text = _IMG_MARKERS_INLINE_RE.sub("", text)
        text = re.sub(r"\s{2,}", " ", text).strip()
        return text

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

    @staticmethod
    def _should_include_llm_sections(result: IngestResult) -> bool:
        if result.llm_outputs_state != "ok":
            return False
        extras = result.llm_outputs.extras or {}
        return str(extras.get("regenerated_by") or "") != "heuristic_rules"

    def _feed_llm_outputs(self, result: IngestResult) -> dict:
        if not self._should_include_llm_sections(result):
            return {"summary": "", "key_points": [], "tags": [], "extras": {}}
        llm = result.llm_outputs
        summary = self._clean_text_for_note(llm.summary)
        key_points = [self._clean_text_for_note(point) for point in llm.key_points]
        key_points = [point for point in key_points if point]
        tags = [self._clean_text_for_note(tag) for tag in llm.tags]
        tags = [tag for tag in tags if tag]
        return {
            "summary": summary,
            "key_points": key_points,
            "tags": tags,
            "extras": dict(llm.extras or {}),
        }

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

    def relocate_articles_to_collection(
        self,
        *,
        collection_key: str,
        article_dirs_in_order: list[str],
    ) -> dict[str, str]:
        """Move stored article dirs under data/collections/<collection_key>/items in order.

        Returns mapping {old_abs_path: new_abs_path} for successfully moved dirs.
        """
        collection_dir = self._paths.data_dir / "collections" / collection_key
        items_dir = collection_dir / "items"
        next_items_dir = collection_dir / ".items.next"
        collection_dir.mkdir(parents=True, exist_ok=True)
        if next_items_dir.exists():
            shutil.rmtree(next_items_dir)
        next_items_dir.mkdir(parents=True, exist_ok=True)

        moved: dict[str, str] = {}
        for i, raw_path in enumerate(article_dirs_in_order, start=1):
            src = Path(raw_path).expanduser().resolve()
            if not src.is_dir():
                continue
            dst_name = f"{i:03d}-{self._strip_item_prefix(src.name)}"
            dst = (next_items_dir / dst_name).resolve()
            final_dst = (items_dir / dst_name).resolve()
            if dst.exists():
                shutil.rmtree(dst)
            # Freshly stored data/<article> can be moved; existing collection items are copied then swapped.
            if src.parent == self._paths.data_dir:
                shutil.move(str(src), str(dst))
            else:
                shutil.copytree(src, dst)
            moved[str(src)] = str(final_dst)

        if items_dir.exists():
            shutil.rmtree(items_dir)
        next_items_dir.rename(items_dir)

        if moved:
            self._rewrite_catalog_article_dirs(moved)
        return moved

    @staticmethod
    def _strip_item_prefix(name: str) -> str:
        return _ITEM_PREFIX_RE.sub("", name or "").strip() or (name or "")

    def _rewrite_catalog_article_dirs(self, moved: dict[str, str]) -> None:
        records: list[dict] = []
        changed = False
        with self._paths.catalog_file.open("r", encoding="utf-8") as handle:
            for line in handle:
                raw = line.strip()
                if not raw:
                    continue
                try:
                    rec = json.loads(raw)
                except Exception:
                    continue
                old_dir = str(rec.get("article_dir") or "")
                if old_dir in moved:
                    rec["article_dir"] = moved[old_dir]
                    changed = True
                records.append(rec)
        if not changed:
            return
        with self._paths.catalog_file.open("w", encoding="utf-8") as handle:
            for rec in records:
                handle.write(json.dumps(rec, ensure_ascii=False) + "\n")
