from __future__ import annotations

import argparse
import asyncio
import json
import re
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from onefetch.adapters import GenericHtmlAdapter, WechatAdapter, XiaohongshuAdapter
from onefetch.config import OneFetchConfig
from onefetch.pipeline import IngestionPipeline
from onefetch.router import Router
from onefetch.storage import StorageService

URL_RE = re.compile(r"https?://[^\s<>()\[\]{}\"']+")
SENTENCE_SPLIT_RE = re.compile(r"(?<=[。！？!?\.])\s+")


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
    ingest.add_argument("--store", action="store_true", help="Persist artifacts to data/ and catalog")
    ingest.add_argument("--present", action="store_true", help="Print normalized presentation blocks for LLM summarization")
    return parser


def _build_run_summary(report, *, duration_sec: float) -> dict:
    crawler_counter: Counter[str] = Counter()
    comment_source_counter: Counter[str] = Counter()
    error_counter: Counter[str] = Counter()
    risk_counter = 0
    comment_total = 0

    for result in report.results:
        crawler_counter[result.crawler_id] += 1
        comment_total += result.comment_count
        comment_source_counter[result.comment_source or "none"] += 1
        if result.risk_controlled:
            risk_counter += 1
        if result.error_code:
            error_counter[result.error_code] += 1

    success_count = report.fetched_count + report.stored_count + report.duplicate_count
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "duration_sec": round(duration_sec, 3),
        "requested_urls": len(report.requested_urls),
        "fetched_count": report.fetched_count,
        "stored_count": report.stored_count,
        "duplicate_count": report.duplicate_count,
        "failed_count": report.failed_count,
        "success_rate": round((success_count / len(report.requested_urls)) if report.requested_urls else 0.0, 4),
        "crawler_distribution": dict(crawler_counter),
        "comment_total": comment_total,
        "comment_source_distribution": dict(comment_source_counter),
        "error_distribution": dict(error_counter),
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
            f"- Fetched (No Store): {summary['fetched_count']}",
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
        if summary.get("error_distribution"):
            lines.extend(["", "## Error Distribution", ""])
            for key, value in summary.get("error_distribution", {}).items():
                lines.append(f"- {key}: {value}")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _build_key_points(text: str, max_points: int = 3) -> list[str]:
    cleaned = " ".join((text or "").split())
    if not cleaned:
        return []
    candidates = [chunk.strip() for chunk in SENTENCE_SPLIT_RE.split(cleaned) if chunk.strip()]
    if not candidates:
        return [cleaned[:180]]
    return [point[:180] for point in candidates[:max_points]]


def _print_present(report) -> None:
    for idx, result in enumerate(report.results, start=1):
        print(f"### Item {idx}")
        print(f"- status: {result.status}")
        print(f"- crawler: {result.crawler_id}")
        print(f"- source_url: {result.source_url}")
        if result.title:
            print(f"- title: {result.title}")
        print(f"- comments: {result.comment_count} ({result.comment_source})")
        if result.error_code:
            print(f"- error_code: {result.error_code}")
            print(f"- error_type: {result.error_type}")
            print(f"- retryable: {result.retryable}")
        points = _build_key_points(result.body_excerpt)
        if points:
            print("- key_points:")
            for point in points:
                print(f"  - {point}")
        if result.body_preview:
            print(f"- summary: {result.body_preview}")
        print()


async def run_ingest(args: argparse.Namespace) -> int:
    adapters = [XiaohongshuAdapter(), WechatAdapter(), GenericHtmlAdapter()]
    router = Router(adapters)

    if args.list_crawlers:
        for adapter in router.list_adapters():
            print(adapter)
        return 0

    urls = extract_urls(args.inputs, args.text)
    if not urls:
        print("No URLs found. Pass URLs directly or via --text.")
        return 2

    storage = None
    if args.store:
        config = OneFetchConfig.from_project_root(args.project_root)
        storage = StorageService(config.paths())

    pipeline = IngestionPipeline(router=router, storage=storage)

    start = time.monotonic()
    report = await pipeline.ingest_urls(urls, forced_adapter=args.crawler or None, store=args.store)
    duration = time.monotonic() - start

    summary = _build_run_summary(report, duration_sec=duration)
    _write_report_files(summary, json_path=args.report_json, md_path=args.report_md)

    if args.json:
        print(report.model_dump_json(indent=2))
        return 0

    mode_text = "store" if args.store else "fetch-only"
    print(
        f"Processed {len(report.requested_urls)} URL(s) [{mode_text}]: "
        f"{report.fetched_count} fetched, {report.stored_count} stored, "
        f"{report.duplicate_count} duplicates, {report.failed_count} failed."
    )

    for result in report.results:
        print(f"[{result.status}] {result.source_url}")
        print(f"  crawler={result.crawler_id}")
        if result.error:
            print(f"  error={result.error}")
            if result.error_code:
                print(f"  error_code={result.error_code} type={result.error_type} retryable={result.retryable}")
        if result.title:
            print(f"  title={result.title}")
        print(f"  comments={result.comment_count} source={result.comment_source}")
        if result.body_preview:
            print(f"  preview={result.body_preview}")
        if result.raw_path:
            print(f"  raw={result.raw_path}")
        if result.feed_path:
            print(f"  feed={result.feed_path}")
        if result.note_path:
            print(f"  note={result.note_path}")

    if args.present:
        print("\n## Present")
        _print_present(report)

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
