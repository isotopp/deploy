from __future__ import annotations

import pwd
from pathlib import Path

from .command_common import CommonOptions, source_backed_backup_path, source_backed_home
from .errors import CreatePreflightError
from .gitops import clone_command, discover_updater, local_git_safe_directories
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
    runner.run(["chown", "-R", f"{project.username}:{project.username}", str(home_path)])
    runner.run(
        list(clone_command(project, checkout_path)),
        cwd=home_path,
        username=project.username,
    )
    if isinstance(project, WsgiSiteProject):
        runner.run(["uv", "sync"], cwd=checkout_path, username=project.username)
        runner.run(["ln", "-sfn", ".venv", "venv"], cwd=checkout_path, username=project.username)

    updater: tuple[str, ...] | None = None
    if project.source_type == "local_git":
        updater = discover_updater(Path(project.source))
    elif options.execution.mode is RunMode.LIVE and checkout_path.exists():
        updater = discover_updater(checkout_path)
    if updater is not None:
        runner.run(list(updater), cwd=checkout_path, username=project.username)


def configure_local_git_safe_directories(project: DeployProject, options: CommonOptions) -> None:
    if not isinstance(project, (StaticSiteProject, WsgiSiteProject)):
        return
    runner = CommandRunner(options.execution)
    home_path = source_backed_home(project)
    for safe_directory in local_git_safe_directories(project):
        runner.run(
            ["git", "config", "--global", "--add", "safe.directory", safe_directory],
            cwd=home_path,
            username=project.username,
        )


def purge_source_backed_project(project: DeployProject, options: CommonOptions) -> Path | None:
    if not isinstance(project, (StaticSiteProject, WsgiSiteProject)):
        return None

    home_path = source_backed_home(project)
    backup_path = source_backed_backup_path(project)
    if home_path is None or backup_path is None:
        return None
    checkout_path = home_path / project.project_dir

    runner = CommandRunner(options.execution)
    archive_planned = False
    user_exists = True
    try:
        pwd.getpwnam(project.username)
    except KeyError:
        user_exists = False

    if options.execution.mode is RunMode.CONFIGTEST:
        runner.run(["rm", "-f", str(backup_path)])
        runner.run(
            [
                "tar",
                "--exclude",
                str(checkout_path),
                "-czf",
                str(backup_path),
                str(home_path),
            ]
        )
        runner.run(["userdel", "-r", project.username])
        return backup_path

    if options.execution.mode is RunMode.DRY_RUN:
        return backup_path

    if home_path.exists():
        runner.run(["rm", "-f", str(backup_path)])
        runner.run(
            [
                "tar",
                "--exclude",
                str(checkout_path),
                "-czf",
                str(backup_path),
                str(home_path),
            ]
        )
        archive_planned = True
    if user_exists:
        runner.run(["userdel", "-r", project.username])
    return backup_path if archive_planned else None
