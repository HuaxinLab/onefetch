from __future__ import annotations

from urllib.parse import quote, urlparse

from onefetch.adapters.generic_html import GenericHtmlAdapter
from onefetch.http import create_async_client
from onefetch.models import FeedEntry


class XAdapter(GenericHtmlAdapter):
    id = "x"
    priority = 900

    def supports(self, url: str) -> bool:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        if host not in {"x.com", "www.x.com", "twitter.com", "www.twitter.com"}:
            return False
        path = (parsed.path or "").lower()
        return "/status/" in path or "/i/article/" in path

    async def crawl(self, url: str) -> FeedEntry:
        try:
            feed = await super().crawl(url)
        except RuntimeError:
            feed = await self._fallback_feed(url)
            if feed:
                return feed
            raise

        if self._looks_like_x_shell(feed.body, feed.raw_body, title=feed.title):
            fallback = await self._fallback_feed(url)
            if fallback:
                return fallback
        return feed

    async def _fallback_feed(self, url: str) -> FeedEntry | None:
        text = await self._fetch_x_fallback(url)
        if not text:
            return None
        return FeedEntry(
            source_url=url,
            canonical_url=url,
            crawler_id=self.id,
            title="X post (fallback)",
            author=None,
            published_at=None,
            body=text,
            raw_body=text,
            images=[],
            metadata={"fallback_source": "oembed+tco+reader"},
        )

    @staticmethod
    def _looks_like_x_shell(content: str, body_text: str, *, title: str | None = None) -> bool:
        merged = f"{title or ''}\n{content or ''}\n{body_text or ''}".lower()
        markers = [
            "something went wrong, but don’t fret",
            "something went wrong, but don't fret",
            "privacy related extensions may cause issues on x.com",
            "don’t miss what’s happening",
            "people on x are the first to know",
            "log in sign up",
        ]
        if any(m in merged for m in markers):
            return True
        if len((content or "").strip()) < 120 and 'data-testid="tweet"' not in merged and "tweettext" not in merged:
            return True
        return False

    @staticmethod
    def _extract_reader_markdown(text: str) -> str:
        if not text:
            return ""
        marker = "Markdown Content:"
        idx = text.find(marker)
        body = text[idx + len(marker):] if idx >= 0 else text
        cleaned = body.strip()
        if not cleaned:
            return ""
        if "Don’t miss what’s happening" in cleaned or "People on X are the first to know." in cleaned:
            return ""
        return cleaned

    async def _fetch_x_fallback(self, url: str) -> str:
        oembed_url = (
            "https://publish.twitter.com/oembed"
            f"?omit_script=1&dnt=true&url={quote(url, safe='')}"
        )
        try:
            async with create_async_client(timeout=20, follow_redirects=True) as client:
                oembed_resp = await client.get(oembed_url)
                oembed_resp.raise_for_status()
                payload = oembed_resp.json()
                html_snippet = str(payload.get("html") or "")
                if not html_snippet:
                    return ""

                block = self._parse_html_tree(f"<div>{html_snippet}</div>")
                text = " ".join((block.text_content() or "").split()).strip()
                if text and "https://t.co/" not in text and len(text) >= 40:
                    return text

                links = block.xpath(".//a/@href")
                tco = next((link for link in links if isinstance(link, str) and link.startswith("https://t.co/")), "")
                if not tco:
                    return ""

                resolved = await client.get(tco)
                target_url = str(resolved.url)
                if "/i/article/" not in target_url:
                    return ""

                reader_url = "https://r.jina.ai/http://" + target_url.replace("https://", "").replace("http://", "")
                reader_resp = await client.get(reader_url)
                reader_resp.raise_for_status()
                return self._extract_reader_markdown(reader_resp.text)[:20000]
        except Exception:
            return ""

