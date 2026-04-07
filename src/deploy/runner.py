from __future__ import annotations

import os
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from .errors import CommandExecutionError
from .runtime import ExecutionContext, RunMode, shell_join


@dataclass(frozen=True)
class CommandResult:
    argv: tuple[str, ...]
    returncode: int


@dataclass
class CommandRunner:
    context: ExecutionContext

    def run(
        self,
        argv: Sequence[str],
        *,
        cwd: Path | None = None,
        username: str | None = None,
        check: bool = True,
        env: dict[str, str] | None = None,
    ) -> CommandResult:
        command = tuple(argv)
        effective_command = command
        effective_env = env
        effective_cwd = cwd
        if username is not None:
            inner_command = command
            if cwd is not None:
                script = f"cd {shell_join([str(cwd)])} && exec {shell_join(command)}"
                inner_command = ("sh", "-lc", script)
                effective_cwd = None
            inline_env_prefix: tuple[str, ...] = ()
            if env is not None:
                inline_env_prefix = (
                    "env",
                    *(f"{key}={value}" for key, value in sorted(env.items())),
                )
                effective_env = None
            effective_command = ("sudo", "-u", username, "--", *inline_env_prefix, *inner_command)
        reporter = self.context.reporter
        started_at: float | None = None
        command_text = shell_join(effective_command)
        if reporter is not None:
            started_at = reporter.command_started(command_text)
        if self.context.mode is RunMode.LIVE:
            subprocess_env = None
            if effective_env is not None:
                subprocess_env = os.environ.copy()
                subprocess_env.update(effective_env)
            completed = subprocess.run(
                effective_command,
                cwd=effective_cwd,
                check=False,
                env=subprocess_env,
            )
            result = CommandResult(argv=effective_command, returncode=completed.returncode)
            if reporter is not None and started_at is not None:
                reporter.command_finished(command_text, started_at, completed.returncode)
            if check and completed.returncode != 0:
                joined_command = shell_join(effective_command)
                raise CommandExecutionError(
                    f"command failed with exit code {completed.returncode}: {joined_command}"
                )
            return result

        if self.context.mode is RunMode.CONFIGTEST:
            log_path = self.context.command_log_path()
            assert log_path is not None
            log_path.parent.mkdir(parents=True, exist_ok=True)
            if not log_path.exists():
                log_path.write_text("#!/bin/sh\nset -eu\n\n", encoding="utf-8")
            with log_path.open("a", encoding="utf-8") as handle:
                if cwd is not None and username is None:
                    handle.write(f"cd {shell_join([str(cwd)])}\n")
                if env is not None and username is None:
                    logged_env_prefix = " ".join(
                        shell_join([f"{key}={value}"]) for key, value in sorted(env.items())
                    )
                    handle.write(f"env {logged_env_prefix} ")
                handle.write(f"{shell_join(effective_command)}\n")
            if reporter is not None and started_at is not None:
                reporter.command_finished(command_text, started_at, 0)
            return CommandResult(argv=effective_command, returncode=0)

        if reporter is not None and started_at is not None:
            reporter.command_finished(command_text, started_at, 0)
        return CommandResult(argv=effective_command, returncode=0)
