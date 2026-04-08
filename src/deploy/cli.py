from __future__ import annotations

import argparse
import importlib.metadata
import json
import sys
import tomllib
from collections.abc import Sequence
from pathlib import Path

from .apache import render_site_config
from .apache_state import write_apache_state
from .command_common import CommonOptions
from .command_handlers import (
    adopt_project,
    bootstrap_apache,
    create_project,
    delete_project,
    restart_httpd,
    restart_project,
    update_project,
)
from .errors import ImportPreflightError, ProjectNotFoundError
from .models import (
    CustomProject,
    DeployProject,
    GoSiteProject,
    ProxyProject,
    RedirectSiteProject,
    StaticSiteProject,
    WsgiSiteProject,
    project_from_record,
)
from .output import dump_json
from .project_store import ProjectStore
from .runtime import ExecutionContext, RunMode, VerboseReporter
from .settings import DeploySettings


def build_parser() -> argparse.ArgumentParser:
    settings = DeploySettings()
    parser = argparse.ArgumentParser(prog="deploy")
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="emit JSON output",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="print top-level steps, command timing, and a final timing summary",
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

    export_parser = subparsers.add_parser(
        "export",
        help="export a project to ./<project> and optional ./<project>.conf",
    )
    export_parser.add_argument("name", help="project name")

    import_parser = subparsers.add_parser(
        "import",
        help="import ./<project> and optional ./<project>.conf, then restart httpd",
    )
    import_parser.add_argument("name", help="project name")

    subparsers.add_parser("version", help="print the deploy package version")

    delete_parser = subparsers.add_parser(
        "delete",
        help="remove project metadata and apache config, then restart httpd",
    )
    delete_parser.add_argument("name", help="project name")
    delete_parser.add_argument(
        "--force",
        action="store_true",
        help="continue cleanup even if restart or purge commands fail",
    )

    restart_parser = subparsers.add_parser(
        "restart",
        help="regenerate apache config and restart httpd",
    )
    restart_parser.add_argument("name", help="project name")

    start_parser = subparsers.add_parser(
        "start",
        help="regenerate apache config and start httpd",
    )
    start_parser.add_argument("name", help="project name")

    stop_parser = subparsers.add_parser(
        "stop",
        help="stop httpd",
    )
    stop_parser.add_argument("name", help="project name")

    update_parser = subparsers.add_parser(
        "update",
        help="update a source-backed deployed working tree",
    )
    update_parser.add_argument("name", help="project name")

    logs_parser = subparsers.add_parser(
        "logs",
        help="tail apache access and error logs for a project",
    )
    logs_parser.add_argument("name", help="project name")

    create_parser = subparsers.add_parser(
        "create",
        help="validate and preview a project definition",
    )
    create_subparsers = create_parser.add_subparsers(dest="project_type", required=True)

    adopt_parser = subparsers.add_parser(
        "adopt",
        help="attach deploy metadata to an existing source-backed site",
    )
    adopt_subparsers = adopt_parser.add_subparsers(dest="project_type", required=True)

    proxy_parser = create_subparsers.add_parser("proxy", help="create a proxied site preview")
    add_common_create_args(proxy_parser)
    proxy_parser.add_argument("--upstream-host", default="127.0.0.1")
    proxy_parser.add_argument("--upstream-port", "--port", type=int, required=True)
    proxy_parser.add_argument("--upstream-scheme", choices=("http", "https"), default="http")

    custom_parser = create_subparsers.add_parser(
        "custom",
        help="create a custom site from an Apache config fragment",
    )
    add_common_create_args(custom_parser)
    custom_parser.add_argument("--config-file", type=Path, required=True)

    go_parser = create_subparsers.add_parser(
        "go",
        help="create a Go service site behind the Apache proxy",
    )
    add_common_create_args(go_parser)
    go_parser.add_argument("--source-type", choices=("git", "local_git"), required=True)
    go_parser.add_argument("--source", required=True)
    go_parser.add_argument("--username", required=True)
    go_parser.add_argument("--upstream-port", "--port", type=int, required=True)
    go_parser.add_argument("--project-dir-name", default=None)
    go_parser.add_argument("--home", default=None)
    go_parser.add_argument("--binary-name", default=None)
    go_parser.add_argument("--service-name", default=None)

    adopt_go_parser = adopt_subparsers.add_parser(
        "go",
        help="adopt an existing Go service site behind the Apache proxy",
    )
    add_common_create_args(adopt_go_parser)
    adopt_go_parser.add_argument("--source-type", choices=("git", "local_git"), required=True)
    adopt_go_parser.add_argument("--source", required=True)
    adopt_go_parser.add_argument("--username", required=True)
    adopt_go_parser.add_argument("--upstream-port", "--port", type=int, required=True)
    adopt_go_parser.add_argument("--project-dir-name", default=None)
    adopt_go_parser.add_argument("--home", default=None)
    adopt_go_parser.add_argument("--binary-name", default=None)
    adopt_go_parser.add_argument("--service-name", default=None)

    redirect_parser = create_subparsers.add_parser(
        "redirect",
        help="create a redirect site preview",
    )
    add_common_create_args(redirect_parser)
    redirect_parser.add_argument("--to-hostname", required=True)

    static_parser = create_subparsers.add_parser(
        "static",
        help="create a static site preview",
    )
    add_common_create_args(static_parser)
    static_parser.add_argument("--source-type", choices=("git", "local_git"), required=True)
    static_parser.add_argument("--source", required=True)
    static_parser.add_argument("--username", required=True)
    static_parser.add_argument("--project-dir-name", default=None)
    static_parser.add_argument("--home", default=None)

    adopt_static_parser = adopt_subparsers.add_parser(
        "static",
        help="adopt an existing static site checkout",
    )
    add_common_create_args(adopt_static_parser)
    adopt_static_parser.add_argument("--source-type", choices=("git", "local_git"), required=True)
    adopt_static_parser.add_argument("--source", required=True)
    adopt_static_parser.add_argument("--username", required=True)
    adopt_static_parser.add_argument("--project-dir-name", default=None)
    adopt_static_parser.add_argument("--home", default=None)

    wsgi_parser = create_subparsers.add_parser(
        "wsgi",
        help="create a WSGI site preview",
    )
    add_common_create_args(wsgi_parser)
    wsgi_parser.add_argument("--source-type", choices=("git", "local_git"), required=True)
    wsgi_parser.add_argument("--source", required=True)
    wsgi_parser.add_argument("--username", required=True)
    wsgi_parser.add_argument("--project-dir-name", default=None)
    wsgi_parser.add_argument("--home", default=None)

    adopt_wsgi_parser = adopt_subparsers.add_parser(
        "wsgi",
        help="adopt an existing WSGI site checkout",
    )
    add_common_create_args(adopt_wsgi_parser)
    adopt_wsgi_parser.add_argument("--source-type", choices=("git", "local_git"), required=True)
    adopt_wsgi_parser.add_argument("--source", required=True)
    adopt_wsgi_parser.add_argument("--username", required=True)
    adopt_wsgi_parser.add_argument("--project-dir-name", default=None)
    adopt_wsgi_parser.add_argument("--home", default=None)

    bootstrap_parser = subparsers.add_parser(
        "bootstrap-apache",
        help="manage the shared apache baseline",
    )
    bootstrap_mode_group = bootstrap_parser.add_mutually_exclusive_group()
    bootstrap_mode_group.add_argument(
        "--all",
        action="store_true",
        dest="bootstrap_all",
        help="replace the managed apache baseline after rotating /etc/httpd to /etc/httpd.bak",
    )
    bootstrap_mode_group.add_argument(
        "--ip",
        action="store_true",
        dest="bootstrap_ip_only",
        help="only refresh the server-status/server-info IP restriction lines",
    )
    bootstrap_parser.add_argument(
        "--additional-ip",
        action="append",
        default=[],
        dest="additional_ips",
        help="additional IP address to include in the status/info ACLs; may be repeated",
    )

    return parser


def add_common_create_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("name")
    parser.add_argument("--hostname", required=True)


def common_options(args: argparse.Namespace) -> CommonOptions:
    settings = DeploySettings()
    reporter = None
    if args.verbose and not args.json_output:
        reporter = VerboseReporter(phase=args.command)
    if args.configtest is not None:
        execution = ExecutionContext(
            mode=RunMode.CONFIGTEST,
            configtest_prefix=args.configtest,
            reporter=reporter,
        )
    elif args.dry_run:
        execution = ExecutionContext(mode=RunMode.DRY_RUN, reporter=reporter)
    else:
        execution = ExecutionContext(mode=RunMode.LIVE, reporter=reporter)
    return CommonOptions(
        json_output=args.json_output,
        verbose=args.verbose,
        execution=execution,
        project_dir=args.project_dir,
        apache_sites_dir=args.apache_sites_dir,
        apache_tls_config=args.apache_tls_config,
        machine_fqdn=settings.paths.machine_fqdn,
        config_file=getattr(args, "config_file", None),
    )


def build_project_from_args(args: argparse.Namespace) -> DeployProject:
    if args.project_type == "custom":
        return CustomProject(
            name=args.name,
            project_type="custom",
            hostname=args.hostname,
            config=True,
        )
    if args.project_type == "go":
        return GoSiteProject(
            name=args.name,
            project_type="go_site",
            hostname=args.hostname,
            source_type=args.source_type,
            source=args.source,
            username=args.username,
            project_dir=args.project_dir_name or "checkout",
            upstream_port=args.upstream_port,
            home=args.home,
            managed_user=args.command != "adopt",
            managed_checkout=args.command != "adopt",
            binary_name=args.binary_name,
            service_name=args.service_name,
        )
    if args.project_type == "redirect":
        return RedirectSiteProject(
            name=args.name,
            project_type="redirect_site",
            hostname=args.hostname,
            to_hostname=args.to_hostname,
        )
    if args.project_type == "static":
        return StaticSiteProject(
            name=args.name,
            project_type="static_site",
            hostname=args.hostname,
            source_type=args.source_type,
            source=args.source,
            username=args.username,
            project_dir=args.project_dir_name or "checkout",
            home=args.home,
            managed_user=args.command != "adopt",
            managed_checkout=args.command != "adopt",
        )
    if args.project_type == "wsgi":
        return WsgiSiteProject(
            name=args.name,
            project_type="wsgi_site",
            hostname=args.hostname,
            source_type=args.source_type,
            source=args.source,
            username=args.username,
            project_dir=args.project_dir_name or "checkout",
            home=args.home,
            managed_user=args.command != "adopt",
            managed_checkout=args.command != "adopt",
        )
    return ProxyProject(
        name=args.name,
        project_type="proxy",
        hostname=args.hostname,
        upstream_host=args.upstream_host,
        upstream_port=args.upstream_port,
        upstream_scheme=args.upstream_scheme,
    )


def show_project(
    store: ProjectStore,
    name: str,
    *,
    json_output: bool,
    reporter: VerboseReporter | None = None,
) -> int:
    if name == "projects":
        with reporter.step("list projects") if reporter else _noop_context():
            summaries = store.list_summaries()
        if json_output:
            print(
                dump_json(
                    [
                        {"name": summary.name, "type": summary.project_type}
                        for summary in summaries
                    ]
                )
            )
        else:
            name_width = max((len(summary.name) for summary in summaries), default=4)
            print(f"{'NAME':<{name_width}}  TYPE")
            for summary in summaries:
                print(f"{summary.name:<{name_width}}  {summary.project_type}")
        return 0

    with reporter.step("load project") if reporter else _noop_context():
        project = store.load(name)
    with reporter.step("load fragment") if reporter else _noop_context():
        fragment_content = store.load_fragment(name)
    with reporter.step("render apache site") if reporter else _noop_context():
        site_config = render_site_config(project, fragment_content=fragment_content)
    if json_output:
        print(
            dump_json(
                {
                    "project": project,
                    "apache_site": site_config,
                    "fragment": fragment_content,
                }
            )
        )
        return 0

    print(f"project: {project.name}")
    print(f"type: {project.project_type}")
    print(f"hostname: {project.hostname}")
    print()
    if fragment_content is not None:
        print("fragment:")
        print(fragment_content.rstrip())
        print()
    if not isinstance(project, CustomProject):
        print(site_config.content.rstrip())
    return 0


def export_project(
    store: ProjectStore,
    name: str,
    *,
    json_output: bool,
    reporter: VerboseReporter | None = None,
) -> int:
    with reporter.step("load project") if reporter else _noop_context():
        project = store.load(name)
    with reporter.step("load fragment") if reporter else _noop_context():
        fragment_content = store.load_fragment(name)
    export_path = Path(name)
    with reporter.step("write export files") if reporter else _noop_context():
        export_path.write_text(dump_json(project.to_record()) + "\n", encoding="utf-8")
        wrote_fragment = False
        if fragment_content is not None:
            Path(f"{export_path}.conf").write_text(fragment_content, encoding="utf-8")
            wrote_fragment = True
    if json_output:
        print(
            dump_json(
                {
                    "project": project,
                    "export_file": export_path,
                    "fragment_file": Path(f"{export_path}.conf") if wrote_fragment else None,
                }
            )
        )
        return 0
    print(f"project_file: {export_path}")
    if wrote_fragment:
        print(f"fragment_file: {export_path}.conf")
    return 0


def import_project(
    store: ProjectStore,
    name: str,
    *,
    options: CommonOptions,
    reporter: VerboseReporter | None = None,
) -> int:
    import_path = Path(name)
    fragment_path = Path(f"{name}.conf")
    with reporter.step("load import file") if reporter else _noop_context():
        try:
            record = json.loads(import_path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise ProjectNotFoundError(f"import file {import_path} does not exist") from exc
    with reporter.step("validate import file") if reporter else _noop_context():
        if not isinstance(record, dict):
            raise ImportPreflightError("import file must contain a JSON object")
        project_name = record.get("project")
        if project_name != name:
            raise ImportPreflightError(
                "import file project field does not match command name: "
                f"{project_name!r} != {name!r}"
            )
        imported_project = project_from_record(record, name=name)
        existing_project: DeployProject | None
        try:
            existing_project = store.load(name)
        except ProjectNotFoundError:
            existing_project = None
        if (
            existing_project is not None
            and existing_project.project_type != imported_project.project_type
        ):
            raise ImportPreflightError(
                "project type changes are not allowed: "
                f"{existing_project.project_type} -> {imported_project.project_type}"
            )
        fragment_content = (
            fragment_path.read_text(encoding="utf-8") if fragment_path.exists() else None
        )
        if isinstance(imported_project, CustomProject) and fragment_content is None:
            raise ImportPreflightError(
                f"custom project import requires fragment file {fragment_path}"
            )
    import_store = ProjectStore(options.project_dir, context=options.execution)
    with reporter.step("store imported fragment") if reporter else _noop_context():
        fragment_file: Path | None = None
        if fragment_content is not None:
            fragment_file = import_store.save_fragment(name, fragment_content)
        elif existing_project is not None:
            import_store.delete_fragment(name)
    with reporter.step("write apache state") if reporter else _noop_context():
        written, warnings = write_apache_state(
            imported_project,
            options=options,
            store=import_store,
        )
    with reporter.step("restart httpd") if reporter else _noop_context():
        restart_httpd(options)
    site_config = render_site_config(
        imported_project,
        fragment_content=import_store.load_fragment(name),
    )
    if options.json_output:
        print(
            dump_json(
                {
                    "phase": "import",
                    "mode": options.execution.mode.value,
                    "project": imported_project,
                    "written": written,
                    "fragment_file": fragment_file,
                    "apache_site": site_config,
                    "warnings": warnings,
                    "command_log": options.execution.command_log_path(),
                }
            )
        )
        return 0
    print(f"mode: {options.execution.mode.value}")
    for label, path in written.items():
        print(f"{label}: {path}")
    if fragment_file is not None:
        print(f"fragment_file: {fragment_file}")
    for warning in warnings:
        print(f"warning: {warning}")
    if options.execution.command_log_path() is not None:
        print(f"command_log: {options.execution.command_log_path()}")
    return 0


def deploy_version() -> str:
    try:
        return importlib.metadata.version("deploy")
    except importlib.metadata.PackageNotFoundError:
        pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
        with pyproject.open("rb") as handle:
            data = tomllib.load(handle)
        return str(data["project"]["version"])


class _noop_context:
    def __enter__(self):
        return None

    def __exit__(self, exc_type, exc, tb):
        return False


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    options = common_options(args)
    store = ProjectStore(options.project_dir)

    if args.command == "show":
        result = show_project(
            store,
            args.name,
            json_output=options.json_output,
            reporter=options.execution.reporter,
        )
        if options.execution.reporter is not None:
            options.execution.reporter.print_summary()
        return result

    if args.command == "export":
        result = export_project(
            store,
            args.name,
            json_output=options.json_output,
            reporter=options.execution.reporter,
        )
        if options.execution.reporter is not None:
            options.execution.reporter.print_summary()
        return result

    if args.command == "import":
        result = import_project(
            store,
            args.name,
            options=options,
            reporter=options.execution.reporter,
        )
        if options.execution.reporter is not None:
            options.execution.reporter.print_summary()
        return result

    if args.command == "version":
        version = deploy_version()
        if options.json_output:
            print(dump_json({"version": version}))
        else:
            print(version)
        if options.execution.reporter is not None:
            options.execution.reporter.print_summary()
        return 0

    if args.command == "create":
        result = create_project(build_project_from_args(args), options)
        if options.execution.reporter is not None:
            options.execution.reporter.print_summary()
        return result

    if args.command == "adopt":
        result = adopt_project(build_project_from_args(args), options)
        if options.execution.reporter is not None:
            options.execution.reporter.print_summary()
        return result

    if args.command == "delete":
        result = delete_project(args.name, options, force=args.force)
        if options.execution.reporter is not None:
            options.execution.reporter.print_summary()
        return result

    if args.command == "restart":
        result = restart_project(args.name, options)
        if options.execution.reporter is not None:
            options.execution.reporter.print_summary()
        return result

    if args.command == "start":
        from .command_handlers import start_project

        result = start_project(args.name, options)
        if options.execution.reporter is not None:
            options.execution.reporter.print_summary()
        return result

    if args.command == "stop":
        from .command_handlers import stop_project

        result = stop_project(args.name, options)
        if options.execution.reporter is not None:
            options.execution.reporter.print_summary()
        return result

    if args.command == "update":
        result = update_project(args.name, options)
        if options.execution.reporter is not None:
            options.execution.reporter.print_summary()
        return result

    if args.command == "logs":
        from .command_handlers import logs_project

        result = logs_project(args.name, options)
        if options.execution.reporter is not None:
            options.execution.reporter.print_summary()
        return result

    if args.command == "bootstrap-apache":
        result = bootstrap_apache(
            args.bootstrap_all,
            args.bootstrap_ip_only,
            options,
            additional_ips=args.additional_ips,
        )
        if options.execution.reporter is not None:
            options.execution.reporter.print_summary()
        return result

    parser.error(f"unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
