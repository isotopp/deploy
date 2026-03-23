from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .models import DeployProject, StaticSiteProject, WsgiSiteProject


@dataclass(frozen=True)
class UpdatePlan:
    supported: bool
    working_tree: Path | None
    commands: tuple[tuple[str, ...], ...]
    reason: str | None = None


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
    if isinstance(project, WsgiSiteProject):
        commands.append(("venv/bin/python", "-m", "pip", "install", "-r", "requirements.txt"))

    return UpdatePlan(
        supported=True,
        working_tree=working_tree,
        commands=tuple(commands),
    )
