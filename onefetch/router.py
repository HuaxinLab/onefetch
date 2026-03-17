from __future__ import annotations

from urllib.parse import urlparse, urlunparse

from onefetch.adapters.base import BaseAdapter


def normalize_url(url: str) -> str:
    parsed = urlparse(url.strip())
    scheme = (parsed.scheme or "https").lower()
    netloc = parsed.netloc.lower().replace(":80", "").replace(":443", "")
    path = parsed.path.rstrip("/") or "/"
    cleaned = parsed._replace(scheme=scheme, netloc=netloc, path=path, fragment="")
    return urlunparse(cleaned)


class Router:
    def __init__(self, adapters: list[BaseAdapter]) -> None:
        self._adapters = adapters

    def list_adapters(self) -> list[str]:
        return [adapter.id for adapter in self._adapters]

    def route(self, url: str, forced_adapter: str | None = None) -> BaseAdapter:
        if forced_adapter:
            for adapter in self._adapters:
                if adapter.id == forced_adapter:
                    return adapter
            raise LookupError(f"Adapter not found: {forced_adapter}")

        for adapter in self._adapters:
            if adapter.supports(url):
                return adapter

        raise LookupError(f"No adapter matched URL: {url}")
