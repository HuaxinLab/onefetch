from __future__ import annotations

import asyncio
import os
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
        mode = self._render_mode()
        fetch_error = ""
        final_url = url
        status_code = 200
        headers: dict[str, str] = {}
        body_text = ""
        used_browser = False

        if mode != "browser":
            try:
                async with create_async_client(timeout=30, follow_redirects=True) as client:
                    response = await client.get(url)
                    response.raise_for_status()
                final_url = str(response.url)
                status_code = response.status_code
                headers = {k.lower(): v for k, v in response.headers.items()}
                body_text = response.text
            except Exception as exc:
                fetch_error = str(exc)

        title = author = None
        published_at = None
        content = ""
        if body_text:
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

        should_try_browser = mode == "browser" or (mode == "auto" and self._needs_browser_fallback(content, body_text))
        browser_status: dict[str, str] = {"status": "skipped", "reason": "not_needed"}

        if should_try_browser:
            rendered_html, rendered_url, render_state = await self._render_with_browser(final_url if body_text else url)
            browser_status = render_state
            if rendered_html:
                used_browser = True
                body_text = rendered_html
                final_url = rendered_url or final_url
                status_code = 200 if status_code <= 0 else status_code
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

        if not body_text and fetch_error:
            raise RuntimeError(f"generic_html fetch failed: {fetch_error}")

        if not content:
            content = body_text[:5000]

        canonical = normalize_url(final_url)
        capture = Capture(
            source_url=url,
            canonical_url=canonical,
            final_url=final_url,
            status_code=status_code,
            headers=headers,
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
            metadata={
                "content_type": headers.get("content-type", ""),
                "render_mode": "browser" if used_browser else "http",
                "browser": browser_status,
            },
        )
        return CrawlOutput(capture=capture, feed=feed)

    @staticmethod
    def _render_mode() -> str:
        raw = os.getenv("ONEFETCH_GENERIC_RENDER_MODE", "auto").strip().lower()
        if raw in {"http", "auto", "browser"}:
            return raw
        return "auto"

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
        cleaned = html.fromstring(html.tostring(tree, encoding="unicode"))
        remove_xpaths = [
            "//nav",
            "//header",
            "//footer",
            "//*[@role='navigation']",
            "//*[@role='banner']",
            "//*[contains(concat(' ', normalize-space(@class), ' '), ' sidebar ')]",
        ]
        for xpath in remove_xpaths:
            for node in cleaned.xpath(xpath):
                parent = node.getparent()
                if parent is not None:
                    parent.remove(node)

        candidates = cleaned.xpath("//article") or cleaned.xpath("//main") or cleaned.xpath("//body")
        if not candidates:
            return ""
        text = candidates[0].text_content()
        text = re.sub(r"\n\s*\n+", "\n\n", text)
        return text.strip()[:20000]

    @staticmethod
    def _needs_browser_fallback(content: str, body_text: str) -> bool:
        if not body_text:
            return True
        normalized = body_text.lower()
        if "enable javascript" in normalized or "please turn javascript" in normalized:
            return True
        if "id=\"__next\"" in normalized and len(content or "") < 120:
            return True
        return len(content or "") < 160

    @staticmethod
    async def _render_with_browser(url: str) -> tuple[str | None, str, dict[str, str]]:
        try:
            from playwright.async_api import async_playwright
        except Exception:
            return None, url, {"status": "skipped", "reason": "playwright_not_installed"}

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

                html_text = await page.content()
                final_url = page.url
                await browser.close()
                return html_text, final_url, {"status": "ok", "load_mode": load_mode}
        except Exception as exc:
            return None, url, {"status": "failed", "reason": str(exc)}

    @staticmethod
    def _parse_datetime(value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            normalized = value.replace("Z", "+00:00")
            return datetime.fromisoformat(normalized)
        except ValueError:
            return None
