from onefetch import cli
from onefetch.adapters.base import BaseAdapter
from onefetch.models import Capture, CrawlOutput, FeedEntry


class FakeAdapter(BaseAdapter):
    id = "fake"
    register = False
    calls = 0

    def supports(self, url: str) -> bool:
        return True

    async def crawl(self, url: str) -> CrawlOutput:
        type(self).calls += 1
        capture = Capture(
            source_url=url,
            canonical_url=url,
            final_url=url,
            status_code=200,
            body="<html><body>ok</body></html>",
        )
        feed = FeedEntry(
            source_url=url,
            canonical_url=url,
            crawler_id=self.id,
            title="ok",
            body="full content",
        )
        return CrawlOutput(capture=capture, feed=feed)


def test_ingest_present_mode_outputs_block(tmp_path, capsys) -> None:
    exit_code = cli.main(["ingest", "https://example.com", "--present", "--project-root", str(tmp_path)])
    out = capsys.readouterr().out

    assert exit_code == 0
    assert "## Present" in out
    assert "### Item 1" in out


def test_ingest_present_attaches_llm_outputs_from_file(tmp_path, capsys, monkeypatch) -> None:
    monkeypatch.setattr(cli, "create_default_adapters", lambda: [FakeAdapter()])
    llm_file = tmp_path / "llm_output.json"
    llm_file.write_text(
        '{"summary":"hello","key_points":["a","b"],"tags":["x","y"]}',
        encoding="utf-8",
    )

    exit_code = cli.main(
        [
            "ingest",
            "https://example.com",
            "--present",
            "--project-root",
            str(tmp_path),
            "--llm-output-file",
            str(llm_file),
        ]
    )
    out = capsys.readouterr().out

    assert exit_code == 0
    assert "- llm_summary: hello" in out
    assert "- llm_outputs_state: ok" in out
    assert "- llm_key_points:" in out
    assert "- llm_tags: x, y" in out
    assert "cache=" in out
    cache_dir = tmp_path / "reports" / "cache"
    assert cache_dir.exists()
    assert len(list(cache_dir.glob("*.json"))) >= 1


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


def test_ingest_present_reads_default_llm_output_file(tmp_path, capsys, monkeypatch) -> None:
    monkeypatch.setattr(cli, "create_default_adapters", lambda: [FakeAdapter()])
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / "llm_output.json").write_text(
        '{"summary":"default summary","key_points":["k1"],"tags":["t1"]}',
        encoding="utf-8",
    )

    exit_code = cli.main(
        [
            "ingest",
            "https://example.com",
            "--project-root",
            str(tmp_path),
            "--present",
        ]
    )
    out = capsys.readouterr().out

    assert exit_code == 0
    assert "- llm_summary: default summary" in out
    assert "- llm_outputs_state: ok" in out
    assert "- llm_tags: t1" in out


def test_ingest_present_marks_fallback_state_on_invalid_llm_output(tmp_path, capsys, monkeypatch) -> None:
    monkeypatch.setattr(cli, "create_default_adapters", lambda: [FakeAdapter()])
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / "llm_output.json").write_text(
        "summary: hello\nkey_points: [a,b]",
        encoding="utf-8",
    )

    exit_code = cli.main(
        [
            "ingest",
            "https://example.com",
            "--project-root",
            str(tmp_path),
            "--present",
        ]
    )
    out = capsys.readouterr().out

    assert exit_code == 0
    assert "- llm_outputs_state: fallback" in out
    assert "- llm_output_validation_error:" in out
