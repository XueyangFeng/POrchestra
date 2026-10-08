"""MainAgent working memory for POrchestra.

Raw traces stay in the original AOrchestra-style history:
    self.history.append({"attempt": ..., "action": ..., "result": result})

This bus only stores compact interaction events shown to MainAgent.
"""

from __future__ import annotations

import json
import os
from typing import Any, Literal

from porchestra.protocol import validate_sae


EventType = Literal["delegate", "revise"]


class MainMemoryBus:
    """Compact MainAgent working memory.

    Each event is stored as a plain dict so the prompt view maps directly to
    the data structure.
    """

    def __init__(self, include_raw_observation: bool | None = None) -> None:
        if include_raw_observation is None:
            include_raw_observation = _env_flag("PORCHESTRA_INCLUDE_RAW_OBSERVATION")
        self.include_raw_observation = include_raw_observation
        self.working_memory: list[dict[str, Any]] = []

    def clear(self) -> None:
        self.working_memory.clear()

    def add_event(
        self,
        *,
        attempt_id: int,
        revision_id: int,
        event: EventType,
        params: dict[str, Any],
        result: dict[str, Any],
        sae: dict[str, Any],
        raw_observation: Any | None = None,
    ) -> dict[str, Any]:
        """Add one SubAgent interaction event to working memory."""
        errors = validate_sae(sae)
        if errors:
            raise ValueError("Invalid SAE message: " + "; ".join(errors))

        trace_ref = _trace_ref(attempt_id, revision_id)
        sae_record = (
            _attach_raw_observation(sae, raw_observation)
            if self.include_raw_observation
            else sae
        )
        action = sae_record["action"]
        task_scope = action["task_scope"]
        resource = action["resource"]
        evidence = sae_record["evidence"]
        evidence_source = os.getenv("PORCHESTRA_EVIDENCE_SOURCE", "sae").lower()
        trace_summary = result.get("trace_summary")
        main_evidence_summary = (
            str(trace_summary).strip()
            if evidence_source == "trace_summary" and str(trace_summary or "").strip()
            else evidence["summary"]
        )
        entry = {
            "attempt": attempt_id,
            "revision": revision_id,
            "event": event,
            "sae_action": action["type"],
            "model": result.get("model") or params.get("model", "unknown"),
            "model_alias": params.get("model") or result.get("model") or "unknown",
            "tools": result.get("tools_assigned") or params.get("tools") or [],
            "steps": result.get("steps_taken", 0),
            "max_steps": result.get("statistics", {}).get("max_steps", 30),
            "task": params.get("task_instruction", "N/A"),
            "state": sae_record["state"],
            "completion_status": sae_record.get("status"),
            "result": sae_record.get("result", ""),
            "summary": sae_record.get("summary", ""),
            "action_request": action.get("request", ""),
            "action_reason": action["reason"],
            "task_scope_operation": task_scope["operation"],
            "task_scope_object": task_scope["object"],
            "task_scope_details": task_scope["details"],
            "resource_operation": resource["operation"],
            "resource_object": resource["object"],
            "resource_details": resource["details"],
            "evidence_source": evidence_source,
            "evidence_summary": main_evidence_summary,
            "sae_evidence_summary": evidence["summary"],
            # Prefer the system-extracted final environment observation.  The
            # SubAgent-authored raw object remains only as a compatibility
            # fallback for non-GAIA callers that do not enable extraction.
            "evidence_raw": evidence.get(
                "raw_observation",
                evidence.get("raw", {}),
            ),
            "trace_ref": trace_ref,
        }
        self.working_memory.append(entry)
        return entry

    def format_working_memory(self) -> str:
        """Render the compact memory shown to MainAgent."""
        if not self.working_memory:
            return "No SubAgent interactions yet."

        blocks = []
        aligned = (
            os.getenv("PORCHESTRA_GAIA_PROMPT_VARIANT", "control_skill").lower()
            == "aorch_aligned"
        )
        done_count = 0
        for item in self.working_memory:
            if aligned:
                status = item.get("completion_status") or (
                    "partial" if item.get("sae_action") == "revise" else "blocked"
                )
                emoji = "✅" if status == "done" else "⚠️"
                lines = [
                    (
                        f"[Attempt {item['attempt']}] {emoji} {status} | "
                        f"Model: {item.get('model_alias', 'unknown')} | "
                        f"Steps: {item['steps']}/{item['max_steps']}"
                    ),
                    f"├─ Task: {item['task']}",
                    (
                        f"├─ Result: \"{item['result']}\""
                        if item.get("result")
                        else "├─ Result: (no result)"
                    ),
                ]
                if item.get("summary"):
                    lines.append(f"├─ Summary: {item['summary']}")
                if item.get("evidence_summary"):
                    label = (
                        "Trace summary"
                        if item.get("evidence_source") == "trace_summary"
                        else "Evidence"
                    )
                    lines.append(f"├─ {label}:\n{_indent_text(item['evidence_summary'], '   ')}")
                if item.get("sae_action") == "revise":
                    lines.extend([
                        f"├─ Revise request: {item['action_request']}",
                        (
                            f"├─ Task scope: {item['task_scope_operation']} "
                            f"{item['task_scope_object']} | {item['task_scope_details']}"
                        ),
                        (
                            f"├─ Resource: {item['resource_operation']} "
                            f"{item['resource_object']} | {item['resource_details']}"
                        ),
                    ])
                lines[-1] = lines[-1].replace("├─", "└─", 1)
                blocks.append("\n".join(lines))
                done_count += status == "done"
                continue

            label = _event_label(item["attempt"], item["revision"], item["event"])
            tools = ",".join(str(t) for t in item.get("tools", [])) or "none"
            header = (
                f"[{label}] {item['sae_action']} | Model: {item['model']} | "
                f"Tools: {tools} | Steps: {item['steps']}/{item['max_steps']}"
            )
            lines = [
                header,
                f"├─ Task: {item['task']}",
                f"├─ State: {item['state']}",
            ]
            if item.get("completion_status"):
                lines.append(f"├─ Status: {item['completion_status']}")
            if item.get("result"):
                lines.append(f"├─ Result: {item['result']}")
            if item.get("summary"):
                lines.append(f"├─ Summary: {item['summary']}")
            evidence_label = (
                "Evidence (trace summary)"
                if item.get("evidence_source") == "trace_summary"
                else "Evidence"
            )
            lines.extend([
                f"├─ Action: {item['sae_action']} | {item['action_request']}",
                (
                    f"├─ Task scope: {item['task_scope_operation']} "
                    f"{item['task_scope_object']} | {item['task_scope_details']}"
                ),
                (
                    f"├─ Resource: {item['resource_operation']} "
                    f"{item['resource_object']} | {item['resource_details']}"
                ),
                f"├─ {evidence_label}: {item['evidence_summary']}",
            ])
            raw_text = _format_raw(item.get("evidence_raw"))
            if raw_text:
                lines.append(f"└─ Raw: {raw_text}")
            else:
                lines[-1] = lines[-1].replace("├─ Evidence", "└─ Evidence", 1)
            blocks.append("\n".join(lines))
        if aligned:
            blocks.append(
                f"---\nSummary: {done_count}/{len(self.working_memory)} subtasks done"
            )
        return "\n\n".join(blocks)


def _attach_raw_observation(sae: dict[str, Any], raw_observation: Any | None) -> dict[str, Any]:
    sae_record = dict(sae)
    evidence = dict(sae_record.get("evidence", {}))
    if raw_observation is not None:
        evidence["raw_observation"] = raw_observation
    sae_record["evidence"] = evidence
    return sae_record


def _event_label(attempt_id: int, revision_id: int, event: str) -> str:
    if event == "delegate":
        return f"Attempt {attempt_id} delegate"
    return f"Attempt {attempt_id} revise {revision_id}"


def _trace_ref(attempt_id: int, revision_id: int) -> str:
    return f"A{attempt_id}.R{revision_id}"


def _format_raw(value: Any) -> str:
    if not isinstance(value, dict) or not value:
        return ""
    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return str(value)


def _indent_text(text: str, prefix: str) -> str:
    return "\n".join(prefix + line for line in str(text).splitlines())


def _env_flag(name: str) -> bool:
    value = os.getenv(name, "")
    return value.strip().lower() in {"1", "true", "yes", "on"}
