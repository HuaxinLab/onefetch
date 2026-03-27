from __future__ import annotations

import json
import os
import re

from onefetch.secret_store import SecretStoreError, cookie_key, get_secret


def load_cookie(
    *,
    domains: list[str],
    file_names: list[str] | None = None,
    parse_json_cookie: bool = False,
) -> str:
    """Resolve cookie with encrypted secret-store-first fallback to env."""
    for domain in _candidate_domains(domains):
        try:
            value = get_secret(cookie_key(domain))
        except SecretStoreError:
            return ""
        if value:
            if parse_json_cookie:
                parsed = _parse_cookie_json(value)
                if parsed:
                    return parsed
            return value

    for key in _candidate_env_keys(domains):
        value = os.getenv(key, "").strip()
        if value:
            if parse_json_cookie:
                parsed = _parse_cookie_json(value)
                if parsed:
                    return parsed
            return value
    return ""


def _candidate_domains(domains: list[str]) -> list[str]:
    candidates: list[str] = []
    for domain in domains:
        normalized = _normalize_domain(domain)
        if not normalized:
            continue
        candidates.append(normalized)
        if normalized.startswith("www."):
            candidates.append(normalized[4:])
    seen: set[str] = set()
    result: list[str] = []
    for item in candidates:
        if not item or item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def _candidate_env_keys(domains: list[str]) -> list[str]:
    keys: list[str] = []
    seen: set[str] = set()
    for domain in domains:
        normalized = _normalize_domain(domain)
        if not normalized:
            continue

        generated = [
            f"ONEFETCH_COOKIE_{_slug(normalized)}",
            f"ONEFETCH_{_site_slug(normalized)}_COOKIE",
        ]
        if normalized.startswith("www."):
            without_www = normalized[4:]
            generated.extend(
                [
                    f"ONEFETCH_COOKIE_{_slug(without_www)}",
                    f"ONEFETCH_{_site_slug(without_www)}_COOKIE",
                ]
            )
        for key in generated:
            if key in seen:
                continue
            seen.add(key)
            keys.append(key)
    return keys


def _normalize_domain(domain: str) -> str:
    return domain.strip().lower()


def _slug(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "_", value.upper())


def _site_slug(domain: str) -> str:
    parts = [p for p in domain.split(".") if p]
    if len(parts) >= 2:
        return _slug(parts[-2])
    if parts:
        return _slug(parts[0])
    return "COOKIE"


def _parse_cookie_json(raw: str) -> str:
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return ""

    if not isinstance(data, dict):
        return ""

    full = str(data.get("full_cookie_string", "") or "").strip()
    if full:
        return full

    cookies = data.get("cookies")
    if isinstance(cookies, dict):
        pairs = [f"{k}={v}" for k, v in cookies.items() if str(k).strip()]
        return "; ".join(pairs).strip()
    return ""
