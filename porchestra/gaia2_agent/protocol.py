"""State-Action-Evidence protocol helpers for GAIA2-POrchestra."""

from __future__ import annotations

from typing import Any

ACTION_TYPES = {"finish", "revise", "stop"}
TASK_SCOPE_OPERATIONS = {"keep", "reduce", "expand", "remove", "decompose", "follow_up"}
RESOURCE_OPERATIONS = {"keep", "request"}
RESOURCE_OBJECTS = {"context", "tool", "budget", "constraint", "state_handoff", "none"}


def validate_sae(value: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, dict):
        return ["SAE must be an object"]

    if not _text(value.get("state")):
        errors.append("state must be a non-empty string")

    action = value.get("action")
    if not isinstance(action, dict):
        errors.append("action must be an object")
        action = {}

    if action.get("type") not in ACTION_TYPES:
        errors.append("action.type must be finish, revise, or stop")

    task_scope = action.get("task_scope")
    if not isinstance(task_scope, dict):
        errors.append("action.task_scope must be an object")
        task_scope = {}
    if task_scope.get("operation") not in TASK_SCOPE_OPERATIONS:
        errors.append("action.task_scope.operation is invalid")
    if not _text(task_scope.get("object")):
        errors.append("action.task_scope.object must be a non-empty string")
    if not _text(task_scope.get("details")):
        errors.append("action.task_scope.details must be a non-empty string")

    resource = action.get("resource")
    if not isinstance(resource, dict):
        errors.append("action.resource must be an object")
        resource = {}
    if resource.get("operation") not in RESOURCE_OPERATIONS:
        errors.append("action.resource.operation must be keep or request")
    if resource.get("object") not in RESOURCE_OBJECTS:
        errors.append("action.resource.object is invalid")
    if not _text(resource.get("details")):
        errors.append("action.resource.details must be a non-empty string")

    if not _text(action.get("request")):
        errors.append("action.request must be a non-empty string")
    if not _text(action.get("reason")):
        errors.append("action.reason must be a non-empty string")

    evidence = value.get("evidence")
    if not isinstance(evidence, dict):
        errors.append("evidence must be an object")
        evidence = {}
    if not _text(evidence.get("summary")):
        errors.append("evidence.summary must be a non-empty string")
    if "raw" in evidence and not isinstance(evidence.get("raw"), dict):
        errors.append("evidence.raw must be an object when provided")

    return errors


def repair_sae(control: str, payload: Any, latest_observation: Any = None) -> dict[str, Any]:
    if not isinstance(payload, dict):
        payload = {}

    action = payload.get("action") if isinstance(payload.get("action"), dict) else {}
    action_type = action.get("type") if action.get("type") in ACTION_TYPES else control
    if action_type not in ACTION_TYPES:
        action_type = "stop"

    task_scope = _coerce_task_scope(action.get("task_scope"), action_type)
    resource = _coerce_resource(action.get("resource"), action_type)
    evidence = payload.get("evidence") if isinstance(payload.get("evidence"), dict) else {}

    sae = {
        "state": _string_or(payload.get("state"), f"SubAgent produced {action_type}."),
        "action": {
            "type": action_type,
            "task_scope": task_scope,
            "resource": resource,
            "request": _string_or(action.get("request"), _default_request(action_type)),
            "reason": _string_or(action.get("reason"), f"Repaired from {control} control output."),
        },
        "evidence": {
            "summary": _string_or(
                evidence.get("summary"),
                f"Latest observation before {action_type}: {str(latest_observation)[:500]}",
            ),
            "raw": evidence.get("raw") if isinstance(evidence.get("raw"), dict) else {},
        },
    }
    return sae


def budget_exhausted_sae(max_steps: int) -> dict[str, Any]:
    return {
        "state": f"SubAgent reached its step budget of {max_steps}.",
        "action": {
            "type": "stop",
            "task_scope": {
                "operation": "remove",
                "object": "current path",
                "details": "The current path exhausted its step budget.",
            },
            "resource": {
                "operation": "keep",
                "object": "none",
                "details": "No further resource request is made after budget exhaustion.",
            },
            "request": "Stop this path and let MainAgent decide the next action.",
            "reason": "Continuing without a new plan risks redundant or incorrect side effects.",
        },
        "evidence": {
            "summary": f"The SubAgent used all {max_steps} allotted steps.",
            "raw": {},
        },
    }


def _coerce_task_scope(value: Any, action_type: str) -> dict[str, str]:
    default = {
        "finish": ("keep", "assigned subtask", "The assigned subtask is ready for handoff."),
        "revise": ("keep", "assigned subtask", "MainAgent should decide how to adjust the task scope."),
        "stop": ("remove", "current path", "The current path should not continue."),
    }[action_type]
    if not isinstance(value, dict):
        return {"operation": default[0], "object": default[1], "details": default[2]}
    operation = value.get("operation") if value.get("operation") in TASK_SCOPE_OPERATIONS else default[0]
    return {
        "operation": operation,
        "object": _string_or(value.get("object"), default[1]),
        "details": _string_or(value.get("details"), default[2]),
    }


def _coerce_resource(value: Any, action_type: str) -> dict[str, str]:
    default = (
        ("request", "context", "MainAgent guidance is needed.")
        if action_type == "revise"
        else ("keep", "none", "No resource change is requested.")
    )
    if not isinstance(value, dict):
        return {"operation": default[0], "object": default[1], "details": default[2]}
    operation = value.get("operation") if value.get("operation") in RESOURCE_OPERATIONS else default[0]
    obj = value.get("object") if value.get("object") in RESOURCE_OBJECTS else default[1]
    return {
        "operation": operation,
        "object": obj,
        "details": _string_or(value.get("details"), default[2]),
    }


def _default_request(action_type: str) -> str:
    if action_type == "finish":
        return "Report this local result to MainAgent."
    if action_type == "revise":
        return "Ask MainAgent to revise the current task or resources."
    return "Stop this path and let MainAgent decide the next action."


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _string_or(value: Any, fallback: str) -> str:
    return value.strip() if isinstance(value, str) and value.strip() else fallback
