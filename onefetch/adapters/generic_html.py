from __future__ import annotations

import asyncio
import os
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from lxml import html

from onefetch.adapters.base import BaseAdapter, get_proxy_server, node_to_text
from onefetch.http import create_async_client
from onefetch.models import FeedEntry
from onefetch.router import normalize_url


class GenericHtmlAdapter(BaseAdapter):
    id = "generic_html"
    priority = 1000

    def supports(self, url: str) -> bool:
        return True

    async def crawl(self, url: str) -> FeedEntry:
        mode = self._render_mode()
        fetch_error = ""
        final_url = url
        status_code = 200
        headers: dict[str, str] = {}
        body_text = ""
        used_browser = False
        images: list[str] = []
        cookie = self._load_cookie(url)

        if mode != "browser":
            try:
                request_headers = {}
                if cookie:
                    request_headers["cookie"] = cookie
                async with create_async_client(timeout=30, follow_redirects=True, headers=request_headers) as client:
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
            content, images = self._extract_main_text(tree)

        should_try_browser = mode == "browser" or (mode == "auto" and self._needs_browser_fallback(content, body_text))
        browser_status: dict[str, str] = {"status": "skipped", "reason": "not_needed"}

        if should_try_browser:
            rendered_html, rendered_url, render_state = await self._render_with_browser(final_url if body_text else url, cookie=cookie)
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
                content, images = self._extract_main_text(tree)

        if not body_text and fetch_error:
            raise RuntimeError(f"generic_html fetch failed: {fetch_error}")

        # If browser was needed but Playwright is missing, raise so pipeline can
        # populate error_code=dep.playwright_missing and action_hint with install command.
        if should_try_browser and not used_browser:
            if browser_status.get("reason") == "playwright_not_installed":
                raise RuntimeError(
                    "This page requires browser rendering but Playwright is not installed."
                )

        if not content:
            content = body_text[:5000]

        # 内容为空或需要登录
        if not cookie and self._looks_like_login_required(content, body_text, title=title):
            domain = (urlparse(url).hostname or "").lower()
            raise RuntimeError(
                f"页面内容为空或需要登录才能查看。可通过 setup_cookie.sh {domain} 配置 Cookie 后重试。"
            )

        canonical = normalize_url(final_url)
        return FeedEntry(
            source_url=url,
            canonical_url=canonical,
            crawler_id=self.id,
            title=title or "Untitled page",
            author=author,
            published_at=published_at,
            body=content,
            raw_body=body_text,
            images=images,
            metadata={
                "content_type": headers.get("content-type", ""),
                "render_mode": "browser" if used_browser else "http",
                "browser": browser_status,
            },
        )

    @staticmethod
    def _load_cookie(url: str) -> str:
        """Load cookie from .secrets/<domain>_cookie.txt if exists."""
        domain = (urlparse(url).hostname or "").lower()
        if not domain:
            return ""
        project_root = Path(os.getenv("ONEFETCH_PROJECT_ROOT", ".")).resolve()
        secrets_dir = project_root / ".secrets"
        if not secrets_dir.is_dir():
            return ""
        cookie_file = secrets_dir / f"{domain}_cookie.txt"
        if cookie_file.is_file():
            return cookie_file.read_text(encoding="utf-8").strip()
        # 尝试去掉 www. 前缀
        if domain.startswith("www."):
            cookie_file = secrets_dir / f"{domain[4:]}_cookie.txt"
            if cookie_file.is_file():
                return cookie_file.read_text(encoding="utf-8").strip()
        return ""

    @staticmethod
    def _looks_like_login_required(content: str, body_text: str, *, title: str | None = None) -> bool:
        """检测页面是否需要登录才能查看内容。"""
        text = (content or "").strip()
        raw = (body_text or "").lower()
        title_lower = (title or "").lower()
        # 标题明确含登录/注册
        if any(m in title_lower for m in ["登录", "注册", "login", "sign in"]):
            return True
        # 内容极少（去噪后几乎为空）
        if len(text) < 50:
            return True
        # 常见登录提示关键词（仅在内容极少时检查，避免误判有正常内容的页面）
        if len(text) < 300:
            login_markers = [
                "请登录", "请先登录", "登录后查看",
                "需要登录", "请注册", "log in to",
            ]
            for marker in login_markers:
                if marker in raw:
                    return True
        return False

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
            return "", []
        text, images = node_to_text(candidates[0], image_placeholders=True)
        return text[:20000], images

    @staticmethod
    def _needs_browser_fallback(content: str, body_text: str) -> bool:
        if not body_text:
            return True
        normalized = body_text.lower()
        if "enable javascript" in normalized or "please turn javascript" in normalized or "without javascript" in normalized:
            return True
        # Chinese SPA placeholders
        for marker in ("加载中", "正在加载", "页面加载中", "数据加载中"):
            if marker in body_text and len(content or "") < 300:
                return True
        if "id=\"__next\"" in normalized and len(content or "") < 120:
            return True
        # Common SPA root markers with little content
        if len(content or "") < 300:
            for spa_marker in ('id="app"', 'id="root"', 'id="__nuxt"'):
                if spa_marker in normalized:
                    return True
        return len(content or "") < 160

    @staticmethod
    async def _render_with_browser(url: str, *, cookie: str = "") -> tuple[str | None, str, dict[str, str]]:
        try:
            from playwright.async_api import async_playwright
        except Exception:
            return None, url, {"status": "failed", "reason": "playwright_not_installed"}

        try:
            async with async_playwright() as p:
                launch_args = {
                    "headless": True,
                    "args": [
                        "--disable-gpu",
                        "--disable-dev-shm-usage",
                        "--disable-blink-features=AutomationControlled",
                        "--window-size=1280,800",
                    ],
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
                    domain = urlparse(url).hostname or ""
                    cookies = []
                    for pair in cookie.split(";"):
                        pair = pair.strip()
                        if "=" not in pair:
                            continue
                        name, value = pair.split("=", 1)
                        # 同时设置精确域名和父域，确保 cookie 被正确发送
                        cookies.append({"name": name.strip(), "value": value.strip(), "domain": domain, "path": "/"})
                        # 父域通配（如 .geekbang.org）
                        parts = domain.split(".")
                        if len(parts) > 2:
                            parent = "." + ".".join(parts[-2:])
                            cookies.append({"name": name.strip(), "value": value.strip(), "domain": parent, "path": "/"})
                    if cookies:
                        await page.context.add_cookies(cookies)

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
