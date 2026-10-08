"""Compact working memory for GAIA2-POrchestra."""

from __future__ import annotations

import json
from typing import Any

from porchestra.gaia2_agent.protocol import validate_sae
from porchestra.gaia2_agent.sae_ablation import main_visible_sae_record, validate_sae_ablation


class WorkingMemory:
    def __init__(self, *, sae_ablation: str = "") -> None:
        self.sae_ablation = validate_sae_ablation(sae_ablation)
        self.items: list[dict[str, Any]] = []

    def add(
        self,
        *,
        attempt: int,
        revision: int,
        event: str,
        task: str,
        tools: list[str],
        steps: int,
        max_steps: int,
        sae: dict[str, Any],
    ) -> None:
        errors = validate_sae(sae)
        if errors:
            raise ValueError("; ".join(errors))
        action = sae["action"]
        self.items.append(main_visible_sae_record(
            {
                "attempt": attempt,
                "revision": revision,
                "event": event,
                "sae_action": action["type"],
                "task": task,
                "tools": tools,
                "steps": steps,
                "max_steps": max_steps,
                "state": sae["state"],
                "request": action["request"],
                "reason": action["reason"],
                "task_scope": action["task_scope"],
                "resource": action["resource"],
                "evidence": sae["evidence"]["summary"],
                "evidence_raw": sae["evidence"].get("raw", {}),
            }, self.sae_ablation
        ))

    def add_inspection(self, *, source: str, target_id: str, content: str) -> None:
        self.items.append(
            {
                "kind": "inspection",
                "source": source,
                "target_id": target_id,
                "content": content,
            }
        )

    def format(self) -> str:
        if not self.items:
            return "No SubAgent interactions yet."
        blocks = []
        for item in self.items:
            if item.get("kind") == "inspection":
                blocks.append(
                    "\n".join(
                        [
                            f"[Inspection] {item['source']} {item['target_id']}",
                            str(item["content"]),
                        ]
                    )
                )
                continue
            if item["event"] == "delegate":
                label = f"Attempt {item['attempt']} delegate"
            elif item["event"] == "resume":
                label = f"Attempt {item['attempt']} resume after environment update"
            else:
                label = f"Attempt {item['attempt']} revise {item['revision']}"
            tools = ", ".join(item["tools"]) if item["tools"] else "none"
            lines = [
                (
                    f"[{label}] {item['sae_action']} | Tools: {tools} | "
                    f"Steps: {item['steps']}/{item['max_steps']}"
                ),
                f"├─ Task: {item['task']}",
            ]
            if "state" in item:
                lines.append(f"├─ State: {item['state']}")
            if "request" in item:
                lines.append(f"├─ Request: {item['request']}")
            if "task_scope" in item:
                task_scope = item["task_scope"]
                lines.append(
                    f"├─ Task scope: {task_scope['operation']} "
                    f"{task_scope['object']} | {task_scope['details']}"
                )
            if "resource" in item:
                resource = item["resource"]
                lines.append(
                    f"├─ Resource: {resource['operation']} "
                    f"{resource['object']} | {resource['details']}"
                )
            if "evidence" in item:
                lines.append(f"├─ Evidence: {item['evidence']}")
            raw_text = _format_raw(item.get("evidence_raw"))
            if raw_text:
                lines.append(f"└─ Raw: {raw_text}")
            elif "evidence" in item:
                lines[-1] = lines[-1].replace("├─ Evidence:", "└─ Evidence:", 1)
            blocks.append("\n".join(lines))
        return "\n\n".join(blocks)


def _format_raw(raw: Any) -> str:
    if not isinstance(raw, dict) or not raw:
        return ""
    return json.dumps(raw, ensure_ascii=False, default=str)
