from __future__ import annotations

from pathlib import Path

from .apache import render_site_config
from .apache_bootstrap import run_bootstrap
from .apache_state import write_apache_state, write_tls_state_excluding
from .command_common import CommonOptions, prepare_project_for_adopt, prepare_project_for_create
from .errors import ProjectNotFoundError
from .fs import FileSystem
from .gitops import build_update_plan
from .models import CustomProject, DeployProject, GoSiteProject, StaticSiteProject, WsgiSiteProject
from .output import dump_json
from .project_store import ProjectStore
from .runner import CommandResult, CommandRunner
from .runtime import RunMode
from .settings import DeploySettings
from .source_backed import (
    configure_local_git_safe_directories,
    ensure_adoptable_source_backed_target,
    ensure_fresh_source_backed_target,
    ensure_update_safe,
    normalize_static_site_permissions,
    provision_source_backed_project,
    purge_source_backed_project,
)
from .systemd import (
    go_site_binary_name,
    go_site_service_unit_name,
    go_site_service_unit_path,
    render_go_site_service,
)


def restart_httpd(options: CommonOptions) -> None:
    runner = CommandRunner(options.execution)
    # mod_md may provision a certificate on the first restart cycle and only
    # activate it on the second cycle, so this double restart is intentional.
    runner.run(["systemctl", "stop", "httpd.service"])
    runner.run(["systemctl", "start", "httpd.service"])
    runner.run(["systemctl", "stop", "httpd.service"])
    runner.run(["systemctl", "start", "httpd.service"])
    runner.run(["systemctl", "--no-pager", "status", "httpd.service"])


def start_httpd(options: CommonOptions) -> None:
    runner = CommandRunner(options.execution)
    runner.run(["systemctl", "start", "httpd.service"])
    runner.run(["systemctl", "--no-pager", "status", "httpd.service"])


def stop_httpd(options: CommonOptions) -> None:
    runner = CommandRunner(options.execution)
    runner.run(["systemctl", "stop", "httpd.service"])


def restart_httpd_forced(options: CommonOptions) -> list[str]:
    runner = CommandRunner(options.execution)
    warnings: list[str] = []
    commands = [
        ["systemctl", "stop", "httpd.service"],
        ["systemctl", "start", "httpd.service"],
        ["systemctl", "stop", "httpd.service"],
        ["systemctl", "start", "httpd.service"],
        ["systemctl", "--no-pager", "status", "httpd.service"],
    ]
    for command in commands:
        result = runner.run(command, check=False)
        warnings.extend(_forced_command_warnings(result))
    return warnings


def _forced_command_warnings(result: CommandResult) -> list[str]:
    if result.returncode == 0:
        return []
    return [f"forced cleanup command failed ({result.returncode}): {' '.join(result.argv)}"]


def _run_go_site_lifecycle_command(
    project: GoSiteProject,
    options: CommonOptions,
    command: list[str],
    *,
    force: bool = False,
) -> list[str]:
    runner = CommandRunner(options.execution)
    result = runner.run(command, check=not force)
    return _forced_command_warnings(result) if force else []


def _go_site_checkout_path(project: GoSiteProject) -> Path:
    assert project.home is not None
    return Path(project.home) / project.project_dir


def _build_go_site_binary(project: GoSiteProject, options: CommonOptions) -> None:
    checkout_path = _go_site_checkout_path(project)
    runner = CommandRunner(options.execution)
    runner.run(
        ["go", "build", "-o", go_site_binary_name(project)],
        cwd=checkout_path,
        username=project.username,
    )


def _write_go_site_systemd_unit(project: GoSiteProject, options: CommonOptions) -> Path:
    file_system = FileSystem(options.execution)
    return file_system.write_text(
        go_site_service_unit_path(project),
        render_go_site_service(project),
    )


def _delete_go_site_systemd_unit(project: GoSiteProject, options: CommonOptions) -> Path:
    unit_path = options.execution.stage_path(go_site_service_unit_path(project))
    if options.execution.mode is not RunMode.DRY_RUN:
        unit_path.unlink(missing_ok=True)
    return unit_path


def _enable_and_start_go_site_service(project: GoSiteProject, options: CommonOptions) -> None:
    runner = CommandRunner(options.execution)
    runner.run(["systemctl", "daemon-reload"])
    runner.run(["systemctl", "enable", "--now", go_site_service_unit_name(project)])


def _delete_go_site_service(
    project: GoSiteProject,
    options: CommonOptions,
    *,
    force: bool,
) -> list[str]:
    warnings: list[str] = []
    warnings.extend(
        _run_go_site_lifecycle_command(
            project,
            options,
            ["systemctl", "disable", "--now", go_site_service_unit_name(project)],
            force=force,
        )
    )
    _delete_go_site_systemd_unit(project, options)
    warnings.extend(
        _run_go_site_lifecycle_command(
            project,
            options,
            ["systemctl", "daemon-reload"],
            force=force,
        )
    )
    return warnings


def create_project(project: DeployProject, options: CommonOptions) -> int:
    project = prepare_project_for_create(project)
    ensure_fresh_source_backed_target(project, options)
    provision_source_backed_project(project, options)
    store = ProjectStore(options.project_dir, context=options.execution)
    fragment_file: Path | None = None
    systemd_unit_file: Path | None = None
    if isinstance(project, CustomProject) and options.config_file is not None:
        fragment_file = store.save_fragment(
            project.name,
            options.config_file.read_text(encoding="utf-8"),
        )
    if isinstance(project, GoSiteProject):
        _build_go_site_binary(project, options)
        systemd_unit_file = _write_go_site_systemd_unit(project, options)
        _enable_and_start_go_site_service(project, options)
    written, warnings = write_apache_state(project, options=options, store=store)
    restart_httpd(options)
    site_config = render_site_config(project, fragment_content=store.load_fragment(project.name))
    if options.json_output:
        print(
            dump_json(
                {
                    "phase": "apply",
                    "mode": options.execution.mode.value,
                    "project": project,
                    "written": written,
                    "fragment_file": fragment_file,
                    "systemd_unit_file": systemd_unit_file,
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
    if systemd_unit_file is not None:
        print(f"systemd_unit_file: {systemd_unit_file}")
    for warning in warnings:
        print(f"warning: {warning}")
    if options.execution.command_log_path() is not None:
        print(f"command_log: {options.execution.command_log_path()}")
    return 0


def adopt_project(project: DeployProject, options: CommonOptions) -> int:
    project = prepare_project_for_adopt(project)
    ensure_adoptable_source_backed_target(project, options)
    store = ProjectStore(options.project_dir, context=options.execution)
    written, warnings = write_apache_state(project, options=options, store=store)
    restart_httpd(options)
    site_config = render_site_config(project, fragment_content=store.load_fragment(project.name))
    if options.json_output:
        print(
            dump_json(
                {
                    "phase": "adopt",
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
    if isinstance(project, GoSiteProject):
        runner = CommandRunner(options.execution)
        runner.run(["systemctl", "restart", go_site_service_unit_name(project)])
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


def start_project(name: str, options: CommonOptions) -> int:
    store = ProjectStore(options.project_dir, context=options.execution)
    project = store.load(name)
    written, warnings = write_apache_state(project, options=options, store=store)
    if isinstance(project, GoSiteProject):
        runner = CommandRunner(options.execution)
        runner.run(["systemctl", "start", go_site_service_unit_name(project)])
    start_httpd(options)
    if options.json_output:
        print(
            dump_json(
                {
                    "phase": "start",
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


def stop_project(name: str, options: CommonOptions) -> int:
    store = ProjectStore(options.project_dir, context=options.execution)
    project = store.load(name)
    stop_httpd(options)
    if isinstance(project, GoSiteProject):
        runner = CommandRunner(options.execution)
        runner.run(["systemctl", "stop", go_site_service_unit_name(project)])
    if options.json_output:
        print(
            dump_json(
                {
                    "phase": "stop",
                    "mode": options.execution.mode.value,
                    "project": project,
                    "command_log": options.execution.command_log_path(),
                }
            )
        )
        return 0

    print(f"mode: {options.execution.mode.value}")
    print(f"project: {project.name}")
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
                        "fragment_file": None,
                        "apache_site_file": None,
                        "systemd_unit_file": None,
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
    deleted_fragment_file = store.delete_fragment(name)
    deleted_systemd_unit_file: Path | None = None
    deleted_site_file = options.execution.stage_path(
        options.apache_sites_dir / f"{project.hostname}.conf"
    )
    if options.execution.mode is not RunMode.DRY_RUN:
        deleted_site_file.unlink(missing_ok=True)
    tls_file, warnings = write_tls_state_excluding(options, store, excluded_names={name})
    if isinstance(project, GoSiteProject):
        deleted_systemd_unit_file = options.execution.stage_path(go_site_service_unit_path(project))
        warnings.extend(_delete_go_site_service(project, options, force=force))
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
                        "fragment_file": deleted_fragment_file,
                        "apache_site_file": deleted_site_file,
                        "systemd_unit_file": deleted_systemd_unit_file,
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
    print(f"deleted fragment_file: {deleted_fragment_file}")
    print(f"deleted apache_site_file: {deleted_site_file}")
    if deleted_systemd_unit_file is not None:
        print(f"deleted systemd_unit_file: {deleted_systemd_unit_file}")
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
    if isinstance(project, (StaticSiteProject, WsgiSiteProject, GoSiteProject)):
        configure_local_git_safe_directories(project, options)
        ensure_update_safe(project, options)
    if plan.supported and plan.working_tree is not None:
        for command in plan.commands:
            if isinstance(project, (StaticSiteProject, WsgiSiteProject, GoSiteProject)) and (
                project.source_type != "local_git" or command[0] != "git"
            ):
                if command[0] == "systemctl":
                    runner.run(list(command), cwd=plan.working_tree)
                else:
                    runner.run(list(command), cwd=plan.working_tree, username=project.username)
            else:
                runner.run(list(command), cwd=plan.working_tree)
        normalize_static_site_permissions(project, options)
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


def logs_project(name: str, options: CommonOptions) -> int:
    store = ProjectStore(options.project_dir, context=options.execution)
    project = store.load(name)
    error_log = DeploySettings().paths.apache_log_dir / f"error-{project.hostname}.log"
    access_log = DeploySettings().paths.apache_log_dir / f"access-{project.hostname}.log"
    runner = CommandRunner(options.execution)
    if isinstance(project, GoSiteProject):
        command = (
            f"tail -F {error_log} {access_log} & "
            f"exec journalctl --no-pager -u {go_site_service_unit_name(project)} -f"
        )
        runner.run(["sh", "-lc", command])
    else:
        runner.run(["tail", "-F", str(error_log), str(access_log)])
    if options.json_output:
        print(
            dump_json(
                {
                    "phase": "logs",
                    "mode": options.execution.mode.value,
                    "project": project,
                    "files": {
                        "error_log": error_log,
                        "access_log": access_log,
                    },
                    "service_unit": (
                        go_site_service_unit_name(project)
                        if isinstance(project, GoSiteProject)
                        else None
                    ),
                    "command_log": options.execution.command_log_path(),
                }
            )
        )
        return 0

    print(f"mode: {options.execution.mode.value}")
    print(f"error_log: {error_log}")
    print(f"access_log: {access_log}")
    if options.execution.command_log_path() is not None:
        print(f"command_log: {options.execution.command_log_path()}")
    return 0


def bootstrap_apache(
    mode_all: bool,
    mode_ip_only: bool,
    options: CommonOptions,
    *,
    additional_ips: list[str],
) -> int:
    result = run_bootstrap(
        settings=DeploySettings(),
        context=options.execution,
        mode_all=mode_all,
        mode_ip_only=mode_ip_only,
        additional_ips=additional_ips,
    )
    if options.json_output:
        print(
            dump_json(
                {
                    "phase": "bootstrap_apache",
                    "mode": options.execution.mode.value,
                    "all": mode_all,
                    "ip_only": mode_ip_only,
                    "additional_ips": additional_ips,
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
    if additional_ips:
        print(f"additional_ips: {', '.join(additional_ips)}")
    if result.external_ip is not None:
        print(f"external_ip: {result.external_ip}")
    for label, path in result.written.items():
        print(f"{label}: {path}")
    if options.execution.command_log_path() is not None:
        print(f"command_log: {options.execution.command_log_path()}")
    return 0
