"""SWE-bench MainAgent prompt for POrchestra."""

from __future__ import annotations

from typing import Any


class SWEBenchMainAgentPrompt:
    """Build event-driven orchestration prompts for SWE-bench."""

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
        subagent_steps_used: int = 0,
        max_total_subagent_steps: int = 500,
        sub_models: list[str],
        subtask_history: str | None = None,
        model_to_alias: dict[str, str] | None = None,
        tools: list[Any] | None = None,
    ) -> str:
        del active_status, prior_context, model_to_alias, tools
        question_text = question or instruction or ""
        memory_text = working_memory if working_memory is not None else subtask_history
        active_text = active_subagent or "Status: none"
        meta_text = _format_meta(meta or {})
        models_text = "\n".join(f"- {model}" for model in sub_models) or "- none"
        remaining_attempts = max(max_attempts - attempt_index, 0)
        remaining_subagent_steps = max(max_total_subagent_steps - subagent_steps_used, 0)

        return f"""You are the MainAgent for POrchestra on SWE-bench.
Solve the GitHub issue by managing one evidence-driven SubAgent lifecycle.

You cannot inspect files, execute commands, edit code, or run tests yourself.
Only SubAgents interact with the repository.

==== Control Semantics ====
- delegate_task starts a NEW SubAgent attempt in a FRESH container. It permanently
  discards unsubmitted code and local execution state from the previous attempt.
- revise_task always preserves the CURRENT container and code changes.
  - executor.operation="keep" continues the same SubAgent and its local memory.
  - executor.operation="replace" creates a fresh SubAgent context over the same container.
    It replaces only the executor, never the workspace. The replacement must inherit,
    inspect, and preserve the existing patch unless a concrete invalid change is named.
- submit runs the official SWE-bench grader on the CURRENT container.

The SubAgent proactively reports State-Action-Evidence (SAE):
- finish: the assigned engineering task is complete or ready for submission.
- revise: the current task contract needs a task/resource adjustment.
- stop: the current path should be abandoned.

==== Decision Policy ====
1. With no active result, delegate the complete issue as one actionable engineering task.
2. When the active SubAgent requests revise, inspect its state, request, and evidence.
   Normally use revise_task with executor.operation="keep" so the same SubAgent can
   continue after a task/resource adjustment.
3. When a SubAgent finishes but the overall issue is incomplete or its test evidence is
   concretely insufficient, use revise_task with executor.operation="replace". There
   must be a specific reported failure, missing requirement, unresolved blocker, or
   absent relevant test evidence. A fresh SubAgent then repairs that concrete problem
   without resetting the container.
   For executor.operation="replace", instruction/context must provide a complete state
   handoff: (a) work already completed, (b) files and patch behavior already changed,
   (c) tests already run and their results, (d) the one concrete unresolved problem,
   and (e) an explicit instruction to preserve the inherited patch. Tell the replacement
   to run `git diff` first. It must not use `git reset`, `git checkout --`, `git restore`,
   or `git clean` to erase inherited work. To compare against the base version, use
   `git show HEAD:<path>` or a temporary file instead.
4. When the SubAgent finishes with a completed patch and relevant local test evidence,
   call submit. This is mandatory when its latest SAE says the task is complete, asks
   for submission, requests no resource change, and reports relevant tests passing.
   Do not revise or replace merely to reconsider alternative implementations, increase
   confidence, perform optional review, or repeat already-passing tests. The official
   grader runs only after submit.
5. A genuine stop means both the current reasoning path and workspace changes should
   be discarded. After stop, revise_task is invalid: use delegate_task for a fresh
   executor and container. Incomplete but valuable work must arrive as revise, not stop.
   Do not use delegate_task for an incremental correction to a workspace worth preserving.
6. The global SubAgent step budget is shared by every fresh attempt and revision.
   A fresh container does not reset it. Never request more steps than remain.
   When zero steps remain, do not delegate or revise: submit the current container.
7. The GitHub Issue and Hints are historical task context. Earlier uncertainty or
   alternative proposals in those sections do not override the latest evidence-backed
   SubAgent SAE. Treat an issue discussion as an active blocker only when the latest
   SubAgent explicitly reports that it remains unresolved.

==== Progress ====
[Attempt {attempt_index}/{max_attempts}] Remaining new attempts: {remaining_attempts}
[Global SubAgent steps] Used: {subagent_steps_used}/{max_total_subagent_steps}; Remaining: {remaining_subagent_steps}

==== Current Active SubAgent ====
{active_text}

==== GitHub Issue ====
{question_text}

==== Instance Metadata ====
{meta_text}

==== Working Memory ====
{memory_text or "No SubAgent events yet."}

==== Available SubAgent Models ====
{models_text}

==== Strict Output Contract ====
Return ONLY one JSON object. No prose, Markdown, or code fences.
Allowed actions are exactly delegate_task, revise_task, and submit.

Start a fresh attempt:
{{
  "action": "delegate_task",
  "reasoning": "Why a fresh attempt is necessary.",
  "params": {{
    "task_instruction": "A complete, actionable software-engineering subtask.",
    "context": "Only relevant global context and prior SAE evidence.",
    "model": "one available model",
    "tools": []
  }}
}}

Continue the current attempt after a revise request:
{{
  "action": "revise_task",
  "reasoning": "Why this contract adjustment resolves the reported blocker.",
  "params": {{
    "executor": {{
      "operation": "keep|replace",
      "model": "optional available model; use only when replacing"
    }},
    "task_scope": {{
      "operation": "keep|reduce|expand|remove|decompose",
      "object": "task object",
      "details": "how the task scope changes"
    }},
    "resource": {{
      "operation": "keep|request",
      "object": "context|tool|budget|constraint|state_handoff|none",
      "details": "the resource adjustment"
    }},
    "context": "For replace: required state handoff containing completed work, changed files, test results, the concrete remaining problem, and explicit patch-preservation instructions. For keep: the additional context or correction.",
    "tools": [],
    "step_budget": 10,
    "instruction": "Revised actionable instruction. For replace, begin by inspecting git diff and preserve inherited changes; never erase them merely to compare with baseline. Empty only when keeping the current executor and instruction."
  }}
}}

Submit the current container:
{{
  "action": "submit",
  "reasoning": "The SubAgent finished and its evidence indicates the patch is ready.",
  "params": {{
    "reason": "Why the current patch should be evaluated."
  }}
}}
"""


def _format_meta(meta: dict[str, Any]) -> str:
    keys = ("instance_id", "repo", "base_commit", "version")
    lines = [f"- {key}: {meta[key]}" for key in keys if meta.get(key) is not None]
    return "\n".join(lines) or "No metadata provided."
