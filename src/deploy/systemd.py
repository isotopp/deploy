from __future__ import annotations

from pathlib import Path

from .models import GoSiteProject
from .settings import DeploySettings


def go_site_binary_name(project: GoSiteProject) -> str:
    return project.binary_name or project.name


def go_site_service_basename(project: GoSiteProject) -> str:
    return project.service_name or project.name


def go_site_service_unit_name(project: GoSiteProject) -> str:
    return f"{go_site_service_basename(project)}.service"


def go_site_service_unit_path(project: GoSiteProject) -> Path:
    return DeploySettings().paths.systemd_unit_dir / go_site_service_unit_name(project)


def render_go_site_service(project: GoSiteProject) -> str:
    assert project.home is not None
    checkout_path = Path(project.home) / project.project_dir
    binary_path = checkout_path / go_site_binary_name(project)
    return (
        "[Unit]\n"
        f"Description={project.hostname} Go service\n"
        "After=network.target\n\n"
        "[Service]\n"
        "Type=simple\n"
        f"User={project.username}\n"
        f"Group={project.username}\n"
        f"WorkingDirectory={checkout_path}\n"
        f"ExecStart={binary_path}\n"
        "Restart=always\n"
        "RestartSec=5\n\n"
        "[Install]\n"
        "WantedBy=multi-user.target\n"
    )
