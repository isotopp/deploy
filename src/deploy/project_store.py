from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .errors import ProjectNotFoundError
from .models import DeployProject, project_from_record, project_path


@dataclass
class ProjectStore:
    project_dir: Path

    def list_names(self) -> list[str]:
        if not self.project_dir.exists():
            return []
        return sorted(path.name for path in self.project_dir.iterdir() if path.is_file())

    def load(self, name: str) -> DeployProject:
        path = project_path(self.project_dir, name)
        if not path.exists():
            raise ProjectNotFoundError(f"project {name} does not exist")
        with path.open("r", encoding="utf-8") as handle:
            record = json.load(handle)
        return project_from_record(record, name=name)

    def save(self, project: DeployProject) -> Path:
        self.project_dir.mkdir(parents=True, exist_ok=True)
        path = project_path(self.project_dir, project.name)
        with path.open("w", encoding="utf-8") as handle:
            json.dump(project.to_record(), handle, indent=2, sort_keys=True)
            handle.write("\n")
        return path
