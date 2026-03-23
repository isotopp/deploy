from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any


def _normalize(value: Any) -> Any:
    if is_dataclass(value):
        return {key: _normalize(item) for key, item in asdict(value).items()}
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {key: _normalize(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_normalize(item) for item in value]
    return value


def dump_json(value: Any) -> str:
    return json.dumps(_normalize(value), indent=2, sort_keys=True)
