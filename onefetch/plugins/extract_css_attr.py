from __future__ import annotations

from lxml import html

from onefetch.plugins.base import PluginResult, PluginTask
from onefetch.plugins.http import fetch_text


def _selector_to_xpath(selector: str) -> str:
    selector = selector.strip()
    if not selector:
        raise ValueError("selector is required")

    if selector.startswith("#"):
        return f"//*[@id='{selector[1:]}']"

    if selector.startswith("."):
        cls = selector[1:]
        return f"//*[contains(concat(' ', normalize-space(@class), ' '), ' {cls} ')]"

    if "." in selector and " " not in selector and selector.count(".") == 1:
        tag, cls = selector.split(".", 1)
        if tag and cls:
            return f"//{tag}[contains(concat(' ', normalize-space(@class), ' '), ' {cls} ')]"

    if " " not in selector and ">" not in selector:
        return f"//{selector}"

    raise ValueError(
        "unsupported selector format; supported: #id, .class, tag, tag.class"
    )


class ExtractCssAttrPlugin:
    id = "extract_css_attr"
    description = "Extract an attribute/text from HTML by simple CSS selector"

    def supports(self, task: PluginTask) -> bool:
        return task.plugin_id == self.id

    def run(self, task: PluginTask) -> PluginResult:
        selector = task.options.get("selector", "")
        attr = task.options.get("attr", "src")
        index = int(task.options.get("index", "0") or "0")
        html_text = task.options.get("html")

        if not html_text:
            if not task.url:
                return PluginResult(plugin_id=self.id, ok=False, error="url is required")
            html_text = fetch_text(task.url)

        try:
            xpath = _selector_to_xpath(selector)
            tree = html.fromstring(html_text)
            nodes = tree.xpath(xpath)
            if not nodes or index >= len(nodes):
                return PluginResult(
                    plugin_id=self.id,
                    ok=False,
                    error="selector did not match enough nodes",
                    meta={"selector": selector, "count": str(len(nodes))},
                )

            node = nodes[index]
            if attr == "text":
                value = (node.text_content() or "").strip()
            else:
                value = (node.get(attr) or "").strip()

            if not value:
                return PluginResult(
                    plugin_id=self.id,
                    ok=False,
                    error=f"attribute '{attr}' not found or empty",
                    meta={"selector": selector, "index": str(index)},
                )

            return PluginResult(
                plugin_id=self.id,
                ok=True,
                value=value,
                meta={"selector": selector, "attr": attr, "index": str(index)},
            )
        except Exception as exc:
            return PluginResult(plugin_id=self.id, ok=False, error=str(exc))
