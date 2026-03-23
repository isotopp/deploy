from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .errors import ProjectNotFoundError
from .models import DeployProject, project_from_record, project_path
from .runtime import ExecutionContext, RunMode


@dataclass
class ProjectStore:
    project_dir: Path
    context: ExecutionContext | None = None

    def _target_dir(self) -> Path:
        if self.context is not None and self.context.mode is RunMode.CONFIGTEST:
            return self.context.stage_path(self.project_dir)
        return self.project_dir

    def list_names(self) -> list[str]:
        if self.context is not None and self.context.mode is RunMode.CONFIGTEST:
            names = set[str]()
            for directory in (self.project_dir, self._target_dir()):
                if directory.exists():
                    names.update(path.name for path in directory.iterdir() if path.is_file())
            return sorted(names)

        target_dir = self._target_dir()
        if not target_dir.exists():
            return []
        return sorted(path.name for path in target_dir.iterdir() if path.is_file())

    def load(self, name: str) -> DeployProject:
        path = project_path(self._target_dir(), name)
        if (
            self.context is not None
            and self.context.mode is RunMode.CONFIGTEST
            and not path.exists()
        ):
            path = project_path(self.project_dir, name)
        if not path.exists():
            raise ProjectNotFoundError(f"project {name} does not exist")
        with path.open("r", encoding="utf-8") as handle:
            record = json.load(handle)
        return project_from_record(record, name=name)

    def save(self, project: DeployProject) -> Path:
        target = project_path(self._target_dir(), project.name)
        if self.context is not None and self.context.mode is RunMode.DRY_RUN:
            return target
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8") as handle:
            json.dump(project.to_record(), handle, indent=2, sort_keys=True)
            handle.write("\n")
        return target

    def delete(self, name: str) -> Path:
        target = project_path(self._target_dir(), name)
        if self.context is not None and self.context.mode is RunMode.DRY_RUN:
            return target
        target.unlink(missing_ok=True)
        return target
