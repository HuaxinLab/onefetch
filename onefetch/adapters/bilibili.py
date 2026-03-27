from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone
from urllib.parse import urlparse

from lxml import html

from onefetch.adapters.base import BaseAdapter, get_proxy_server, node_to_text
from onefetch.credentials import get_cookie_for_domains
from onefetch.http import create_async_client
from onefetch.models import FeedEntry
from onefetch.router import normalize_url

_BV_RE = re.compile(r"/(video|bangumi/play)/(BV[\w]+|ep\d+|ss\d+)")
_OPUS_RE = re.compile(r"/opus/(\d+)")


class BilibiliAdapter(BaseAdapter):
    id = "bilibili"
    priority = 200

    def supports(self, url: str) -> bool:
        host = (urlparse(url).hostname or "").lower()
        if not host.endswith("bilibili.com"):
            return False
        path = urlparse(url).path or "/"
        return bool(_BV_RE.search(path) or _OPUS_RE.search(path))

    async def crawl(self, url: str) -> FeedEntry:
        path = urlparse(url).path or "/"
        if _BV_RE.search(path):
            return await self._crawl_video(url)
        return await self._crawl_opus(url)

    # ---- 视频页面 ----

    async def _crawl_video(self, url: str) -> FeedEntry:
        bvid = self._extract_bvid(url)
        if not bvid:
            raise RuntimeError(f"无法从 URL 提取 BV 号: {url}")

        cookie = self._load_cookie()
        headers = self._request_headers(cookie)

        async with create_async_client(timeout=30, follow_redirects=True, headers=headers) as client:
            # 视频信息
            resp = await client.get(f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}")
            resp.raise_for_status()
            data = resp.json()
            if data.get("code") != 0:
                raise RuntimeError(f"B 站视频信息获取失败: {data.get('message', '')}")

            info = data["data"]
            cid = info["cid"]
            title = info.get("title", "")
            author = (info.get("owner") or {}).get("name", "")
            desc = (info.get("desc") or "").strip()
            duration = info.get("duration", 0)
            published_ts = info.get("pubdate") or info.get("ctime")
            published_at = datetime.fromtimestamp(published_ts, tz=timezone.utc) if published_ts else None
            cover = info.get("pic", "")

            # 字幕
            subtitle_text = ""
            subtitle_source = "none"
            resp2 = await client.get(f"https://api.bilibili.com/x/player/wbi/v2?bvid={bvid}&cid={cid}")
            sub_data = resp2.json()
            subtitles = (sub_data.get("data") or {}).get("subtitle", {}).get("subtitles", [])

            if subtitles:
                sub_url = subtitles[0].get("subtitle_url", "")
                if sub_url.startswith("//"):
                    sub_url = "https:" + sub_url
                if sub_url:
                    resp3 = await client.get(sub_url)
                    sub_json = resp3.json()
                    body_items = sub_json.get("body", [])
                    subtitle_text = "\n".join(item.get("content", "") for item in body_items)
                    lan = subtitles[0].get("lan_doc", "")
                    subtitle_source = f"ai-subtitle ({lan})" if subtitles[0].get("ai_type") else f"subtitle ({lan})"

        # 构建正文
        sections: list[str] = []
        if desc:
            sections.append(f"简介：\n{desc}")
        if subtitle_text:
            sections.append(f"字幕全文：\n{subtitle_text}")
        elif not cookie:
            sections.append("（未获取到字幕，B 站字幕需要登录。可通过 setup_cookie.sh www.bilibili.com 配置 Cookie 后重试。）")
        else:
            sections.append("（该视频无字幕）")
        body = "\n\n".join(sections)

        images: list[str] = []
        if cover and cover.startswith("http"):
            images.append(cover)

        canonical = normalize_url(url)
        return FeedEntry(
            source_url=url,
            canonical_url=canonical,
            crawler_id=self.id,
            title=title,
            author=author,
            published_at=published_at,
            body=body,
            raw_body="",
            images=images,
            metadata={
                "platform": "bilibili",
                "content_type": "video",
                "bvid": bvid,
                "cid": cid,
                "duration": duration,
                "subtitle_source": subtitle_source,
            },
        )

    # ---- 专栏/动态页面 ----

    async def _crawl_opus(self, url: str) -> FeedEntry:
        cookie = self._load_cookie()
        request_headers = self._request_headers(cookie)

        async with create_async_client(timeout=30, follow_redirects=True, headers=request_headers) as client:
            response = await client.get(url)
            response.raise_for_status()

        final_url = str(response.url)
        body_text = response.text
        tree = html.fromstring(body_text)

        title = self._first_text(tree, [
            "//meta[@property='og:title']/@content",
            "//title/text()",
        ])
        author = self._first_text(tree, ["//meta[@name='author']/@content"])

        content, images = "", []
        # 专栏通常是 SPA，需要 Playwright
        if len(tree.text_content().strip()) < 200 or not self._has_article_content(tree):
            rendered_html = await self._render_with_browser(final_url, cookie)
            if rendered_html:
                body_text = rendered_html
                tree = html.fromstring(body_text)
                title = self._first_text(tree, [
                    "//meta[@property='og:title']/@content",
                    "//title/text()",
                ]) or title
                author = self._first_text(tree, ["//meta[@name='author']/@content"]) or author

        # 精确提取文章内容区
        content_nodes = tree.xpath("//div[contains(@class,'opus-module-content')]")
        if content_nodes:
            content, images = node_to_text(content_nodes[0], image_placeholders=True)
        else:
            content, images = node_to_text(tree, image_placeholders=True)
        content = content[:60000]

        # 从 opus-module-author 提取作者和时间
        if not author:
            author = self._extract_opus_author(tree)
        published_at = self._extract_opus_time(tree)

        if title and " - 哔哩哔哩" in title:
            title = title.split(" - 哔哩哔哩")[0].strip()

        canonical = normalize_url(final_url)
        return FeedEntry(
            source_url=url,
            canonical_url=canonical,
            crawler_id=self.id,
            title=title or "B 站内容",
            author=author,
            published_at=published_at,
            body=content,
            raw_body=body_text,
            images=images,
            metadata={
                "platform": "bilibili",
                "content_type": "opus",
            },
        )

    # ---- 工具方法 ----

    @staticmethod
    def _extract_bvid(url: str) -> str | None:
        m = re.search(r"(BV[\w]+)", url)
        return m.group(1) if m else None

    @staticmethod
    def _load_cookie() -> str:
        return get_cookie_for_domains(["bilibili.com", "www.bilibili.com"])

    @staticmethod
    def _request_headers(cookie: str = "") -> dict[str, str]:
        headers = {
            "user-agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            "referer": "https://www.bilibili.com/",
        }
        if cookie:
            headers["cookie"] = cookie
        return headers

    @staticmethod
    def _first_text(tree: html.HtmlElement, xpaths: list[str]) -> str | None:
        for xpath in xpaths:
            values = tree.xpath(xpath)
            if values:
                val = values[0]
                if isinstance(val, str) and val.strip():
                    return val.strip()
        return None

    @staticmethod
    def _extract_opus_author(tree: html.HtmlElement) -> str | None:
        nodes = tree.xpath("//div[contains(@class,'opus-module-author')]")
        if not nodes:
            return None
        text = nodes[0].text_content().strip()
        # 格式："花心实验室 编辑于 2026年03月06日 22:07"
        if "编辑于" in text:
            return text.split("编辑于")[0].strip()
        if "发布于" in text:
            return text.split("发布于")[0].strip()
        return text.strip() or None

    @staticmethod
    def _extract_opus_time(tree: html.HtmlElement) -> datetime | None:
        nodes = tree.xpath("//div[contains(@class,'opus-module-author')]")
        if not nodes:
            return None
        text = nodes[0].text_content().strip()
        # "编辑于 2026年03月06日 22:07" 或 "发布于 ..."
        m = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日\s*(\d{1,2}):(\d{2})", text)
        if m:
            from datetime import timedelta
            _CST = timezone(timedelta(hours=8))
            return datetime(
                int(m.group(1)), int(m.group(2)), int(m.group(3)),
                int(m.group(4)), int(m.group(5)),
                tzinfo=_CST,
            )
        return None

    @staticmethod
    def _has_article_content(tree: html.HtmlElement) -> bool:
        """检测页面是否有实际渲染的文章内容（不只是 DOM 骨架）。"""
        for sel in ["//div[contains(@class,'opus-module-content')]", "//article"]:
            nodes = tree.xpath(sel)
            if not nodes:
                continue
            content_text = nodes[0].text_content().strip()
            if len(content_text) < 100:
                continue
            # 检查代码块是否已渲染（B 站 SPA 的 pre 标签可能是空壳）
            pres = nodes[0].xpath(".//pre")
            if pres and all(not p.text_content().strip() for p in pres):
                return False  # 有代码块但全是空的，需要 Playwright
            return True
        return False

    @staticmethod
    async def _render_with_browser(url: str, cookie: str = "") -> str | None:
        try:
            from playwright.async_api import async_playwright
        except Exception:
            return None

        try:
            async with async_playwright() as p:
                launch_args = {
                    "headless": True,
                    "args": ["--disable-gpu", "--disable-dev-shm-usage", "--disable-blink-features=AutomationControlled"],
                }
                proxy = get_proxy_server()
                if proxy:
                    launch_args["proxy"] = {"server": proxy}
                browser = await p.chromium.launch(**launch_args)
                page = await browser.new_page(
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/131.0.0.0 Safari/537.36"
                    ),
                    viewport={"width": 1280, "height": 800},
                )

                if cookie:
                    from urllib.parse import urlparse as _urlparse
                    domain = _urlparse(url).hostname or ""
                    cookies = []
                    for pair in cookie.split(";"):
                        pair = pair.strip()
                        if "=" not in pair:
                            continue
                        name, value = pair.split("=", 1)
                        cookies.append({"name": name.strip(), "value": value.strip(), "domain": domain, "path": "/"})
                    if cookies:
                        await page.context.add_cookies(cookies)

                await page.add_init_script(
                    "Object.defineProperty(navigator, 'webdriver', { get: () => false });"
                )

                try:
                    await page.goto(url, wait_until="networkidle", timeout=45000)
                except Exception:
                    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    await asyncio.sleep(3)

                html_text = await page.content()
                await browser.close()
                return html_text
        except Exception:
            return None
