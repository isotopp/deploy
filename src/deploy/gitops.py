from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

from .models import DeployProject, StaticSiteProject, WsgiSiteProject


@dataclass(frozen=True)
class UpdatePlan:
    supported: bool
    working_tree: Path | None
    commands: tuple[tuple[str, ...], ...]
    reason: str | None = None


def discover_updater(project_root: Path) -> tuple[str, ...] | None:
    pyproject_path = project_root / "pyproject.toml"
    if not pyproject_path.exists():
        return None
    data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    tool = data.get("tool")
    if not isinstance(tool, dict):
        return None
    deploy = tool.get("deploy")
    if not isinstance(deploy, dict):
        return None
    updater = deploy.get("updater")
    if (
        not isinstance(updater, list)
        or not updater
        or not all(isinstance(item, str) for item in updater)
    ):
        return None
    return tuple(updater)


def project_working_tree(project: DeployProject) -> Path | None:
    if isinstance(project, (StaticSiteProject, WsgiSiteProject)) and project.home is not None:
        return Path(project.home) / project.project_dir
    return None


def build_update_plan(project: DeployProject) -> UpdatePlan:
    if not isinstance(project, (StaticSiteProject, WsgiSiteProject)):
        return UpdatePlan(
            supported=False,
            working_tree=None,
            commands=(),
            reason="project type has no source-backed update workflow",
        )

    working_tree = project_working_tree(project)
    if working_tree is None:
        return UpdatePlan(
            supported=False,
            working_tree=None,
            commands=(),
            reason="project has no deployed working tree location",
        )

    commands: list[tuple[str, ...]] = [
        ("git", "reset", "--hard"),
        ("git", "pull", "--rebase"),
    ]
    commands.append(("uv", "sync"))
    updater = discover_updater(working_tree)
    if updater is not None:
        commands.append(updater)

    return UpdatePlan(
        supported=True,
        working_tree=working_tree,
        commands=tuple(commands),
    )
