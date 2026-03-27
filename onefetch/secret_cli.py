from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import sys
from urllib.parse import urlparse

from onefetch.cookie_formats import CookieFormatError, parse_cookie_input
from onefetch.secret_store import (
    SecretStoreError,
    cookie_key,
    list_secret_keys,
    move_secret_key,
    set_secret,
)
from onefetch.secret_web_import import serve_web_import


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="OneFetch secret helper")
    sub = parser.add_subparsers(dest="cmd", required=True)

    set_cookie = sub.add_parser("set-cookie", help="Save cookie for domain into encrypted store")
    set_cookie.add_argument("--domain", required=True)
    set_cookie.add_argument("--value", required=True)

    import_cookies = sub.add_parser("import-cookies", help="Import plaintext cookie files into encrypted store")
    import_cookies.add_argument(
        "--file",
        action="append",
        dest="files",
        default=[],
        help="Cookie file path (can pass multiple times)",
    )
    import_cookies.add_argument(
        "--domain",
        default="",
        help="Cookie domain override (required when filename is not <domain>_cookie.txt and only one --file is passed)",
    )
    import_env = sub.add_parser("import-env", help="Import cookie from an environment variable into encrypted store")
    import_env.add_argument("--name", required=True, help="Environment variable name that stores cookie value")
    import_env.add_argument("--domain", required=True, help="Target cookie domain, e.g. zhihu.com")
    web_import = sub.add_parser("serve-web-import", help="Start a local web page for cookie import")
    web_import.add_argument("--host", default="0.0.0.0", help="Bind host (default: 0.0.0.0)")
    web_import.add_argument("--port", type=int, default=8788, help="Bind port (default: 8788)")
    web_import.add_argument("--share-host", default="", help="Public/LAN host to show in share URL")
    web_import.add_argument("--code", default="", help="Pairing code (auto-generate when empty)")
    web_import.add_argument(
        "--one-time",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Shutdown service after first successful import (default: true)",
    )
    sub.add_parser("normalize-cookies", help="Normalize cookie keys to canonical domains")

    args = parser.parse_args(argv)

    try:
        if args.cmd == "set-cookie":
            set_secret(cookie_key(args.domain), args.value, secret_type="cookie")
            return 0
        if args.cmd == "import-cookies":
            imported = import_cookie_files(args.files, domain_override=args.domain)
            print(f"[secret-cli] imported {imported} cookies")
            return 0
        if args.cmd == "import-env":
            import_cookie_from_env(args.name, args.domain)
            return 0
        if args.cmd == "serve-web-import":
            imported = serve_web_import(
                args.host,
                args.port,
                code=args.code,
                one_time=bool(args.one_time),
                share_host=args.share_host,
            )
            print(f"[secret-cli] web import completed, imported={imported}")
            return 0
        if args.cmd == "normalize-cookies":
            changed = normalize_cookie_keys()
            print(f"[secret-cli] normalized {changed} cookie keys")
            return 0
    except (SecretStoreError, CookieFormatError) as exc:
        print(f"[secret-cli] {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("[secret-cli] cancelled by user")
        return 130

    return 1


def import_cookie_files(files: list[str], *, domain_override: str = "") -> int:
    targets = _resolve_cookie_files(files)
    if not targets:
        raise SecretStoreError("no cookie files found, pass --file <path>")
    if domain_override and len(targets) != 1:
        raise SecretStoreError("--domain can only be used with exactly one --file")

    imported = 0
    for path in targets:
        domain = (domain_override or _domain_from_filename(path.name)).strip().lower()
        if not domain:
            raise SecretStoreError(f"cannot infer domain from filename: {path.name}; pass --domain")
        raw = path.read_text(encoding="utf-8")
        if not raw.strip():
            continue
        parsed = parse_cookie_input(raw, domain_hint=domain)
        target_domain = parsed.inferred_domain or domain
        canonical = canonical_cookie_domain(target_domain)
        set_secret(cookie_key(canonical), parsed.header, secret_type="cookie")
        imported += 1
        print(f"[secret-cli] imported {path} -> key=cookie.{canonical}")
    return imported


def _resolve_cookie_files(files: list[str]) -> list[Path]:
    candidates = [Path(item).expanduser() for item in files if item.strip()]
    existing: list[Path] = []
    seen: set[str] = set()
    for path in candidates:
        resolved = path.resolve()
        key = str(resolved)
        if key in seen:
            continue
        seen.add(key)
        if resolved.is_file():
            existing.append(resolved)
    return existing


def import_cookie_from_env(env_name: str, domain: str) -> None:
    env_name = env_name.strip()
    raw = os.getenv(env_name, "").strip()
    if not env_name:
        raise SecretStoreError("env name is required")
    if not raw:
        raise SecretStoreError(f"env var not found or empty: {env_name}")
    parsed = parse_cookie_input(raw, domain_hint=domain)
    canonical = canonical_cookie_domain(parsed.inferred_domain or domain)
    set_secret(cookie_key(canonical), parsed.header, secret_type="cookie")
    print(f"[secret-cli] imported env:{env_name} -> key=cookie.{canonical}")


def normalize_cookie_keys() -> int:
    changed = 0
    for key in list_secret_keys(secret_type="cookie"):
        if not key.startswith("cookie."):
            continue
        domain = key[len("cookie.") :]
        canonical = canonical_cookie_domain(domain)
        new_key = f"cookie.{canonical}"
        result = move_secret_key(key, new_key)
        if result in {"moved", "dropped"}:
            changed += 1
            print(f"[secret-cli] {result}: {key} -> {new_key}")
    return changed


def canonical_cookie_domain(domain: str) -> str:
    raw = (domain or "").strip().lower()
    parsed = urlparse(raw if "://" in raw else f"//{raw}", scheme="http")
    normalized = (parsed.hostname or raw).strip().lower()
    if normalized.startswith("www."):
        normalized = normalized[4:]

    aliases = {
        "zhihu": "zhihu.com",
        "douyin": "douyin.com",
        "doubao": "doubao.com",
        "bilibili": "bilibili.com",
        "xiaohongshu": "xiaohongshu.com",
    }
    if normalized in aliases:
        return aliases[normalized]

    if "." not in normalized and re.fullmatch(r"[a-z0-9-]+", normalized):
        return f"{normalized}.com"
    return normalized


def _domain_from_filename(name: str) -> str:
    lowered = (name or "").strip().lower()
    if lowered.endswith("_cookie.txt"):
        return lowered[: -len("_cookie.txt")]
    return ""


if __name__ == "__main__":
    raise SystemExit(main())
