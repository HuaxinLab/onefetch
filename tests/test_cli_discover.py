from __future__ import annotations

import json
import importlib.util
from pathlib import Path

from onefetch import cli
from onefetch.adapters.base import BaseAdapter
from onefetch.models import FeedEntry


class FakeAdapter(BaseAdapter):
    id = "fake"
    register = False

    def supports(self, _url: str) -> bool:
        return True

    async def crawl(self, url: str) -> FeedEntry:
        return FeedEntry(
            source_url=url,
            canonical_url=url,
            crawler_id=self.id,
            title="seed",
            body="seed body",
            raw_body="<html><body>seed</body></html>",
        )


class FakeExpander:
    id = "fake_expander"

    def supports(self, url: str) -> bool:
        return "example.com" in url

    def discover(self, seed_url: str, _html_text: str):
        return {
            "discovered_urls": [seed_url + "/a", seed_url + "/a", seed_url + "/b"],
            "stats": {"source": "fake"},
            "warnings": ["w1"],
            "next_cursor": "nxt",
        }


def test_discover_returns_structured_report(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli, "create_default_adapters", lambda: [FakeAdapter()])
    monkeypatch.setattr(cli, "load_installed_expanders", lambda _project_root: [FakeExpander()])

    exit_code = cli.main(
        [
            "discover",
            "https://example.com/seed",
            "--project-root",
            str(tmp_path),
            "--json",
        ]
    )
    out = capsys.readouterr().out

    assert exit_code == 0
    payload = json.loads(out)
    assert payload["discovered_count"] == 2
    assert payload["failed_count"] == 0
    assert payload["results"][0]["expander_id"] == "fake_expander"
    assert payload["results"][0]["discovered_urls"] == [
        "https://example.com/seed/a",
        "https://example.com/seed/b",
    ]
    assert payload["results"][0]["next_cursor"] == "nxt"


def test_discover_ingest_chain_runs_ingest(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli, "create_default_adapters", lambda: [FakeAdapter()])
    monkeypatch.setattr(cli, "load_installed_expanders", lambda _project_root: [FakeExpander()])

    exit_code = cli.main(
        [
            "discover",
            "https://example.com/seed",
            "--project-root",
            str(tmp_path),
            "--ingest",
            "--ingest-present",
        ]
    )
    out = capsys.readouterr().out

    assert exit_code == 0
    assert "Processed 1 seed URL(s): 2 discovered, 0 failed." in out
    assert "Processed 2 URL(s) [fetch-only]" in out
    assert "https://example.com/seed/a" in out
    assert "https://example.com/seed/b" in out


def test_discover_writes_default_reports(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli, "create_default_adapters", lambda: [FakeAdapter()])
    monkeypatch.setattr(cli, "load_installed_expanders", lambda _project_root: [FakeExpander()])

    exit_code = cli.main(
        [
            "discover",
            "https://example.com/seed",
            "--project-root",
            str(tmp_path),
        ]
    )
    out = capsys.readouterr().out

    assert exit_code == 0
    assert "discover_report=" in out

    report_dir = tmp_path / "reports" / "discover"
    run_reports = list(report_dir.glob("seed-*.json"))
    assert run_reports, "expected discover latest-by-seed report"

    payload = json.loads(run_reports[0].read_text(encoding="utf-8"))
    assert payload["requested_urls"] == ["https://example.com/seed"]
    assert payload["discovered_count"] == 2


def test_discover_ingest_store_writes_collection_manifest(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli, "create_default_adapters", lambda: [FakeAdapter()])
    monkeypatch.setattr(cli, "load_installed_expanders", lambda _project_root: [FakeExpander()])

    exit_code = cli.main(
        [
            "discover",
            "https://example.com/seed",
            "--project-root",
            str(tmp_path),
            "--ingest",
            "--ingest-store",
            "--ingest-from-cache",
        ]
    )
    out = capsys.readouterr().out
    assert exit_code == 0
    assert "[discover] collection_manifest=" in out

    collections_root = tmp_path / "data" / "collections"
    run_dirs = [p for p in collections_root.iterdir() if p.is_dir()]
    assert run_dirs, "expected one collection run dir"
    manifest_path = run_dirs[0] / "manifest.json"
    assert manifest_path.exists()

    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert payload["seed_urls"] == ["https://example.com/seed"]
    assert "discovered_urls" in payload and len(payload["discovered_urls"]) == 2
    assert "items" in payload and len(payload["items"]) == 3
    assert payload["collection_key"].startswith("seed-")
    assert payload["items"][0]["source_url"] == "https://example.com/seed"
    for item in payload["items"]:
        assert item["feed_path"].startswith("items/")


def test_geekbang_intro_img_placeholders_are_renumbered() -> None:
    adapter_file = Path(__file__).resolve().parents[1] / ".onefetch" / "extensions" / "geekbang" / "adapter.py"
    spec = importlib.util.spec_from_file_location("test_geekbang_adapter", adapter_file)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    text = "课程知识地图如下：\n[IMG:1]\n[IMG:1]"
    out = module.GeekbangAdapter._renumber_img_placeholders(text)
    assert out == "课程知识地图如下：\n[IMG:1]\n[IMG:2]"


def test_discover_request_key_is_order_insensitive() -> None:
    key1 = cli._discover_request_key(["https://a.com/1", "https://b.com/2"])
    key2 = cli._discover_request_key(["https://b.com/2", "https://a.com/1"])
    assert key1 == key2
