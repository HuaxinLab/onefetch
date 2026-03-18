from __future__ import annotations

import gzip
from urllib.request import Request, urlopen

DEFAULT_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/132.0.0.0 Safari/537.36"
)


def fetch_text(url: str, *, timeout: float = 20.0, user_agent: str = DEFAULT_UA) -> str:
    req = Request(
        url,
        headers={
            "User-Agent": user_agent,
            "Accept": "*/*",
            "Accept-Encoding": "gzip",
        },
    )
    with urlopen(req, timeout=timeout) as resp:
        data = resp.read()
    if len(data) >= 2 and data[:2] == b"\x1f\x8b":
        data = gzip.decompress(data)
    return data.decode("utf-8", errors="replace")
