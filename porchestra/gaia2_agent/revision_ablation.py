"""Single-dimension revision ablations for GAIA2 POrchestra."""

from __future__ import annotations

import os
from typing import Any


REVISION_ABLATIONS = frozenset({"task", "context", "tools", "budget"})

_LIMITS = {
    "task": (
        "The active SubAgent's task instruction and task scope cannot be changed "
        "by revise_task in this run. Keep the original assigned subtask; "
        "use the other revision resources or a fresh delegation if needed. "
        "Do not smuggle a new task into context or resource details."
    ),
    "context": (
        "revise_task cannot add context, constraints, or state handoff to the "
        "active SubAgent in this run. Use the existing context and other "
        "available revision dimensions. Do not smuggle new factual context "
        "into instruction or resource details."
    ),
    "tools": (
        "revise_task cannot change the active SubAgent's tool permissions in "
        "this run. Its original tool list remains fixed; use other revision "
        "dimensions or a fresh delegation if the needed tools differ."
    ),
    "budget": (
        "revise_task cannot add execution steps to the active SubAgent in "
        "this run. Its original local step limit remains fixed; use the other "
        "revision dimensions or a fresh delegation if more work remains."
    ),
}


def configured_revision_ablation() -> str:
    """Read and validate the experiment mode once per GAIA2 agent instance."""
    mode = os.environ.get("PORCHESTRA_REVISE_ABLATION", "").strip().lower()
    if mode and mode not in REVISION_ABLATIONS:
        raise ValueError(f"Invalid PORCHESTRA_REVISE_ABLATION={mode!r}")
    return mode


def ablation_notice(mode: str) -> str:
    """The same limitation is shown to MainAgent and SubAgent."""
    return _LIMITS[mode] if mode else ""


def mask_revision_params(params: dict[str, Any], mode: str) -> dict[str, Any]:
    """Enforce a revision ablation without changing the proposed action."""
    if mode and mode not in REVISION_ABLATIONS:
        raise ValueError(f"Invalid revision ablation: {mode!r}")
    effective = dict(params)
    if mode == "task":
        effective.pop("instruction", None)
        effective.pop("task_scope", None)
    elif mode == "context":
        effective.pop("context", None)
        resource = effective.get("resource")
        if isinstance(resource, dict) and resource.get("object") in {
            "context", "constraint", "state_handoff"
        }:
            effective.pop("resource", None)
    elif mode == "tools":
        effective.pop("tools", None)
        resource = effective.get("resource")
        if isinstance(resource, dict) and resource.get("object") == "tool":
            effective.pop("resource", None)
    elif mode == "budget":
        effective.pop("step_budget", None)
        resource = effective.get("resource")
        if isinstance(resource, dict) and resource.get("object") == "budget":
            effective.pop("resource", None)
    return effective
