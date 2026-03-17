from __future__ import annotations

import argparse
import asyncio
import json
import re
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from onefetch.adapters import GenericHtmlAdapter, XiaohongshuAdapter
from onefetch.config import OneFetchConfig
from onefetch.pipeline import IngestionPipeline
from onefetch.router import Router
from onefetch.storage import StorageService

URL_RE = re.compile(r"https?://[^\s<>()\[\]{}\"']+")


def extract_urls(chunks: list[str], text: str = "") -> list[str]:
    seen: set[str] = set()
    urls: list[str] = []
    for chunk in [*chunks, text]:
        for match in URL_RE.findall(chunk or ""):
            cleaned = match.rstrip(".,);]}>")
            if cleaned not in seen:
                seen.add(cleaned)
                urls.append(cleaned)
    return urls


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="OneFetch CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    ingest = sub.add_parser("ingest", help="Ingest one or more URLs")
    ingest.add_argument("inputs", nargs="*", help="URL(s) or free text containing URL(s)")
    ingest.add_argument("--text", default="", help="Optional free text to scan for URLs")
    ingest.add_argument("--crawler", default="", help="Force adapter id")
    ingest.add_argument("--project-root", default=".", help="Project root (default: current directory)")
    ingest.add_argument("--json", action="store_true", help="Print JSON report")
    ingest.add_argument("--list-crawlers", action="store_true", help="List available adapters")
    ingest.add_argument("--report-json", default="", help="Optional output path for run summary JSON")
    ingest.add_argument("--report-md", default="", help="Optional output path for run summary Markdown")
    return parser


def _build_run_summary(report, *, duration_sec: float) -> dict:
    crawler_counter: Counter[str] = Counter()
    comment_source_counter: Counter[str] = Counter()
    risk_counter = 0
    comment_total = 0

    for result in report.results:
        crawler_counter[result.crawler_id] += 1
        if result.status != "stored" or not result.feed_path:
            continue
        feed_path = Path(result.feed_path)
        if not feed_path.exists():
            continue
        try:
            feed = json.loads(feed_path.read_text(encoding="utf-8"))
        except Exception:
            continue

        comment_total += len(feed.get("comments") or [])
        cf = (feed.get("metadata") or {}).get("comment_fetch") or {}
        source = cf.get("source") or "none"
        comment_source_counter[source] += 1
        api = cf.get("api") or {}
        if api.get("reason") in {"risk_controlled", "risk_cooldown"}:
            risk_counter += 1

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "duration_sec": round(duration_sec, 3),
        "requested_urls": len(report.requested_urls),
        "stored_count": report.stored_count,
        "duplicate_count": report.duplicate_count,
        "failed_count": report.failed_count,
        "success_rate": round((report.stored_count / len(report.requested_urls)) if report.requested_urls else 0.0, 4),
        "crawler_distribution": dict(crawler_counter),
        "comment_total": comment_total,
        "comment_source_distribution": dict(comment_source_counter),
        "risk_controlled_count": risk_counter,
    }


def _write_report_files(summary: dict, *, json_path: str, md_path: str) -> None:
    if json_path:
        path = Path(json_path).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    if md_path:
        path = Path(md_path).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            "# OneFetch Run Report",
            "",
            f"- Generated At: {summary['generated_at']}",
            f"- Duration: {summary['duration_sec']} sec",
            f"- Requested URLs: {summary['requested_urls']}",
            f"- Stored: {summary['stored_count']}",
            f"- Duplicates: {summary['duplicate_count']}",
            f"- Failed: {summary['failed_count']}",
            f"- Success Rate: {summary['success_rate']}",
            f"- Total Comments Captured: {summary['comment_total']}",
            f"- Risk Controlled Count: {summary['risk_controlled_count']}",
            "",
            "## Crawler Distribution",
            "",
        ]
        for key, value in summary.get("crawler_distribution", {}).items():
            lines.append(f"- {key}: {value}")
        lines.extend(["", "## Comment Source Distribution", ""])
        for key, value in summary.get("comment_source_distribution", {}).items():
            lines.append(f"- {key}: {value}")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")


async def run_ingest(args: argparse.Namespace) -> int:
    adapters = [XiaohongshuAdapter(), GenericHtmlAdapter()]
    router = Router(adapters)

    if args.list_crawlers:
        for adapter in router.list_adapters():
            print(adapter)
        return 0

    urls = extract_urls(args.inputs, args.text)
    if not urls:
        print("No URLs found. Pass URLs directly or via --text.")
        return 2

    config = OneFetchConfig.from_project_root(args.project_root)
    storage = StorageService(config.paths())
    pipeline = IngestionPipeline(router=router, storage=storage)

    start = time.monotonic()
    report = await pipeline.ingest_urls(urls, forced_adapter=args.crawler or None)
    duration = time.monotonic() - start

    summary = _build_run_summary(report, duration_sec=duration)
    _write_report_files(summary, json_path=args.report_json, md_path=args.report_md)

    if args.json:
        print(report.model_dump_json(indent=2))
        return 0

    print(
        f"Processed {len(report.requested_urls)} URL(s): "
        f"{report.stored_count} stored, {report.duplicate_count} duplicates, {report.failed_count} failed."
    )
    for result in report.results:
        print(f"[{result.status}] {result.source_url}")
        print(f"  crawler={result.crawler_id}")
        if result.error:
            print(f"  error={result.error}")
        if result.raw_path:
            print(f"  raw={result.raw_path}")
        if result.feed_path:
            print(f"  feed={result.feed_path}")
        if result.note_path:
            print(f"  note={result.note_path}")

    if args.report_json:
        print(f"  report_json={Path(args.report_json).expanduser()}")
    if args.report_md:
        print(f"  report_md={Path(args.report_md).expanduser()}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "ingest":
        return asyncio.run(run_ingest(args))

    print(json.dumps({"error": f"Unsupported command: {args.command}"}))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
