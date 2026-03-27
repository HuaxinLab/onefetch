from __future__ import annotations

import asyncio
import os
import re
from datetime import datetime
from urllib.parse import urlparse

from lxml import html

from onefetch.adapters.base import BaseAdapter, get_proxy_server, node_to_text
from onefetch.http import create_async_client
from onefetch.models import FeedEntry
from onefetch.router import normalize_url
from onefetch.secrets import load_cookie


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
            tree = self._parse_html_tree(body_text)
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
                tree = self._parse_html_tree(body_text)
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
    def _sanitize_html_text(text: str) -> str:
        # lxml rejects NULL bytes and most C0 controls in XML-compatible mode.
        # Keep TAB/LF/CR and strip the rest to avoid parser crashes on malformed pages.
        return re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F]", "", text or "")

    @classmethod
    def _parse_html_tree(cls, text: str) -> html.HtmlElement:
        return html.fromstring(cls._sanitize_html_text(text))

    @staticmethod
    def _load_cookie(url: str) -> str:
        domain = (urlparse(url).hostname or "").lower()
        if not domain:
            return ""
        return load_cookie(domains=[domain])

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
        cleaned = GenericHtmlAdapter._parse_html_tree(html.tostring(tree, encoding="unicode"))
        remove_xpaths = [
            "//script",
            "//style",
            "//noscript",
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
        normalized = GenericHtmlAdapter._normalize_markdown_structure(candidates[0])
        text, images = node_to_text(normalized, image_placeholders=True)
        return text[:20000], images

    @staticmethod
    def _normalize_markdown_structure(node: html.HtmlElement) -> html.HtmlElement:
        normalized = html.fromstring(html.tostring(node, encoding="unicode"))
        GenericHtmlAdapter._normalize_lists(normalized)
        GenericHtmlAdapter._normalize_links(normalized)
        GenericHtmlAdapter._normalize_tables(normalized)
        # Keep heading hierarchy for downstream LLM understanding.
        heading_nodes = normalized.xpath(".//h1|.//h2|.//h3|.//h4|.//h5|.//h6")
        min_level = 0
        if heading_nodes:
            levels: list[int] = []
            for heading in heading_nodes:
                tag = str(getattr(heading, "tag", "") or "").lower()
                if tag.startswith("h") and tag[1:].isdigit():
                    levels.append(int(tag[1:]))
            if levels:
                min_level = min(levels)
        if min_level > 0:
            for heading in heading_nodes:
                tag = str(getattr(heading, "tag", "") or "").lower()
                if not (tag.startswith("h") and tag[1:].isdigit()):
                    continue
                level = int(tag[1:])
                mapped_level = max(3, min(level - min_level + 3, 6))
                prefix = "#" * mapped_level + " "
                existing = heading.text or ""
                if not existing.startswith(prefix):
                    heading.text = prefix + existing

        # Preserve block-code as fenced markdown.
        for pre in normalized.xpath(".//pre"):
            text = (pre.text_content() or "").replace("\u00a0", " ").replace("\u200b", "")
            text = text.replace("\r\n", "\n").replace("\r", "\n").strip("\n")
            if not text.strip():
                continue
            lang = GenericHtmlAdapter._detect_code_language(pre)
            fence = f"```{lang}" if lang else "```"
            pre.clear()
            pre.text = f"\n{fence}\n{text}\n```"
        return normalized

    @staticmethod
    def _detect_code_language(pre_node: html.HtmlElement) -> str:
        candidates = [
            str(pre_node.get("data-language") or ""),
            str(pre_node.get("data-lang") or ""),
            str(pre_node.get("language") or ""),
            str(pre_node.get("class") or ""),
        ]
        for code in pre_node.xpath(".//code"):
            candidates.extend(
                [
                    str(code.get("data-language") or ""),
                    str(code.get("data-lang") or ""),
                    str(code.get("language") or ""),
                    str(code.get("class") or ""),
                ]
            )
        for item in candidates:
            low = item.lower()
            match = re.search(r"language-([a-z0-9_+-]+)", low)
            if match:
                return match.group(1)
            if low in {
                "python",
                "javascript",
                "typescript",
                "java",
                "go",
                "rust",
                "c",
                "cpp",
                "bash",
                "shell",
                "json",
                "yaml",
                "sql",
            }:
                return low
        return ""

    @staticmethod
    def _normalize_lists(node: html.HtmlElement) -> None:
        for list_node in node.xpath(".//ul|.//ol"):
            ordered = str(getattr(list_node, "tag", "")).lower() == "ol"
            items = list_node.xpath("./li")
            for idx, li in enumerate(items, start=1):
                prefix = f"{idx}. " if ordered else "- "
                text = li.text or ""
                if not text.startswith(prefix):
                    li.text = prefix + text

    @staticmethod
    def _normalize_links(node: html.HtmlElement) -> None:
        for anchor in node.xpath(".//a[@href]"):
            # Keep image wrappers for downstream image placeholder extraction.
            if anchor.xpath(".//img"):
                continue
            href = (anchor.get("href") or "").strip()
            if href.startswith("//"):
                href = "https:" + href
            text = " ".join((anchor.text_content() or "").split())
            if href and text:
                label = f"[{text}]({href})"
            else:
                label = text or href
            replacement = html.Element("span")
            replacement.text = label
            parent = anchor.getparent()
            if parent is not None:
                parent.replace(anchor, replacement)

    @staticmethod
    def _normalize_tables(node: html.HtmlElement) -> None:
        for table in node.xpath(".//table"):
            block = GenericHtmlAdapter._table_to_markdown(table)
            if not block:
                continue
            replacement = html.Element("div")
            replacement.text = "\n" + block + "\n"
            parent = table.getparent()
            if parent is not None:
                parent.replace(table, replacement)

    @staticmethod
    def _table_to_markdown(table_node: html.HtmlElement) -> str:
        rows: list[list[str]] = []
        header_by_th = False
        for tr in table_node.xpath(".//tr"):
            cells = tr.xpath("./th|./td")
            if not cells:
                continue
            values: list[str] = []
            if tr.xpath("./th"):
                header_by_th = True
            for cell in cells:
                text = " ".join((cell.text_content() or "").split())
                values.append(text.replace("|", r"\|"))
            rows.append(values)
        if not rows:
            return ""

        col_count = max(len(row) for row in rows)
        normalized_rows = [row + [""] * (col_count - len(row)) for row in rows]
        header = normalized_rows[0]
        body = normalized_rows[1:]
        if not header_by_th and not body:
            return ""
        lines = [
            "| " + " | ".join(header) + " |",
            "| " + " | ".join(["---"] * col_count) + " |",
        ]
        for row in body:
            lines.append("| " + " | ".join(row) + " |")
        return "\n".join(lines)

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
        # Content is mostly URLs (SPA nav links rendered for SEO, no real body text)
        if content:
            url_chars = sum(len(m) for m in re.findall(r"https?://\S+", content))
            if url_chars > len(content) * 0.5:
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
