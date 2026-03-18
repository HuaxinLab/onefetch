from __future__ import annotations

import json
import re
import time
from collections.abc import Iterable
from typing import Any

from onefetch.plugins.base import PluginResult, PluginTask
from onefetch.plugins.http import fetch_text

DEFAULT_JS_URL_REGEX = r'(https?:)?//cdn\.dingtalkapps\.com/dingding/wukong_office_network/[^"\\]+/wukong/[^"\\]+\.js'
DEFAULT_JSONP_BASE_REGEX = r'(https://hudong\.alicdn\.com/api/data/v2/[^"\\]+\.js\?t=)'
DEFAULT_VERSION_REGEX = r'b=\{imageUrl:"[^"]+",version:"([^"]+)"\}'
DEFAULT_FALLBACK_IMAGE_REGEX = r'b=\{imageUrl:"([^"]+)",version:"[^"]+"\}'


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
        # dedupe while preserving order
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

    def run(self, task: PluginTask) -> PluginResult:
        opts = task.options
        callback = str(opts.get("callback", "img_url"))
        field = str(opts.get("field", "img_url"))
        append_version = str(opts.get("append_version", "false")).lower() in {"1", "true", "yes"}
        default_fallback = str(opts.get("fallback_default_image", "true")).lower() in {"1", "true", "yes"}
        ts_value = str(opts.get("ts") or int(time.time() * 1000))

        trace: dict[str, Any] = {
            "callback": callback,
            "field": field,
            "append_version": append_version,
            "steps": [],
        }

        try:
            html_text = opts.get("html")
            if not html_text and task.url:
                html_text = fetch_text(task.url)
                trace["steps"].append({"step": "fetch_html", "ok": True, "url": task.url})
            if not html_text:
                return PluginResult(plugin_id=self.id, ok=False, error="url or html is required", meta=trace)

            # Resolve JS candidates.
            js_candidates: list[tuple[str, str]] = []
            explicit_js_url = str(opts.get("js_url", "")).strip()
            if explicit_js_url:
                js_candidates.append((explicit_js_url, "explicit_js_url"))

            js_patterns = self._normalize_candidates(opts.get("js_url_regexes"))
            if not js_patterns:
                js_patterns = self._normalize_candidates(opts.get("js_url_regex"))
            if not js_patterns:
                js_patterns = [DEFAULT_JS_URL_REGEX]

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
                return PluginResult(
                    plugin_id=self.id,
                    ok=False,
                    error="failed to resolve js content",
                    meta=trace,
                )

            # Optional short-circuit when jsonp_body is provided.
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
                        base_patterns = [DEFAULT_JSONP_BASE_REGEX]

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

                    wrapper = re.search(rf"{re.escape(callback)}\((.*)\)\s*$", jsonp_body)
                    if not wrapper:
                        trace["steps"].append(
                            {"step": "parse_jsonp", "ok": False, "url": jsonp_url, "reason": "callback_mismatch"}
                        )
                        continue

                    try:
                        payload = json.loads(wrapper.group(1))
                    except Exception as exc:
                        trace["steps"].append(
                            {"step": "parse_jsonp", "ok": False, "url": jsonp_url, "reason": f"invalid_json:{exc}"}
                        )
                        continue

                    value = payload.get(field)
                    fallback_used = False
                    if (not isinstance(value, str) or not value) and default_fallback:
                        fallback_regex = str(opts.get("fallback_image_regex", DEFAULT_FALLBACK_IMAGE_REGEX))
                        value = self._first_match(fallback_regex, js_text)
                        fallback_used = bool(value)

                    if not isinstance(value, str) or not value:
                        trace["steps"].append(
                            {
                                "step": "extract_field",
                                "ok": False,
                                "url": jsonp_url,
                                "reason": f"missing_field:{field}",
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
                        }
                    )
                    trace["selected"] = {
                        "js_source": js_source,
                        "jsonp_url": jsonp_url,
                        "fallback_used": fallback_used,
                    }
                    return PluginResult(plugin_id=self.id, ok=True, value=value, meta=trace)

            return PluginResult(
                plugin_id=self.id,
                ok=False,
                error=f"field '{field}' missing or empty",
                meta=trace,
            )
        except Exception as exc:
            trace["fatal_error"] = str(exc)
            return PluginResult(plugin_id=self.id, ok=False, error=str(exc), meta=trace)
