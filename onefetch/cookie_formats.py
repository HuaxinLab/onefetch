from __future__ import annotations

from dataclasses import dataclass


class CookieFormatError(ValueError):
    pass


@dataclass
class ParsedCookie:
    header: str
    inferred_domain: str | None = None


def parse_cookie_input(raw: str, *, domain_hint: str = "") -> ParsedCookie:
    text = (raw or "").strip()
    if not text:
        raise CookieFormatError("cookie text is empty")

    parsed_netscape = _parse_netscape_cookie_file(text, domain_hint=domain_hint)
    if parsed_netscape is not None:
        return parsed_netscape

    header = _normalize_cookie_header(text)
    if not header:
        raise CookieFormatError("invalid cookie format")
    return ParsedCookie(header=header, inferred_domain=(domain_hint.strip().lower() or None))


def _normalize_cookie_header(text: str) -> str:
    s = text.strip().replace("\r", "")
    if s.lower().startswith("cookie:"):
        s = s.split(":", 1)[1].strip()
    s = " ".join(part for part in s.splitlines() if part.strip()).strip()
    if "=" not in s:
        return ""
    # Accept one cookie pair or header string with ';'.
    return s


def _parse_netscape_cookie_file(text: str, *, domain_hint: str = "") -> ParsedCookie | None:
    lines = [line.strip("\r") for line in text.splitlines()]
    entries: list[tuple[str, str, str]] = []

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 7:
            continue
        domain_raw = parts[0].strip().lstrip(".").lower()
        name = parts[5].strip()
        value = parts[6].strip()
        if not domain_raw or not name:
            continue
        entries.append((domain_raw, name, value))

    if not entries:
        return None

    target = domain_hint.strip().lower().lstrip(".")
    if target:
        selected = [item for item in entries if _domain_match(target, item[0])]
        if not selected:
            raise CookieFormatError(f"no cookies matched domain: {target}")
        header = "; ".join(f"{name}={value}" for _, name, value in selected)
        return ParsedCookie(header=header, inferred_domain=target)

    domains = sorted({item[0] for item in entries})
    if len(domains) != 1:
        raise CookieFormatError("multiple domains in cookies.txt; pass --domain")
    only_domain = domains[0]
    selected = [item for item in entries if item[0] == only_domain]
    header = "; ".join(f"{name}={value}" for _, name, value in selected)
    return ParsedCookie(header=header, inferred_domain=only_domain)


def _domain_match(target: str, cookie_domain: str) -> bool:
    if target == cookie_domain:
        return True
    return target.endswith("." + cookie_domain)
