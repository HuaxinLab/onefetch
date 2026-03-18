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


def node_to_text(node: lxml_html.HtmlElement) -> str:
    """Extract text from an lxml element, preserving block-level line breaks."""
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
    text = node.text_content()
    text = text.replace("\u00a0", " ")
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    lines = [line.strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line).strip()


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
