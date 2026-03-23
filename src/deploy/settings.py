from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class DeployPaths:
    project_dir: Path = Path("/etc/projects")
    apache_sites_dir: Path = Path("/etc/httpd/conf.sites.d")
    apache_tls_config: Path = Path("/etc/httpd/conf.d/ssldomain.conf")
    apache_macros_config: Path = Path("/etc/httpd/conf.d/macros.conf")


@dataclass(frozen=True)
class DeploySettings:
    paths: DeployPaths = field(default_factory=DeployPaths)
    ssl_domain_list: tuple[str, ...] = (
        "vaultwarden.home.koehntopp.de",
        "unifi.home.koehntopp.de",
        "kris.home.koehntopp.de",
        "hass.home.koehntopp.de",
    )
