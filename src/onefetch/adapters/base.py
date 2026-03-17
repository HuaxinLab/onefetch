from __future__ import annotations

from abc import ABC, abstractmethod

from onefetch.models import CrawlOutput


class BaseAdapter(ABC):
    id: str

    @abstractmethod
    def supports(self, url: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def crawl(self, url: str) -> CrawlOutput:
        raise NotImplementedError
