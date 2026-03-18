from __future__ import annotations

import json
import re

from onefetch.plugins.base import PluginResult, PluginTask
from onefetch.plugins.http import fetch_text


class ExtractJsonpFieldPlugin:
    id = "extract_jsonp_field"
    description = "Extract a field value from JSONP response"

    def supports(self, task: PluginTask) -> bool:
        return task.plugin_id == self.id

    def run(self, task: PluginTask) -> PluginResult:
        callback = task.options.get("callback", "callback")
        field = task.options.get("field", "img_url")
        jsonp_url = task.options.get("jsonp_url") or task.url
        jsonp_body = task.options.get("jsonp_body")

        if not jsonp_body:
            if not jsonp_url:
                return PluginResult(plugin_id=self.id, ok=False, error="jsonp_url is required")
            jsonp_body = fetch_text(jsonp_url)

        match = re.search(rf"{re.escape(callback)}\((.*)\)\s*$", jsonp_body)
        if not match:
            return PluginResult(
                plugin_id=self.id,
                ok=False,
                error="invalid jsonp response or callback mismatch",
                meta={"callback": callback},
            )

        try:
            payload = json.loads(match.group(1))
        except json.JSONDecodeError as exc:
            return PluginResult(plugin_id=self.id, ok=False, error=f"invalid json: {exc}")

        value = payload.get(field)
        if not isinstance(value, str) or not value:
            return PluginResult(
                plugin_id=self.id,
                ok=False,
                error=f"field '{field}' missing or empty",
                meta={"field": field},
            )

        return PluginResult(
            plugin_id=self.id,
            ok=True,
            value=value,
            meta={"field": field, "callback": callback},
        )
