from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar

from onefetch.models import CrawlOutput


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
    async def crawl(self, url: str) -> CrawlOutput:
        raise NotImplementedError
