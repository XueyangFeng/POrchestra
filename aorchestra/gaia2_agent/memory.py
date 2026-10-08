"""Official-style task entry memory for GAIA2 AOrchestra."""

from __future__ import annotations

from typing import Any


class TaskEntryMemory:
    def __init__(self) -> None:
        self.entries: list[dict[str, Any]] = []

    def add(self, entry: dict[str, Any]) -> None:
        self.entries.append(entry)

    def format(self) -> str:
        if not self.entries:
            return "No subtasks completed yet."

        blocks: list[str] = []
        done_count = 0
        for entry in self.entries:
            status = str(entry.get("status") or "partial")
            if status == "done":
                done_count += 1
            lines = [
                (
                    f"[Attempt {entry.get('attempt')}] {status} | "
                    f"Model: {entry.get('model', 'unknown')} | "
                    f"Steps: {entry.get('steps_taken', 0)}/{entry.get('max_steps', 30)}"
                ),
                f"|- Task: {entry.get('instruction', 'N/A')}",
                f"|- Result: {entry.get('result') or '(no result)'}",
            ]
            if entry.get("summary"):
                lines.append(f"|- Summary: {entry['summary']}")
            if entry.get("trace_summary"):
                lines.append(f"`- Trace summary:\n{entry['trace_summary']}")
            else:
                lines[-1] = lines[-1].replace("|-", "`-", 1)
            blocks.append("\n".join(lines))

        blocks.append(f"---\nSummary: {done_count}/{len(self.entries)} subtasks done")
        return "\n\n".join(blocks)
