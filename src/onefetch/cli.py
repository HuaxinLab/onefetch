from __future__ import annotations

import argparse
import asyncio
import json
import re

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
    return parser


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
    report = await pipeline.ingest_urls(urls, forced_adapter=args.crawler or None)

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
