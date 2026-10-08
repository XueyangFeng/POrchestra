"""Per-task live JSONL tracing for POrchestra runs."""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


class LiveTrace:
    """Append-only per-task JSONL trace for interrupted runs."""

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    @classmethod
    def for_task(cls, live_root: Path, task_id: str) -> "LiveTrace":
        return cls(live_root / task_id / "events.jsonl")

    def append(self, event_name: str, **payload: Any) -> None:
        record = {
            "time": datetime.now().isoformat(),
            "event": event_name,
            **payload,
        }
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(_jsonable(record), ensure_ascii=False) + "\n")


def _jsonable(obj: Any) -> Any:
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    if is_dataclass(obj) and not isinstance(obj, type):
        return {str(k): _jsonable(v) for k, v in asdict(obj).items()}
    if isinstance(obj, dict):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(item) for item in obj]
    return str(obj)
