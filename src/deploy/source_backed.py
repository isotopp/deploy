from __future__ import annotations

import pwd
import subprocess
from pathlib import Path

from .command_common import CommonOptions, source_backed_backup_path, source_backed_home
from .errors import CreatePreflightError
from .gitops import (
    clone_command,
    discover_updater,
    local_git_safe_directories,
    normalize_runtime_command,
    resolved_uv_executable,
)
from .models import DeployProject, StaticSiteProject, WsgiSiteProject
from .runner import CommandRunner
from .runtime import RunMode


def ensure_fresh_source_backed_target(project: DeployProject, options: CommonOptions) -> None:
    if not isinstance(project, (StaticSiteProject, WsgiSiteProject)):
        return

    if options.execution.mode is not RunMode.LIVE:
        return

    assert project.home is not None
    home_path = Path(project.home)
    checkout_path = home_path / project.project_dir

    try:
        pwd.getpwnam(project.username)
    except KeyError:
        pass
    else:
        raise CreatePreflightError(f"user already exists: {project.username}")

    if home_path.exists():
        raise CreatePreflightError(f"home already exists: {home_path}")
    if checkout_path.exists():
        raise CreatePreflightError(f"checkout already exists: {checkout_path}")


def provision_source_backed_project(project: DeployProject, options: CommonOptions) -> None:
    if not isinstance(project, (StaticSiteProject, WsgiSiteProject)):
        return

    assert project.home is not None
    home_path = Path(project.home)
    checkout_path = home_path / project.project_dir
    runner = CommandRunner(options.execution)

    runner.run(["useradd", "-m", "-c", f"Project {project.name} owner", project.username])
    runner.run(["mkdir", "-p", str(home_path)])
    configure_local_git_safe_directories(project, options)
    clone_username = project.username if project.source_type == "git" else None
    runner.run(
        list(clone_command(project, checkout_path)),
        cwd=home_path,
        username=clone_username,
    )
    runner.run(["chown", "-R", f"{project.username}:{project.username}", str(home_path)])
    if isinstance(project, WsgiSiteProject):
        runner.run([resolved_uv_executable(), "sync"], cwd=checkout_path, username=project.username)
        runner.run(["ln", "-sfn", ".venv", "venv"], cwd=checkout_path, username=project.username)

    updater: tuple[str, ...] | None = None
    if project.source_type == "local_git":
        updater = discover_updater(Path(project.source))
    elif options.execution.mode is RunMode.LIVE and checkout_path.exists():
        updater = discover_updater(checkout_path)
    if updater is not None:
        runner.run(
            list(normalize_runtime_command(updater)),
            cwd=checkout_path,
            username=project.username,
        )


def configure_local_git_safe_directories(project: DeployProject, options: CommonOptions) -> None:
    if not isinstance(project, (StaticSiteProject, WsgiSiteProject)):
        return
    desired_safe_directories = _desired_safe_directories(project)
    existing_safe_directories = set()
    if options.execution.mode is RunMode.LIVE:
        existing_safe_directories = _existing_safe_directories()
    runner = CommandRunner(options.execution)
    for safe_directory in desired_safe_directories:
        if safe_directory in existing_safe_directories:
            continue
        runner.run(
            ["git", "config", "--global", "--add", "safe.directory", safe_directory],
        )


def purge_source_backed_project(
    project: DeployProject, options: CommonOptions, *, force: bool = False
) -> tuple[Path | None, list[str]]:
    if not isinstance(project, (StaticSiteProject, WsgiSiteProject)):
        return None, []

    home_path = source_backed_home(project)
    backup_path = source_backed_backup_path(project)
    if home_path is None or backup_path is None:
        return None, []
    checkout_path = home_path / project.project_dir

    runner = CommandRunner(options.execution)
    archive_planned = False
    warnings: list[str] = []
    user_exists = True
    try:
        pwd.getpwnam(project.username)
    except KeyError:
        user_exists = False

    if options.execution.mode is RunMode.CONFIGTEST:
        runner.run(["rm", "-f", str(backup_path)], check=not force)
        runner.run(
            [
                "tar",
                "--exclude",
                str(checkout_path),
                "-czf",
                str(backup_path),
                str(home_path),
            ],
            check=not force,
        )
        runner.run(["userdel", "-r", project.username], check=not force)
        return backup_path, warnings

    if options.execution.mode is RunMode.DRY_RUN:
        return backup_path, warnings

    if home_path.exists():
        rm_result = runner.run(["rm", "-f", str(backup_path)], check=not force)
        warnings.extend(_forced_warnings(rm_result, force))
        tar_result = runner.run(
            [
                "tar",
                "--exclude",
                str(checkout_path),
                "-czf",
                str(backup_path),
                str(home_path),
            ],
            check=not force,
        )
        warnings.extend(_forced_warnings(tar_result, force))
        if tar_result.returncode == 0:
            archive_planned = True
    if user_exists:
        userdel_result = runner.run(["userdel", "-r", project.username], check=not force)
        warnings.extend(_forced_warnings(userdel_result, force))
    return (backup_path if archive_planned else None), warnings


def _forced_warnings(result, force: bool) -> list[str]:
    if not force or result.returncode == 0:
        return []
    return [f"forced cleanup command failed ({result.returncode}): {' '.join(result.argv)}"]


def _desired_safe_directories(project: StaticSiteProject | WsgiSiteProject) -> tuple[str, ...]:
    checkout_path = Path(project.home or source_backed_home(project) or "") / project.project_dir
    desired = [
        *local_git_safe_directories(project),
        str(checkout_path),
        str(checkout_path / ".git"),
    ]
    deduped: list[str] = []
    seen: set[str] = set()
    for path in desired:
        if path and path not in seen:
            seen.add(path)
            deduped.append(path)
    return tuple(deduped)


def _existing_safe_directories() -> set[str]:
    completed = subprocess.run(
        ["git", "config", "--global", "--get-all", "safe.directory"],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode not in {0, 1}:
        return set()
    return {line.strip() for line in completed.stdout.splitlines() if line.strip()}
