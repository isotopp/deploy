from __future__ import annotations

import shlex
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class RunMode(Enum):
    LIVE = "live"
    DRY_RUN = "dry_run"
    CONFIGTEST = "configtest"


@dataclass(frozen=True)
class ExecutionContext:
    mode: RunMode
    configtest_prefix: Path | None = None

    def stage_path(self, path: Path) -> Path:
        if self.mode is not RunMode.CONFIGTEST:
            return path
        assert self.configtest_prefix is not None
        relative = path.relative_to(path.anchor)
        return self.configtest_prefix / relative

    def command_log_path(self) -> Path | None:
        if self.mode is not RunMode.CONFIGTEST:
            return None
        assert self.configtest_prefix is not None
        return self.configtest_prefix / "cmdlog.sh"


def shell_join(argv: Sequence[str]) -> str:
    return " ".join(shlex.quote(part) for part in argv)
