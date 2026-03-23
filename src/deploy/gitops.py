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


def _resolved_source_path(source: str) -> Path:
    path = Path(source).expanduser()
    if path.is_absolute():
        return path
    return path.resolve()


def _safe_directory_args(source_path: Path) -> tuple[str, ...]:
    git_dir = source_path / ".git"
    return (str(source_path), str(git_dir))


def local_git_safe_directories(project: StaticSiteProject | WsgiSiteProject) -> tuple[str, ...]:
    if project.source_type != "local_git":
        return ()
    source_path = _resolved_source_path(project.source)
    return _safe_directory_args(source_path)


def clone_command(
    project: StaticSiteProject | WsgiSiteProject, checkout_path: Path
) -> tuple[str, ...]:
    source = project.source
    if project.source_type == "local_git":
        source = str(_resolved_source_path(project.source))
    return ("git", "clone", source, str(checkout_path))


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

    commands: list[tuple[str, ...]] = [("git", "reset", "--hard")]
    commands.append(("git", "pull", "--rebase"))
    commands.append(("uv", "sync"))
    updater = discover_updater(working_tree)
    if updater is not None:
        commands.append(updater)

    return UpdatePlan(
        supported=True,
        working_tree=working_tree,
        commands=tuple(commands),
    )
