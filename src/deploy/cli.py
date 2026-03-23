from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from .apache import collect_hostnames, render_site_config, render_ssldomain_config
from .fs import FileSystem
from .gitops import build_update_plan
from .models import (
    DeployProject,
    ProxyProject,
    RedirectSiteProject,
    StaticSiteProject,
    WsgiSiteProject,
)
from .output import dump_json
from .project_store import ProjectStore
from .runner import CommandRunner
from .runtime import ExecutionContext, RunMode
from .settings import DeploySettings


@dataclass(frozen=True)
class CommonOptions:
    json_output: bool
    execution: ExecutionContext
    project_dir: Path
    apache_sites_dir: Path
    apache_tls_config: Path
    machine_fqdn: str
    ssl_domain_list: tuple[str, ...]


def build_parser() -> argparse.ArgumentParser:
    settings = DeploySettings()
    parser = argparse.ArgumentParser(prog="deploy")
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="emit JSON output",
    )
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--dry-run",
        action="store_true",
        help="preview without writing or running",
    )
    mode_group.add_argument(
        "--configtest",
        type=Path,
        help="write generated files under a prefix and log commands to cmdlog.sh",
    )
    parser.add_argument("--project-dir", type=Path, default=settings.paths.project_dir)
    parser.add_argument(
        "--apache-sites-dir",
        type=Path,
        default=settings.paths.apache_sites_dir,
    )
    parser.add_argument(
        "--apache-tls-config",
        type=Path,
        default=settings.paths.apache_tls_config,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    show_parser = subparsers.add_parser("show", help="show a project or list projects")
    show_parser.add_argument("name", help="project name or 'projects'")

    delete_parser = subparsers.add_parser(
        "delete",
        help="remove project metadata and apache config, then restart httpd",
    )
    delete_parser.add_argument("name", help="project name")

    restart_parser = subparsers.add_parser(
        "restart",
        help="regenerate apache config and restart httpd",
    )
    restart_parser.add_argument("name", help="project name")

    update_parser = subparsers.add_parser(
        "update",
        help="update a source-backed deployed working tree",
    )
    update_parser.add_argument("name", help="project name")

    create_parser = subparsers.add_parser(
        "create",
        help="validate and preview a project definition",
    )
    create_subparsers = create_parser.add_subparsers(dest="project_type", required=True)

    proxy_parser = create_subparsers.add_parser("proxy", help="create a proxied site preview")
    _add_common_create_args(proxy_parser)
    proxy_parser.add_argument("--upstream-host", default="127.0.0.1")
    proxy_parser.add_argument("--upstream-port", "--port", type=int, required=True)
    proxy_parser.add_argument("--upstream-scheme", choices=("http", "https"), default="http")

    redirect_parser = create_subparsers.add_parser(
        "redirect-site",
        aliases=["redirect_site"],
        help="create a redirect site preview",
    )
    _add_common_create_args(redirect_parser)
    redirect_parser.add_argument("--to-hostname", required=True)

    static_parser = create_subparsers.add_parser(
        "static-site",
        aliases=["static_site"],
        help="create a static site preview",
    )
    _add_common_create_args(static_parser)
    static_parser.add_argument("--source", required=True)
    static_parser.add_argument("--username", required=True)
    static_parser.add_argument("--project-dir-name", default=None)
    static_parser.add_argument("--home", default=None)

    wsgi_parser = create_subparsers.add_parser(
        "wsgi-site",
        aliases=["wsgi_site"],
        help="create a WSGI site preview",
    )
    _add_common_create_args(wsgi_parser)
    wsgi_parser.add_argument("--source", required=True)
    wsgi_parser.add_argument("--username", required=True)
    wsgi_parser.add_argument("--project-dir-name", default=None)
    wsgi_parser.add_argument("--home", default=None)

    return parser


def _add_common_create_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("name")
    parser.add_argument("--hostname", required=True)


def _common_options(args: argparse.Namespace) -> CommonOptions:
    settings = DeploySettings()
    if args.configtest is not None:
        execution = ExecutionContext(mode=RunMode.CONFIGTEST, configtest_prefix=args.configtest)
    elif args.dry_run:
        execution = ExecutionContext(mode=RunMode.DRY_RUN)
    else:
        execution = ExecutionContext(mode=RunMode.LIVE)
    return CommonOptions(
        json_output=args.json_output,
        execution=execution,
        project_dir=args.project_dir,
        apache_sites_dir=args.apache_sites_dir,
        apache_tls_config=args.apache_tls_config,
        machine_fqdn=settings.paths.machine_fqdn,
        ssl_domain_list=settings.ssl_domain_list,
    )


def _build_project_from_args(args: argparse.Namespace) -> DeployProject:
    if args.project_type in {"redirect-site", "redirect_site"}:
        return RedirectSiteProject(
            name=args.name,
            project_type="redirect_site",
            hostname=args.hostname,
            to_hostname=args.to_hostname,
        )
    if args.project_type in {"static-site", "static_site"}:
        return StaticSiteProject(
            name=args.name,
            project_type="static_site",
            hostname=args.hostname,
            source=args.source,
            username=args.username,
            project_dir=args.project_dir_name or args.name,
            home=args.home,
        )
    if args.project_type in {"wsgi-site", "wsgi_site"}:
        return WsgiSiteProject(
            name=args.name,
            project_type="wsgi_site",
            hostname=args.hostname,
            source=args.source,
            username=args.username,
            project_dir=args.project_dir_name or args.name,
            home=args.home,
        )
    return ProxyProject(
        name=args.name,
        project_type="proxy",
        hostname=args.hostname,
        upstream_host=args.upstream_host,
        upstream_port=args.upstream_port,
        upstream_scheme=args.upstream_scheme,
    )


def _show_project(store: ProjectStore, name: str, *, json_output: bool) -> int:
    if name == "projects":
        names = store.list_names()
        if json_output:
            print(dump_json({"projects": names}))
        else:
            for project_name in names:
                print(f"- {project_name}")
        return 0

    project = store.load(name)
    site_config = render_site_config(project)
    if json_output:
        print(dump_json({"project": project, "apache_site": site_config}))
        return 0

    print(f"project: {project.name}")
    print(f"type: {project.project_type}")
    print(f"hostname: {project.hostname}")
    print()
    print(site_config.content.rstrip())
    return 0


def _write_apache_state(
    project: DeployProject,
    *,
    options: CommonOptions,
    store: ProjectStore,
) -> dict[str, Path]:
    file_system = FileSystem(options.execution)
    site_config = render_site_config(project)
    project_file = store.save(project)
    apache_site_file = file_system.write_text(
        options.apache_sites_dir / site_config.filename,
        site_config.content,
    )
    all_projects = [store.load(name) for name in store.list_names()]
    hostnames = collect_hostnames(
        all_projects,
        options.ssl_domain_list,
        fqdn=options.machine_fqdn,
    )
    apache_tls_file = file_system.write_text(
        options.apache_tls_config,
        render_ssldomain_config(hostnames, fqdn=options.machine_fqdn),
    )
    return {
        "project_file": project_file,
        "apache_site_file": apache_site_file,
        "apache_tls_file": apache_tls_file,
    }


def _restart_httpd(options: CommonOptions) -> None:
    runner = CommandRunner(options.execution)
    runner.run(["systemctl", "stop", "httpd.service"])
    runner.run(["systemctl", "start", "httpd.service"])
    runner.run(["systemctl", "stop", "httpd.service"])
    runner.run(["systemctl", "start", "httpd.service"])
    runner.run(["systemctl", "status", "httpd.service"])


def _write_tls_state(options: CommonOptions, store: ProjectStore) -> Path:
    return _write_tls_state_excluding(options, store, excluded_names=set())


def _write_tls_state_excluding(
    options: CommonOptions,
    store: ProjectStore,
    *,
    excluded_names: set[str],
) -> Path:
    file_system = FileSystem(options.execution)
    all_projects = [store.load(name) for name in store.list_names() if name not in excluded_names]
    hostnames = collect_hostnames(
        all_projects,
        options.ssl_domain_list,
        fqdn=options.machine_fqdn,
    )
    return file_system.write_text(
        options.apache_tls_config,
        render_ssldomain_config(hostnames, fqdn=options.machine_fqdn),
    )


def _create_project(project: DeployProject, options: CommonOptions) -> int:
    store = ProjectStore(options.project_dir, context=options.execution)
    written = _write_apache_state(project, options=options, store=store)
    _restart_httpd(options)
    site_config = render_site_config(project)
    if options.json_output:
        print(
            dump_json(
                {
                    "phase": "apply",
                    "mode": options.execution.mode.value,
                    "project": project,
                    "written": written,
                    "apache_site": site_config,
                    "command_log": options.execution.command_log_path(),
                }
            )
        )
        return 0

    print(f"mode: {options.execution.mode.value}")
    for label, path in written.items():
        print(f"{label}: {path}")
    if options.execution.command_log_path() is not None:
        print(f"command_log: {options.execution.command_log_path()}")
    return 0


def _restart_project(name: str, options: CommonOptions) -> int:
    store = ProjectStore(options.project_dir, context=options.execution)
    project = store.load(name)
    written = _write_apache_state(project, options=options, store=store)
    _restart_httpd(options)
    if options.json_output:
        print(
            dump_json(
                {
                    "phase": "restart",
                    "mode": options.execution.mode.value,
                    "project": project,
                    "written": written,
                    "command_log": options.execution.command_log_path(),
                }
            )
        )
        return 0

    print(f"mode: {options.execution.mode.value}")
    for label, path in written.items():
        print(f"{label}: {path}")
    if options.execution.command_log_path() is not None:
        print(f"command_log: {options.execution.command_log_path()}")
    return 0


def _delete_project(name: str, options: CommonOptions) -> int:
    store = ProjectStore(options.project_dir, context=options.execution)
    project = store.load(name)
    deleted_project_file = store.delete(name)
    deleted_site_file = options.execution.stage_path(
        options.apache_sites_dir / f"{project.hostname}.conf"
    )
    if options.execution.mode is not RunMode.DRY_RUN:
        deleted_site_file.unlink(missing_ok=True)
    tls_file = _write_tls_state_excluding(options, store, excluded_names={name})
    _restart_httpd(options)
    if options.json_output:
        print(
            dump_json(
                {
                    "phase": "delete",
                    "mode": options.execution.mode.value,
                    "project": project,
                    "deleted": {
                        "project_file": deleted_project_file,
                        "apache_site_file": deleted_site_file,
                    },
                    "written": {"apache_tls_file": tls_file},
                    "command_log": options.execution.command_log_path(),
                }
            )
        )
        return 0

    print(f"mode: {options.execution.mode.value}")
    print(f"deleted project_file: {deleted_project_file}")
    print(f"deleted apache_site_file: {deleted_site_file}")
    print(f"written apache_tls_file: {tls_file}")
    if options.execution.command_log_path() is not None:
        print(f"command_log: {options.execution.command_log_path()}")
    return 0


def _update_project(name: str, options: CommonOptions) -> int:
    store = ProjectStore(options.project_dir, context=options.execution)
    project = store.load(name)
    plan = build_update_plan(project)
    runner = CommandRunner(options.execution)
    if plan.supported and plan.working_tree is not None:
        for command in plan.commands:
            runner.run(list(command), cwd=plan.working_tree)
    if options.json_output:
        print(
            dump_json(
                {
                    "phase": "update",
                    "mode": options.execution.mode.value,
                    "project": project,
                    "supported": plan.supported,
                    "working_tree": plan.working_tree,
                    "commands": plan.commands,
                    "reason": plan.reason,
                    "command_log": options.execution.command_log_path(),
                }
            )
        )
        return 0

    print(f"mode: {options.execution.mode.value}")
    print(f"supported: {plan.supported}")
    if plan.reason is not None:
        print(f"reason: {plan.reason}")
    if plan.working_tree is not None:
        print(f"working_tree: {plan.working_tree}")
    for command in plan.commands:
        print("command:", " ".join(command))
    if options.execution.command_log_path() is not None:
        print(f"command_log: {options.execution.command_log_path()}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    options = _common_options(args)
    store = ProjectStore(options.project_dir)

    if args.command == "show":
        return _show_project(store, args.name, json_output=options.json_output)

    if args.command == "create":
        project = _build_project_from_args(args)
        return _create_project(project, options)

    if args.command == "delete":
        return _delete_project(args.name, options)

    if args.command == "restart":
        return _restart_project(args.name, options)

    if args.command == "update":
        return _update_project(args.name, options)

    parser.error(f"unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
