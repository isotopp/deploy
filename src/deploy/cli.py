from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from .apache import render_site_config
from .models import (
    DeployProject,
    ProxyProject,
    RedirectSiteProject,
    StaticSiteProject,
    WsgiSiteProject,
)
from .output import dump_json
from .project_store import ProjectStore
from .settings import DeploySettings


@dataclass(frozen=True)
class CommonOptions:
    json_output: bool
    project_dir: Path
    apache_sites_dir: Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="deploy")
    parser.add_argument("--json", action="store_true", dest="json_output", help="emit JSON output")
    parser.add_argument("--project-dir", type=Path, default=DeploySettings().paths.project_dir)
    parser.add_argument(
        "--apache-sites-dir",
        type=Path,
        default=DeploySettings().paths.apache_sites_dir,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    show_parser = subparsers.add_parser("show", help="show a project or list projects")
    show_parser.add_argument("name", help="project name or 'projects'")

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
    return CommonOptions(
        json_output=args.json_output,
        project_dir=args.project_dir,
        apache_sites_dir=args.apache_sites_dir,
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


def _create_preview(project: DeployProject, options: CommonOptions) -> int:
    site_config = render_site_config(project)
    project_file = options.project_dir / project.name
    apache_file = options.apache_sites_dir / site_config.filename
    if options.json_output:
        print(
            dump_json(
                {
                    "phase": "preview",
                    "project": project,
                    "project_file": project_file,
                    "apache_site_file": apache_file,
                    "apache_site": site_config,
                }
            )
        )
        return 0

    print("phase-1 preview only")
    print(f"project file: {project_file}")
    print(f"apache site file: {apache_file}")
    print()
    print(site_config.content.rstrip())
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
        return _create_preview(project, options)

    parser.error(f"unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
