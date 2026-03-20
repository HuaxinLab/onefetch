from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import shlex
import time
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from onefetch.adapters import create_default_adapters
from onefetch.cache import TempCacheService
from onefetch.config import OneFetchConfig
from onefetch.extensions import (
    install_extensions,
    load_installed_expanders,
    list_installed_extensions,
    list_remote_extensions,
    remove_extensions,
    update_extensions,
)
from onefetch.llm_outputs import parse_and_validate_llm_outputs
from onefetch.models import BatchDiscoverReport, BatchIngestReport, DiscoverResult, IngestResult
from onefetch.pipeline import IngestionPipeline
from onefetch.plugins import PluginTask, create_default_registry
from onefetch.plugins.presets import list_presets, load_preset
from onefetch.router import Router
from onefetch.storage import StorageService

URL_RE = re.compile(r"https?://[^\s<>()\[\]{}\"']+")
SENTENCE_SPLIT_RE = re.compile(r"(?<=[。！？!?\.])\s+")
IMG_PLACEHOLDER_RE = re.compile(r"\[IMG:\d+\]\n?")


def strip_image_placeholders(text: str) -> str:
    """Remove [IMG:N] markers from text."""
    return IMG_PLACEHOLDER_RE.sub("", text).strip()


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


def _discover_run_id(seed_urls: list[str]) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    seed_blob = "|".join(seed_urls)
    digest = hashlib.sha1(seed_blob.encode("utf-8")).hexdigest()[:8]
    return f"{stamp}-{digest}"


def _discover_seed_key(seed_url: str) -> str:
    return hashlib.sha1((seed_url or "").encode("utf-8")).hexdigest()[:16]


def _discover_request_key(seed_urls: list[str]) -> str:
    blob = "|".join(seed_urls)
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()[:16]


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
    ingest.add_argument(
        "--cache-temp",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Write temporary cache files under reports/cache (default: enabled)",
    )
    ingest.add_argument(
        "--cache-max-items",
        type=int,
        default=200,
        help="Maximum number of temp cache files to keep (default: 200)",
    )
    ingest.add_argument(
        "--from-cache",
        action="store_true",
        help="Reuse temporary cache results first; crawl only cache misses",
    )
    ingest.add_argument(
        "--refresh",
        action="store_true",
        help="Force live crawl and bypass cache read for this run",
    )
    ingest.add_argument("--store", action="store_true", help="Persist artifacts to data/ and catalog")
    ingest.add_argument("--present", action="store_true", help="Print normalized presentation blocks for LLM summarization")
    ingest.add_argument("--raw", action="store_true", help="Save raw HTML to reports/raw/ for further processing")
    ingest.add_argument("--with-images", action="store_true", help="Download images when using --store")

    backfill = sub.add_parser("cache-backfill", help="Backfill LLM outputs into an existing cache entry")
    backfill.add_argument("url", help="The URL whose cache entry to update")
    backfill.add_argument("--json-data", default="", help='LLM outputs as JSON string: {"summary":"...","key_points":["..."],"tags":["..."]}')
    backfill.add_argument("--project-root", default=".", help="Project root (default: current directory)")

    images = sub.add_parser("images", help="Extract image URLs from a page")
    images.add_argument("inputs", nargs="*", help="URL(s)")
    images.add_argument("--text", default="", help="Optional free text to scan for URLs")
    images.add_argument("--crawler", default="", help="Force adapter id")
    images.add_argument("--proxy", action="store_true", help="Output wsrv.nl proxied URLs")
    images.add_argument("--download", default="", help="Download images to specified directory")
    images.add_argument("--project-root", default=".", help="Project root (default: current directory)")

    plugin = sub.add_parser("plugin", help="Run independent plugins")
    plugin_sub = plugin.add_subparsers(dest="plugin_command", required=True)

    plugin_list = plugin_sub.add_parser("list", help="List available plugins")
    plugin_list.add_argument("--json", action="store_true", help="Print JSON output")
    plugin_list.add_argument("--with-presets", action="store_true", help="Include preset names per plugin")

    plugin_run = plugin_sub.add_parser("run", help="Run one plugin")
    plugin_run.add_argument("plugin_id", help="Plugin id to execute")
    plugin_run.add_argument("--url", default="", help="Target URL")
    plugin_run.add_argument(
        "--opt",
        action="append",
        default=[],
        help="Plugin option as key=value; can be repeated",
    )
    plugin_run.add_argument("--json", action="store_true", help="Print JSON output")

    plugin_presets = plugin_sub.add_parser("presets", help="List available presets")
    plugin_presets.add_argument("--json", action="store_true", help="Print JSON output")
    plugin_presets.add_argument("--plugin-id", default="", help="Optional plugin id filter")

    plugin_doctor = plugin_sub.add_parser("doctor", help="Diagnose plugin execution and surface actionable hints")
    plugin_doctor.add_argument("plugin_id", help="Plugin id to diagnose")
    plugin_doctor.add_argument("--url", default="", help="Target URL")
    plugin_doctor.add_argument(
        "--opt",
        action="append",
        default=[],
        help="Plugin option as key=value; can be repeated",
    )
    plugin_doctor.add_argument("--json", action="store_true", help="Print JSON output")

    ext = sub.add_parser("ext", help="Manage optional site extensions (adapter/expander bundles)")
    ext_sub = ext.add_subparsers(dest="ext_command", required=True)

    ext_list = ext_sub.add_parser("list", help="List installed extensions")
    ext_list.add_argument("--json", action="store_true", help="Print JSON output")
    ext_list.add_argument("--remote", action="store_true", help="List available extensions from remote index")
    ext_list.add_argument("--repo", default=os.getenv("ONEFETCH_EXT_REPO", ""), help="Extension repository git URL")
    ext_list.add_argument("--ref", default=os.getenv("ONEFETCH_EXT_REF", "main"), help="Git ref for extension repository")
    ext_list.add_argument("--project-root", default=".", help="Project root (default: current directory)")

    ext_install = ext_sub.add_parser("install", help="Install extension(s)")
    ext_install.add_argument("ids", nargs="*", help="Extension IDs")
    ext_install.add_argument("--all", action="store_true", help="Install all extensions from remote index")
    ext_install.add_argument("--repo", default=os.getenv("ONEFETCH_EXT_REPO", ""), help="Extension repository git URL")
    ext_install.add_argument("--ref", default=os.getenv("ONEFETCH_EXT_REF", "main"), help="Git ref for extension repository")
    ext_install.add_argument("--project-root", default=".", help="Project root (default: current directory)")

    ext_remove = ext_sub.add_parser("remove", help="Remove installed extension(s)")
    ext_remove.add_argument("ids", nargs="*", help="Installed extension IDs")
    ext_remove.add_argument("--all", action="store_true", help="Remove all installed extensions")
    ext_remove.add_argument("--project-root", default=".", help="Project root (default: current directory)")

    ext_update = ext_sub.add_parser("update", help="Update installed extension(s) from remote index")
    ext_update.add_argument("ids", nargs="*", help="Extension IDs")
    ext_update.add_argument("--all", action="store_true", help="Update all extensions from remote index")
    ext_update.add_argument("--repo", default=os.getenv("ONEFETCH_EXT_REPO", ""), help="Extension repository git URL")
    ext_update.add_argument("--ref", default=os.getenv("ONEFETCH_EXT_REF", "main"), help="Git ref for extension repository")
    ext_update.add_argument("--project-root", default=".", help="Project root (default: current directory)")

    discover = sub.add_parser("discover", help="Discover URLs from seed pages using installed expanders")
    discover.add_argument("inputs", nargs="*", help="Seed URL(s) or free text containing URL(s)")
    discover.add_argument("--text", default="", help="Optional free text to scan for URLs")
    discover.add_argument("--project-root", default=".", help="Project root (default: current directory)")
    discover.add_argument("--crawler", default="", help="Force adapter id for seed-page fetch")
    discover.add_argument("--expander", default="", help="Force expander id")
    discover.add_argument("--json", action="store_true", help="Print JSON report")
    discover.add_argument("--present", action="store_true", help="Print discovered URL blocks")
    discover.add_argument("--ingest", action="store_true", help="Run ingest on discovered URLs in this command")
    discover.add_argument("--ingest-crawler", default="", help="Optional forced crawler id for follow-up ingest")
    discover.add_argument("--ingest-store", action="store_true", help="Persist artifacts in follow-up ingest")
    discover.add_argument("--ingest-present", action="store_true", help="Print normalized blocks in follow-up ingest")
    discover.add_argument("--ingest-from-cache", action="store_true", help="Prefer cache in follow-up ingest")
    discover.add_argument("--ingest-refresh", action="store_true", help="Force live crawl in follow-up ingest")
    discover.add_argument("--ingest-with-images", action="store_true", help="Keep/download images in follow-up ingest")
    discover.add_argument(
        "--ingest-cache-temp",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Enable temp cache in follow-up ingest",
    )
    discover.add_argument("--ingest-cache-max-items", type=int, default=200, help="Temp cache max entries in follow-up ingest")
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



def _llm_outputs_state(parsed_output) -> str:
    if parsed_output.extras.get("validation_error"):
        return "fallback"
    if parsed_output.summary or parsed_output.key_points or parsed_output.tags:
        return "ok"
    return "missing"


async def _run_llm_regen_command(payload_json: str) -> tuple[int, str, str]:
    cmd = os.getenv("ONEFETCH_LLM_REGEN_CMD", "").strip()
    if not cmd:
        return 127, "", "ONEFETCH_LLM_REGEN_CMD is not configured"
    argv = shlex.split(cmd)
    if not argv:
        return 127, "", "ONEFETCH_LLM_REGEN_CMD is empty"
    proc = await asyncio.create_subprocess_exec(
        *argv,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate(payload_json.encode("utf-8"))
    return proc.returncode, stdout.decode("utf-8", errors="replace"), stderr.decode("utf-8", errors="replace")


async def _try_llm_regenerate(result) -> bool:
    payload = {
        "source_url": result.source_url,
        "canonical_url": result.canonical_url,
        "crawler_id": result.crawler_id,
        "title": result.title,
        "body_full": result.body_full,
    }
    code, stdout, stderr = await _run_llm_regen_command(json.dumps(payload, ensure_ascii=False))
    if code != 0 or not (stdout or "").strip():
        if stderr.strip():
            result.llm_outputs.extras = {**result.llm_outputs.extras, "llm_regen_error": stderr.strip()[:400]}
        return False
    parsed = parse_and_validate_llm_outputs(stdout)
    state = _llm_outputs_state(parsed)
    if state != "ok":
        result.llm_outputs.extras = {
            **result.llm_outputs.extras,
            "llm_regen_error": "llm_regen_output_invalid",
            "llm_regen_raw_output": stdout[:400],
        }
        return False
    result.llm_outputs = parsed
    result.llm_outputs.extras = {**result.llm_outputs.extras, "regenerated_by": "llm_command"}
    result.llm_outputs_state = "ok"
    return True


def _regenerate_llm_outputs_from_rules(result) -> None:
    body = strip_image_placeholders(result.body_full or result.body_preview or "")
    if not body:
        return
    summary = _preview_text(body, limit=360)
    key_points = _build_key_points(body, max_points=5)
    tags: list[str] = []
    crawler_hint = (result.crawler_id or "").strip()
    if crawler_hint:
        tags.append(crawler_hint)
    title_hint = (result.title or "").strip()
    if title_hint:
        tags.append("article")
    dedup_tags: list[str] = []
    seen: set[str] = set()
    for tag in tags:
        if tag in seen:
            continue
        seen.add(tag)
        dedup_tags.append(tag)
    result.llm_outputs.summary = summary
    result.llm_outputs.key_points = key_points
    result.llm_outputs.tags = dedup_tags
    previous_extras = {
        key: value
        for key, value in result.llm_outputs.extras.items()
        if key not in {"validation_error", "raw_output", "repaired_from_non_strict_json"}
    }
    result.llm_outputs.extras = {
        **previous_extras,
        "regenerated_from_full_body": True,
        "regenerated_by": "heuristic_rules",
        "previous_state": result.llm_outputs_state,
        "user_notice": (
            "正文内容已正常保存；但本次摘要/要点/标签是自动整理结果，可能不够准确。"
            "你可以稍后让我重新整理这部分。"
        ),
    }
    result.llm_outputs_state = "ok"


async def _ensure_store_ready_llm_outputs(report) -> None:
    for result in report.results:
        if result.status == "failed":
            continue
        if result.llm_outputs_state in {"fallback", "missing"}:
            llm_regenerated = await _try_llm_regenerate(result)
            if not llm_regenerated:
                _regenerate_llm_outputs_from_rules(result)


def _preview_text(text: str, limit: int = 280) -> str:
    normalized = " ".join((text or "").split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 1] + "…"


def _build_key_points(text: str, max_points: int = 3) -> list[str]:
    cleaned = " ".join((text or "").split())
    if not cleaned:
        return []
    candidates = [chunk.strip() for chunk in SENTENCE_SPLIT_RE.split(cleaned) if chunk.strip()]
    if not candidates:
        return [cleaned[:180]]
    return [point[:180] for point in candidates[:max_points]]


def _build_adapters(project_root: str) -> list:
    try:
        return create_default_adapters(project_root=project_root)
    except TypeError:
        # Backward-compatible for tests/mocks that monkeypatch no-arg callables.
        return create_default_adapters()


def _print_present(report, *, with_images: bool = False) -> None:
    for idx, result in enumerate(report.results, start=1):
        print(f"### Item {idx}")
        print(f"- status: {result.status}")
        print(f"- crawler: {result.crawler_id}")
        print(f"- source_url: {result.source_url}")
        if result.title:
            print(f"- title: {result.title}")
        if result.author:
            print(f"- author: {result.author}")
        if result.published_at:
            print(f"- published_at: {result.published_at}")
        print(f"- comments: {result.comment_count} ({result.comment_source})")
        if result.error_code:
            print(f"- error_code: {result.error_code}")
            print(f"- error_type: {result.error_type}")
            print(f"- retryable: {result.retryable}")
        if result.action_hint:
            print(f"- action_hint: {result.action_hint}")
        points = _build_key_points(strip_image_placeholders(result.body_full))
        if points:
            print("- key_points:")
            for point in points:
                print(f"  - {point}")
        if result.body_preview:
            print(f"- summary: {result.body_preview}")
        if result.body_full:
            body_output = result.body_full if with_images else strip_image_placeholders(result.body_full)
            print("- full_body:")
            print("```text")
            print(body_output)
            print("```")
        if with_images and result.images:
            import urllib.parse
            print("- images:")
            for i, img_url in enumerate(result.images, 1):
                proxy_url = f"https://wsrv.nl/?url={urllib.parse.quote(img_url, safe='')}"
                print(f"  - [IMG:{i}]: {img_url}")
                print(f"    proxy: {proxy_url}")
        if result.llm_outputs.summary:
            print(f"- llm_summary: {result.llm_outputs.summary}")
        print(f"- llm_outputs_state: {result.llm_outputs_state}")
        if result.llm_outputs.key_points:
            print("- llm_key_points:")
            for point in result.llm_outputs.key_points:
                print(f"  - {point}")
        if result.llm_outputs.tags:
            print(f"- llm_tags: {', '.join(result.llm_outputs.tags)}")
        if result.llm_outputs.extras.get("validation_error"):
            print(f"- llm_output_validation_error: {result.llm_outputs.extras['validation_error']}")
        if result.llm_outputs.extras.get("regenerated_by") == "heuristic_rules":
            print(f"- notice: {result.llm_outputs.extras.get('user_notice')}")
        if result.cache_path:
            print(f"- cache_path: {result.cache_path}")
        print()


async def _run_raw_fetch(
    urls: list[str],
    router: Router,
    paths,
    forced_adapter: str | None = None,
) -> int:
    """Fetch URLs and save raw HTML to reports/raw/."""
    raw_dir = paths.reports_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    for url in urls:
        try:
            adapter = router.route(url, forced_adapter=forced_adapter)
            feed = await adapter.crawl(url)
            if not feed.raw_body:
                print(f"[raw] no raw body for: {url}")
                continue
            stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
            safe_id = feed.content_hash[:8] if feed.content_hash else "unknown"
            filename = f"{stamp}-{safe_id}.html"
            path = raw_dir / filename
            path.write_text(feed.raw_body, encoding="utf-8")
            print(f"[raw] {adapter.id} | {feed.title or url}")
            print(f"[raw] saved: {path} ({len(feed.raw_body)} bytes)")
        except Exception as exc:
            print(f"[raw] failed: {url} — {exc}")
    return 0


async def run_ingest(args: argparse.Namespace) -> int:
    urls = extract_urls(args.inputs, args.text)
    if not urls:
        print("No URLs found. Pass URLs directly or via --text.")
        return 2
    return await _run_ingest_urls(args, urls)


async def _run_ingest_urls(args: argparse.Namespace, urls: list[str]) -> int:
    adapters = _build_adapters(args.project_root)
    router = Router(adapters)

    if getattr(args, "list_crawlers", False):
        for adapter in router.list_adapters():
            print(adapter)
        return 0

    config = OneFetchConfig.from_project_root(args.project_root)
    paths = config.paths()

    if args.raw:
        return await _run_raw_fetch(urls, router, paths, forced_adapter=args.crawler or None)

    cache_service = TempCacheService(paths, max_entries=args.cache_max_items) if args.cache_temp else None
    pipeline = IngestionPipeline(router=router)

    start = time.monotonic()
    report = BatchIngestReport(requested_urls=urls)
    pending_urls = urls
    cached_results_by_url: dict[str, IngestResult] = {}
    cache_hit_states: dict[str, str] = {}
    if args.from_cache and not args.refresh and cache_service is not None:
        pending_urls = []
        for source_url in urls:
            cached = cache_service.load_latest_result(source_url)
            if cached is None:
                pending_urls.append(source_url)
                continue
            cached.cache_path = "<cache-hit>"
            cached_results_by_url[source_url] = cached
            cache_hit_states[source_url] = cached.llm_outputs_state

    if pending_urls:
        fresh_report = await pipeline.ingest_urls(pending_urls, forced_adapter=args.crawler or None)
        for result in fresh_report.results:
            cached_results_by_url[result.source_url] = result

    report.results = [cached_results_by_url[url] for url in urls if url in cached_results_by_url]
    report.fetched_count, report.stored_count, report.duplicate_count, report.failed_count = _count_result_statuses(report)
    duration = time.monotonic() - start

    if args.store:
        await _ensure_store_ready_llm_outputs(report)

    # Update cache: touch if unchanged, save if modified
    if cache_service is not None:
        for result in report.results:
            if result.status == "failed":
                continue
            original_state = cache_hit_states.get(result.source_url)
            if original_state == "ok" and result.llm_outputs_state == "ok":
                cache_service.touch_result(result.canonical_url, result.content_hash)
                latest = cache_service.find_latest_path(result.source_url)
                if latest is not None:
                    result.cache_path = str(latest)
            else:
                result.cache_path = cache_service.save_result(result)

    # Persist to data/ (after cache is up to date)
    if args.store:
        storage = StorageService(paths)
        with_images = getattr(args, "with_images", False)
        for result in report.results:
            if result.status == "failed":
                continue
            article_dir, is_dup, img_failures = storage.store_result(result, with_images=with_images)
            result.feed_path = article_dir
            result.status = "duplicate" if is_dup else "stored"
            for msg in img_failures:
                print(f"  warning: {msg}")

    summary = _build_run_summary(report, duration_sec=duration)
    _write_report_files(summary, json_path=args.report_json, md_path=args.report_md)

    if args.json:
        setattr(args, "_last_ingest_report", report)
        setattr(args, "_last_paths", paths)
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
            if result.action_hint:
                print(f"  action_hint={result.action_hint}")
        if result.title:
            print(f"  title={result.title}")
        print(f"  comments={result.comment_count} source={result.comment_source}")
        if result.body_preview:
            print(f"  preview={result.body_preview}")
        if result.feed_path:
            print(f"  stored={result.feed_path}")
        if result.cache_path:
            print(f"  cache={result.cache_path}")

    if args.present:
        print("\n## Present")
        _print_present(report, with_images=getattr(args, "with_images", False))

    if args.report_json:
        print(f"  report_json={Path(args.report_json).expanduser()}")
    if args.report_md:
        print(f"  report_md={Path(args.report_md).expanduser()}")
    setattr(args, "_last_ingest_report", report)
    setattr(args, "_last_paths", paths)
    return 0


def _count_result_statuses(report: BatchIngestReport) -> tuple[int, int, int, int]:
    fetched = stored = duplicate = failed = 0
    for result in report.results:
        if result.status == "fetched":
            fetched += 1
        elif result.status == "stored":
            stored += 1
        elif result.status == "duplicate":
            duplicate += 1
        elif result.status == "failed":
            failed += 1
    return fetched, stored, duplicate, failed


def _parse_opt_pairs(raw_opts: list[str]) -> dict[str, str]:
    options: dict[str, str] = {}
    for item in raw_opts:
        if "=" not in item:
            raise ValueError(f"Invalid --opt value '{item}', expected key=value")
        key, value = item.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError(f"Invalid --opt value '{item}', empty key")
        options[key] = value
    return options


def _build_plugin_task(args: argparse.Namespace) -> PluginTask:
    options = _parse_opt_pairs(args.opt)
    preset_name = str(options.get("preset", "")).strip()
    if preset_name:
        preset_options = load_preset(preset_name, plugin_id=args.plugin_id)
        options = {**preset_options, **{k: v for k, v in options.items() if k != "preset"}}
    return PluginTask(plugin_id=args.plugin_id, url=args.url, options=options)


def run_plugin(args: argparse.Namespace) -> int:
    registry = create_default_registry()
    if args.plugin_command == "list":
        preset_map: dict[str, list[str]] = {}
        if args.with_presets:
            for preset in list_presets():
                pid = preset.get("plugin_id", "")
                if not pid:
                    continue
                preset_map.setdefault(pid, []).append(preset["name"])

        rows = []
        for plugin in registry.list_plugins():
            item = {"id": plugin.id, "description": plugin.description}
            if args.with_presets:
                item["presets"] = sorted(preset_map.get(plugin.id, []))
            rows.append(item)
        if args.json:
            print(json.dumps(rows, ensure_ascii=False, indent=2))
        else:
            for row in rows:
                if args.with_presets:
                    presets_text = ", ".join(row.get("presets", [])) or "-"
                    print(f"{row['id']}\t{row['description']}\tpresets: {presets_text}")
                else:
                    print(f"{row['id']}\t{row['description']}")
        return 0

    if args.plugin_command == "presets":
        rows = list_presets(plugin_id=args.plugin_id)
        if args.json:
            print(json.dumps(rows, ensure_ascii=False, indent=2))
        else:
            for row in rows:
                print(f"{row['name']}\t{row['plugin_id']}\t{row['source']}\t{row['description']}")
        return 0

    if args.plugin_command == "run":
        try:
            task = _build_plugin_task(args)
        except ValueError as exc:
            print(str(exc))
            return 2
        result = registry.run(task)
        if args.json:
            print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
        else:
            if result.ok:
                print(result.value)
            else:
                print(f"ERROR: {result.error}")
        return 0 if result.ok else 1

    if args.plugin_command == "doctor":
        try:
            task = _build_plugin_task(args)
        except ValueError as exc:
            print(str(exc))
            return 2
        result = registry.run(task)
        diagnosis = {
            "plugin_id": result.plugin_id,
            "ok": result.ok,
            "error": result.error,
            "error_code": result.meta.get("error_code", ""),
            "suggestion": result.meta.get("suggestion", ""),
            "selected": result.meta.get("selected", {}),
            "steps": result.meta.get("steps", []),
            "value_preview": result.value[:180] if result.value else "",
        }
        if args.json:
            print(json.dumps(diagnosis, ensure_ascii=False, indent=2))
        else:
            if diagnosis["ok"]:
                print(f"OK {diagnosis['plugin_id']}")
                if diagnosis["value_preview"]:
                    print(f"value={diagnosis['value_preview']}")
                print(f"steps={len(diagnosis['steps'])}")
            else:
                print(f"FAIL {diagnosis['plugin_id']}")
                if diagnosis["error"]:
                    print(f"error={diagnosis['error']}")
                if diagnosis["error_code"]:
                    print(f"error_code={diagnosis['error_code']}")
                if diagnosis["suggestion"]:
                    print(f"suggestion={diagnosis['suggestion']}")
        return 0 if diagnosis["ok"] else 1

    print(json.dumps({"error": f"Unsupported plugin command: {args.plugin_command}"}))
    return 2


def _default_ext_repo(args: argparse.Namespace) -> str:
    repo = (args.repo or "").strip()
    if repo:
        return repo
    raise RuntimeError("Extension repo is required. Pass --repo or set ONEFETCH_EXT_REPO.")


def run_ext(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).expanduser()
    cmd = args.ext_command
    if cmd == "list":
        if args.remote:
            try:
                rows = list_remote_extensions(_default_ext_repo(args), ref=args.ref)
            except Exception as exc:
                print(f"[ext] remote list failed: {exc}")
                return 1
            if args.json:
                print(json.dumps(rows, ensure_ascii=False, indent=2))
            else:
                for row in rows:
                    print(
                        f"{row['id']}\t{row['version'] or '-'}\t{row['name'] or '-'}\t{row['description'] or '-'}"
                    )
            return 0

        rows = list_installed_extensions(project_root)
        payload = [
            {
                "id": row.id,
                "name": row.name,
                "version": row.version,
                "path": str(row.path),
                "provides": row.provides,
                "domains": row.domains,
                "enabled": row.enabled,
                "reason": row.reason,
            }
            for row in rows
        ]
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            if not payload:
                print("[ext] no installed extensions")
            for row in payload:
                state = "enabled" if row["enabled"] else f"disabled({row['reason']})"
                provides = ",".join(row["provides"]) if row["provides"] else "-"
                print(f"{row['id']}\t{row['version'] or '-'}\t{provides}\t{state}\t{row['path']}")
        return 0

    if cmd == "install":
        try:
            installed = install_extensions(
                project_root,
                repo_url=_default_ext_repo(args),
                ref=args.ref,
                ids=args.ids,
                install_all=args.all,
            )
        except Exception as exc:
            print(f"[ext] install failed: {exc}")
            return 1
        for ext_id in installed:
            print(f"[ext] installed: {ext_id}")
        return 0

    if cmd == "remove":
        try:
            removed = remove_extensions(project_root, ids=args.ids, remove_all=args.all)
        except Exception as exc:
            print(f"[ext] remove failed: {exc}")
            return 1
        if not removed:
            print("[ext] nothing removed")
            return 0
        for ext_id in removed:
            print(f"[ext] removed: {ext_id}")
        return 0

    if cmd == "update":
        try:
            updated = update_extensions(
                project_root,
                repo_url=_default_ext_repo(args),
                ref=args.ref,
                ids=args.ids,
                update_all=args.all,
            )
        except Exception as exc:
            print(f"[ext] update failed: {exc}")
            return 1
        for ext_id in updated:
            print(f"[ext] updated: {ext_id}")
        return 0

    print(json.dumps({"error": f"Unsupported ext command: {cmd}"}))
    return 2


def run_cache_backfill(args: argparse.Namespace) -> int:
    """Backfill LLM outputs into an existing cache entry for a URL."""
    config = OneFetchConfig(project_root=Path(args.project_root).expanduser())
    paths = config.paths()
    cache_service = TempCacheService(paths)

    cached = cache_service.load_latest_result(args.url)
    if cached is None:
        print(f"[cache-backfill] no cache entry found for: {args.url}")
        return 1

    json_data = args.json_data
    if not json_data:
        # Read from stdin
        import sys
        json_data = sys.stdin.read()

    if not json_data.strip():
        print("[cache-backfill] empty input, aborted")
        return 1

    parsed = parse_and_validate_llm_outputs(json_data)
    state = _llm_outputs_state(parsed)

    cached.llm_outputs = parsed
    cached.llm_outputs_state = state
    saved_path = cache_service.save_result(cached)
    print(f"[cache-backfill] updated: {saved_path}")
    print(f"[cache-backfill] llm_outputs_state: {state}")
    return 0


def _dedup_urls(urls: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for url in urls:
        if url not in seen:
            seen.add(url)
            out.append(url)
    return out


def _normalize_discovered_urls(value: object) -> tuple[list[str], dict, list[str], str]:
    if isinstance(value, list):
        urls = [str(x).strip() for x in value if str(x).strip()]
        return _dedup_urls(urls), {"discovered_count": len(urls)}, [], ""
    if isinstance(value, dict):
        urls_raw = value.get("discovered_urls")
        if urls_raw is None:
            urls_raw = value.get("urls")
        urls = [str(x).strip() for x in (urls_raw or []) if str(x).strip()]
        stats = value.get("stats") if isinstance(value.get("stats"), dict) else {}
        warnings = value.get("warnings") if isinstance(value.get("warnings"), list) else []
        next_cursor = str(value.get("next_cursor") or "").strip()
        return _dedup_urls(urls), stats, [str(x) for x in warnings if str(x).strip()], next_cursor
    return [], {}, [f"unsupported_discover_output_type:{type(value).__name__}"], ""


def _build_discover_ingest_args(args: argparse.Namespace) -> argparse.Namespace:
    return argparse.Namespace(
        command="ingest",
        inputs=[],
        text="",
        crawler=args.ingest_crawler,
        project_root=args.project_root,
        json=False,
        list_crawlers=False,
        report_json="",
        report_md="",
        cache_temp=args.ingest_cache_temp,
        cache_max_items=args.ingest_cache_max_items,
        from_cache=args.ingest_from_cache,
        refresh=args.ingest_refresh,
        store=args.ingest_store,
        present=args.ingest_present,
        raw=False,
        with_images=args.ingest_with_images,
    )


def _write_discover_default_reports(report: BatchDiscoverReport, paths) -> Path:
    discover_dir = paths.reports_dir / "discover"
    discover_dir.mkdir(parents=True, exist_ok=True)
    out_path: Path
    if len(report.requested_urls) == 1:
        by_seed_dir = discover_dir / "by_seed"
        by_seed_dir.mkdir(parents=True, exist_ok=True)
        seed_key = _discover_seed_key(report.requested_urls[0])
        out_path = by_seed_dir / f"{seed_key}.json"
    else:
        by_batch_dir = discover_dir / "by_batch"
        by_batch_dir.mkdir(parents=True, exist_ok=True)
        req_key = _discover_request_key(report.requested_urls)
        out_path = by_batch_dir / f"{req_key}.json"
    out_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    return out_path


def _collection_key_for_report(report: BatchDiscoverReport) -> str:
    if len(report.requested_urls) == 1:
        return f"seed-{_discover_seed_key(report.requested_urls[0])}"
    return f"batch-{_discover_request_key(report.requested_urls)}"


def _write_collection_manifest(
    *,
    collection_key: str,
    paths,
    discover_report: BatchDiscoverReport,
    ingest_report: BatchIngestReport,
    moved_paths: dict[str, str],
) -> Path:
    collection_dir = paths.data_dir / "collections" / collection_key
    collection_dir.mkdir(parents=True, exist_ok=True)
    items: list[dict] = []
    for idx, result in enumerate(ingest_report.results, start=1):
        feed_path = str(result.feed_path or "").strip()
        moved_feed_path = moved_paths.get(feed_path, feed_path)
        cache_path = str(result.cache_path or "").strip()
        items.append(
            {
                "order": idx,
                "source_url": result.source_url,
                "canonical_url": result.canonical_url,
                "status": result.status,
                "crawler_id": result.crawler_id,
                "title": result.title,
                "feed_path": moved_feed_path,
                "cache_path": cache_path,
                "llm_outputs_state": result.llm_outputs_state,
            }
        )

    payload = {
        "collection_key": collection_key,
        "run_id": discover_report.run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "seed_urls": discover_report.requested_urls,
        "discovered_urls": [u for row in discover_report.results for u in row.discovered_urls],
        "items": items,
    }
    manifest_path = collection_dir / "manifest.json"
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest_path


async def run_discover(args: argparse.Namespace) -> int:
    seed_urls = extract_urls(args.inputs, args.text)
    if not seed_urls:
        print("No URLs found. Pass URLs directly or via --text.")
        return 2

    config = OneFetchConfig.from_project_root(args.project_root)
    paths = config.paths()
    run_id = _discover_run_id(seed_urls)

    adapters = _build_adapters(args.project_root)
    router = Router(adapters)
    expanders = load_installed_expanders(args.project_root)
    if args.expander:
        expanders = [item for item in expanders if item.expander_id == args.expander]

    report = BatchDiscoverReport(
        run_id=run_id,
        generated_at=datetime.now(timezone.utc).isoformat(),
        requested_urls=seed_urls,
    )
    all_discovered: list[str] = []
    for seed_url in seed_urls:
        matched = None
        if args.expander:
            for expander in expanders:
                if expander.expander_id == args.expander:
                    matched = expander
                    break
        else:
            for expander in expanders:
                try:
                    if expander.supports(seed_url):
                        matched = expander
                        break
                except Exception:
                    continue
        if matched is None:
            report.results.append(
                DiscoverResult(
                    seed_url=seed_url,
                    status="failed",
                    error="no_matching_expander",
                    warnings=["No installed expander supports this URL."],
                )
            )
            continue

        try:
            matched_id = str(getattr(matched, "expander_id", "") or getattr(matched, "id", "")).strip() or "unknown"
            adapter = router.route(seed_url, forced_adapter=args.crawler or None)
            feed = await adapter.crawl(seed_url)
            html_text = feed.raw_body or ""
            discovered_raw = matched.discover(seed_url, html_text)
            discovered_urls, stats, warnings, next_cursor = _normalize_discovered_urls(discovered_raw)
            report.results.append(
                DiscoverResult(
                    seed_url=seed_url,
                    expander_id=matched_id,
                    discovered_urls=discovered_urls,
                    stats={**stats, "seed_crawler": adapter.id, "raw_body_present": bool(html_text)},
                    warnings=warnings,
                    next_cursor=next_cursor,
                    status="ok",
                )
            )
            all_discovered.extend(discovered_urls)
        except Exception as exc:
            report.results.append(
                DiscoverResult(
                    seed_url=seed_url,
                    expander_id=matched_id,
                    status="failed",
                    error=str(exc),
                    warnings=["discover_execution_failed"],
                )
            )

    report.discovered_count = sum(len(item.discovered_urls) for item in report.results)
    report.failed_count = sum(1 for item in report.results if item.status == "failed")
    report_path = _write_discover_default_reports(report, paths)

    if args.json:
        print(report.model_dump_json(indent=2))
    else:
        print(
            f"Processed {len(report.requested_urls)} seed URL(s): "
            f"{report.discovered_count} discovered, {report.failed_count} failed."
        )
        for result in report.results:
            print(f"[{result.status}] {result.seed_url}")
            if result.expander_id:
                print(f"  expander={result.expander_id}")
            print(f"  discovered={len(result.discovered_urls)}")
            if result.error:
                print(f"  error={result.error}")
            if result.warnings:
                print(f"  warnings={', '.join(result.warnings)}")
            if args.present and result.discovered_urls:
                for url in result.discovered_urls:
                    print(f"  - {url}")
        print(f"  discover_report={report_path}")

    if args.ingest:
        urls = _dedup_urls(all_discovered)
        if not urls:
            print("[discover] no discovered URLs to ingest.")
            return 0
        ingest_args = _build_discover_ingest_args(args)
        exit_code = await _run_ingest_urls(ingest_args, urls)
        ingest_report = getattr(ingest_args, "_last_ingest_report", None)
        if exit_code == 0 and args.ingest_store and ingest_report is not None:
            storage = StorageService(paths)
            stored_dirs = [str(r.feed_path or "").strip() for r in ingest_report.results if r.status == "stored" and str(r.feed_path or "").strip()]
            collection_key = _collection_key_for_report(report)
            moved_paths = storage.relocate_articles_to_collection(
                collection_key=collection_key,
                article_dirs_in_order=stored_dirs,
            )
            for row in ingest_report.results:
                fp = str(row.feed_path or "").strip()
                if fp in moved_paths:
                    row.feed_path = moved_paths[fp]
            manifest_path = _write_collection_manifest(
                collection_key=collection_key,
                paths=paths,
                discover_report=report,
                ingest_report=ingest_report,
                moved_paths=moved_paths,
            )
            print(f"[discover] collection_manifest={manifest_path}")
        return exit_code
    return 0


async def run_images(args: argparse.Namespace) -> int:
    """Extract image URLs from one or more pages."""
    adapters = _build_adapters(args.project_root)
    router = Router(adapters)
    urls = extract_urls(args.inputs, args.text)
    if not urls:
        print("No URLs found.")
        return 2

    download_dir = Path(args.download).expanduser() if args.download else None
    if download_dir:
        download_dir.mkdir(parents=True, exist_ok=True)

    for url in urls:
        try:
            adapter = router.route(url, forced_adapter=args.crawler or None)
            feed = await adapter.crawl(url)
            if not feed.images:
                print(f"[images] {adapter.id} | {feed.title or url} | 0 images")
                continue
            print(f"[images] {adapter.id} | {feed.title or url} | {len(feed.images)} images")
            for i, img_url in enumerate(feed.images):
                if args.proxy:
                    import urllib.parse
                    proxied = f"https://wsrv.nl/?url={urllib.parse.quote(img_url, safe='')}"
                    print(proxied)
                else:
                    print(img_url)

                if download_dir:
                    await _download_image(img_url, download_dir, index=i + 1)
        except Exception as exc:
            print(f"[images] failed: {url} — {exc}")
    return 0


async def _download_image(url: str, output_dir: Path, *, index: int) -> None:
    import urllib.parse
    from onefetch.http import create_async_client

    async def _try_fetch(target_url: str) -> tuple[bytes | None, str]:
        try:
            async with create_async_client(timeout=30, follow_redirects=True) as client:
                response = await client.get(target_url)
                response.raise_for_status()
            return response.content, response.headers.get("content-type", "image/jpeg")
        except Exception:
            return None, ""

    data, ct = await _try_fetch(url)
    if data is None:
        proxy_url = f"https://wsrv.nl/?url={urllib.parse.quote(url, safe='')}"
        data, ct = await _try_fetch(proxy_url)
    if data is None:
        print(f"  download failed (direct + wsrv.nl): {url}")
        return
    ext = ".webp" if "webp" in ct else ".png" if "png" in ct else ".gif" if "gif" in ct else ".jpg"
    filename = f"{index:03d}{ext}"
    path = output_dir / filename
    path.write_bytes(data)
    print(f"  saved: {path} ({len(data)} bytes)")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "ingest":
        return asyncio.run(run_ingest(args))
    if args.command == "images":
        return asyncio.run(run_images(args))
    if args.command == "cache-backfill":
        return run_cache_backfill(args)
    if args.command == "plugin":
        return run_plugin(args)
    if args.command == "ext":
        return run_ext(args)
    if args.command == "discover":
        return asyncio.run(run_discover(args))

    print(json.dumps({"error": f"Unsupported command: {args.command}"}))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
