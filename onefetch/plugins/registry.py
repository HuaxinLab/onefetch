from __future__ import annotations

from onefetch.plugins.base import Plugin, PluginResult, PluginTask
from onefetch.plugins.extract_css_attr import ExtractCssAttrPlugin
from onefetch.plugins.extract_html_js_jsonp import ExtractHtmlJsJsonpPlugin
from onefetch.plugins.extract_jsonp_field import ExtractJsonpFieldPlugin


class PluginRegistry:
    def __init__(self, plugins: list[Plugin] | None = None) -> None:
        self._plugins: dict[str, Plugin] = {}
        for plugin in plugins or []:
            self.register(plugin)

    def register(self, plugin: Plugin) -> None:
        self._plugins[plugin.id] = plugin

    def list_plugins(self) -> list[Plugin]:
        return [self._plugins[k] for k in sorted(self._plugins.keys())]

    def get(self, plugin_id: str) -> Plugin | None:
        return self._plugins.get(plugin_id)

    def run(self, task: PluginTask) -> PluginResult:
        plugin = self.get(task.plugin_id)
        if plugin is None:
            return PluginResult(plugin_id=task.plugin_id, ok=False, error="plugin not found")
        if not plugin.supports(task):
            return PluginResult(plugin_id=task.plugin_id, ok=False, error="plugin does not support this task")
        return plugin.run(task)


def create_default_registry() -> PluginRegistry:
    return PluginRegistry(
        plugins=[
            ExtractCssAttrPlugin(),
            ExtractHtmlJsJsonpPlugin(),
            ExtractJsonpFieldPlugin(),
        ]
    )
