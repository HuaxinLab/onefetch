from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone
from urllib.parse import urlparse

from lxml import html

from onefetch.adapters.base import BaseAdapter, node_to_text
from onefetch.http import create_async_client
from onefetch.models import FeedEntry
from onefetch.router import normalize_url


class WechatAdapter(BaseAdapter):
    id = "wechat"
    priority = 200

    def supports(self, url: str) -> bool:
        host = (urlparse(url).hostname or "").lower()
        return host == "mp.weixin.qq.com"

    async def crawl(self, url: str) -> FeedEntry:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
        async with create_async_client(timeout=30, follow_redirects=True, headers=headers) as client:
            response = await client.get(url)
            response.raise_for_status()

        final_url = str(response.url)
        canonical = normalize_url(final_url)
        body_text = response.text
        tree = html.fromstring(body_text)

        title, author, published_at, content, images, cleanup_info = self._extract_article(tree, body_text)
        mode = "http"

        should_browser_fallback = self._needs_browser_fallback(tree, content)
        browser_status: dict[str, str] = {"status": "skipped", "reason": "not_needed"}
        if should_browser_fallback:
            browser_data, browser_status = await self._extract_with_browser(final_url)
            if browser_data:
                mode = "browser"
                title = browser_data.get("title") or title
                author = browser_data.get("author") or author
                published_at = browser_data.get("published_at") or published_at
                content = browser_data.get("content") or content
                cleanup_info = browser_data.get("cleanup") or cleanup_info
            elif browser_status.get("reason") == "playwright_not_installed":
                raise RuntimeError(
                    "WeChat page requires browser rendering but Playwright is not installed."
                )

        return FeedEntry(
            source_url=url,
            canonical_url=canonical,
            crawler_id=self.id,
            title=title or "微信公众号文章",
            author=author,
            published_at=published_at,
            body=content,
            raw_body=body_text,
            images=images,
            metadata={
                "platform": "wechat",
                "content_type": "wechat_article",
                "render_mode": mode,
                "browser": browser_status,
                "cleanup": cleanup_info,
            },
        )

    @staticmethod
    def _extract_article(
        tree: html.HtmlElement,
        raw_html: str,
    ) -> tuple[str | None, str | None, datetime | None, str, list[str], dict[str, int]]:
        title = WechatAdapter._first_text(
            tree,
            [
                "//*[@id='activity-name']/text()",
                "//meta[@property='og:title']/@content",
                "//title/text()",
            ],
        )
        author = WechatAdapter._first_text(tree, ["//*[@id='js_name']/text()", "//meta[@name='author']/@content"])
        published_raw = WechatAdapter._first_text(tree, ["//*[@id='publish_time']/text()", "//*[@id='js_publish_time']/text()"])

        content = ""
        content_images: list[str] = []
        blocks = tree.xpath("//*[@id='js_content']")
        if blocks:
            content, content_images = WechatAdapter._clean_text_from_node(blocks[0])
        if not content:
            article_nodes = tree.xpath("//article") or tree.xpath("//main")
            if article_nodes:
                content, content_images = WechatAdapter._clean_text_from_node(article_nodes[0])

        if title and "微信公众平台" in title:
            title = title.replace("微信公众平台", "").strip(" -")

        published_at = WechatAdapter._parse_datetime(published_raw)
        if published_at is None:
            ts_match = re.search(r"\bvar\s+ct\s*=\s*['\"]?(\d{10})['\"]?", raw_html)
            if ts_match:
                published_at = datetime.fromtimestamp(int(ts_match.group(1)), tz=timezone.utc)

        cleaned_content, cleanup_info = WechatAdapter._sanitize_content(content)
        return title, author, published_at, cleaned_content[:40000], content_images, cleanup_info

    @staticmethod
    def _needs_browser_fallback(tree: html.HtmlElement, content: str) -> bool:
        if len((content or "").strip()) >= 500:
            return False
        page_text = tree.text_content().lower()
        markers = [
            "环境异常",
            "完成验证后即可继续访问",
            "验证码",
            "wappoc_appmsgcaptcha",
            "访问过于频繁",
        ]
        return any(marker in page_text for marker in markers) or len((content or "").strip()) < 180

    @staticmethod
    async def _extract_with_browser(url: str) -> tuple[dict | None, dict[str, str]]:
        try:
            from playwright.async_api import async_playwright
        except Exception:
            return None, {"status": "failed", "reason": "playwright_not_installed"}

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=[
                        "--disable-gpu",
                        "--disable-dev-shm-usage",
                        "--disable-blink-features=AutomationControlled",
                        "--window-size=1280,800",
                    ],
                )
                page = await browser.new_page(
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/131.0.0.0 Safari/537.36"
                    ),
                    viewport={"width": 1280, "height": 800},
                )

                await page.add_init_script(
                    """
                    Object.defineProperty(navigator, 'webdriver', { get: () => false });
                    Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh', 'en'] });
                    Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
                    window.chrome = { runtime: {} };
                    """
                )

                try:
                    await page.goto(url, wait_until="networkidle", timeout=45000)
                    load_mode = "networkidle"
                except Exception:
                    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    await asyncio.sleep(3)
                    load_mode = "domcontentloaded"

                data = await page.evaluate(
                    """
                    () => {
                      const text = (el) => (el?.innerText || el?.textContent || '').trim();
                      const title = text(document.querySelector('#activity-name'))
                        || text(document.querySelector('h1'))
                        || document.title;
                      const author = text(document.querySelector('#js_name'))
                        || text(document.querySelector('.rich_media_meta_text'));
                      const published = text(document.querySelector('#publish_time'))
                        || text(document.querySelector('#js_publish_time'));
                      const content = text(document.querySelector('#js_content'))
                        || text(document.querySelector('article'))
                        || text(document.body);
                      return { title, author, published, content };
                    }
                    """
                )
                await browser.close()
                cleaned_content, cleanup_info = WechatAdapter._sanitize_content((data.get("content") or "").strip())
                published_at = WechatAdapter._parse_datetime(data.get("published") or "")
                return (
                    {
                        "title": (data.get("title") or "").strip(),
                        "author": (data.get("author") or "").strip(),
                        "published_at": published_at,
                        "content": cleaned_content[:40000],
                        "cleanup": cleanup_info,
                    },
                    {"status": "ok", "load_mode": load_mode},
                )
        except Exception as exc:
            return None, {"status": "failed", "reason": str(exc)}

    @staticmethod
    def _first_text(tree: html.HtmlElement, xpaths: list[str]) -> str | None:
        for xpath in xpaths:
            values = tree.xpath(xpath)
            if not values:
                continue
            value = values[0]
            if isinstance(value, str):
                stripped = value.strip()
                if stripped:
                    return stripped
        return None

    @staticmethod
    def _clean_text_from_node(node: html.HtmlElement) -> tuple[str, list[str]]:
        clone = html.fromstring(html.tostring(node, encoding="unicode"))
        for unwanted in clone.xpath(".//script|.//style|.//noscript|.//iframe"):
            parent = unwanted.getparent()
            if parent is not None:
                parent.remove(unwanted)
        return node_to_text(clone, image_placeholders=True)

    @staticmethod
    def _sanitize_content(text: str) -> tuple[str, dict[str, int]]:
        lines = [line.strip() for line in (text or "").splitlines()]
        filtered: list[str] = []
        removed = 0
        patterns = [
            re.compile(r"^微信扫一扫"),
            re.compile(r"^预览时标签不可点"),
            re.compile(r"^继续滑动看下一个"),
            re.compile(r"^喜欢此内容的人还喜欢"),
            re.compile(r"^阅读\s*\d+"),
            re.compile(r"^在看\s*\d+"),
            re.compile(r"^分享\s*$"),
            re.compile(r"^收藏\s*$"),
            re.compile(r"^点赞\s*$"),
            re.compile(r"^写留言\s*$"),
            re.compile(r"^投诉$"),
            re.compile(r"^点击下方卡片关注"),
            re.compile(r"^以上内容由.*提供$"),
            re.compile(r"^var\s+\w+"),
        ]

        for line in lines:
            if not line:
                continue
            if any(p.search(line) for p in patterns):
                removed += 1
                continue
            filtered.append(line)

        compact = []
        for line in filtered:
            if compact and compact[-1] == line:
                removed += 1
                continue
            compact.append(line)

        return "\n\n".join(compact).strip(), {"removed_lines": removed, "kept_lines": len(compact)}

    @staticmethod
    def _parse_datetime(value: str | None) -> datetime | None:
        if not value:
            return None
        value = value.strip()
        patterns = [
            "%Y-%m-%d",
            "%Y/%m/%d",
            "%Y-%m-%d %H:%M",
            "%Y/%m/%d %H:%M",
            "%Y-%m-%d %H:%M:%S",
            "%Y/%m/%d %H:%M:%S",
        ]
        for pattern in patterns:
            try:
                dt = datetime.strptime(value, pattern)
                return dt.replace(tzinfo=timezone.utc)
            except ValueError:
                continue
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
