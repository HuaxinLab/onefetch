from __future__ import annotations

import re
from datetime import datetime

from lxml import html

from onefetch.adapters.base import BaseAdapter
from onefetch.http import create_async_client
from onefetch.models import Capture, CrawlOutput, FeedEntry
from onefetch.router import normalize_url


class GenericHtmlAdapter(BaseAdapter):
    id = "generic_html"

    def supports(self, url: str) -> bool:
        return True

    async def crawl(self, url: str) -> CrawlOutput:
        async with create_async_client(timeout=30, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()

        final_url = str(response.url)
        canonical = normalize_url(final_url)
        body_text = response.text
        tree = html.fromstring(body_text)

        title = self._first_text(tree, ["//meta[@property='og:title']/@content", "//title/text()"])
        author = self._first_text(tree, ["//meta[@name='author']/@content", "//meta[@property='article:author']/@content"])
        published_raw = self._first_text(
            tree,
            [
                "//meta[@property='article:published_time']/@content",
                "//time/@datetime",
            ],
        )
        published_at = self._parse_datetime(published_raw)

        content = self._extract_main_text(tree)
        if not content:
            content = body_text[:5000]

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
            title=title or "Untitled page",
            author=author,
            published_at=published_at,
            body=content,
            metadata={"content_type": response.headers.get("content-type", "")},
        )
        return CrawlOutput(capture=capture, feed=feed)

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
    def _extract_main_text(tree: html.HtmlElement) -> str:
        candidates = tree.xpath("//article") or tree.xpath("//main") or tree.xpath("//body")
        if not candidates:
            return ""
        text = candidates[0].text_content()
        text = re.sub(r"\n\s*\n+", "\n\n", text)
        return text.strip()[:20000]

    @staticmethod
    def _parse_datetime(value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            normalized = value.replace("Z", "+00:00")
            return datetime.fromisoformat(normalized)
        except ValueError:
            return None
