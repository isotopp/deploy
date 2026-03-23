from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class DeployPaths:
    project_dir: Path = Path("/etc/projects")
    httpd_conf: Path = Path("/etc/httpd/conf/httpd.conf")
    apache_sites_dir: Path = Path("/etc/httpd/conf.sites.d")
    apache_log_dir: Path = Path("/var/log/httpd")
    apache_tls_config: Path = Path("/etc/httpd/conf.d/ssldomain.conf")
    apache_macros_config: Path = Path("/etc/httpd/conf.d/macros.conf")
    ssl_conf: Path = Path("/etc/httpd/conf.d/ssl.conf")
    brotli_module_conf: Path = Path("/etc/httpd/conf.modules.d/00-brotli.conf")
    dav_module_conf: Path = Path("/etc/httpd/conf.modules.d/00-dav.conf")
    cgi_module_conf: Path = Path("/etc/httpd/conf.modules.d/01-cgi.conf")
    httpd_logrotate: Path = Path("/etc/logrotate.d/httpd")
    apache_sites_include: str = "IncludeOptional conf.sites.d/*.conf"
    machine_fqdn: str = "server.home.koehntopp.de"


@dataclass(frozen=True)
class DeploySettings:
    paths: DeployPaths = field(default_factory=DeployPaths)
