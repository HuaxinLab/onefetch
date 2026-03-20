from __future__ import annotations

import json

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
