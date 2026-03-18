from __future__ import annotations

import asyncio
import json
import os
import random
import re
import time
from datetime import datetime, timezone
from urllib.parse import urlparse

from lxml import html

from onefetch.adapters.base import BaseAdapter
from onefetch.http import create_async_client
from onefetch.models import Capture, CrawlOutput, FeedComment, FeedEntry
from onefetch.router import normalize_url


class XiaohongshuAdapter(BaseAdapter):
    id = "xiaohongshu"
    priority = 100
    _api_risk_cooldown_until: float = 0.0
    _api_last_request_at: float = 0.0

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

        state = self._extract_initial_state(body_text)
        title, author, content, published_at, metadata, state_comments = self._extract_from_html_and_state(
            body_text, final_url, state
        )
        canonical = normalize_url(metadata.get("canonical_url", canonical))

        mode = self._comment_mode_flags()
        comments = state_comments if mode["state"] else []

        api_status = {"status": "skipped", "reason": "mode_excludes_api"}
        if mode["api"] and not comments:
            api_comments, api_status = await self._fetch_comments(metadata.get("note_id"), canonical_url=canonical)
            if api_comments:
                comments = api_comments

        dom_status = {"status": "skipped", "reason": "mode_excludes_dom"}
        if mode["dom"] and not comments:
            dom_comments, dom_status = await self._fetch_comments_dom(final_url=final_url)
            if dom_comments:
                comments = dom_comments

        metadata["comment_fetch"] = {
            "mode": mode["raw"],
            "source": "state" if (comments and comments == state_comments and mode["state"]) else ("api" if api_status.get("status") == "ok" and comments else ("dom" if dom_status.get("status") == "ok" and comments else "none")),
            "state_count": len(state_comments),
            "api": api_status,
            "dom": dom_status,
        }

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
            comments=comments,
            metadata=metadata,
        )
        return CrawlOutput(capture=capture, feed=feed)

    def _extract_from_html_and_state(
        self,
        html_text: str,
        final_url: str,
        state: dict | None,
    ) -> tuple[str | None, str | None, str | None, datetime | None, dict, list[FeedComment]]:
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

        metadata: dict = {
            "platform": "xiaohongshu",
            "final_url": final_url,
        }
        if og_url:
            metadata["canonical_url"] = og_url

        comments: list[FeedComment] = []

        note_detail = self._pick_note_detail(state, final_url)
        if note_detail:
            note = note_detail.get("note") or {}
            if isinstance(note.get("title"), str) and note["title"].strip():
                title = note["title"].strip()
            body = self._build_note_body(note)
            if body:
                description = body

            user = note.get("user") or {}
            if isinstance(user.get("nickname"), str) and user["nickname"].strip():
                author = user["nickname"].strip()

            note_time = note.get("time") or note.get("lastUpdateTime")
            if published_at is None and isinstance(note_time, (int, float)):
                published_at = datetime.fromtimestamp(note_time / 1000, tz=timezone.utc)

            interact = note.get("interactInfo") or {}
            metadata.update(
                {
                    "content_type": "note",
                    "note_id": note.get("noteId") or self._extract_note_id(final_url),
                    "interact_info": {
                        "liked_count": interact.get("likedCount"),
                        "comment_count": interact.get("commentCount"),
                        "collect_count": interact.get("collectedCount"),
                        "share_count": interact.get("shareCount"),
                    },
                }
            )
            comments = self._parse_comments_from_note_detail(note_detail)
        else:
            profile = (((state or {}).get("user") or {}).get("userPageData")) or {}
            basic = profile.get("basicInfo") or {}
            interactions = profile.get("interactions") or []
            if isinstance(basic.get("nickname"), str) and basic["nickname"].strip():
                title = basic["nickname"].strip()
                author = basic["nickname"].strip()
            profile_lines: list[str] = []
            if isinstance(basic.get("desc"), str) and basic["desc"].strip():
                profile_lines.append(basic["desc"].strip())
            for item in interactions:
                if isinstance(item, dict) and item.get("name") and item.get("count") is not None:
                    profile_lines.append(f"{item['name']}: {item['count']}")
            if profile_lines:
                description = "\n".join(profile_lines)
            metadata["content_type"] = "profile"

        if title and title.endswith(" - 小红书"):
            title = title[:-6].strip()

        return title, author, description, published_at, metadata, comments

    @staticmethod
    def _comment_mode_flags() -> dict[str, object]:
        raw = os.getenv("ONEFETCH_XHS_COMMENT_MODE", "state+api").strip().lower()
        if raw == "off":
            return {"raw": raw, "state": False, "api": False, "dom": False}
        tokens = {part.strip() for part in raw.split("+") if part.strip()}
        if not tokens:
            tokens = {"state", "api"}
        return {
            "raw": raw,
            "state": "state" in tokens,
            "api": "api" in tokens,
            "dom": "dom" in tokens,
        }

    @staticmethod
    def _extract_initial_state(html_text: str) -> dict | None:
        marker = "window.__INITIAL_STATE__="
        start = html_text.find(marker)
        if start < 0:
            return None
        idx = start + len(marker)
        while idx < len(html_text) and html_text[idx] != "{":
            idx += 1
        raw = XiaohongshuAdapter._extract_balanced_object(html_text, idx)
        if not raw:
            return None
        normalized = re.sub(r":\s*undefined(?=[,}])", ": null", raw)
        normalized = re.sub(r"\bundefined\b", "null", normalized)
        try:
            return json.loads(normalized)
        except json.JSONDecodeError:
            return None

    def _pick_note_detail(self, state: dict | None, final_url: str) -> dict | None:
        note_map = (((state or {}).get("note") or {}).get("noteDetailMap")) or {}
        if not isinstance(note_map, dict) or not note_map:
            return None

        note_id = self._extract_note_id(final_url)
        if note_id and isinstance(note_map.get(note_id), dict):
            return note_map[note_id]

        # Fallback for cases where URL note id differs from hydrated state key.
        first_key = next(iter(note_map), None)
        if first_key and isinstance(note_map.get(first_key), dict):
            return note_map[first_key]
        return None

    @staticmethod
    def _extract_note_id(url: str) -> str:
        parts = [part for part in urlparse(url).path.split("/") if part]
        if len(parts) >= 2 and parts[0] in {"explore", "discovery"}:
            # /explore/<note_id>
            if parts[0] == "explore":
                return parts[1]
            # /discovery/item/<note_id>
            if len(parts) >= 3 and parts[1] == "item":
                return parts[2]
        return ""

    @staticmethod
    def _build_note_body(note: dict) -> str:
        title = (note.get("title") or "").strip()
        desc = (note.get("desc") or "").strip()
        parts: list[str] = []
        if title:
            parts.append(title)
        if desc:
            parts.append(desc)

        tags = note.get("tagList") or []
        tag_names = [item.get("name", "").strip() for item in tags if isinstance(item, dict) and item.get("name")]
        if tag_names:
            parts.append("Tags: " + ", ".join(tag_names))
        return "\n\n".join(part for part in parts if part)

    @staticmethod
    def _parse_comments_from_note_detail(note_detail: dict) -> list[FeedComment]:
        comments: list[FeedComment] = []
        comments_blob = (note_detail.get("comments") or {}).get("list") or []
        for item in comments_blob:
            if not isinstance(item, dict):
                continue
            text = (item.get("content") or item.get("text") or "").strip()
            if not text:
                continue
            user = item.get("user_info") or item.get("user_info_v2") or item.get("user") or {}
            author = user.get("nickname")
            comments.append(FeedComment(author=author, text=text))
        return comments

    async def _fetch_comments(self, note_id: str | None, *, canonical_url: str) -> tuple[list[FeedComment], dict]:
        if not note_id:
            return [], {"status": "skipped", "reason": "missing_note_id"}

        cookie = os.getenv("ONEFETCH_XHS_COOKIE", "").strip()
        if not cookie:
            return [], {"status": "skipped", "reason": "missing_cookie"}
        cooldown_remaining = self._risk_cooldown_remaining()
        if cooldown_remaining > 0:
            return [], {
                "status": "skipped",
                "reason": "risk_cooldown",
                "cooldown_remaining_sec": round(cooldown_remaining, 2),
            }
        max_pages = self._env_int("ONEFETCH_XHS_COMMENT_MAX_PAGES", default=3, min_value=1, max_value=20)
        max_items = self._env_int("ONEFETCH_XHS_COMMENT_MAX_ITEMS", default=50, min_value=1, max_value=500)
        max_retries = self._env_int("ONEFETCH_XHS_API_MAX_RETRIES", default=2, min_value=0, max_value=5)
        min_interval = self._env_float("ONEFETCH_XHS_API_MIN_INTERVAL_SEC", default=1.0, min_value=0.1, max_value=10.0)
        backoff_base = self._env_float("ONEFETCH_XHS_API_BACKOFF_SEC", default=1.0, min_value=0.1, max_value=10.0)
        risk_cooldown = self._env_int("ONEFETCH_XHS_API_RISK_COOLDOWN_SEC", default=900, min_value=30, max_value=86400)
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; OneFetch/0.1)",
            "Accept": "application/json, text/plain, */*",
            "Referer": canonical_url,
            "Cookie": cookie,
        }
        parsed: list[FeedComment] = []
        cursor = ""
        pages_fetched = 0
        has_more = False
        endpoint = "https://edith.xiaohongshu.com/api/sns/web/v2/comment/page"
        seen: set[tuple[str | None, str]] = set()

        try:
            async with create_async_client(timeout=20, follow_redirects=True, headers=headers) as client:
                for _ in range(max_pages):
                    url = (
                        f"{endpoint}?note_id={note_id}&cursor={cursor}&top_comment_id=&image_formats=jpg,webp,avif"
                    )
                    response = None
                    payload = None
                    for attempt in range(max_retries + 1):
                        await self._wait_api_interval(min_interval)
                        response = await client.get(url)
                        self._api_last_request_at = time.monotonic()
                        if response.status_code == 200:
                            try:
                                payload = response.json()
                            except Exception:
                                payload = None
                        if self._is_risk_signal(
                            http_status=response.status_code,
                            api_code=(payload or {}).get("code"),
                        ):
                            self._mark_risk_cooldown(risk_cooldown)
                            return parsed, {
                                "status": "failed",
                                "reason": "risk_controlled",
                                "http_status": response.status_code,
                                "code": (payload or {}).get("code"),
                                "msg": (payload or {}).get("msg", ""),
                                "pages_fetched": pages_fetched,
                                "count": len(parsed),
                                "cooldown_sec": risk_cooldown,
                            }
                        if response.status_code == 200 and isinstance(payload, dict) and payload.get("success"):
                            break
                        if attempt < max_retries:
                            await self._sleep_backoff(backoff_base, attempt)
                    pages_fetched += 1

                    if response is None:
                        return parsed, {
                            "status": "failed",
                            "reason": "request_error",
                            "pages_fetched": pages_fetched,
                            "count": len(parsed),
                        }
                    if response.status_code != 200:
                        return parsed, {
                            "status": "failed",
                            "reason": "http_error",
                            "http_status": response.status_code,
                            "pages_fetched": pages_fetched,
                            "count": len(parsed),
                            "retries": max_retries,
                        }
                    if not isinstance(payload, dict):
                        return parsed, {
                            "status": "failed",
                            "reason": "invalid_payload",
                            "pages_fetched": pages_fetched,
                            "count": len(parsed),
                        }
                    if not payload.get("success"):
                        return parsed, {
                            "status": "failed",
                            "reason": "api_error",
                            "code": payload.get("code"),
                            "msg": payload.get("msg", ""),
                            "pages_fetched": pages_fetched,
                            "count": len(parsed),
                            "retries": max_retries,
                        }

                    data = payload.get("data") or {}
                    for item in data.get("comments") or []:
                        if not isinstance(item, dict):
                            continue
                        flattened = self._flatten_comment_with_replies(item)
                        for author, text in flattened:
                            key = (author, text)
                            if key in seen:
                                continue
                            seen.add(key)
                            parsed.append(FeedComment(author=author, text=text))
                            if len(parsed) >= max_items:
                                return parsed, {
                                    "status": "ok",
                                    "count": len(parsed),
                                    "has_more": bool(data.get("has_more")),
                                    "cursor": data.get("cursor", ""),
                                    "pages_fetched": pages_fetched,
                                    "limit_hit": True,
                                }

                    has_more = bool(data.get("has_more"))
                    cursor = str(data.get("cursor") or "")
                    if not has_more or not cursor:
                        break
        except Exception as exc:
            return parsed, {"status": "failed", "reason": "request_error", "error": str(exc), "pages_fetched": pages_fetched}

        return parsed, {
            "status": "ok",
            "count": len(parsed),
            "has_more": has_more,
            "cursor": cursor,
            "pages_fetched": pages_fetched,
            "limit_hit": False,
        }

    @staticmethod
    def _flatten_comment_with_replies(item: dict) -> list[tuple[str | None, str]]:
        entries: list[tuple[str | None, str]] = []

        root_text = (item.get("content") or item.get("text") or "").strip()
        root_user = item.get("user_info") or item.get("user_info_v2") or item.get("user") or {}
        root_author = root_user.get("nickname")
        if root_text:
            entries.append((root_author, root_text))

        reply_lists = [
            item.get("sub_comments"),
            item.get("sub_comment_list"),
            item.get("subCommentList"),
            item.get("replies"),
            item.get("reply_list"),
        ]
        for reply_list in reply_lists:
            if not isinstance(reply_list, list):
                continue
            for reply in reply_list:
                if not isinstance(reply, dict):
                    continue
                reply_text = (reply.get("content") or reply.get("text") or "").strip()
                if not reply_text:
                    continue
                reply_user = reply.get("user_info") or reply.get("user_info_v2") or reply.get("user") or {}
                reply_author = reply_user.get("nickname")
                # Flatten threaded reply while preserving "is a reply" signal.
                entries.append((reply_author, f"↳ {reply_text}"))
        return entries

    async def _fetch_comments_dom(self, *, final_url: str) -> tuple[list[FeedComment], dict]:
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            return [], {
                "status": "failed",
                "reason": "playwright_missing",
                "hint": (
                    "Install with: .venv/bin/python -m pip install -e '.[browser]' "
                    "&& .venv/bin/python -m playwright install chromium"
                ),
            }

        cookie_header = os.getenv("ONEFETCH_XHS_COOKIE", "").strip()
        comment_records: list[FeedComment] = []
        tasks: list[asyncio.Task] = []
        seen: set[tuple[str | None, str]] = set()

        async def parse_response(resp) -> None:
            if "/api/sns/web/v2/comment/page" not in resp.url:
                return
            try:
                payload = await resp.json()
            except Exception:
                return
            if not isinstance(payload, dict) or not payload.get("success"):
                return
            data = payload.get("data") or {}
            for item in data.get("comments") or []:
                if not isinstance(item, dict):
                    continue
                text = (item.get("content") or "").strip()
                if not text:
                    continue
                user = item.get("user_info") or item.get("user_info_v2") or item.get("user") or {}
                author = user.get("nickname")
                key = (author, text)
                if key in seen:
                    continue
                seen.add(key)
                comment_records.append(FeedComment(author=author, text=text))

        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (compatible; OneFetch/0.1)",
                locale="zh-CN",
            )
            if cookie_header:
                cookies = []
                for part in cookie_header.split(";"):
                    if "=" not in part:
                        continue
                    name, value = part.split("=", 1)
                    name = name.strip()
                    value = value.strip()
                    if not name:
                        continue
                    cookies.append(
                        {
                            "name": name,
                            "value": value,
                            "domain": ".xiaohongshu.com",
                            "path": "/",
                        }
                    )
                if cookies:
                    await context.add_cookies(cookies)

            page = await context.new_page()

            def on_response(resp) -> None:
                tasks.append(asyncio.create_task(parse_response(resp)))

            page.on("response", on_response)
            await page.goto(final_url, wait_until="domcontentloaded", timeout=30000)
            # Trigger possible lazy-loaded comments area.
            await page.evaluate(
                """
                () => {
                  const clickables = Array.from(document.querySelectorAll('button, a, div, span'));
                  for (const el of clickables) {
                    const txt = (el.textContent || '').trim();
                    if (!txt) continue;
                    if (/评论|条评论/.test(txt) && txt.length <= 30) {
                      try { el.click(); } catch (_) {}
                    }
                  }
                  window.scrollTo(0, document.body.scrollHeight * 0.5);
                }
                """
            )
            await page.wait_for_timeout(5000)
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)

            if not comment_records:
                # Fallback: parse visible comment-like text blocks from rendered DOM.
                dom_payload = await page.evaluate(
                    """
                    () => {
                      const selectors = [
                        '.comments-el .content',
                        '.comments-el .comment-content',
                        '.comment-list .content',
                        '[class*="comment"] [class*="content"]'
                      ];
                      const out = [];
                      const seen = new Set();
                      for (const sel of selectors) {
                        document.querySelectorAll(sel).forEach((node) => {
                          const text = (node.textContent || '').trim();
                          if (!text || text.length < 2 || text.length > 600) return;
                          if (seen.has(text)) return;
                          seen.add(text);
                          out.push({ author: null, text });
                        });
                        if (out.length >= 20) break;
                      }
                      return out;
                    }
                    """
                )
                if isinstance(dom_payload, list):
                    for item in dom_payload[:20]:
                        if not isinstance(item, dict):
                            continue
                        text = str(item.get("text", "")).strip()
                        if not text:
                            continue
                        comment_records.append(FeedComment(author=item.get("author"), text=text))

            await context.close()
            await browser.close()

        return comment_records, {
            "status": "ok" if comment_records else "empty",
            "count": len(comment_records),
        }

    @staticmethod
    def _env_int(name: str, *, default: int, min_value: int, max_value: int) -> int:
        raw = os.getenv(name, "").strip()
        if not raw:
            return default
        try:
            value = int(raw)
        except ValueError:
            return default
        return max(min_value, min(max_value, value))

    @staticmethod
    def _env_float(name: str, *, default: float, min_value: float, max_value: float) -> float:
        raw = os.getenv(name, "").strip()
        if not raw:
            return default
        try:
            value = float(raw)
        except ValueError:
            return default
        return max(min_value, min(max_value, value))

    @classmethod
    def _risk_cooldown_remaining(cls) -> float:
        return max(0.0, cls._api_risk_cooldown_until - time.monotonic())

    @classmethod
    def _mark_risk_cooldown(cls, seconds: int) -> None:
        cls._api_risk_cooldown_until = max(cls._api_risk_cooldown_until, time.monotonic() + float(seconds))

    @staticmethod
    def _is_risk_signal(*, http_status: int | None, api_code: int | None) -> bool:
        if http_status in {429, 461}:
            return True
        return api_code in {300011, 300012}

    @classmethod
    async def _wait_api_interval(cls, min_interval: float) -> None:
        elapsed = time.monotonic() - cls._api_last_request_at
        wait_sec = min_interval - elapsed
        if wait_sec > 0:
            await asyncio.sleep(wait_sec)

    @staticmethod
    async def _sleep_backoff(base: float, attempt: int) -> None:
        jitter = random.uniform(0.0, 0.25)
        await asyncio.sleep(base * (2**attempt) + jitter)

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
