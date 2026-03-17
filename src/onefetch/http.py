from __future__ import annotations

import os
import ssl

import certifi
import httpx
import truststore


def create_async_client(*, timeout: int = 30, follow_redirects: bool = True, headers: dict[str, str] | None = None) -> httpx.AsyncClient:
    insecure = os.getenv("ONEFETCH_INSECURE_TLS", "").strip() in {"1", "true", "TRUE", "yes", "on"}
    if insecure:
        verify: bool | str | ssl.SSLContext = False
    else:
        # Prefer macOS/system trust store to avoid CA mismatch issues in Python venvs.
        verify = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)

    if os.getenv("ONEFETCH_TLS_CERTIFI", "").strip() in {"1", "true", "TRUE", "yes", "on"}:
        verify = certifi.where()

    return httpx.AsyncClient(
        follow_redirects=follow_redirects,
        timeout=timeout,
        headers=headers,
        verify=verify,
    )
