import json

from onefetch import cli
from onefetch.adapters.base import BaseAdapter
from onefetch.models import FeedEntry


class FakeAdapter(BaseAdapter):
    id = "fake"
    register = False
    calls = 0

    def supports(self, url: str) -> bool:
        return True

    async def crawl(self, url: str) -> FeedEntry:
        type(self).calls += 1
        return FeedEntry(
            source_url=url,
            canonical_url=url,
            crawler_id=self.id,
            title="ok",
            body="full content",
        )


def test_ingest_present_mode_outputs_block(tmp_path, capsys) -> None:
    exit_code = cli.main(["ingest", "https://example.com", "--present", "--project-root", str(tmp_path)])
    out = capsys.readouterr().out

    assert exit_code == 0
    assert "## Present" in out
    assert "### Item 1" in out


def test_cache_backfill_attaches_llm_outputs(tmp_path, capsys, monkeypatch) -> None:
    FakeAdapter.calls = 0
    monkeypatch.setattr(cli, "create_default_adapters", lambda: [FakeAdapter()])

    # Step 1: fetch and cache
    cli.main(["ingest", "https://example.com", "--project-root", str(tmp_path)])
    capsys.readouterr()

    # Step 2: backfill LLM outputs
    backfill_exit = cli.main([
        "cache-backfill", "https://example.com",
        "--project-root", str(tmp_path),
        "--json-data", '{"summary":"hello","key_points":["a","b"],"tags":["x","y"]}',
    ])
    assert backfill_exit == 0

    # Step 3: read from cache, verify LLM outputs attached
    exit_code = cli.main([
        "ingest", "https://example.com",
        "--project-root", str(tmp_path),
        "--from-cache", "--present",
    ])
    out = capsys.readouterr().out

    assert exit_code == 0
    assert FakeAdapter.calls == 1  # no second crawl
    assert "- llm_summary: hello" in out
    assert "- llm_outputs_state: ok" in out
    assert "- llm_key_points:" in out
    assert "- llm_tags: x, y" in out


def test_cache_backfill_marks_fallback_on_invalid_json(tmp_path, capsys, monkeypatch) -> None:
    FakeAdapter.calls = 0
    monkeypatch.setattr(cli, "create_default_adapters", lambda: [FakeAdapter()])

    cli.main(["ingest", "https://example.com", "--project-root", str(tmp_path)])
    capsys.readouterr()

    backfill_exit = cli.main([
        "cache-backfill", "https://example.com",
        "--project-root", str(tmp_path),
        "--json-data", "summary: hello\nkey_points: [a,b]",
    ])
    assert backfill_exit == 0

    exit_code = cli.main([
        "ingest", "https://example.com",
        "--project-root", str(tmp_path),
        "--from-cache", "--present",
    ])
    out = capsys.readouterr().out

    assert exit_code == 0
    assert "- llm_outputs_state: fallback" in out
    assert "- llm_output_validation_error:" in out


def test_cache_backfill_fails_for_unknown_url(tmp_path, capsys) -> None:
    exit_code = cli.main([
        "cache-backfill", "https://unknown.example.com",
        "--project-root", str(tmp_path),
        "--json-data", '{"summary":"test"}',
    ])
    assert exit_code == 1
    out = capsys.readouterr().out
    assert "no cache entry found" in out


def test_ingest_from_cache_skips_second_crawl(tmp_path, monkeypatch) -> None:
    FakeAdapter.calls = 0
    monkeypatch.setattr(cli, "create_default_adapters", lambda: [FakeAdapter()])

    first_exit = cli.main(
        [
            "ingest",
            "https://example.com",
            "--project-root",
            str(tmp_path),
        ]
    )
    assert first_exit == 0
    assert FakeAdapter.calls == 1

    second_exit = cli.main(
        [
            "ingest",
            "https://example.com",
            "--project-root",
            str(tmp_path),
            "--from-cache",
        ]
    )
    assert second_exit == 0
    assert FakeAdapter.calls == 1


def test_ingest_refresh_bypasses_cache_even_with_from_cache(tmp_path, monkeypatch) -> None:
    FakeAdapter.calls = 0
    monkeypatch.setattr(cli, "create_default_adapters", lambda: [FakeAdapter()])

    first_exit = cli.main(
        [
            "ingest",
            "https://example.com",
            "--project-root",
            str(tmp_path),
        ]
    )
    assert first_exit == 0
    assert FakeAdapter.calls == 1

    second_exit = cli.main(
        [
            "ingest",
            "https://example.com",
            "--project-root",
            str(tmp_path),
            "--from-cache",
            "--refresh",
        ]
    )
    assert second_exit == 0
    assert FakeAdapter.calls == 2


def test_store_flow_regenerates_llm_outputs_from_full_body(tmp_path, capsys, monkeypatch) -> None:
    FakeAdapter.calls = 0
    monkeypatch.setattr(cli, "create_default_adapters", lambda: [FakeAdapter()])

    # Fetch first (no LLM outputs — state will be "missing")
    first_exit = cli.main(
        ["ingest", "https://example.com", "--project-root", str(tmp_path), "--present"]
    )
    assert first_exit == 0
    assert FakeAdapter.calls == 1
    capsys.readouterr()

    # Store from cache — should regenerate LLM from rules since state is missing
    second_exit = cli.main(
        ["ingest", "https://example.com", "--project-root", str(tmp_path),
         "--from-cache", "--store", "--present"]
    )
    out = capsys.readouterr().out
    assert second_exit == 0
    assert FakeAdapter.calls == 1
    assert "- llm_outputs_state: ok" in out
    assert "正文内容已正常保存" in out

    cache_files = sorted((tmp_path / "reports" / "cache").glob("*.json"))
    assert cache_files
    payload = json.loads(cache_files[-1].read_text(encoding="utf-8"))
    assert payload["llm_outputs_state"] == "ok"
    assert payload["llm_outputs"]["extras"]["regenerated_from_full_body"] is True


def test_store_flow_prefers_llm_regeneration_when_command_available(tmp_path, capsys, monkeypatch) -> None:
    FakeAdapter.calls = 0
    monkeypatch.setattr(cli, "create_default_adapters", lambda: [FakeAdapter()])

    async def fake_llm_regen_command(payload_json: str) -> tuple[int, str, str]:
        assert "full content" in payload_json
        return 0, '{"summary":"regen summary","key_points":["r1","r2"],"tags":["regen"]}', ""

    monkeypatch.setenv("ONEFETCH_LLM_REGEN_CMD", "mock-llm-cmd")
    monkeypatch.setattr(cli, "_run_llm_regen_command", fake_llm_regen_command)

    exit_code = cli.main(
        ["ingest", "https://example.com", "--project-root", str(tmp_path),
         "--store", "--present"]
    )
    out = capsys.readouterr().out

    assert exit_code == 0
    assert "- llm_summary: regen summary" in out
    assert "- llm_outputs_state: ok" in out
    assert "- llm_tags: regen" in out
