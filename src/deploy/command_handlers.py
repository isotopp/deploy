from __future__ import annotations

from .apache import render_site_config
from .apache_bootstrap import run_bootstrap
from .apache_state import write_apache_state, write_tls_state_excluding
from .command_common import CommonOptions, prepare_project_for_create
from .errors import ProjectNotFoundError
from .gitops import build_update_plan
from .models import DeployProject, StaticSiteProject, WsgiSiteProject
from .output import dump_json
from .project_store import ProjectStore
from .runner import CommandResult, CommandRunner
from .runtime import RunMode
from .settings import DeploySettings
from .source_backed import (
    configure_local_git_safe_directories,
    ensure_fresh_source_backed_target,
    provision_source_backed_project,
    purge_source_backed_project,
)


def restart_httpd(options: CommonOptions) -> None:
    runner = CommandRunner(options.execution)
    # mod_md may provision a certificate on the first restart cycle and only
    # activate it on the second cycle, so this double restart is intentional.
    runner.run(["systemctl", "stop", "httpd.service"])
    runner.run(["systemctl", "start", "httpd.service"])
    runner.run(["systemctl", "stop", "httpd.service"])
    runner.run(["systemctl", "start", "httpd.service"])
    runner.run(["systemctl", "status", "httpd.service"])


def restart_httpd_forced(options: CommonOptions) -> list[str]:
    runner = CommandRunner(options.execution)
    warnings: list[str] = []
    commands = [
        ["systemctl", "stop", "httpd.service"],
        ["systemctl", "start", "httpd.service"],
        ["systemctl", "stop", "httpd.service"],
        ["systemctl", "start", "httpd.service"],
        ["systemctl", "status", "httpd.service"],
    ]
    for command in commands:
        result = runner.run(command, check=False)
        warnings.extend(_forced_command_warnings(result))
    return warnings


def _forced_command_warnings(result: CommandResult) -> list[str]:
    if result.returncode == 0:
        return []
    return [f"forced cleanup command failed ({result.returncode}): {' '.join(result.argv)}"]


def create_project(project: DeployProject, options: CommonOptions) -> int:
    project = prepare_project_for_create(project)
    ensure_fresh_source_backed_target(project, options)
    provision_source_backed_project(project, options)
    store = ProjectStore(options.project_dir, context=options.execution)
    written, warnings = write_apache_state(project, options=options, store=store)
    restart_httpd(options)
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
                    "warnings": warnings,
                    "command_log": options.execution.command_log_path(),
                }
            )
        )
        return 0

    print(f"mode: {options.execution.mode.value}")
    for label, path in written.items():
        print(f"{label}: {path}")
    for warning in warnings:
        print(f"warning: {warning}")
    if options.execution.command_log_path() is not None:
        print(f"command_log: {options.execution.command_log_path()}")
    return 0


def restart_project(name: str, options: CommonOptions) -> int:
    store = ProjectStore(options.project_dir, context=options.execution)
    project = store.load(name)
    written, warnings = write_apache_state(project, options=options, store=store)
    restart_httpd(options)
    if options.json_output:
        print(
            dump_json(
                {
                    "phase": "restart",
                    "mode": options.execution.mode.value,
                    "project": project,
                    "written": written,
                    "warnings": warnings,
                    "command_log": options.execution.command_log_path(),
                }
            )
        )
        return 0

    print(f"mode: {options.execution.mode.value}")
    for label, path in written.items():
        print(f"{label}: {path}")
    for warning in warnings:
        print(f"warning: {warning}")
    if options.execution.command_log_path() is not None:
        print(f"command_log: {options.execution.command_log_path()}")
    return 0


def delete_project(name: str, options: CommonOptions, *, force: bool = False) -> int:
    store = ProjectStore(options.project_dir, context=options.execution)
    try:
        project = store.load(name)
    except ProjectNotFoundError:
        if not force:
            raise
        warnings = [f"project already absent: {name}"]
        if options.json_output:
            print(
                dump_json(
                    {
                        "phase": "delete",
                        "mode": options.execution.mode.value,
                        "force": force,
                        "project": None,
                        "deleted": {
                            "project_file": None,
                            "apache_site_file": None,
                            "backup_archive": None,
                        },
                        "written": {"apache_tls_file": None},
                        "warnings": warnings,
                        "command_log": options.execution.command_log_path(),
                    }
                )
            )
            return 0

        print(f"mode: {options.execution.mode.value}")
        print(f"force: {force}")
        for warning in warnings:
            print(f"warning: {warning}")
        if options.execution.command_log_path() is not None:
            print(f"command_log: {options.execution.command_log_path()}")
        return 0
    deleted_project_file = store.delete(name)
    deleted_site_file = options.execution.stage_path(
        options.apache_sites_dir / f"{project.hostname}.conf"
    )
    if options.execution.mode is not RunMode.DRY_RUN:
        deleted_site_file.unlink(missing_ok=True)
    tls_file, warnings = write_tls_state_excluding(options, store, excluded_names={name})
    if force:
        warnings.extend(restart_httpd_forced(options))
        backup_archive, purge_warnings = purge_source_backed_project(project, options, force=True)
        warnings.extend(purge_warnings)
    else:
        restart_httpd(options)
        backup_archive, purge_warnings = purge_source_backed_project(project, options)
        warnings.extend(purge_warnings)
    if options.json_output:
        print(
            dump_json(
                {
                    "phase": "delete",
                    "mode": options.execution.mode.value,
                    "force": force,
                    "project": project,
                    "deleted": {
                        "project_file": deleted_project_file,
                        "apache_site_file": deleted_site_file,
                        "backup_archive": backup_archive,
                    },
                    "written": {"apache_tls_file": tls_file},
                    "warnings": warnings,
                    "command_log": options.execution.command_log_path(),
                }
            )
        )
        return 0

    print(f"mode: {options.execution.mode.value}")
    print(f"force: {force}")
    print(f"deleted project_file: {deleted_project_file}")
    print(f"deleted apache_site_file: {deleted_site_file}")
    if backup_archive is not None:
        print(f"backup_archive: {backup_archive}")
    print(f"written apache_tls_file: {tls_file}")
    for warning in warnings:
        print(f"warning: {warning}")
    if options.execution.command_log_path() is not None:
        print(f"command_log: {options.execution.command_log_path()}")
    return 0


def update_project(name: str, options: CommonOptions) -> int:
    store = ProjectStore(options.project_dir, context=options.execution)
    project = store.load(name)
    plan = build_update_plan(project)
    runner = CommandRunner(options.execution)
    if isinstance(project, (StaticSiteProject, WsgiSiteProject)):
        configure_local_git_safe_directories(project, options)
    if plan.supported and plan.working_tree is not None:
        for command in plan.commands:
            if isinstance(project, (StaticSiteProject, WsgiSiteProject)) and (
                project.source_type != "local_git" or command[0] != "git"
            ):
                runner.run(list(command), cwd=plan.working_tree, username=project.username)
            else:
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


def bootstrap_apache(mode_all: bool, mode_ip_only: bool, options: CommonOptions) -> int:
    result = run_bootstrap(
        settings=DeploySettings(),
        context=options.execution,
        mode_all=mode_all,
        mode_ip_only=mode_ip_only,
    )
    if options.json_output:
        print(
            dump_json(
                {
                    "phase": "bootstrap_apache",
                    "mode": options.execution.mode.value,
                    "all": mode_all,
                    "ip_only": mode_ip_only,
                    "written": result.written,
                    "external_ip": result.external_ip,
                    "command_log": options.execution.command_log_path(),
                }
            )
        )
        return 0

    print(f"mode: {options.execution.mode.value}")
    print(f"bootstrap_all: {mode_all}")
    print(f"bootstrap_ip_only: {mode_ip_only}")
    if result.external_ip is not None:
        print(f"external_ip: {result.external_ip}")
    for label, path in result.written.items():
        print(f"{label}: {path}")
    if options.execution.command_log_path() is not None:
        print(f"command_log: {options.execution.command_log_path()}")
    return 0
