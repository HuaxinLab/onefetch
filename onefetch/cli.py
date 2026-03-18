from __future__ import annotations

import argparse
import asyncio
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
from onefetch.llm_outputs import parse_and_validate_llm_outputs
from onefetch.models import BatchIngestReport, IngestResult
from onefetch.pipeline import IngestionPipeline
from onefetch.plugins import PluginTask, create_default_registry
from onefetch.plugins.presets import list_presets, load_preset
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
    ingest.add_argument(
        "--llm-output-file",
        default="",
        help="Optional override path for raw LLM output (JSON/text). Default path: reports/llm_output.json",
    )
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


def _resolve_llm_output_path(args: argparse.Namespace, reports_dir: Path) -> Path | None:
    if args.llm_output_file:
        path = Path(args.llm_output_file).expanduser()
        return path if path.exists() else None
    default_path = reports_dir / "llm_output.json"
    return default_path if default_path.exists() else None


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
    body = (result.body_full or result.body_excerpt or result.body_preview or "").strip()
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
        if result.body_full:
            print("- full_body:")
            print("```text")
            print(result.body_full)
            print("```")
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


async def run_ingest(args: argparse.Namespace) -> int:
    adapters = create_default_adapters()
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
    paths = config.paths()
    storage = None
    if args.store:
        storage = StorageService(paths)
    cache_service = TempCacheService(paths, max_entries=args.cache_max_items) if args.cache_temp else None

    pipeline = IngestionPipeline(router=router, storage=storage)

    start = time.monotonic()
    report = BatchIngestReport(requested_urls=urls)
    pending_urls = urls
    cached_results_by_url: dict[str, IngestResult] = {}
    if args.from_cache and not args.refresh and cache_service is not None:
        pending_urls = []
        for source_url in urls:
            cached = cache_service.load_latest_result(source_url)
            if cached is None:
                pending_urls.append(source_url)
                continue
            cached.cache_path = "<cache-hit>"
            cached_results_by_url[source_url] = cached

    if pending_urls:
        fresh_report = await pipeline.ingest_urls(pending_urls, forced_adapter=args.crawler or None, store=args.store)
        for result in fresh_report.results:
            cached_results_by_url[result.source_url] = result

    report.results = [cached_results_by_url[url] for url in urls if url in cached_results_by_url]
    report.fetched_count, report.stored_count, report.duplicate_count, report.failed_count = _count_result_statuses(report)
    duration = time.monotonic() - start

    llm_output_path = _resolve_llm_output_path(args, paths.reports_dir)
    if llm_output_path is not None:
        raw_output = llm_output_path.read_text(encoding="utf-8")
        parsed_output = parse_and_validate_llm_outputs(raw_output)
        parsed_state = _llm_outputs_state(parsed_output)
        for result in report.results:
            result.llm_outputs = parsed_output
            result.llm_outputs_state = parsed_state

    if args.store:
        await _ensure_store_ready_llm_outputs(report)

    if cache_service is not None:
        for result in report.results:
            if result.status == "failed":
                continue
            result.cache_path = cache_service.save_result(result)

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
        if result.cache_path:
            print(f"  cache={result.cache_path}")

    if args.present:
        print("\n## Present")
        _print_present(report)

    if args.report_json:
        print(f"  report_json={Path(args.report_json).expanduser()}")
    if args.report_md:
        print(f"  report_md={Path(args.report_md).expanduser()}")
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


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "ingest":
        return asyncio.run(run_ingest(args))
    if args.command == "plugin":
        return run_plugin(args)

    print(json.dumps({"error": f"Unsupported command: {args.command}"}))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
