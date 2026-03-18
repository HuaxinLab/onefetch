from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class Paths:
    project_root: Path
    data_dir: Path
    reports_dir: Path
    temp_cache_dir: Path
    feed_dir: Path
    notes_dir: Path
    catalog_file: Path


@dataclass(slots=True)
class OneFetchConfig:
    project_root: Path
    data_dir_name: str = "data"

    @classmethod
    def from_project_root(cls, project_root: str | Path | None = None) -> "OneFetchConfig":
        root = Path(project_root or ".").expanduser().resolve()
        return cls(project_root=root)

    def paths(self) -> Paths:
        data_dir = self.project_root / self.data_dir_name
        reports_dir = self.project_root / "reports"
        return Paths(
            project_root=self.project_root,
            data_dir=data_dir,
            reports_dir=reports_dir,
            temp_cache_dir=reports_dir / "cache",
            feed_dir=data_dir / "feed",
            notes_dir=data_dir / "notes",
            catalog_file=data_dir / "catalog.jsonl",
        )
