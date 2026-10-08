"""POrchestra ReAct-style SubAgent."""

from __future__ import annotations

import json
import os
import re
from typing import Any

from pydantic import Field

from base.agent.base_agent import BaseAgent
from base.agent.memory import Memory
from base.agent.truncating_memory import truncate_text
from base.engine.logs import LogLevel, logger
from base.engine.utils import parse_llm_action_response, parse_llm_output
from benchmark.common.env import Action, BasicInfo, Observation

from porchestra.prompts.swebench_subagent import (
    build_swebench_final_handoff_prompt,
    build_swebench_native_tools,
    build_swebench_subagent_prompt,
    observation_state_info,
    parse_swebench_hybrid_response,
    parse_swebench_subagent_response,
)


SAE_PARAMS_FORMAT = """{
  "state": "<A concise factual statement of the SubAgent's current local state: what has been found, completed, ruled out, or remains uncertain.>",
  "action": {
    "type": "finish|revise|stop",
    "task_scope": {
      "operation": "keep|reduce|expand|remove|decompose",
      "object": "<The task object to modify.>",
      "details": "<How the task scope should change.>"
    },
    "resource": {
      "operation": "keep|request",
      "object": "context|tool|budget|constraint|state_handoff|none",
      "details": "<What resource is needed or how resources should change.>"
    },
    "request": "<The concrete request to MainAgent.>",
    "reason": "<The reason that supports this request.>"
  },
  "evidence": {
    "summary": "<Verbatim excerpts of relevant raw tool outputs; no paraphrasing or interpretation.>"
  }
}"""


FINAL_SAE_PARAMS_FORMAT = """{
  "state": "<A concise factual statement of the SubAgent's current local state: what has been found, completed, ruled out, or remains uncertain.>",
  "action": {
    "type": "finish|revise|stop",
    "task_scope": {
      "operation": "keep|reduce|expand|remove|decompose",
      "object": "<The assigned subtask or current path.>",
      "details": "<Use keep when reporting completed or preservable work; use remove when this path should stop.>"
    },
    "resource": {
      "operation": "keep|request",
      "object": "context|tool|budget|constraint|state_handoff|none",
      "details": "<For revise, request the minimum concrete resource needed to continue.>"
    },
    "request": "<The concrete final handoff request.>",
    "reason": "<The reason that supports this request.>"
  },
  "evidence": {
    "summary": "<Verbatim excerpts of relevant raw tool outputs; no paraphrasing or interpretation.>"
  }
}"""


LEGACY_FINAL_SAE_PARAMS_FORMAT = """{
  "state": "<A concise factual statement of the SubAgent's final local state.>",
  "action": {
    "type": "finish|stop",
    "task_scope": {
      "operation": "keep|remove",
      "object": "<The assigned subtask or current path.>",
      "details": "<Use keep for a usable result and remove when this path should stop.>"
    },
    "resource": {
      "operation": "keep",
      "object": "none",
      "details": "<No additional resource request at the final boundary.>"
    },
    "request": "<The concrete final handoff request.>",
    "reason": "<The reason supporting finish or stop.>"
  },
  "evidence": {
    "summary": "<Verbatim excerpts of relevant raw tool outputs; no paraphrasing or interpretation.>"
  }
}"""


AORCH_ALIGNED_SAE_PARAMS_FORMAT = """{
  "result": "<The concise answer or best usable local result; use an empty string when no result is available.>",
  "status": "done|partial|blocked",
  "summary": "<A brief factual summary of what was completed, what remains, and any issues.>",
  "state": "<A concise factual statement of the current local state.>",
  "action": {
    "type": "finish|revise|stop",
    "task_scope": {
      "operation": "keep|reduce|expand|remove|decompose",
      "object": "<The assigned subtask or current path.>",
      "details": "<How the task scope should change or be preserved.>"
    },
    "resource": {
      "operation": "keep|request",
      "object": "context|tool|budget|constraint|state_handoff|none",
      "details": "<What resource is needed or why no resource change is needed.>"
    },
    "request": "<The concrete request to MainAgent.>",
    "reason": "<The reason that supports this control action.>"
  },
  "evidence": {
    "summary": "<A concise factual summary of relevant observations supporting the result and status.>"
  }
}"""


AORCH_ALIGNED_GAIA_PROMPT = """You are a specialized SubAgent. Complete the assigned task efficiently.

==== Progress ====
[Step {current_step}/{max_steps}] Remaining {remaining_steps} steps
{budget_warning}

==== Your Task (from MainAgent) ====
{task_instruction}

==== Context ====
{context}

==== Original Question (for reference) ====
{original_question}

==== Available Tools ====
{action_space}

==== Guidelines ====
1. Focus on completing YOUR TASK above.
2. Think step by step before outputting an action.
3. Write key observations to the "memory" field.
4. Use print() in ExecuteCodeAction to see computation results.
5. Once done, use finish immediately with status="done" and the concise result.
6. If useful work exists but the assigned task is incomplete, do not call it done: use status="partial". Use status="blocked" when no useful progress can continue under the current conditions.
7. Use revise only when preserving this same attempt and changing task scope, context, tools, constraints, or step budget would let it continue. Use stop when this path should be abandoned.

When remaining_steps <= 5, make a final handoff before exhausting the budget. Do not change an incomplete result into status="done" merely because the budget is low.

==== Tool Output Format ====
For ordinary tools, return ONLY JSON:
{{
  "action": "<tool_name>",
  "params": {{}},
  "memory": "<key observation>"
}}

==== Control Output Format ====
For finish, revise, or stop, return ONLY JSON:
{{
  "action": "finish|revise|stop",
  "params": {sae_params_format},
  "memory": "<brief local memory>"
}}

Control rules:
- result/status/summary follow the AOrchestra GAIA finish semantics.
- status="done" means the assigned task is complete, not merely that a tool ran successfully.
- status="partial" or status="blocked" explicitly preserves an incomplete handoff for MainAgent.
- action.type must match the top-level action.
- state and evidence must distinguish observations from inference and unresolved assumptions.

==== Memory ====
{memory}

==== Current Observation ====
{obs}
"""


AORCH_ALIGNED_FINAL_HANDOFF_PROMPT = """You are a specialized SubAgent at the final step boundary.
Do not use tools. Do not request revise. Make one final handoff to MainAgent.

==== Progress ====
[Step {current_step}/{max_steps}] Final handoff step

==== Your Task (from MainAgent) ====
{task_instruction}

==== Context ====
{context}

==== Original Question (for reference) ====
{original_question}

Use finish with status="done" only if the assigned task is complete. Use finish with status="partial" for useful incomplete work, or status="blocked" when the task could not be completed under current conditions. Use stop only when the path should be abandoned.

Return ONLY JSON:
{{
  "action": "finish|stop",
  "params": {sae_params_format},
  "memory": "<brief final local memory>"
}}

==== Memory ====
{memory}

==== Current Observation ====
{obs}
"""


GAIA_PROMPT = """You are a specialized SubAgent in POrchestra.
Complete the assigned task efficiently.

==== Progress ====
[Step {current_step}/{max_steps}] Remaining {remaining_steps} steps
{budget_warning}

==== Your Task from MainAgent ====
{task_instruction}

==== Context from MainAgent ====
{context}

==== Original Question ====
{original_question}

==== Available Tools ====
{action_space}

==== Guidelines ====
1. Focus on the assigned task. Do not focus on the whole question unless necessary.
2. Use tools until you can make a useful handoff to MainAgent or encounter difficulty.
3. Use finish when the assigned subtask is complete.
4. Use stop when the current path should be removed.
5. Use revise when you believe a resource adjustment or task adjustment is needed.

==== Evidence Handoff ====
evidence.summary must quote relevant raw tool outputs verbatim, without paraphrasing or adding conclusions; put your analysis in state or action.reason, and write "No tool output available" if no tool output exists.

==== Tool Output Format ====
For ordinary tools, return ONLY JSON:
{{
  "action": "<tool_name>",
  "params": {{}},
  "memory": "<key observation>"
}}

==== SAE Output Format ====
For finish, revise, or stop, return ONLY JSON:
{{
  "action": "finish|revise|stop",
  "params": {sae_params_format},
  "memory": "<brief local memory>"
}}

SAE rules:
- params.state only states facts; it must not contain requests.
- params.action.type must match the top-level action.
- params.action.task_scope.operation describes the task adjustment: keep, reduce, expand, remove, or decompose.
- params.action.resource.operation is keep or request; use resource.object="none" when no resource change is needed.
- params.evidence.summary must contain only verbatim excerpts of actual tool outputs.

==== Memory ====
{memory}

==== Current Observation ====
{obs}
"""


FINAL_HANDOFF_PROMPT = """You are a specialized SubAgent in POrchestra at the final step boundary.
Do not use tools. Make one final handoff to MainAgent.

==== Progress ====
[Step {current_step}/{max_steps}] Final handoff step

==== Your Task from MainAgent ====
{task_instruction}

==== Context from MainAgent ====
{context}

==== Original Question ====
{original_question}

==== Guidelines ====
1. Use finish if you completed the assigned task or have a usable local result.
2. Use revise if the local result is worth preserving and a concrete resource or task adjustment would let the same attempt continue.
3. Use stop if the path is invalid, exhausted without useful state, or a fresh attempt would be preferable.
4. Write key final observations to the state, evidence, and memory fields.

==== Evidence Handoff ====
evidence.summary must quote relevant raw tool outputs verbatim, without paraphrasing or adding conclusions; put your analysis in state or action.reason, and write "No tool output available" if no tool output exists.

==== SAE Output Format ====
Return ONLY JSON:
{{
  "action": "finish|revise|stop",
  "params": {sae_params_format},
  "memory": "<brief final local memory>"
}}

SAE rules:
- params.state only states facts; it must not contain requests.
- params.action.type must match the top-level action.
- params.action.task_scope.operation should normally be keep for finish/revise and remove for stop.
- params.action.resource.operation should be request for a revise that needs additional resources.
- params.evidence.summary must contain only verbatim excerpts of actual tool outputs.

==== Memory ====
{memory}

==== Current Observation ====
{obs}
"""


# The TaskCraft DeepSeek-v4 rollout started before the control-action skill was
# added. Keep the original prompt selectable so model-only comparisons can use
# exactly the same SubAgent instructions without changing the default behavior.
LEGACY_GAIA_PROMPT = """You are a specialized SubAgent in POrchestra.
Complete the assigned task efficiently.

==== Progress ====
[Step {current_step}/{max_steps}] Remaining {remaining_steps} steps
{budget_warning}

==== Your Task from MainAgent ====
{task_instruction}

==== Context from MainAgent ====
{context}

==== Original Question ====
{original_question}

==== Available Tools ====
{action_space}

==== Guidelines ====
1. Focus on the assigned task. Do not focus on the whole question unless necessary.
2. Use tools until you can make a useful handoff to MainAgent or encounter difficulty.
3. Use finish when the assigned subtask is complete.
4. Use stop when the current path should be removed.
5. Use revise when you believe a resource adjustment or task adjustment is needed.

==== Evidence Handoff ====
evidence.summary must quote relevant raw tool outputs verbatim, without paraphrasing or adding conclusions; put your analysis in state or action.reason, and write "No tool output available" if no tool output exists.

==== Tool Output Format ====
For ordinary tools, return ONLY JSON:
{{
  "action": "<tool_name>",
  "params": {{}},
  "memory": "<key observation>"
}}

==== SAE Output Format ====
For finish, revise, or stop, return ONLY JSON:
{{
  "action": "finish|revise|stop",
  "params": {sae_params_format},
  "memory": "<brief local memory>"
}}

SAE rules:
- params.state only states facts; it must not contain requests.
- params.action.type must match the top-level action.
- params.action.task_scope.operation describes the task adjustment: keep, reduce, expand, remove, or decompose.
- params.action.resource.operation is keep or request; use resource.object="none" when no resource change is needed.
- params.evidence.summary must contain only verbatim excerpts of actual tool outputs.

==== Memory ====
{memory}

==== Current Observation ====
{obs}
"""


LEGACY_FINAL_HANDOFF_PROMPT = """You are a specialized SubAgent in POrchestra at the final step boundary.
Do not use tools. Do not request revise. Make one final handoff to MainAgent.

==== Progress ====
[Step {current_step}/{max_steps}] Final handoff step

==== Your Task from MainAgent ====
{task_instruction}

==== Context from MainAgent ====
{context}

==== Original Question ====
{original_question}

==== Guidelines ====
1. Use finish if you completed the assigned task or have a usable local result.
2. Use stop if this path is invalid, wasteful, unsupported by evidence, or should not continue.
3. Write key final observations to the "memory" field.

==== Evidence Handoff ====
evidence.summary must quote relevant raw tool outputs verbatim, without paraphrasing or adding conclusions; put your analysis in state or action.reason, and write "No tool output available" if no tool output exists.

==== SAE Output Format ====
Return ONLY JSON:
{{
  "action": "finish|stop",
  "params": {sae_params_format},
  "memory": "<brief final local memory>"
}}

SAE rules:
- params.state only states facts; it must not contain requests.
- params.action.type must match the top-level action.
- params.action.task_scope.operation should be keep for finish and remove for stop.
- params.action.resource must keep object="none"; no resources can be requested here.
- params.evidence.summary must contain only verbatim excerpts of actual tool outputs.

==== Memory ====
{memory}

==== Current Observation ====
{obs}
"""


class ReActSubAgent(BaseAgent):
    """ReAct SubAgent that reports State-Action-Evidence to MainAgent."""

    name: str = Field(default="POrchestraReActSubAgent")
    description: str = Field(default="ReAct SubAgent with SAE handoff")

    benchmark_type: str = Field(default="gaia")
    task_instruction: str = Field(default="")
    context: str = Field(default="")
    original_question: str = Field(default="")
    allowed_tools: list[str] | None = Field(default=None)

    current_env_instruction: str = Field(default="")
    current_action_space: str = Field(default="")
    memory: Memory = Field(default=None)
    live_trace: Any = Field(default=None, exclude=True)
    max_observation_chars: int = Field(default=10_000)

    class Config:
        arbitrary_types_allowed = True

    def reset(self, env_info: BasicInfo) -> None:
        if self.memory is None:
            self.memory = Memory(llm=self.llm, max_memory=10)
        else:
            self.memory.clear()

        if not self.original_question:
            self.original_question = env_info.instruction

        self.current_env_instruction = env_info.instruction
        if self.benchmark_type == "swebench":
            self.current_action_space = str(
                (env_info.meta_data or {}).get("command_docs") or env_info.action_space
            )
        elif self.allowed_tools:
            self.current_action_space = self._filter_action_space(env_info.action_space, self.allowed_tools)
        else:
            self.current_action_space = env_info.action_space

    def _normalize_tool_name(self, name: str) -> str:
        normalized = name.lower().replace("_", "")
        if normalized.endswith("action"):
            normalized = normalized[:-6]
        return normalized

    def _tool_matches(self, tool_name: str, allowed_tools: list[str]) -> bool:
        if tool_name in allowed_tools:
            return True
        normalized_tool = self._normalize_tool_name(tool_name)
        return any(self._normalize_tool_name(allowed) == normalized_tool for allowed in allowed_tools)

    def _filter_action_space(self, action_space: str, allowed_tools: list[str]) -> str:
        blocks = re.split(r"\n(?=### )", action_space)
        filtered = []
        for block in blocks:
            if block.startswith("Available actions"):
                filtered.append(block.rstrip())
                continue
            match = re.match(r"### (\w+)", block)
            if not match:
                continue
            tool_name = match.group(1)
            if self._normalize_tool_name(tool_name) in {"finish", "revise", "stop"}:
                filtered.append(block.rstrip())
            elif self._tool_matches(tool_name, allowed_tools):
                filtered.append(block.rstrip())
        return "\n\n".join(filtered)

    def parse_action(self, resp: str) -> dict[str, Any]:
        if self.benchmark_type == "swebench":
            return parse_swebench_subagent_response(resp)
        return parse_llm_action_response(resp)

    def _uses_native_swebench_tools(self) -> bool:
        if self.benchmark_type != "swebench":
            return False
        setting = os.getenv("PORCHESTRA_SWEBENCH_NATIVE_TOOL_CALLING", "auto").lower()
        if setting in {"0", "false", "off", "disabled"}:
            return False
        supports_native = callable(getattr(self.llm, "call_with_tools", None))
        if setting in {"1", "true", "on", "enabled"}:
            return supports_native
        model = str(getattr(getattr(self.llm, "config", None), "model", "")).lower()
        return supports_native and "gemini" in model

    async def _call_swebench_native_model(
        self, prompt: str
    ) -> tuple[dict[str, Any], str]:
        payload = await self.llm.call_with_tools(
            prompt,
            tools=build_swebench_native_tools(),
            tool_choice="auto",
        )
        action = parse_swebench_hybrid_response(payload)
        return action, json.dumps(payload, ensure_ascii=False)

    async def record_transition(
        self,
        *,
        action: Action,
        observation_after: Observation,
        thinking: str | None = None,
        reward: float | None = None,
        raw_response: str | None = None,
    ) -> None:
        """Store an executed action together with the observation it produced."""
        await self.memory.add_memory(
            obs=observation_after,
            action=action,
            thinking=thinking,
            reward=reward,
            raw_response=raw_response,
        )

    def _bounded_swebench_observation(self, observation: Any) -> Any:
        if self.benchmark_type != "swebench":
            return observation
        if isinstance(observation, dict):
            bounded = dict(observation)
            for key in ("output", "message", "stdout", "stderr"):
                if key in bounded:
                    bounded[key] = truncate_text(
                        bounded[key], self.max_observation_chars
                    )
            return bounded
        return truncate_text(observation, self.max_observation_chars)

    def _get_memory(self) -> str:
        return self.memory.as_text()

    def _get_budget_warning(self, remaining_steps: int) -> str:
        if remaining_steps <= 3:
            return f"CRITICAL: Only {remaining_steps} steps left. Use finish, revise, or stop now."
        if remaining_steps <= 5:
            return f"Warning: {remaining_steps} steps remaining. Prepare a SAE handoff."
        return ""

    def _build_prompt(
        self,
        *,
        observation: Any,
        current_step: int,
        max_steps: int,
        remaining_steps: int,
        budget_warning: str,
    ) -> str:
        if self.benchmark_type == "swebench":
            return build_swebench_subagent_prompt(
                task_instruction=self.task_instruction,
                context=self.context,
                original_question=self.original_question,
                command_docs=self.current_action_space,
                state_info=observation_state_info(observation),
                memory=self._get_memory(),
                observation=self._bounded_swebench_observation(observation),
                current_step=current_step,
                max_steps=max_steps,
                remaining_steps=remaining_steps,
                budget_warning=budget_warning,
                native_tool_calling=self._uses_native_swebench_tools(),
            )
        prompt_variant = os.getenv(
            "PORCHESTRA_GAIA_PROMPT_VARIANT", "control_skill"
        ).lower()
        if prompt_variant == "aorch_aligned":
            prompt_template = AORCH_ALIGNED_GAIA_PROMPT
            sae_params_format = AORCH_ALIGNED_SAE_PARAMS_FORMAT
        elif prompt_variant in {"legacy", "baseline", "0", "false"}:
            prompt_template = LEGACY_GAIA_PROMPT
            sae_params_format = SAE_PARAMS_FORMAT
        else:
            prompt_template = GAIA_PROMPT
            sae_params_format = SAE_PARAMS_FORMAT
        return prompt_template.format(
            task_instruction=self.task_instruction,
            context=self.context or "None",
            original_question=self.original_question,
            action_space=self.current_action_space,
            memory=self._get_memory(),
            obs=observation,
            current_step=current_step,
            max_steps=max_steps,
            remaining_steps=remaining_steps,
            budget_warning=budget_warning,
            sae_params_format=sae_params_format,
        )

    async def step(
        self,
        observation: Observation,
        history: Any,
        current_step: int = 1,
        max_steps: int = 30,
    ) -> tuple[Action, str, str]:
        remaining_steps = max_steps - current_step
        prompt = self._build_prompt(
            observation=observation,
            current_step=current_step,
            max_steps=max_steps,
            remaining_steps=remaining_steps,
            budget_warning=self._get_budget_warning(remaining_steps),
        )

        logger.log_to_file(LogLevel.INFO, f"POrchestra ReActSubAgent Input:\n{prompt}\n")
        _append_live(
            self.live_trace,
            "subagent_prompt",
            current_step=current_step,
            max_steps=max_steps,
            remaining_steps=remaining_steps,
            task_instruction=self.task_instruction,
            context=self.context,
            observation=observation,
            prompt=prompt,
        )
        native_tool_calling = self._uses_native_swebench_tools()
        try:
            if native_tool_calling:
                action, resp = await self._call_swebench_native_model(prompt)
            else:
                resp = await self.llm(prompt)
                action = self.parse_action(resp)
        except Exception as e:
            logger.error(f"POrchestra ReActSubAgent LLM call failed: {e}")
            resp = ""
            action = self.parse_action(resp)
        if self.benchmark_type == "swebench":
            thinking = action.get("reasoning")
        else:
            memory_content = parse_llm_output(resp, "memory")
            thinking = memory_content.get("memory") if isinstance(memory_content, dict) else None
        _append_live(
            self.live_trace,
            "subagent_response",
            current_step=current_step,
            response=resp,
            action=action,
        )

        logger.agent_action(f"POrchestra ReActSubAgent Action: {action}")
        return action, resp, prompt

    async def final_handoff(
        self,
        observation: Observation,
        history: Any,
        current_step: int = 1,
        max_steps: int = 30,
    ) -> tuple[Action, str, str]:
        """Produce a final finish/stop SAE handoff at the step boundary."""
        legacy_gaia = False
        aligned_gaia = False
        if self.benchmark_type == "swebench":
            prompt = build_swebench_final_handoff_prompt(
                task_instruction=self.task_instruction,
                context=self.context,
                original_question=self.original_question,
                memory=self._get_memory(),
                observation=self._bounded_swebench_observation(observation),
                native_tool_calling=False,
            )
        else:
            prompt_variant = os.getenv(
                "PORCHESTRA_GAIA_PROMPT_VARIANT", "control_skill"
            ).lower()
            legacy_gaia = prompt_variant in {"legacy", "baseline", "0", "false"}
            aligned_gaia = prompt_variant == "aorch_aligned"
            if aligned_gaia:
                prompt_template = AORCH_ALIGNED_FINAL_HANDOFF_PROMPT
                sae_params_format = AORCH_ALIGNED_SAE_PARAMS_FORMAT
            elif legacy_gaia:
                prompt_template = LEGACY_FINAL_HANDOFF_PROMPT
                sae_params_format = LEGACY_FINAL_SAE_PARAMS_FORMAT
            else:
                prompt_template = FINAL_HANDOFF_PROMPT
                sae_params_format = FINAL_SAE_PARAMS_FORMAT
            prompt = prompt_template.format(
                task_instruction=self.task_instruction,
                context=self.context or "None",
                original_question=self.original_question,
                memory=self._get_memory(),
                obs=observation,
                current_step=current_step,
                max_steps=max_steps,
                sae_params_format=sae_params_format,
            )

        logger.log_to_file(LogLevel.INFO, f"POrchestra ReActSubAgent Final Handoff Input:\n{prompt}\n")
        _append_live(
            self.live_trace,
            "subagent_final_prompt",
            current_step=current_step,
            max_steps=max_steps,
            task_instruction=self.task_instruction,
            context=self.context,
            observation=observation,
            prompt=prompt,
        )
        try:
            resp = await self.llm(prompt)
            action = self.parse_action(resp)
        except Exception as e:
            logger.error(f"POrchestra ReActSubAgent final handoff LLM call failed: {e}")
            resp = ""
            action = self.parse_action(resp)
        if self.benchmark_type == "swebench":
            thinking = action.get("reasoning")
        else:
            memory_content = parse_llm_output(resp, "memory")
            thinking = memory_content.get("memory") if isinstance(memory_content, dict) else None
        allowed_final_actions = (
            {"finish", "stop"}
            if legacy_gaia or aligned_gaia
            else {"finish", "revise", "stop"}
        )
        if action.get("action") not in allowed_final_actions:
            fallback_action = "revise" if self.benchmark_type == "swebench" else "stop"
            action = {
                "action": fallback_action,
                "params": {
                    "state": (
                        "Final handoff reached, but the model did not return a valid "
                        + "finish/revise/stop"
                        + " action."
                    ),
                    "action": {
                        "type": fallback_action,
                        "task_scope": {
                            "operation": "keep" if fallback_action == "revise" else "remove",
                            "object": "current path",
                            "details": (
                                "Preserve the current path while MainAgent resolves the protocol error."
                                if fallback_action == "revise"
                                else "The final handoff was invalid."
                            ),
                        },
                        "resource": {
                            "operation": "request" if fallback_action == "revise" else "keep",
                            "object": "state_handoff" if fallback_action == "revise" else "none",
                            "details": (
                                "Request a recoverable handoff decision after invalid control output."
                                if fallback_action == "revise"
                                else "No resource change is requested."
                            ),
                        },
                        "request": (
                            "Preserve the workspace and let MainAgent revise or replace the executor."
                            if fallback_action == "revise"
                            else "Stop this path and let MainAgent decide the next step."
                        ),
                        "reason": "The final handoff output did not match the required control protocol.",
                    },
                    "evidence": {
                        "summary": "No valid final SAE handoff was produced.",
                    },
                },
                "memory": thinking or "invalid final handoff",
            }
        _append_live(
            self.live_trace,
            "subagent_final_response",
            current_step=current_step,
            response=resp,
            action=action,
        )

        logger.agent_action(f"POrchestra ReActSubAgent Final Handoff Action: {action}")
        return action, resp, prompt

    async def run(self, request: str = None) -> str:
        del request
        return ""


def _append_live(live_trace: Any, event_name: str, **payload: Any) -> None:
    if live_trace is None:
        return
    try:
        live_trace.append(event_name, **payload)
    except Exception as e:
        logger.debug(f"[POrchestra ReActSubAgent] Failed to write live trace event {event_name}: {e}")
