"""Diagnostic traces for GAIA2 external turn boundaries."""

from __future__ import annotations

import json
import os
import re
import threading
import time
from dataclasses import asdict, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any


_LOCK = threading.Lock()


class BoundaryTrace:
    """Append per-scenario JSONL records without changing agent behavior."""

    def __init__(self, scenario_id: str) -> None:
        trace_dir = os.environ.get("PORCHESTRA_GAIA2_BOUNDARY_TRACE_DIR")
        self.path: Path | None = None
        if trace_dir:
            safe_id = re.sub(r"[^A-Za-z0-9_.-]+", "_", scenario_id) or "unknown"
            self.path = Path(trace_dir) / f"{safe_id}.jsonl"

    @property
    def enabled(self) -> bool:
        return self.path is not None

    def append(self, event: str, **payload: Any) -> None:
        if self.path is None:
            return
        record = {
            "event": event,
            "wall_time": time.time(),
            **payload,
        }
        line = json.dumps(_jsonable(record), ensure_ascii=False)
        with _LOCK:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")


def serialize(value: Any) -> Any:
    """Convert an ARE object to JSON-compatible diagnostics."""
    return _jsonable(value)


def _jsonable(value: Any, *, depth: int = 0) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if depth >= 12:
        return repr(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {
            str(key): _jsonable(item, depth=depth + 1)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(item, depth=depth + 1) for item in value]
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        try:
            return _jsonable(to_dict(), depth=depth + 1)
        except Exception as exc:
            return {"serialization_error": f"{type(exc).__name__}: {exc}", "repr": repr(value)}
    if is_dataclass(value):
        try:
            return _jsonable(asdict(value), depth=depth + 1)
        except Exception:
            pass
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            pass
    return repr(value)
