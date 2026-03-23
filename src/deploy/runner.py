from __future__ import annotations

import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from .runtime import ExecutionContext, RunMode, shell_join


@dataclass(frozen=True)
class CommandResult:
    argv: tuple[str, ...]
    returncode: int


@dataclass
class CommandRunner:
    context: ExecutionContext

    def run(self, argv: Sequence[str], *, cwd: Path | None = None) -> CommandResult:
        command = tuple(argv)
        if self.context.mode is RunMode.LIVE:
            completed = subprocess.run(command, cwd=cwd, check=False)
            return CommandResult(argv=command, returncode=completed.returncode)

        if self.context.mode is RunMode.CONFIGTEST:
            log_path = self.context.command_log_path()
            assert log_path is not None
            log_path.parent.mkdir(parents=True, exist_ok=True)
            if not log_path.exists():
                log_path.write_text("#!/bin/sh\nset -eu\n\n", encoding="utf-8")
            with log_path.open("a", encoding="utf-8") as handle:
                if cwd is not None:
                    handle.write(f"cd {shell_join([str(cwd)])}\n")
                handle.write(f"{shell_join(command)}\n")
            return CommandResult(argv=command, returncode=0)

        return CommandResult(argv=command, returncode=0)
