from __future__ import annotations

import shlex
import time
from collections.abc import Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class RunMode(Enum):
    LIVE = "live"
    DRY_RUN = "dry_run"
    CONFIGTEST = "configtest"


@dataclass(frozen=True)
class TimedEvent:
    kind: str
    name: str
    elapsed_seconds: float


@dataclass
class VerboseReporter:
    phase: str
    events: list[TimedEvent] = field(default_factory=list)
    _phase_started_at: float = field(default_factory=time.perf_counter)

    @contextmanager
    def step(self, name: str):
        started_at = time.perf_counter()
        print(f"verbose: start step {name}")
        try:
            yield
        finally:
            elapsed = time.perf_counter() - started_at
            self.events.append(TimedEvent(kind="step", name=name, elapsed_seconds=elapsed))
            print(f"verbose: done step {name} in {elapsed:.3f}s")

    def command_started(self, command: str) -> float:
        started_at = time.perf_counter()
        print(f"verbose: start command {command}")
        return started_at

    def command_finished(self, command: str, started_at: float, returncode: int) -> None:
        elapsed = time.perf_counter() - started_at
        self.events.append(TimedEvent(kind="command", name=command, elapsed_seconds=elapsed))
        print(f"verbose: done command {command} rc={returncode} in {elapsed:.3f}s")

    def print_summary(self) -> None:
        total = time.perf_counter() - self._phase_started_at
        print(f"verbose: summary for {self.phase}")
        for event in self.events:
            print(f"verbose: {event.kind} {event.name} {event.elapsed_seconds:.3f}s")
        print(f"verbose: total {total:.3f}s")


@dataclass(frozen=True)
class ExecutionContext:
    mode: RunMode
    configtest_prefix: Path | None = None
    reporter: VerboseReporter | None = None

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
