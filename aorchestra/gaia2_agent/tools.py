"""AOrchestra control tool for returning a delegated result."""

from __future__ import annotations

from typing import Any

from are.simulation.tools import Tool


class FinishTool(Tool):
    output_type = "any"

    def __init__(self) -> None:
        self.name = "finish"
        self.description = "Finish this delegated subtask and report its local result to MainAgent."
        self.inputs = {
            "result": {
                "type": "string",
                "description": "Final local result or best partial result.",
            },
            "status": {
                "type": "string",
                "description": "Whether the delegated subtask is done or partial.",
            },
            "summary": {
                "type": "string",
                "description": "Brief evidence, completed work, and remaining issues.",
            },
        }
        self.last_result: dict[str, Any] | None = None
        super().__init__()

    def forward(
        self,
        result: str = "",
        status: str = "partial",
        summary: str = "",
    ) -> dict[str, Any]:
        normalized_status = status if status in {"done", "partial"} else "partial"
        self.last_result = {
            "result": str(result or ""),
            "status": normalized_status,
            "summary": str(summary or ""),
        }
        return {"aorchestra_finish": self.last_result}
