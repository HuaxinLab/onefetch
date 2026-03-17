from __future__ import annotations

import json
from datetime import datetime, timezone
from urllib.parse import urlparse

from lxml import html

from onefetch.adapters.base import BaseAdapter
from onefetch.http import create_async_client
from onefetch.models import Capture, CrawlOutput, FeedEntry
from onefetch.router import normalize_url


class XiaohongshuAdapter(BaseAdapter):
    id = "xiaohongshu"

    def supports(self, url: str) -> bool:
        domain = (urlparse(url).hostname or "").lower()
        return "xiaohongshu.com" in domain or "xhslink.com" in domain

    async def crawl(self, url: str) -> CrawlOutput:
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; OneFetch/0.1)",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
        async with create_async_client(timeout=30, follow_redirects=True, headers=headers) as client:
            response = await client.get(url)
            response.raise_for_status()

        final_url = str(response.url)
        canonical = normalize_url(final_url)
        body_text = response.text

        title, author, content, published_at, metadata = self._extract_from_html(body_text, final_url)
        canonical = normalize_url(metadata.get("canonical_url", canonical))

        capture = Capture(
            source_url=url,
            canonical_url=canonical,
            final_url=final_url,
            status_code=response.status_code,
            headers={k.lower(): v for k, v in response.headers.items()},
            body=body_text,
        )
        feed = FeedEntry(
            source_url=url,
            canonical_url=canonical,
            crawler_id=self.id,
            title=title or "Xiaohongshu content",
            author=author,
            published_at=published_at,
            body=content or "",
            metadata=metadata,
        )
        return CrawlOutput(capture=capture, feed=feed)

    def _extract_from_html(
        self, html_text: str, final_url: str
    ) -> tuple[str | None, str | None, str | None, datetime | None, dict]:
        tree = html.fromstring(html_text)
        og_url = self._first(
            tree,
            [
                "//meta[@property='og:url']/@content",
                "//meta[@name='og:url']/@content",
            ],
        )
        title = self._first(
            tree,
            [
                "//meta[@property='og:title']/@content",
                "//meta[@name='og:title']/@content",
                "//title/text()",
            ],
        )
        author = self._first(
            tree,
            [
                "//meta[@name='author']/@content",
                "//meta[@property='og:article:author']/@content",
            ],
        )
        description = self._first(
            tree,
            [
                "//meta[@name='description']/@content",
                "//meta[@property='og:description']/@content",
                "//meta[@name='og:description']/@content",
            ],
        )
        published_raw = self._first(tree, ["//meta[@property='article:published_time']/@content", "//time/@datetime"])
        published_at = self._parse_datetime(published_raw)
        metadata = {
            "platform": "xiaohongshu",
            "final_url": final_url,
        }
        if og_url:
            metadata["canonical_url"] = og_url

        # Prefer noteDetailMap payload from initial state when present.
        note_data = self._extract_note_data_from_initial_state(html_text, final_url)
        if note_data:
            note_title = note_data.get("title")
            note_desc = note_data.get("desc")
            user = note_data.get("user") or {}
            interact = note_data.get("interactInfo") or {}
            note_time = note_data.get("time")

            if isinstance(note_title, str) and note_title.strip():
                title = note_title.strip()
            if isinstance(note_desc, str) and note_desc.strip():
                description = note_desc.strip()
            if isinstance(user.get("nickname"), str) and user.get("nickname").strip():
                author = user["nickname"].strip()
            if published_at is None and isinstance(note_time, (int, float)):
                published_at = datetime.fromtimestamp(note_time / 1000, tz=timezone.utc)

            metadata.update(
                {
                    "note_id": note_data.get("noteId"),
                    "interact_info": {
                        "liked_count": interact.get("likedCount"),
                        "comment_count": interact.get("commentCount"),
                        "collect_count": interact.get("collectedCount"),
                        "share_count": interact.get("shareCount"),
                    },
                }
            )

        # Trim product suffix for readability.
        if title and title.endswith(" - 小红书"):
            title = title[:-6].strip()
        return title, author, description, published_at, metadata

    def _extract_note_data_from_initial_state(self, html_text: str, url: str) -> dict | None:
        note_id = self._extract_note_id(url)
        if not note_id:
            return None
        marker = f"\"noteDetailMap\":{{\"{note_id}\":"
        idx = html_text.find(marker)
        if idx < 0:
            return None
        start = idx + len(marker)
        note_object = self._extract_balanced_object(html_text, start)
        if not note_object:
            return None
        try:
            payload = json.loads(note_object)
        except json.JSONDecodeError:
            return None
        note = payload.get("note")
        if isinstance(note, dict):
            return note
        return None

    @staticmethod
    def _extract_note_id(url: str) -> str:
        path_parts = [part for part in urlparse(url).path.split("/") if part]
        if len(path_parts) >= 2 and path_parts[0] == "explore":
            return path_parts[1]
        return ""

    @staticmethod
    def _extract_balanced_object(text: str, start: int) -> str | None:
        depth = 0
        in_string = False
        escaped = False
        for idx in range(start, len(text)):
            ch = text[idx]
            if in_string:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == '"':
                    in_string = False
                continue
            if ch == '"':
                in_string = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[start : idx + 1]
        return None

    @staticmethod
    def _first(tree: html.HtmlElement, xpaths: list[str]) -> str | None:
        for xpath in xpaths:
            values = tree.xpath(xpath)
            if values and isinstance(values[0], str) and values[0].strip():
                return values[0].strip()
        return None

    @staticmethod
    def _parse_datetime(value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
