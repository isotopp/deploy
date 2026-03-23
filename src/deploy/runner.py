from __future__ import annotations

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
    ) -> CommandResult:
        command = tuple(argv)
        effective_command = command
        if username is not None:
            effective_command = ("sudo", "-u", username, "--", *command)
        if self.context.mode is RunMode.LIVE:
            completed = subprocess.run(effective_command, cwd=cwd, check=False)
            result = CommandResult(argv=effective_command, returncode=completed.returncode)
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
                if cwd is not None:
                    handle.write(f"cd {shell_join([str(cwd)])}\n")
                handle.write(f"{shell_join(effective_command)}\n")
            return CommandResult(argv=effective_command, returncode=0)

        return CommandResult(argv=effective_command, returncode=0)
