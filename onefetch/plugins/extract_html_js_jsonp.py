from __future__ import annotations

import json
import re
import time

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
    def _first_match(pattern: str, text: str) -> str:
        m = re.search(pattern, text)
        if not m:
            return ""
        if m.lastindex:
            return (m.group(1) or "").strip()
        return (m.group(0) or "").strip()

    def run(self, task: PluginTask) -> PluginResult:
        opts = task.options
        callback = opts.get("callback", "img_url")
        field = opts.get("field", "img_url")
        append_version = opts.get("append_version", "false").lower() in {"1", "true", "yes"}
        default_fallback = opts.get("fallback_default_image", "true").lower() in {"1", "true", "yes"}

        try:
            html_text = opts.get("html")
            if not html_text and task.url:
                html_text = fetch_text(task.url)
            if not html_text:
                return PluginResult(plugin_id=self.id, ok=False, error="url or html is required")

            js_url = opts.get("js_url", "")
            js_url_regex = opts.get("js_url_regex", DEFAULT_JS_URL_REGEX)
            if not js_url:
                js_url = self._first_match(js_url_regex, html_text)
                if js_url.startswith("//"):
                    js_url = "https:" + js_url
            if not js_url and not opts.get("js_body"):
                return PluginResult(plugin_id=self.id, ok=False, error="failed to resolve js_url from html")

            js_text = opts.get("js_body") or fetch_text(js_url)

            jsonp_url = opts.get("jsonp_url", "")
            jsonp_base = opts.get("jsonp_base", "")
            if not jsonp_url:
                if not jsonp_base:
                    base_regex = opts.get("jsonp_base_regex", DEFAULT_JSONP_BASE_REGEX)
                    jsonp_base = self._first_match(base_regex, js_text)
                if not jsonp_base and not opts.get("jsonp_body"):
                    return PluginResult(plugin_id=self.id, ok=False, error="failed to resolve jsonp_base from js")
                if jsonp_base:
                    ts = opts.get("ts") or str(int(time.time() * 1000))
                    jsonp_url = f"{jsonp_base}{ts}&callback={callback}"

            jsonp_body = opts.get("jsonp_body") or (fetch_text(jsonp_url) if jsonp_url else "")
            if not jsonp_body:
                return PluginResult(plugin_id=self.id, ok=False, error="empty jsonp response")

            wrapper = re.search(rf"{re.escape(callback)}\((.*)\)\s*$", jsonp_body)
            if not wrapper:
                return PluginResult(
                    plugin_id=self.id,
                    ok=False,
                    error="invalid jsonp response or callback mismatch",
                    meta={"callback": callback},
                )

            payload = json.loads(wrapper.group(1))
            value = payload.get(field)
            if (not isinstance(value, str) or not value) and default_fallback:
                fallback_regex = opts.get("fallback_image_regex", DEFAULT_FALLBACK_IMAGE_REGEX)
                value = self._first_match(fallback_regex, js_text)

            if not isinstance(value, str) or not value:
                return PluginResult(
                    plugin_id=self.id,
                    ok=False,
                    error=f"field '{field}' missing or empty",
                    meta={"field": field},
                )

            if append_version:
                version_regex = opts.get("version_regex", DEFAULT_VERSION_REGEX)
                version = self._first_match(version_regex, js_text)
                if not version:
                    version = self._first_match(r'version:"([^"]+)"', js_text)
                if version:
                    sep = "&" if "?" in value else "?"
                    value = f"{value}{sep}v={version}"

            return PluginResult(
                plugin_id=self.id,
                ok=True,
                value=value,
                meta={
                    "js_url": js_url,
                    "jsonp_url": jsonp_url,
                    "field": field,
                    "callback": callback,
                },
            )
        except Exception as exc:
            return PluginResult(plugin_id=self.id, ok=False, error=str(exc))
