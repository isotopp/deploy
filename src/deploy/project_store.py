from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .errors import ProjectNotFoundError, ProjectValidationError
from .models import DeployProject, project_from_record, project_path
from .runtime import ExecutionContext, RunMode


@dataclass(frozen=True)
class ProjectSummary:
    name: str
    project_type: str


@dataclass
class ProjectStore:
    project_dir: Path
    context: ExecutionContext | None = None

    @staticmethod
    def _is_project_file(path: Path) -> bool:
        return path.is_file() and not path.name.endswith(".conf")

    def fragment_path(self, name: str) -> Path:
        return self._target_dir() / f"{name}.conf"

    def _target_dir(self) -> Path:
        if self.context is not None and self.context.mode is RunMode.CONFIGTEST:
            return self.context.stage_path(self.project_dir)
        return self.project_dir

    def list_names(self) -> list[str]:
        if self.context is not None and self.context.mode is RunMode.CONFIGTEST:
            names = set[str]()
            for directory in (self.project_dir, self._target_dir()):
                if directory.exists():
                    names.update(
                        path.name for path in directory.iterdir() if self._is_project_file(path)
                    )
            return sorted(names)

        target_dir = self._target_dir()
        if not target_dir.exists():
            return []
        return sorted(path.name for path in target_dir.iterdir() if self._is_project_file(path))

    def load(self, name: str) -> DeployProject:
        record = self.load_record(name)
        return project_from_record(record, name=name)

    def load_record(self, name: str) -> dict[str, object]:
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
        if not isinstance(record, dict):
            raise ProjectValidationError(f"project {name} is not a JSON object")
        return record

    def list_summaries(self) -> list[ProjectSummary]:
        summaries: list[ProjectSummary] = []
        for name in self.list_names():
            try:
                record = self.load_record(name)
            except ProjectValidationError:
                summaries.append(ProjectSummary(name=name, project_type="<invalid>"))
                continue
            project_type = record.get("type")
            if not isinstance(project_type, str) or not project_type:
                project_type = "<invalid>"
            summaries.append(ProjectSummary(name=name, project_type=project_type))
        return summaries

    def load_supported_projects(
        self,
        *,
        excluded_names: set[str] | None = None,
    ) -> tuple[list[DeployProject], list[str]]:
        projects: list[DeployProject] = []
        warnings: list[str] = []
        excluded = excluded_names or set()
        for name in self.list_names():
            if name in excluded:
                continue
            try:
                projects.append(self.load(name))
            except ProjectValidationError as exc:
                warnings.append(f"skipping unsupported project record {name}: {exc}")
        return projects, warnings

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

    def load_fragment(self, name: str) -> str | None:
        path = self.fragment_path(name)
        if (
            self.context is not None
            and self.context.mode is RunMode.CONFIGTEST
            and not path.exists()
        ):
            path = self.project_dir / f"{name}.conf"
        if not path.exists():
            return None
        return path.read_text(encoding="utf-8")

    def save_fragment(self, name: str, content: str) -> Path:
        target = self.fragment_path(name)
        if self.context is not None and self.context.mode is RunMode.DRY_RUN:
            return target
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return target

    def delete_fragment(self, name: str) -> Path:
        target = self.fragment_path(name)
        if self.context is not None and self.context.mode is RunMode.DRY_RUN:
            return target
        target.unlink(missing_ok=True)
        return target
