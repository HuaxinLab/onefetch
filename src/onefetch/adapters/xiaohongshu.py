from __future__ import annotations

from datetime import datetime
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

        title, author, content, published_at = self._extract_from_html(body_text)

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
            metadata={"platform": "xiaohongshu", "final_url": final_url},
        )
        return CrawlOutput(capture=capture, feed=feed)

    def _extract_from_html(self, html_text: str) -> tuple[str | None, str | None, str | None, datetime | None]:
        tree = html.fromstring(html_text)
        title = self._first(tree, ["//meta[@property='og:title']/@content", "//title/text()"])
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
            ],
        )
        published_raw = self._first(tree, ["//meta[@property='article:published_time']/@content", "//time/@datetime"])
        published_at = self._parse_datetime(published_raw)
        return title, author, description, published_at

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
