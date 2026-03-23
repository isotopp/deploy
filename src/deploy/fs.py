from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .runtime import ExecutionContext, RunMode


@dataclass
class FileSystem:
    context: ExecutionContext

    def write_text(self, path: Path, content: str) -> Path:
        target = self.context.stage_path(path)
        if self.context.mode is RunMode.DRY_RUN:
            return target
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return target
