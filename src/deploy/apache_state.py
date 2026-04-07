from __future__ import annotations

from pathlib import Path

from .apache import collect_tls_hostnames, render_site_config, render_ssldomain_config
from .command_common import CommonOptions
from .fs import FileSystem
from .models import DeployProject
from .project_store import ProjectStore


def write_apache_state(
    project: DeployProject,
    *,
    options: CommonOptions,
    store: ProjectStore,
) -> tuple[dict[str, Path], list[str]]:
    file_system = FileSystem(options.execution)
    site_config = render_site_config(project, fragment_content=store.load_fragment(project.name))
    project_file = store.save(project)
    apache_site_file = file_system.write_text(
        options.apache_sites_dir / site_config.filename,
        site_config.content,
    )
    all_projects = [store.load(name) for name in store.list_names()]
    apache_sites_dirs = [options.apache_sites_dir]
    staged_sites_dir = file_system.context.stage_path(options.apache_sites_dir)
    if staged_sites_dir != options.apache_sites_dir:
        apache_sites_dirs.append(staged_sites_dir)
    hostnames, manual_hostnames = collect_tls_hostnames(
        all_projects,
        apache_sites_dirs=apache_sites_dirs,
        fqdn=options.machine_fqdn,
    )
    apache_tls_file = file_system.write_text(
        options.apache_tls_config,
        render_ssldomain_config(hostnames, fqdn=options.machine_fqdn),
    )
    return (
        {
            "project_file": project_file,
            "apache_site_file": apache_site_file,
            "apache_tls_file": apache_tls_file,
        },
        manual_domain_warnings(manual_hostnames),
    )


def write_tls_state(options: CommonOptions, store: ProjectStore) -> tuple[Path, list[str]]:
    return write_tls_state_excluding(options, store, excluded_names=set())


def write_tls_state_excluding(
    options: CommonOptions,
    store: ProjectStore,
    *,
    excluded_names: set[str],
) -> tuple[Path, list[str]]:
    file_system = FileSystem(options.execution)
    all_projects = [store.load(name) for name in store.list_names() if name not in excluded_names]
    apache_sites_dirs = [options.apache_sites_dir]
    staged_sites_dir = file_system.context.stage_path(options.apache_sites_dir)
    if staged_sites_dir != options.apache_sites_dir:
        apache_sites_dirs.append(staged_sites_dir)
    hostnames, manual_hostnames = collect_tls_hostnames(
        all_projects,
        apache_sites_dirs=apache_sites_dirs,
        fqdn=options.machine_fqdn,
    )
    return (
        file_system.write_text(
            options.apache_tls_config,
            render_ssldomain_config(hostnames, fqdn=options.machine_fqdn),
        ),
        manual_domain_warnings(manual_hostnames),
    )


def manual_domain_warnings(hostnames: list[str]) -> list[str]:
    return [f"manual site domain included in ssldomain.conf: {hostname}" for hostname in hostnames]
