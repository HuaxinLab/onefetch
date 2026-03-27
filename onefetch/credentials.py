from __future__ import annotations

from urllib.parse import urlparse

from onefetch.secrets import load_cookie


def get_cookie(domain: str, *, parse_json_cookie: bool = False) -> str:
    domain = (domain or "").strip().lower()
    if not domain:
        return ""
    return load_cookie(domains=[domain], parse_json_cookie=parse_json_cookie)


def get_cookie_for_domains(domains: list[str], *, parse_json_cookie: bool = False) -> str:
    normalized = [(d or "").strip().lower() for d in domains if (d or "").strip()]
    if not normalized:
        return ""
    return load_cookie(domains=normalized, parse_json_cookie=parse_json_cookie)


def get_cookie_for_url(url: str, *, parse_json_cookie: bool = False) -> str:
    domain = (urlparse(url).hostname or "").lower()
    return get_cookie(domain, parse_json_cookie=parse_json_cookie)
