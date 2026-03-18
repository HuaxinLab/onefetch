from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import ClassVar

from lxml import html as lxml_html

from onefetch.models import FeedEntry


_BLOCK_TAGS = frozenset({
    "p", "div", "br", "h1", "h2", "h3", "h4", "h5", "h6",
    "li", "tr", "blockquote", "pre", "section", "article",
})


def node_to_text(node: lxml_html.HtmlElement, *, image_placeholders: bool = False) -> str | tuple[str, list[str]]:
    """Extract text from an lxml element, preserving block-level line breaks.

    If ``image_placeholders`` is True, ``<img>`` tags are replaced with
    ``[IMG:N]`` markers and the function returns ``(text, images)`` where
    images is a list of URLs matching the placeholder indices.
    """
    img_index = 0
    images: list[str] = []
    for el in node.iter():
        if el.tag in _BLOCK_TAGS:
            if el.text:
                el.text = "\n" + el.text
            else:
                el.text = "\n"
            if el.tail:
                el.tail = el.tail + "\n"
            else:
                el.tail = "\n"
        if image_placeholders and el.tag == "img":
            src = el.get("data-src") or el.get("src") or ""
            if src and src.startswith("http") and "svg+xml" not in src and "1px" not in src:
                img_index += 1
                images.append(src)
                marker = f"\n[IMG:{img_index}]\n"
                if el.tail:
                    el.tail = marker + el.tail
                else:
                    el.tail = marker
    text = node.text_content()
    text = text.replace("\u00a0", " ")
    text = text.replace("\u200b", "")
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    lines = [line.strip() for line in text.splitlines()]
    result = "\n".join(line for line in lines if line).strip()
    if image_placeholders:
        return result, images
    return result


class BaseAdapter(ABC):
    id: str = ""
    priority: int = 100
    register: bool = True
    _registry: ClassVar[dict[str, type["BaseAdapter"]]] = {}

    def __init_subclass__(cls, **kwargs) -> None:
        super().__init_subclass__(**kwargs)
        if not getattr(cls, "register", True):
            return
        adapter_id = (getattr(cls, "id", "") or "").strip()
        if not adapter_id:
            return
        existing = BaseAdapter._registry.get(adapter_id)
        if existing and existing is not cls:
            raise RuntimeError(f"Duplicate adapter id registered: {adapter_id}")
        BaseAdapter._registry[adapter_id] = cls

    @classmethod
    def build_registered_instances(cls) -> list["BaseAdapter"]:
        classes = sorted(
            cls._registry.values(),
            key=lambda adapter_cls: (getattr(adapter_cls, "priority", 100), adapter_cls.id),
        )
        return [adapter_cls() for adapter_cls in classes]

    @abstractmethod
    def supports(self, url: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def crawl(self, url: str) -> FeedEntry:
        raise NotImplementedError
