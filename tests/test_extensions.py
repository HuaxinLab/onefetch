import json
import shutil
from pathlib import Path

from onefetch.extensions import (
    import_installed_adapters,
    install_extensions,
    load_installed_expanders,
    list_installed_extensions,
    list_remote_extensions,
    remove_extensions,
    update_extensions,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _prepare_repo(repo_dir: Path, *, version: str = "0.1.0") -> None:
    _write_json(
        repo_dir / "index.json",
        {
            "items": [
                {
                    "id": "demo",
                    "name": "Demo Site",
                    "version": version,
                    "description": "demo bundle",
                    "path": "sites/demo",
                }
            ]
        },
    )
    _write_json(
        repo_dir / "sites" / "demo" / "manifest.json",
        {
            "id": "demo",
            "name": "Demo Site",
            "version": version,
            "provides": ["adapter", "expander"],
            "domains": ["example.com"],
            "entry": {"adapter": "adapter.py:register", "expander": "expander.py:discover"},
            "min_core_version": "0.2.0",
        },
    )
    (repo_dir / "sites" / "demo" / "adapter.py").write_text(
        "def register():\n    return None\n",
        encoding="utf-8",
    )
    (repo_dir / "sites" / "demo" / "expander.py").write_text(
        "def discover(seed_url):\n    return [seed_url]\n",
        encoding="utf-8",
    )


def test_extension_install_list_update_remove(tmp_path, monkeypatch) -> None:
    repo_dir = tmp_path / "repo"
    _prepare_repo(repo_dir, version="0.1.0")

    def fake_clone(_repo_url: str, _ref: str, target_dir: Path) -> None:
        shutil.copytree(repo_dir, target_dir)

    monkeypatch.setattr("onefetch.extensions._clone_repo", fake_clone)

    remote_rows = list_remote_extensions("mock://repo", ref="main")
    assert len(remote_rows) == 1
    assert remote_rows[0]["id"] == "demo"

    installed = install_extensions(tmp_path, repo_url="mock://repo", ids=["demo"])
    assert installed == ["demo"]

    rows = list_installed_extensions(tmp_path)
    assert len(rows) == 1
    assert rows[0].id == "demo"
    assert rows[0].enabled is True

    loaded = import_installed_adapters(tmp_path)
    assert loaded == ["demo"]

    _prepare_repo(repo_dir, version="0.2.0")
    updated = update_extensions(tmp_path, repo_url="mock://repo", ids=["demo"])
    assert updated == ["demo"]

    rows_after_update = list_installed_extensions(tmp_path)
    assert rows_after_update[0].version == "0.2.0"

    removed = remove_extensions(tmp_path, ids=["demo"])
    assert removed == ["demo"]
    assert list_installed_extensions(tmp_path) == []


def test_extension_disabled_when_core_version_out_of_range(tmp_path) -> None:
    ext_dir = tmp_path / ".onefetch" / "extensions" / "demo"
    _write_json(
        ext_dir / "manifest.json",
        {
            "id": "demo",
            "name": "Demo Site",
            "version": "0.1.0",
            "provides": ["adapter"],
            "entry": {"adapter": "adapter.py:register"},
            "min_core_version": "99.0.0",
        },
    )
    (ext_dir / "adapter.py").write_text("def register():\n    return None\n", encoding="utf-8")

    rows = list_installed_extensions(tmp_path)
    assert len(rows) == 1
    assert rows[0].enabled is False

    loaded = import_installed_adapters(tmp_path)
    assert loaded == []


def test_load_installed_expanders_supports_function_entries(tmp_path) -> None:
    ext_dir = tmp_path / ".onefetch" / "extensions" / "demo"
    _write_json(
        ext_dir / "manifest.json",
        {
            "id": "demo",
            "name": "Demo Site",
            "version": "0.1.0",
            "domains": ["example.com"],
            "provides": ["expander"],
            "entry": {"expander": "expander.py:discover"},
            "min_core_version": "0.2.0",
        },
    )
    (ext_dir / "expander.py").write_text(
        "def discover(seed_url):\n    return [seed_url + '/a', seed_url + '/a', seed_url + '/b']\n",
        encoding="utf-8",
    )
    rows = load_installed_expanders(tmp_path)
    assert len(rows) == 1
    assert rows[0].expander_id == "discover"
    assert rows[0].supports("https://example.com") is True
    assert rows[0].discover("https://example.com", "<html></html>") == [
        "https://example.com/a",
        "https://example.com/a",
        "https://example.com/b",
    ]
