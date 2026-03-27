"""Douyin adapter — uses Douyin's built-in AI assistant to get video content.

Unlike other adapters that scrape page content directly, this adapter calls
Douyin's AI video assistant API to get a summary and/or transcript of the video.
"""

from __future__ import annotations

import json
import re
import time
from urllib.parse import urlparse

from onefetch.adapters.base import BaseAdapter
from onefetch.http import create_async_client
from onefetch.models import FeedEntry
from onefetch.secrets import load_cookie

_VIDEO_ID_RE = re.compile(r"/video/(\d+)")
_SHORT_LINK_RE = re.compile(r"v\.douyin\.com")

_BASE_URL = "https://so-landing.douyin.com"
_AID = "6383"
_DEVICE_ID = "7621538686223533610"


class DouyinAdapter(BaseAdapter):
    id = "douyin"
    priority = 200

    def supports(self, url: str) -> bool:
        host = (urlparse(url).hostname or "").lower()
        if not (host.endswith("douyin.com")):
            return False
        path = urlparse(url).path or "/"
        return bool(_VIDEO_ID_RE.search(path) or _SHORT_LINK_RE.search(host))

    async def crawl(self, url: str) -> FeedEntry:
        cookie = self._load_cookie()
        aweme_id = await self._resolve_aweme_id(url)

        if not aweme_id:
            raise RuntimeError(f"Cannot extract aweme_id from: {url}")

        if not cookie:
            raise RuntimeError(
                "Douyin AI requires login cookie. "
                "Run: bash scripts/setup_cookie.sh douyin.com"
            )

        # Step 1: Get summary
        summary = await self._ai_stream(aweme_id, "总结视频内容", cookie)

        # Step 2: Get full transcript with deep think
        transcript = await self._ai_stream(
            aweme_id,
            "给我完整的视频文字版/字幕，不要省略任何内容",
            cookie,
            deep_think=True,
        )

        # Combine results
        parts = []
        if summary:
            parts.append("## 视频总结\n")
            parts.append(summary)
        if transcript:
            parts.append("\n\n## 完整文字版\n")
            parts.append(transcript)

        body = "\n".join(parts) if parts else ""
        title = self._extract_title(summary or transcript or "")

        return FeedEntry(
            source_url=url,
            canonical_url=f"https://www.douyin.com/video/{aweme_id}",
            crawler_id=self.id,
            body=body,
            metadata={"aweme_id": aweme_id, "render_mode": "douyin_ai"},
        )

    async def _resolve_aweme_id(self, url: str) -> str:
        """Extract aweme_id from URL, following redirects for short links."""
        m = _VIDEO_ID_RE.search(url)
        if m:
            return m.group(1)

        # Short link — follow redirect
        try:
            async with create_async_client(timeout=10, follow_redirects=True) as client:
                resp = await client.get(url)
                m = _VIDEO_ID_RE.search(str(resp.url))
                if m:
                    return m.group(1)
        except Exception:
            pass
        return ""

    async def _ai_stream(
        self, aweme_id: str, keyword: str, cookie: str, *, deep_think: bool = False
    ) -> str:
        """Call Douyin AI stream API and return text response."""
        import httpx

        params = {
            "keyword": keyword,
            "ai_search_enter_from_group_id": aweme_id,
            "aid": _AID,
            "device_id": _DEVICE_ID,
            "search_channel": "aweme_ai_chat",
            "search_type": "ai_chat_search",
            "ai_page_type": "ai_chat",
            "token": "search",
            "count": "5",
            "cursor": "0",
            "version_code": "32.1.0",
            "enter_from": "search_result",
            "enter_method": "ai_input",
            "search_source": "ai_input",
            "enable_ai_tab_new_framework": "1",
            "need_integration_card": "1",
            "enable_ai_search_deep_think": "1" if deep_think else "0",
            "ai_chat_message_use_lynx": "1",
            "pc_ai_search_enable_ruyi": "1",
            "pc_ai_search_enable_rich_media": "0",
        }

        headers = {
            "Cookie": cookie,
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            "Referer": f"{_BASE_URL}/",
        }

        full_text = ""
        with httpx.Client(timeout=120, verify=False) as client:
            with client.stream(
                "GET",
                f"{_BASE_URL}/douyin/select/v1/ai/stream/",
                params=params,
                headers=headers,
            ) as resp:
                if resp.status_code != 200:
                    return ""
                for line in resp.iter_lines():
                    if not line.startswith("data:"):
                        continue
                    try:
                        d = json.loads(line[5:])
                    except json.JSONDecodeError:
                        continue
                    spans = _find_key_deep(d, "generation_spans")
                    for span_list in spans:
                        if not isinstance(span_list, list):
                            continue
                        for span in span_list:
                            if not isinstance(span, dict) or span.get("type") != 2:
                                continue
                            text_obj = span.get("text")
                            if isinstance(text_obj, dict):
                                content = text_obj.get("content", "")
                                if content:
                                    full_text += content
                            elif isinstance(text_obj, str) and text_obj:
                                full_text += text_obj

        return full_text

    @staticmethod
    def _load_cookie() -> str:
        return load_cookie(
            domains=["douyin.com", "www.douyin.com"],
            file_names=["douyin_cookie.txt"],
            parse_json_cookie=True,
        )

    @staticmethod
    def _extract_title(text: str) -> str:
        """Try to extract a title from the AI response."""
        for line in text.splitlines():
            line = line.strip().lstrip("#").strip().strip("*").strip()
            if len(line) > 5:
                return line[:80]
        return ""


def _find_key_deep(obj, target_key, depth=0):
    results = []
    if depth > 15:
        return results
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == target_key:
                results.append(v)
            results.extend(_find_key_deep(v, target_key, depth + 1))
    elif isinstance(obj, list):
        for item in obj:
            results.extend(_find_key_deep(item, target_key, depth + 1))
    return results
