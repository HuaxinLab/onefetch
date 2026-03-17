from __future__ import annotations

import os

import certifi
import httpx


def create_async_client(*, timeout: int = 30, follow_redirects: bool = True, headers: dict[str, str] | None = None) -> httpx.AsyncClient:
    insecure = os.getenv("ONEFETCH_INSECURE_TLS", "").strip() in {"1", "true", "TRUE", "yes", "on"}
    verify = False if insecure else certifi.where()
    return httpx.AsyncClient(
        follow_redirects=follow_redirects,
        timeout=timeout,
        headers=headers,
        verify=verify,
    )
