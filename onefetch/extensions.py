from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from onefetch import __version__ as CORE_VERSION

_IMPORTED_ENTRY_FILES: set[Path] = set()


@dataclass(slots=True)
class InstalledExtension:
    id: str
    name: str
    version: str
    path: Path
    provides: list[str]
    domains: list[str]
    enabled: bool
    reason: str


def extensions_root(project_root: str | Path) -> Path:
    return Path(project_root).expanduser().resolve() / ".onefetch" / "extensions"


def _parse_version(value: str) -> tuple[int, ...]:
    parts: list[int] = []
    for chunk in (value or "").split("."):
        digits = "".join(ch for ch in chunk if ch.isdigit())
        parts.append(int(digits or "0"))
    return tuple(parts)


def _version_in_range(core: str, min_ver: str = "", max_ver: str = "") -> bool:
    current = _parse_version(core)
    if min_ver and current < _parse_version(min_ver):
        return False
    if max_ver and current > _parse_version(max_ver):
        return False
    return True


def _manifest_path(site_dir: Path) -> Path:
    return site_dir / "manifest.json"


def _load_manifest(site_dir: Path) -> dict[str, Any] | None:
    manifest_file = _manifest_path(site_dir)
    if not manifest_file.is_file():
        return None
    try:
        payload = json.loads(manifest_file.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _entry_value(manifest: dict[str, Any], key: str) -> str:
    entry = manifest.get("entry")
    if isinstance(entry, dict):
        raw = entry.get(key, "")
        return raw if isinstance(raw, str) else ""
    if key == "adapter" and isinstance(entry, str):
        return entry
    return ""


def list_installed_extensions(project_root: str | Path) -> list[InstalledExtension]:
    root = extensions_root(project_root)
    if not root.is_dir():
        return []
    rows: list[InstalledExtension] = []
    for site_dir in sorted([p for p in root.iterdir() if p.is_dir()], key=lambda p: p.name):
        manifest = _load_manifest(site_dir)
        if manifest is None:
            rows.append(
                InstalledExtension(
                    id=site_dir.name,
                    name=site_dir.name,
                    version="",
                    path=site_dir,
                    provides=[],
                    domains=[],
                    enabled=False,
                    reason="manifest_missing_or_invalid",
                )
            )
            continue

        ext_id = str(manifest.get("id") or site_dir.name).strip() or site_dir.name
        name = str(manifest.get("name") or ext_id).strip() or ext_id
        version = str(manifest.get("version") or "").strip()
        provides_raw = manifest.get("provides") or []
        domains_raw = manifest.get("domains") or []
        provides = [x for x in provides_raw if isinstance(x, str)]
        domains = [x for x in domains_raw if isinstance(x, str)]
        min_ver = str(manifest.get("min_core_version") or "").strip()
        max_ver = str(manifest.get("max_core_version") or "").strip()
        in_range = _version_in_range(CORE_VERSION, min_ver=min_ver, max_ver=max_ver)
        rows.append(
            InstalledExtension(
                id=ext_id,
                name=name,
                version=version,
                path=site_dir,
                provides=provides,
                domains=domains,
                enabled=in_range,
                reason="" if in_range else f"core_version_out_of_range({min_ver or '-'}~{max_ver or '-'})",
            )
        )
    return rows


def _import_entry(site_dir: Path, entry: str) -> tuple[bool, str]:
    if not entry or ":" not in entry:
        return False, "invalid_entry"
    file_name, symbol = entry.split(":", 1)
    file_name = file_name.strip()
    symbol = symbol.strip()
    if not file_name or not symbol:
        return False, "invalid_entry"
    entry_file = (site_dir / file_name).resolve()
    if not entry_file.is_file():
        return False, "entry_file_missing"
    if entry_file in _IMPORTED_ENTRY_FILES:
        return True, "already_imported"

    module_name = f"onefetch_ext_{site_dir.name}_{entry_file.stem}"
    spec = importlib.util.spec_from_file_location(module_name, entry_file)
    if spec is None or spec.loader is None:
        return False, "import_spec_failed"
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        return False, f"import_error:{exc}"
    if not hasattr(module, symbol):
        return False, "entry_symbol_missing"
    _IMPORTED_ENTRY_FILES.add(entry_file)
    return True, "ok"


def import_installed_adapters(project_root: str | Path) -> list[str]:
    loaded: list[str] = []
    for item in list_installed_extensions(project_root):
        if not item.enabled:
            continue
        manifest = _load_manifest(item.path)
        if manifest is None:
            continue
        if "adapter" not in item.provides:
            continue
        entry = _entry_value(manifest, "adapter")
        ok, _reason = _import_entry(item.path, entry)
        if ok:
            loaded.append(item.id)
    return loaded


def _read_repo_index(repo_dir: Path) -> dict[str, Any]:
    payload = json.loads((repo_dir / "index.json").read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("index.json must be an object")
    return payload


def _index_items(index_payload: dict[str, Any]) -> list[dict[str, Any]]:
    items = index_payload.get("items")
    if not isinstance(items, list):
        raise RuntimeError("index.json missing 'items' list")
    valid: list[dict[str, Any]] = []
    for item in items:
        if isinstance(item, dict):
            valid.append(item)
    return valid


def list_remote_extensions(repo_url: str, ref: str = "main") -> list[dict[str, str]]:
    with tempfile.TemporaryDirectory(prefix="onefetch-ext-") as tmp:
        repo_dir = Path(tmp) / "repo"
        _clone_repo(repo_url, ref, repo_dir)
        payload = _read_repo_index(repo_dir)
        rows: list[dict[str, str]] = []
        for item in _index_items(payload):
            rows.append(
                {
                    "id": str(item.get("id") or "").strip(),
                    "name": str(item.get("name") or "").strip(),
                    "version": str(item.get("version") or "").strip(),
                    "description": str(item.get("description") or "").strip(),
                    "path": str(item.get("path") or "").strip(),
                }
            )
        return [row for row in rows if row["id"] and row["path"]]


def _clone_repo(repo_url: str, ref: str, target_dir: Path) -> None:
    cmd = [
        "git",
        "clone",
        "--depth",
        "1",
        "--branch",
        ref,
        repo_url,
        str(target_dir),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        stderr = (proc.stderr or "").strip()
        raise RuntimeError(f"git clone failed: {stderr or 'unknown error'}")


def install_extensions(
    project_root: str | Path,
    *,
    repo_url: str,
    ref: str = "main",
    ids: list[str] | None = None,
    install_all: bool = False,
) -> list[str]:
    selected_ids = [item.strip() for item in (ids or []) if item.strip()]
    if not install_all and not selected_ids:
        raise RuntimeError("No extension ids provided. Pass ids or use --all.")

    install_root = extensions_root(project_root)
    install_root.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="onefetch-ext-") as tmp:
        repo_dir = Path(tmp) / "repo"
        _clone_repo(repo_url, ref, repo_dir)
        payload = _read_repo_index(repo_dir)
        rows = _index_items(payload)
        by_id = {str(item.get("id") or "").strip(): item for item in rows}
        chosen = list(by_id.keys()) if install_all else selected_ids
        installed: list[str] = []
        for ext_id in chosen:
            meta = by_id.get(ext_id)
            if meta is None:
                raise RuntimeError(f"Extension not found in index: {ext_id}")
            rel_path = str(meta.get("path") or "").strip()
            if not rel_path:
                raise RuntimeError(f"Invalid index path for extension: {ext_id}")
            src_dir = (repo_dir / rel_path).resolve()
            if not src_dir.is_dir():
                raise RuntimeError(f"Extension source directory missing: {rel_path}")
            dst_dir = install_root / ext_id
            if dst_dir.exists():
                shutil.rmtree(dst_dir)
            shutil.copytree(src_dir, dst_dir)
            if not _manifest_path(dst_dir).is_file():
                raise RuntimeError(f"manifest.json missing after install: {ext_id}")
            installed.append(ext_id)
        return installed


def update_extensions(
    project_root: str | Path,
    *,
    repo_url: str,
    ref: str = "main",
    ids: list[str] | None = None,
    update_all: bool = False,
) -> list[str]:
    return install_extensions(
        project_root,
        repo_url=repo_url,
        ref=ref,
        ids=ids,
        install_all=update_all,
    )


def remove_extensions(project_root: str | Path, *, ids: list[str] | None = None, remove_all: bool = False) -> list[str]:
    install_root = extensions_root(project_root)
    if not install_root.is_dir():
        return []
    targets = [item.strip() for item in (ids or []) if item.strip()]
    if not remove_all and not targets:
        raise RuntimeError("No extension ids provided. Pass ids or use --all.")
    if remove_all:
        targets = [p.name for p in install_root.iterdir() if p.is_dir()]
    removed: list[str] = []
    for ext_id in targets:
        path = install_root / ext_id
        if not path.exists():
            continue
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink(missing_ok=True)
        removed.append(ext_id)
    return removed
