from __future__ import annotations

import pwd
from dataclasses import dataclass, replace
from pathlib import Path

from .models import DeployProject, StaticSiteProject, WsgiSiteProject
from .runtime import ExecutionContext


@dataclass(frozen=True)
class CommonOptions:
    json_output: bool
    execution: ExecutionContext
    project_dir: Path
    apache_sites_dir: Path
    apache_tls_config: Path
    machine_fqdn: str


def default_home(username: str) -> str:
    try:
        return pwd.getpwnam(username).pw_dir
    except KeyError:
        return f"/home/{username}"


def prepare_project_for_create(project: DeployProject) -> DeployProject:
    if isinstance(project, (StaticSiteProject, WsgiSiteProject)) and project.home is None:
        return replace(project, home=default_home(project.username))
    return project


def source_backed_home(project: DeployProject) -> Path | None:
    if not isinstance(project, (StaticSiteProject, WsgiSiteProject)):
        return None
    home = project.home or default_home(project.username)
    return Path(home)


def source_backed_backup_path(project: DeployProject) -> Path | None:
    home_path = source_backed_home(project)
    if home_path is None:
        return None
    return home_path.with_suffix(".tgz")
