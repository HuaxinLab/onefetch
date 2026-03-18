from __future__ import annotations

import json
import re
import time
from collections.abc import Iterable
from typing import Any

from onefetch.plugins.base import PluginResult, PluginTask
from onefetch.plugins.http import fetch_text

AUTO_JS_URL_PATTERNS = [
    r'(https?:)?//cdn\.dingtalkapps\.com/dingding/wukong_office_network/[^"\\]+/wukong/[^"\\]+\.js',
    r'(https?:)?//cdn\.[^/]+/[^"\\]+\.js',
    r'(https?:)?//static\.[^/]+/[^"\\]+\.js',
    r'(https?:)?//[^"\\]+\.js',
]
AUTO_JSONP_BASE_PATTERNS = [
    r'(https://hudong\.alicdn\.com/api/data/v2/[^"\\]+\.js\?t=)',
    r'(https://[^"\\]+\.js\?t=)',
    r'(https://[^"\\]+callback=[^"\\]+)',
]
DEFAULT_VERSION_REGEX = r'b=\{imageUrl:"[^"]+",version:"([^"]+)"\}'
DEFAULT_FALLBACK_IMAGE_REGEX = r'b=\{imageUrl:"([^"]+)",version:"[^"]+"\}'

COMMON_CALLBACK_CANDIDATES = ["img_url", "callback", "cb", "jsonp"]
COMMON_FIELD_CANDIDATES = ["img_url", "download_url", "url", "value", "data"]


class ExtractHtmlJsJsonpPlugin:
    id = "extract_html_js_jsonp"
    description = "Extract value by HTML -> JS -> JSONP chain"

    def supports(self, task: PluginTask) -> bool:
        return task.plugin_id == self.id

    @staticmethod
    def _normalize_candidates(value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return []
            if raw.startswith("[") and raw.endswith("]"):
                try:
                    parsed = json.loads(raw)
                    if isinstance(parsed, list):
                        return [str(item).strip() for item in parsed if str(item).strip()]
                except Exception:
                    pass
            if "||" in raw:
                return [item.strip() for item in raw.split("||") if item.strip()]
            return [raw]
        if isinstance(value, Iterable):
            out: list[str] = []
            for item in value:
                s = str(item).strip()
                if s:
                    out.append(s)
            return out
        return [str(value).strip()]

    @staticmethod
    def _extract_matches(pattern: str, text: str) -> list[str]:
        values: list[str] = []
        for match in re.finditer(pattern, text):
            if match.lastindex:
                v = match.group(1) or ""
            else:
                v = match.group(0) or ""
            v = v.strip()
            if v:
                values.append(v)
        seen: set[str] = set()
        deduped: list[str] = []
        for item in values:
            if item in seen:
                continue
            seen.add(item)
            deduped.append(item)
        return deduped

    @staticmethod
    def _first_match(pattern: str, text: str) -> str:
        matches = ExtractHtmlJsJsonpPlugin._extract_matches(pattern, text)
        return matches[0] if matches else ""

    @staticmethod
    def _to_bool(value: Any, *, default: bool = False) -> bool:
        if value is None:
            return default
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    @staticmethod
    def _find_string_field(payload: Any, field_candidates: list[str]) -> tuple[str, str]:
        def search(node: Any, key: str) -> str:
            if isinstance(node, dict):
                direct = node.get(key)
                if isinstance(direct, str) and direct:
                    return direct
                for child in node.values():
                    hit = search(child, key)
                    if hit:
                        return hit
            elif isinstance(node, list):
                for child in node:
                    hit = search(child, key)
                    if hit:
                        return hit
            return ""

        for key in field_candidates:
            hit = search(payload, key)
            if hit:
                return hit, key
        return "", ""

    @staticmethod
    def _make_error(code: str, suggestion: str) -> dict[str, str]:
        return {"error_code": code, "suggestion": suggestion}

    def run(self, task: PluginTask) -> PluginResult:
        opts = task.options

        callback = str(opts.get("callback", "img_url"))
        field = str(opts.get("field", "img_url"))
        append_version = self._to_bool(opts.get("append_version"), default=False)
        default_fallback = self._to_bool(opts.get("fallback_default_image"), default=True)
        auto_detect = self._to_bool(opts.get("auto_detect"), default=True)
        ts_value = str(opts.get("ts") or int(time.time() * 1000))

        callback_candidates = self._normalize_candidates(opts.get("callback_candidates"))
        if not callback_candidates:
            callback_candidates = [callback]
            if auto_detect:
                callback_candidates.extend([c for c in COMMON_CALLBACK_CANDIDATES if c not in callback_candidates])

        field_candidates = self._normalize_candidates(opts.get("field_candidates"))
        if not field_candidates:
            field_candidates = [field]
            if auto_detect:
                field_candidates.extend([f for f in COMMON_FIELD_CANDIDATES if f not in field_candidates])

        trace: dict[str, Any] = {
            "callback": callback,
            "field": field,
            "append_version": append_version,
            "auto_detect": auto_detect,
            "steps": [],
        }

        def fail(code: str, message: str, suggestion: str) -> PluginResult:
            trace.update(self._make_error(code, suggestion))
            return PluginResult(plugin_id=self.id, ok=False, error=message, meta=trace)

        try:
            html_text = opts.get("html")
            if not html_text and task.url:
                try:
                    html_text = fetch_text(task.url)
                    trace["steps"].append({"step": "fetch_html", "ok": True, "url": task.url})
                except Exception as exc:
                    trace["steps"].append({"step": "fetch_html", "ok": False, "url": task.url, "error": str(exc)})
                    return fail(
                        "E_HTML_FETCH",
                        str(exc),
                        "Check URL accessibility, retry with --opt html=<content> for offline debug, or refresh network.",
                    )
            if not html_text:
                return fail("E_INPUT_MISSING", "url or html is required", "Provide --url or --opt html=<content>.")

            js_candidates: list[tuple[str, str]] = []
            explicit_js_url = str(opts.get("js_url", "")).strip()
            if explicit_js_url:
                js_candidates.append((explicit_js_url, "explicit_js_url"))

            js_patterns = self._normalize_candidates(opts.get("js_url_regexes"))
            if not js_patterns:
                js_patterns = self._normalize_candidates(opts.get("js_url_regex"))
            if not js_patterns:
                js_patterns = list(AUTO_JS_URL_PATTERNS if auto_detect else [AUTO_JS_URL_PATTERNS[0]])

            for pattern in js_patterns:
                matches = self._extract_matches(pattern, str(html_text))
                trace["steps"].append({"step": "match_js_url", "pattern": pattern, "count": len(matches)})
                for match in matches:
                    url = "https:" + match if match.startswith("//") else match
                    js_candidates.append((url, f"regex:{pattern}"))

            js_body_inline = str(opts.get("js_body", ""))
            js_sources: list[tuple[str, str]] = []
            if js_body_inline:
                js_sources.append((js_body_inline, "inline_js_body"))
            else:
                seen_js_urls: set[str] = set()
                for js_url, source in js_candidates:
                    if not js_url or js_url in seen_js_urls:
                        continue
                    seen_js_urls.add(js_url)
                    try:
                        js_text = fetch_text(js_url)
                        js_sources.append((js_text, js_url))
                        trace["steps"].append({"step": "fetch_js", "ok": True, "url": js_url, "source": source})
                    except Exception as exc:
                        trace["steps"].append(
                            {"step": "fetch_js", "ok": False, "url": js_url, "source": source, "error": str(exc)}
                        )

            if not js_sources:
                return fail(
                    "E_JS_NOT_FOUND",
                    "failed to resolve js content",
                    "Provide js_url/js_body, or tune js_url_regexes (multiple candidates supported).",
                )

            jsonp_body_inline = str(opts.get("jsonp_body", ""))
            explicit_jsonp_url = str(opts.get("jsonp_url", "")).strip()
            explicit_jsonp_base = str(opts.get("jsonp_base", "")).strip()

            for js_text, js_source in js_sources:
                request_targets: list[tuple[str, str]] = []
                if jsonp_body_inline:
                    request_targets.append(("<inline_jsonp>", jsonp_body_inline))
                elif explicit_jsonp_url:
                    request_targets.append((explicit_jsonp_url, ""))
                else:
                    base_patterns = self._normalize_candidates(opts.get("jsonp_base_regexes"))
                    if not base_patterns:
                        base_patterns = self._normalize_candidates(opts.get("jsonp_base_regex"))
                    if not base_patterns:
                        base_patterns = list(AUTO_JSONP_BASE_PATTERNS if auto_detect else [AUTO_JSONP_BASE_PATTERNS[0]])

                    jsonp_bases: list[str] = []
                    if explicit_jsonp_base:
                        jsonp_bases.append(explicit_jsonp_base)
                    for pattern in base_patterns:
                        bases = self._extract_matches(pattern, js_text)
                        trace["steps"].append(
                            {
                                "step": "match_jsonp_base",
                                "pattern": pattern,
                                "count": len(bases),
                                "js_source": js_source,
                            }
                        )
                        jsonp_bases.extend(bases)

                    seen_base: set[str] = set()
                    for base in jsonp_bases:
                        if not base or base in seen_base:
                            continue
                        seen_base.add(base)
                        request_targets.append((f"{base}{ts_value}&callback={callback}", ""))

                if not request_targets:
                    trace["steps"].append({"step": "build_jsonp_targets", "ok": False, "js_source": js_source})
                    continue

                for jsonp_url, inline_body in request_targets:
                    try:
                        jsonp_body = inline_body or fetch_text(jsonp_url)
                        trace["steps"].append(
                            {"step": "fetch_jsonp", "ok": True, "url": jsonp_url, "js_source": js_source}
                        )
                    except Exception as exc:
                        trace["steps"].append(
                            {
                                "step": "fetch_jsonp",
                                "ok": False,
                                "url": jsonp_url,
                                "js_source": js_source,
                                "error": str(exc),
                            }
                        )
                        continue

                    parsed_payload: Any = None
                    parsed_callback = ""

                    for cb in callback_candidates:
                        wrapper = re.search(rf"(?<![A-Za-z0-9_$]){re.escape(cb)}\((.*)\)\s*$", jsonp_body)
                        if wrapper:
                            try:
                                parsed_payload = json.loads(wrapper.group(1))
                                parsed_callback = cb
                                break
                            except Exception as exc:
                                trace["steps"].append(
                                    {
                                        "step": "parse_jsonp",
                                        "ok": False,
                                        "url": jsonp_url,
                                        "reason": f"invalid_json:{exc}",
                                        "callback": cb,
                                    }
                                )

                    if parsed_payload is None and auto_detect:
                        generic = re.search(r'^\s*([A-Za-z_$][A-Za-z0-9_$]*)\((.*)\)\s*$', jsonp_body)
                        if generic:
                            try:
                                parsed_payload = json.loads(generic.group(2))
                                parsed_callback = generic.group(1)
                                trace["steps"].append(
                                    {
                                        "step": "parse_jsonp",
                                        "ok": True,
                                        "url": jsonp_url,
                                        "callback": parsed_callback,
                                        "mode": "auto_detect",
                                    }
                                )
                            except Exception as exc:
                                trace["steps"].append(
                                    {
                                        "step": "parse_jsonp",
                                        "ok": False,
                                        "url": jsonp_url,
                                        "reason": f"invalid_json:{exc}",
                                        "mode": "auto_detect",
                                    }
                                )

                    if parsed_payload is None:
                        trace["steps"].append(
                            {
                                "step": "parse_jsonp",
                                "ok": False,
                                "url": jsonp_url,
                                "reason": "callback_mismatch",
                                "callbacks_tried": callback_candidates,
                            }
                        )
                        continue

                    value, selected_field = self._find_string_field(parsed_payload, field_candidates)
                    fallback_used = False
                    if not value and default_fallback:
                        fallback_regex = str(opts.get("fallback_image_regex", DEFAULT_FALLBACK_IMAGE_REGEX))
                        value = self._first_match(fallback_regex, js_text)
                        fallback_used = bool(value)
                        selected_field = "fallback_image_regex" if fallback_used else selected_field

                    if not value:
                        trace["steps"].append(
                            {
                                "step": "extract_field",
                                "ok": False,
                                "url": jsonp_url,
                                "reason": f"missing_field:{field}",
                                "field_candidates": field_candidates,
                            }
                        )
                        continue

                    version = ""
                    if append_version:
                        version_regex = str(opts.get("version_regex", DEFAULT_VERSION_REGEX))
                        version = self._first_match(version_regex, js_text)
                        if not version:
                            version = self._first_match(r'version:"([^"]+)"', js_text)
                        if version:
                            sep = "&" if "?" in value else "?"
                            value = f"{value}{sep}v={version}"

                    trace["steps"].append(
                        {
                            "step": "extract_field",
                            "ok": True,
                            "url": jsonp_url,
                            "js_source": js_source,
                            "fallback_used": fallback_used,
                            "version": version,
                            "selected_field": selected_field,
                            "selected_callback": parsed_callback,
                        }
                    )
                    trace["selected"] = {
                        "js_source": js_source,
                        "jsonp_url": jsonp_url,
                        "fallback_used": fallback_used,
                        "selected_field": selected_field,
                        "selected_callback": parsed_callback,
                    }
                    return PluginResult(plugin_id=self.id, ok=True, value=value, meta=trace)

            # failures after retries
            js_fetch_failed = any(step.get("step") == "fetch_js" and not step.get("ok") for step in trace["steps"])
            jsonp_fetch_failed = any(step.get("step") == "fetch_jsonp" and not step.get("ok") for step in trace["steps"])
            parse_failed = any(step.get("step") == "parse_jsonp" and not step.get("ok") for step in trace["steps"])

            if jsonp_fetch_failed:
                return fail(
                    "E_JSONP_FETCH",
                    "failed to fetch jsonp targets",
                    "Check jsonp URL/base patterns and network availability.",
                )
            if parse_failed:
                return fail(
                    "E_JSONP_PARSE",
                    "failed to parse jsonp payload",
                    "Adjust callback/callback_candidates or enable auto_detect.",
                )
            if js_fetch_failed:
                return fail(
                    "E_JS_FETCH",
                    "failed to fetch js candidates",
                    "Check js URL candidates or provide js_body directly.",
                )

            return fail(
                "E_FIELD_NOT_FOUND",
                f"field '{field}' missing or empty",
                "Adjust field/field_candidates, or enable fallback_default_image for image scenarios.",
            )
        except Exception as exc:
            trace["fatal_error"] = str(exc)
            return fail("E_UNKNOWN", str(exc), "Retry with --json to inspect trace and refine preset.")
