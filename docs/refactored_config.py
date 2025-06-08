#! /usr/bin/env python3

# WIP, incomplete

import argparse
from abc import ABC, abstractmethod
from dataclasses import dataclass

# from typing import Optional

DEFAULT_DOMAIN = "snackbag.net"


@dataclass(kw_only=True)
class CommonConfig:
    operation: str
    project: str
    debug: int = 0
    dry_run: bool = False
    timeout: int = 30


@dataclass
class StaticSiteConfig(CommonConfig):
    hostname: str
    github: str
    username: str
    project_dir: str


@dataclass
class RedirectSiteConfig(CommonConfig):
    hostname: str
    to_hostname: str


@dataclass
class WSGISiteConfig(CommonConfig):
    hostname: str
    github: str
    username: str
    project_dir: str


@dataclass
class DiscordBotConfig(CommonConfig):
    github: str
    username: str
    project_dir: str


@dataclass
class GoSiteConfig(CommonConfig):
    hostname: str
    github: str
    username: str
    project_dir: str
    port: int


@dataclass
class ProxySiteConfig(CommonConfig):
    hostname: str
    port: int


class Util:
    @staticmethod
    def default_hostname(project: str) -> str:
        return f"{project}.{DEFAULT_DOMAIN}"


def build_parser():
    parser = argparse.ArgumentParser(description="Deploy a service")
    parser.add_argument("-d", "--debug", action="count", default=0)
    parser.add_argument("-n", "--dry-run", action="store_true")
    parser.add_argument("--timeout", type=int, default=30)

    subparsers = parser.add_subparsers(dest="operation", required=True)

    for op in ['create', 'delete', 'show', 'start', 'stop', 'restart', 'update', 'logs']:
        op_parser = subparsers.add_parser(op)
        op_parser.add_argument("project", help="Project name")
        if op == "create":
            type_subs = op_parser.add_subparsers(dest="project_type", required=True)

            static = type_subs.add_parser("static_site", help="Deploy a static site, content from github.")
            static.add_argument("--github", required=True, help="GitHub repository starting with git@github.com:...")
            static.add_argument("--hostname",
                                help=f"Hostname, if left blank, will be set to <project_name>.{DEFAULT_DOMAIN}")
            static.add_argument("--username", help="Username, if left blank, will be set to <project_name>")
            static.add_argument("--project-dir", help="Project directory, if left blank, will be set to <project_name>")

            redirect = type_subs.add_parser("redirect_site", help="Redirect to another hostname.")
            redirect.add_argument("--to-hostname", required=True, help="Hostname to redirect to")
            redirect.add_argument("--hostname",
                                  help=f"Hostname, if left blank, will be set to <project_name>.{DEFAULT_DOMAIN}")

            wsgi = type_subs.add_parser("wsgi_site", help="Deploy a Python based WSGI (flask) site.")
            wsgi.add_argument("--github", required=True, help="GitHub repository starting with git@github.com:...")
            wsgi.add_argument("--hostname",
                              help=f"Hostname, if left blank, will be set to <project_name>.{DEFAULT_DOMAIN}")
            wsgi.add_argument("--username", help="Username, if left blank, will be set to <project_name>")
            wsgi.add_argument("--project-dir", help="Project directory, if left blank, will be set to <project_name>")

            discord = type_subs.add_parser("discord_bot", help="Deploy a Python based Discord bot.")
            discord.add_argument("--github", required=True, help="GitHub repository starting with git@github.com:...")
            discord.add_argument("--username", help="Username, if left blank, will be set to <project_name>")
            discord.add_argument("--project-dir",
                                 help="Project directory, if left blank, will be set to <project_name>")

            go = type_subs.add_parser("go_site",
                                      help="Compile and deploy a Go site, and create a reverse proxy server to a local port.")
            go.add_argument("--github", required=True, help="GitHub repository starting with git@github.com:...")
            go.add_argument("--port", required=True, type=int, help="Port to run the Go server on")
            go.add_argument("--hostname",
                            help=f"Hostname, if left blank, will be set to <project_name>.{DEFAULT_DOMAIN}")
            go.add_argument("--username", help="Username, if left blank, will be set to <project_name>")
            go.add_argument("--project-dir", help="Project directory, if left blank, will be set to <project_name>")

            proxy = type_subs.add_parser("proxy", help="Deploy a reverse proxy server to a local port.")
            proxy.add_argument("--hostname", required=True)
            proxy.add_argument("--port", required=True, type=int)

    return parser


def parse_args():
    parser = build_parser()
    args = parser.parse_args()

    common = {
        "operation": args.operation,
        "project": args.project,
        "debug": args.debug,
        "dry_run": args.dry_run,
        "timeout": args.timeout
    }

    if args.operation == "create":
        match args.project_type:
            case "static_site":
                if args.hostname is None:
                    args.hostname = Util.default_hostname(args.project)
                if args.username is None:
                    args.username = args.project
                if args.project_dir is None:
                    args.project_dir = args.project

                return StaticSiteConfig(**common,
                                        hostname=args.hostname,
                                        github=args.github,
                                        username=args.username,
                                        project_dir=args.project_dir)

            case "redirect_site":
                if args.hostname is None:
                    args.hostname = Util.default_hostname(args.project)

                return RedirectSiteConfig(**common,
                                          hostname=args.hostname,
                                          to_hostname=args.to_hostname)

            case "wsgi_site":
                if args.hostname is None:
                    args.hostname = Util.default_hostname(args.project)
                if args.username is None:
                    args.username = args.project
                if args.project_dir is None:
                    args.project_dir = args.project

                return WSGISiteConfig(**common,
                                      hostname=args.hostname,
                                      github=args.github,
                                      username=args.username,
                                      project_dir=args.project_dir)

            case "discord_bot":
                if args.username is None:
                    args.username = args.project
                if args.project_dir is None:
                    args.project_dir = args.project

                return DiscordBotConfig(**common,
                                        github=args.github,
                                        username=args.username,
                                        project_dir=args.project_dir)

            case "go_site":
                if args.hostname is None:
                    args.hostname = Util.default_hostname(args.project)
                if args.username is None:
                    args.username = args.project
                if args.project_dir is None:
                    args.project_dir = args.project

                return GoSiteConfig(**common,
                                    hostname=args.hostname,
                                    github=args.github,
                                    username=args.username,
                                    project_dir=args.project_dir,
                                    port=args.port)
            case "proxy":
                if args.hostname is None:
                    args.hostname = Util.default_hostname(args.project)

                return ProxySiteConfig(**common,
                                       hostname=args.hostname,
                                       port=args.port)

    else:
        return CommonConfig(**common)


class BaseDeployer(ABC):
    def __init__(self, config):
        self.config = config

    def run(self):
        operation = self.config.operation
        if operation == "create":
            self.create()
        elif operation == "delete":
            self.delete()
        elif operation == "show":
            self.show()
        elif operation == "start":
            self.start()
        elif operation == "stop":
            self.stop()
        elif operation == "restart":
            self.restart()
        elif operation == "update":
            self.update()
        elif operation == "logs":
            self.logs()
        else:
            raise ValueError(f"Unknown operation {operation}")

    @abstractmethod
    def create(self):
        ...

    def delete(self):
        ...

    def show(self):
        ...

    def start(self):
        ...

    def stop(self):
        ...

    def restart(self):
        ...

    def update(self):
        ...

    def logs(self):
        ...


class StaticSiteDeployer(BaseDeployer):
    def create(self):
        print(f"[+] Creating static site: {self.config.project}")
        print(f"    - Cloning {self.config.github} into {self.config.project_dir}")
        print(f"    - Setting up Apache vhost for {self.config.hostname}")

    def delete(self):
        print(f"[-] Deleting static site: {self.config.project}")

    def show(self):
        print(f"[-] Showing static site: {self.config.project}")

    def start(self):
        print(f"[+] Starting static site: {self.config.project}")

    def stop(self):
        print(f"[-] Stopping static site: {self.config.project}")

    def restart(self):
        print(f"[~] Restarting static site: {self.config.project}")

    def update(self):
        print(f"[~] Updating static site: {self.config.project}")

    def logs(self):
        print(f"[-] Tailing logs for static site: {self.config.project}")


def dispatch(config: CommonConfig):
    match config:
        case StaticSiteConfig():
            StaticSiteDeployer(config).run()
        case RedirectSiteConfig():
            RedirectSiteDeployer(config).run()
        case WSGISiteConfig():
            WSGISiteDeployer(config).run()
        case DiscordBotConfig():
            DiscordBotDeployer(config).run()
        case GoSiteConfig():
            GoSiteDeployer(config).run()
        case ProxySiteConfig():
            ProxySiteDeployer(config).run()
        case CommonConfig():
            if config.operation == "show":
                if config.project == "projects":
                    print("[-] Showing all projects")
                else:
                    print(f"[-] Showing project: {config.project}")
            else:
                raise ValueError(f"Unhandled operation for {type(config).__name__}")

if __name__ == "__main__":
    config = parse_args()
    print(f"{config}")  # or dispatch(config)
    dispatch(config)
