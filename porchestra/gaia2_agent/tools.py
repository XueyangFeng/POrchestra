"""Control tools for GAIA2-POrchestra SubAgents."""

from __future__ import annotations

from typing import Any

from are.simulation.tools import Tool

from porchestra.gaia2_agent.protocol import repair_sae


class _ControlTool(Tool):
    output_type = "any"

    def __init__(self, control_name: str):
        self.name = control_name
        self.description = f"POrchestra control action: {control_name}."
        self.inputs = {
            "state": {"type": "string", "description": "Concise factual local state."},
            "action": {"type": "any", "description": "SAE action object."},
            "evidence": {"type": "any", "description": "SAE evidence object."},
        }
        self.last_sae: dict[str, Any] | None = None
        super().__init__()

    def forward(self, state: str, action: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]:
        sae = repair_sae(
            self.name,
            {"state": state, "action": action, "evidence": evidence},
        )
        self.last_sae = sae
        return {"porchestra_control": self.name, "sae": sae}


class FinishTool(_ControlTool):
    def __init__(self):
        super().__init__("finish")


class ReviseTool(_ControlTool):
    def __init__(self):
        super().__init__("revise")


class StopTool(_ControlTool):
    def __init__(self):
        super().__init__("stop")


def make_control_tools() -> dict[str, _ControlTool]:
    tools = [FinishTool(), ReviseTool(), StopTool()]
    return {tool.name: tool for tool in tools}
