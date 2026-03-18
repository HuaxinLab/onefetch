"""Shared HTML-to-Markdown conversion utilities for adapters."""

from __future__ import annotations

import re

from lxml import html
from markdownify import markdownify


_BOILERPLATE_XPATHS = [
    "//script",
    "//style",
    "//noscript",
    "//iframe",
    "//nav",
    "//header",
    "//footer",
    "//*[@role='navigation']",
    "//*[@role='banner']",
    "//*[contains(concat(' ', normalize-space(@class), ' '), ' sidebar ')]",
]


def element_to_markdown(element: html.HtmlElement, *, limit: int = 60000) -> str:
    """Convert an lxml element to cleaned Markdown."""
    clone = html.fromstring(html.tostring(element, encoding="unicode"))
    _remove_boilerplate(clone)
    raw_html = html.tostring(clone, encoding="unicode")
    md = markdownify(raw_html, heading_style="ATX", strip=["img"])
    return _clean_markdown(md)[:limit]


def html_string_to_markdown(raw_html: str, *, limit: int = 60000) -> str:
    """Convert an HTML string (fragment or full) to cleaned Markdown."""
    if not raw_html:
        return ""
    try:
        node = html.fromstring(f"<div>{raw_html}</div>")
    except Exception:
        return raw_html.strip()[:limit]
    raw = html.tostring(node, encoding="unicode")
    md = markdownify(raw, heading_style="ATX", strip=["img"])
    return _clean_markdown(md)[:limit]


def extract_main_content(tree: html.HtmlElement, selectors: list[str] | None = None, *, limit: int = 60000) -> str:
    """Extract main content from a page tree as Markdown.

    Removes boilerplate, finds the main content element, converts to Markdown.
    ``selectors`` are XPath expressions tried in order; defaults to
    //article, //main, //body.
    """
    cleaned = html.fromstring(html.tostring(tree, encoding="unicode"))
    _remove_boilerplate(cleaned)

    if selectors is None:
        selectors = ["//article", "//main", "//body"]

    for xpath in selectors:
        candidates = cleaned.xpath(xpath)
        if candidates:
            raw = html.tostring(candidates[0], encoding="unicode")
            md = markdownify(raw, heading_style="ATX", strip=["img"])
            result = _clean_markdown(md)
            if result:
                return result[:limit]
    return ""


def _remove_boilerplate(tree: html.HtmlElement) -> None:
    for xpath in _BOILERPLATE_XPATHS:
        for node in tree.xpath(xpath):
            parent = node.getparent()
            if parent is not None:
                parent.remove(node)


def _clean_markdown(text: str) -> str:
    text = text.replace("\u00a0", " ")
    # Collapse 3+ blank lines into 2
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
    # Strip trailing whitespace per line
    lines = [line.rstrip() for line in text.splitlines()]
    return "\n".join(lines).strip()
