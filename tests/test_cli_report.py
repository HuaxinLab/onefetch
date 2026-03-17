import json
from pathlib import Path

from onefetch import cli


def test_ingest_generates_report_files(tmp_path: Path) -> None:
    project_root = tmp_path / "proj"
    report_json = tmp_path / "reports" / "run.json"
    report_md = tmp_path / "reports" / "run.md"

    exit_code = cli.main(
        [
            "ingest",
            "https://example.com",
            "--project-root",
            str(project_root),
            "--report-json",
            str(report_json),
            "--report-md",
            str(report_md),
        ]
    )

    assert exit_code == 0
    assert report_json.exists()
    assert report_md.exists()
    payload = json.loads(report_json.read_text(encoding="utf-8"))
    assert payload["fetched_count"] >= 1
    assert "OneFetch Run Report" in report_md.read_text(encoding="utf-8")


def test_ingest_store_mode(tmp_path: Path) -> None:
    project_root = tmp_path / "proj"

    exit_code = cli.main(
        [
            "ingest",
            "https://example.com",
            "--project-root",
            str(project_root),
            "--store",
        ]
    )

    assert exit_code == 0
    assert (project_root / "data" / "catalog.jsonl").exists()
