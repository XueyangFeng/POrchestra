"""SAE protocol validation for POrchestra."""

from __future__ import annotations

from typing import Any


ACTION_TYPES = {"finish", "revise", "stop"}
COMPLETION_STATUSES = {"done", "partial", "blocked"}
TASK_SCOPE_OPERATIONS = {"keep", "reduce", "expand", "remove", "decompose"}
RESOURCE_OPERATIONS = {"keep", "request"}
RESOURCE_OBJECTS = {"context", "tool", "budget", "constraint", "state_handoff", "none"}


def validate_sae(message: Any) -> list[str]:
    """Return validation errors for a State-Action-Evidence message."""
    errors: list[str] = []
    if not isinstance(message, dict):
        return ["SAE message must be an object"]

    state = message.get("state")
    if not isinstance(state, str) or not state.strip():
        errors.append("state must be a non-empty string")

    if "status" in message and message.get("status") not in COMPLETION_STATUSES:
        errors.append("status must be done, partial, or blocked when provided")
    if "result" in message and not isinstance(message.get("result"), str):
        errors.append("result must be a string when provided")
    if "summary" in message and not _non_empty_string(message.get("summary")):
        errors.append("summary must be a non-empty string when provided")

    action = message.get("action")
    if not isinstance(action, dict):
        errors.append("action must be an object")
        action = {}

    action_type = action.get("type")
    if action_type not in ACTION_TYPES:
        errors.append("action.type must be finish, revise, or stop")

    task_scope = action.get("task_scope")
    if not isinstance(task_scope, dict):
        errors.append("action.task_scope must be an object")
        task_scope = {}
    if task_scope.get("operation") not in TASK_SCOPE_OPERATIONS:
        errors.append("action.task_scope.operation is invalid")
    if not _non_empty_string(task_scope.get("object")):
        errors.append("action.task_scope.object must be a non-empty string")
    if not _non_empty_string(task_scope.get("details")):
        errors.append("action.task_scope.details must be a non-empty string")

    resource = action.get("resource")
    if not isinstance(resource, dict):
        errors.append("action.resource must be an object")
        resource = {}
    if resource.get("operation") not in RESOURCE_OPERATIONS:
        errors.append("action.resource.operation must be keep or request")
    if resource.get("object") not in RESOURCE_OBJECTS:
        errors.append("action.resource.object is invalid")
    if not _non_empty_string(resource.get("details")):
        errors.append("action.resource.details must be a non-empty string")

    if not _non_empty_string(action.get("request")):
        errors.append("action.request must be a non-empty string")
    if not _non_empty_string(action.get("reason")):
        errors.append("action.reason must be a non-empty string")

    evidence = message.get("evidence")
    if not isinstance(evidence, dict):
        errors.append("evidence must be an object")
        evidence = {}
    if not _non_empty_string(evidence.get("summary")):
        errors.append("evidence.summary must be a non-empty string")
    if "raw" in evidence and not isinstance(evidence.get("raw"), dict):
        errors.append("evidence.raw must be an object when provided")

    return errors


def _non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())
