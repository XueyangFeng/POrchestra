"""MainAgent prompt for POrchestra."""

from __future__ import annotations

import json
import os
from typing import Any

from aorchestra.prompts.gaia import GAIAMainAgentPrompt


class MainAgentPrompt:
    """Build the MainAgent prompt from compact working memory.

    This mirrors the original AOrch MainAgent decision prompt, but replaces
    subtask history with POrchestra working memory.
    """

    @staticmethod
    def build_prompt(
        *,
        question: str | None = None,
        working_memory: str | None = None,
        active_status: str = "none",
        active_subagent: str | None = None,
        instruction: str | None = None,
        meta: dict[str, Any] | None = None,
        prior_context: str = "",
        attempt_index: int,
        max_attempts: int,
        sub_models: list[str],
        subtask_history: str | None = None,
        model_to_alias: dict[str, str] | None = None,
        tools: list[Any],
    ) -> str:
        question_text = question or instruction or ""
        memory_text = working_memory if working_memory is not None else subtask_history
        active_subagent_text = active_subagent or active_status
        aligned = (
            os.getenv("PORCHESTRA_GAIA_PROMPT_VARIANT", "control_skill").lower()
            == "aorch_aligned"
        )
        if aligned:
            prompt = GAIAMainAgentPrompt.build_prompt(
                instruction=question_text,
                meta=meta or {},
                prior_context=prior_context,
                attempt_index=attempt_index,
                max_attempts=max_attempts,
                sub_models=sub_models,
                subtask_history=memory_text or "",
                model_to_alias=model_to_alias,
                tools=tools,
            )
            if active_status == "revise_requested":
                prompt += f"""

==== POrchestra Proactive Extension ====
The active SubAgent explicitly requested revise. You may use revise_task instead of
starting a new SubAgent when preserving the same local state is useful.

==== Current Active SubAgent ====
{active_subagent_text}

If revise_task is appropriate, return ONLY:
{{
  "action": "revise_task",
  "reasoning": "why preserving and revising this attempt is preferable",
  "params": {{
    "task_scope": {{
      "operation": "keep|reduce|expand|remove|decompose",
      "object": "task object",
      "details": "scope adjustment"
    }},
    "resource": {{
      "operation": "keep|request",
      "object": "context|tool|budget|constraint|state_handoff|none",
      "details": "resource adjustment"
    }},
    "context": "relevant findings and corrected path",
    "tools": ["tool_name"],
    "step_budget": 10,
    "instruction": "revised task instruction"
  }}
}}
""".strip("\n")
            return prompt

        del meta, prior_context, model_to_alias
        remaining_attempts = max(max_attempts - attempt_index, 0)
        memory_description = (
            "- Status: done, partial, or blocked using AOrchestra GAIA semantics.\n"
            "- Result: the concise local answer, if one is available.\n"
            "- Summary: what was completed and what remains.\n"
            "- Trace summary: an independent review of progress, problems, and remaining issues.\n"
            "- Proactive task-scope/resource details appear only for a revise request."
            if aligned
            else (
                "- State: the SubAgent's local factual state.\n"
                "- Action: the SubAgent's requested control action.\n"
                "- Task scope: whether the task boundary should be kept, reduced, expanded, removed, or decomposed.\n"
                "- Resource: whether context, tools, budget, constraints, or state handoff should be requested.\n"
                "- Evidence: a concise summary of the latest relevant environment observations."
            )
        )
        decision_policy = (
            "1. REVIEW the SUBTASK HISTORY: check status, result, summary, trace summary, and unresolved conditions.\n"
            "2. EVALUATE the result against the ORIGINAL QUESTION, not merely against the delegated subtask. Explicitly check whether the delegated task narrowed, literalized, or otherwise misinterpreted any material condition.\n"
            "3. If status=done and the result sufficiently answers every material condition in the ORIGINAL QUESTION, consider complete.\n"
            "4. If status=partial or blocked, do not treat finish as completion. Use delegate_task for remaining work, or revise_task only when the active SubAgent requested revise and preserving it is useful.\n"
            "5. A successful tool call, a finish action, repeated completion labels, or confident wording does not by itself verify correctness. Treat conflicts or limitations in the trace summary as unresolved.\n"
            "6. If the result is sufficient, use complete. If specific work remains, delegate only that remaining work.\n"
            "7. Final answers must be concise: a word, number, name, date, or short phrase."
            if aligned
            else (
                "1. If the working memory is sufficient to answer the QUESTION, use complete.\n"
                "2. If the current active SubAgent requested revise, inspect its task_scope, resource, request, evidence, assigned task, tools, and steps. If the issue can be solved by adjusting the current contract, use revise_task for the same active SubAgent.\n"
                "3. If the latest SubAgent finished, consider complete when its state/evidence is sufficient.\n"
                "4. If the latest SubAgent stopped, use delegate_task for remaining work and avoid repeating the stopped path.\n"
                "5. Final answers must be concise: a word, number, name, date, or short phrase."
            )
        )
        active_section = (
            ""
            if aligned and active_status not in {"running", "revise_requested"}
            else f"==== Current Active SubAgent ====\n{active_subagent_text}\n"
        )
        history_heading = "SUBTASK HISTORY" if aligned else "WORKING MEMORY"
        return f"""You are the MainAgent (Orchestrator) in POrchestra.
Your task is to solve the QUESTION by coordinating SubAgents.

Core distinction:
- delegate_task starts a NEW SubAgent attempt.
- revise_task revises the CURRENT active SubAgent and keeps the same attempt alive.
- complete submits the final answer.

Use the WORKING MEMORY as the only compact interaction state. Each item contains:
{memory_description}

Decision policy:
{decision_policy}

Budget and allocation awareness:
- Your total number of attempts is limited. Make each attempt count.
- A revise request usually means the active SubAgent needs a task-scope adjustment or resource adjustment.
- When revising, analyze whether the task should be kept, reduced, expanded, removed, or decomposed, and whether the needed resource is context, tools, budget, constraints, or state handoff.
- Use revise_task to provide concrete alternative resources or a corrected solution path to the same active SubAgent.
- If a result looks correct and was verified by evidence, trust it and use complete.

==== Progress ====
[Attempt {attempt_index}/{max_attempts}] Remaining attempts: {remaining_attempts}

{active_section}

==== QUESTION ====
{question_text}

==== {history_heading} ====
{memory_text or "No SubAgent interactions yet."}

==== AVAILABLE SUBAGENT MODELS ====
{_format_models(sub_models)}

==== AVAILABLE SUBAGENT TOOLS ====
{_format_tools(tools)}

==== OUTPUT ====
Return ONLY one JSON object.

If the working memory is sufficient:
{{
  "action": "complete",
  "reasoning": "The working memory shows [X], which answers the question.",
  "params": {{
    "answer": "concise final answer"
  }}
}}

If more work is needed:
{{
  "action": "delegate_task",
  "reasoning": "A new SubAgent attempt is needed because [Y] is still missing.",
  "params": {{
    "task_instruction": "A specific, actionable subtask for the next SubAgent.",
    "context": "Relevant State/Action/Evidence from working memory.",
    "model": "one available model",
    "tools": ["tool_name"]
  }}
}}

If the active SubAgent requested revise and should continue in the SAME attempt:
{{
  "action": "revise_task",
  "reasoning": "The active SubAgent requested [X]. Its task_scope/resource diagnosis indicates [Y], so revising the same attempt is better because [Z].",
  "params": {{
    "task_scope": {{
      "operation": "keep|reduce|expand|remove|decompose",
      "object": "the subtask object being adjusted",
      "details": "how the task scope should change"
    }},
    "resource": {{
      "operation": "keep|request",
      "object": "context|tool|budget|constraint|state_handoff|none",
      "details": "what resource is being kept or requested"
    }},
    "context": "Relevant prior findings plus the alternative resources or solution path you provide to the SubAgent.",
    "tools": ["tool_name"],
    "step_budget": 10,
    "instruction": "revised task instruction if needed; otherwise keep the original task"
  }}
}}
"""


def _format_models(models: list[str]) -> str:
    if not models:
        return "No models provided."
    return "\n".join(f"- {model}" for model in models)


def _format_tools(tools: list[Any]) -> str:
    if not tools:
        return "No tools provided."

    lines = []
    for tool in tools:
        name = getattr(tool, "name", str(tool))
        description = getattr(tool, "description", "")
        parameters = getattr(tool, "parameters", None)
        line = f"- {name}"
        if description:
            line += f": {description}"
        if parameters:
            line += "\n  Parameters: " + json.dumps(parameters, ensure_ascii=False)
        lines.append(line)
    return "\n".join(lines)
