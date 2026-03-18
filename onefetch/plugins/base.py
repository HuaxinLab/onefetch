from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from typing import Protocol


@dataclass
class PluginTask:
    plugin_id: str
    url: str = ""
    options: dict[str, Any] = field(default_factory=dict)


@dataclass
class PluginResult:
    plugin_id: str
    ok: bool
    value: str = ""
    error: str = ""
    meta: dict[str, Any] = field(default_factory=dict)


class Plugin(Protocol):
    id: str
    description: str

    def supports(self, task: PluginTask) -> bool: ...

    def run(self, task: PluginTask) -> PluginResult: ...
