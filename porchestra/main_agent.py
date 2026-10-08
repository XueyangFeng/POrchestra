"""POrchestra MainAgent.

This follows the original AOrch MainAgent loop:
prompt -> LLM decision -> tool execution -> memory update.

The main difference is that compact prompt memory is managed by
MainMemoryBus instead of AOrch task_entries/context.
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any

from pydantic import Field

from base.agent.base_agent import BaseAgent
from base.engine.logs import LogLevel, logger
from benchmark.common.env import BasicInfo
from aorchestra.common.utils import parse_json_response

from porchestra.memory import MainMemoryBus
from porchestra.prompts import MainAgentPrompt
from porchestra.protocol import validate_sae


MAIN_LLM_MAX_ATTEMPTS = 5
MAIN_LLM_RETRY_DELAYS = (2.0, 5.0, 10.0, 20.0)
# Backward-compatible names retained for existing SWE-bench callers/tests.
SWE_MAIN_LLM_MAX_ATTEMPTS = MAIN_LLM_MAX_ATTEMPTS
SWE_MAIN_LLM_RETRY_DELAYS = MAIN_LLM_RETRY_DELAYS
_NON_RETRYABLE_LLM_MARKERS = (
    "insufficient balance",
    "insufficient quota",
    "authentication",
    "invalid api key",
    "incorrect api key",
    "unauthorized",
    "status code: 401",
    "status_code=401",
)
_RETRYABLE_LLM_MARKERS = (
    "connection error",
    "connection reset",
    "connection refused",
    "timed out",
    "timeout",
    "rate limit",
    "status code: 429",
    "status_code=429",
    "bad gateway",
    "service unavailable",
    "gateway timeout",
)
_RETRYABLE_LLM_ERROR_NAMES = {
    "APIConnectionError",
    "APITimeoutError",
    "RateLimitError",
    "InternalServerError",
}


def _filter_tool_params(
    tool: Any, params: dict[str, Any]
) -> tuple[dict[str, Any], list[str]]:
    """Drop top-level tool arguments that are absent from its object schema."""
    schema = getattr(tool, "parameters", None)
    if not isinstance(schema, dict) or schema.get("type") != "object":
        return dict(params), []
    properties = schema.get("properties")
    if not isinstance(properties, dict) or schema.get("additionalProperties") is True:
        return dict(params), []
    allowed = set(properties)
    dropped = sorted(str(key) for key in params if key not in allowed)
    return {key: value for key, value in params.items() if key in allowed}, dropped


def _is_retryable_main_llm_error(error: Exception) -> bool:
    """Return whether a MainAgent LLM failure is transient infrastructure."""
    text = f"{type(error).__name__}: {error}".lower()
    if any(marker in text for marker in _NON_RETRYABLE_LLM_MARKERS):
        return False
    status_code = getattr(error, "status_code", None)
    if status_code == 429 or (isinstance(status_code, int) and status_code >= 500):
        return True
    if type(error).__name__ in _RETRYABLE_LLM_ERROR_NAMES:
        return True
    return any(marker in text for marker in _RETRYABLE_LLM_MARKERS)


async def _call_main_llm_with_retry(llm: Any, prompt: str) -> str:
    """Call any POrchestra MainAgent LLM with transient-error retries."""
    for attempt in range(1, MAIN_LLM_MAX_ATTEMPTS + 1):
        try:
            return await llm(prompt)
        except Exception as error:
            if (
                attempt == MAIN_LLM_MAX_ATTEMPTS
                or not _is_retryable_main_llm_error(error)
            ):
                raise
            delay = MAIN_LLM_RETRY_DELAYS[attempt - 1]
            logger.warning(
                "[POrchestra MainAgent] LLM call failed "
                f"({type(error).__name__}: {error}); retrying "
                f"attempt {attempt + 1}/{MAIN_LLM_MAX_ATTEMPTS} in {delay:.1f}s"
            )
            await asyncio.sleep(delay)
    raise RuntimeError("unreachable")


# Kept as an alias so external SWE-bench code does not break.
_call_swe_main_llm_with_retry = _call_main_llm_with_retry


class MainAgent(BaseAgent):
    """MainAgent with POrchestra working memory."""

    name: str = Field(default="POrchestraMainAgent")
    description: str = Field(default="POrchestra orchestrator")

    sub_models: list[str] = Field(default_factory=list)
    tools: list[Any] = Field(default_factory=list)
    subagent_tools: list[Any] = Field(default_factory=list)
    prompt_builder: Any = Field(default=MainAgentPrompt)
    max_attempts: int = Field(default=10)
    benchmark_type: str = Field(default="gaia")

    mask_model_names: bool = Field(default=False)
    model_to_alias: dict[str, str] = Field(default_factory=dict)
    alias_to_model: dict[str, str] = Field(default_factory=dict)
    masked_sub_models: list[str] = Field(default_factory=list)

    instruction: str = Field(default="")
    meta: dict[str, Any] = Field(default_factory=dict)
    decision_step: int = Field(default=0)
    attempt: int = Field(default=0)
    history: list[dict[str, Any]] = Field(default_factory=list)
    memory_bus: MainMemoryBus = Field(default_factory=MainMemoryBus)
    live_trace: Any = Field(default=None, exclude=True)

    active_status: str = Field(default="none")
    active_attempt: int | None = Field(default=None)
    active_revision: int = Field(default=0)
    active_params: dict[str, Any] = Field(default_factory=dict)

    class Config:
        arbitrary_types_allowed = True

    def __init__(self, **data: Any):
        super().__init__(**data)
        if self.mask_model_names and self.sub_models:
            self.model_to_alias = {model: f"model_{i + 1}" for i, model in enumerate(self.sub_models)}
            self.alias_to_model = {alias: model for model, alias in self.model_to_alias.items()}
            self.masked_sub_models = list(self.model_to_alias.values())
        else:
            self.model_to_alias = {model: model for model in self.sub_models}
            self.alias_to_model = {model: model for model in self.sub_models}
            self.masked_sub_models = list(self.sub_models)

    def reset(self, env_info: BasicInfo) -> None:
        self.instruction = env_info.instruction
        self.meta = env_info.meta_data or {}
        self.decision_step = 0
        self.attempt = 0
        self.history = []
        self.memory_bus.clear()
        self.active_status = "none"
        self.active_attempt = None
        self.active_revision = 0
        self.active_params = {}

    def get_usage_cost(self) -> float:
        if self.llm is None:
            return 0.0
        return self.llm.get_usage_summary().get("total_cost", 0.0)

    async def step(self, observation=None, history=None, **kwargs) -> tuple[dict[str, Any], str]:
        """Execute one MainAgent decision."""
        del observation, history, kwargs
        self.decision_step += 1

        working_memory = self.memory_bus.format_working_memory()
        active_subagent = self._format_active_subagent()
        prompt_attempt = self._prompt_attempt_index()
        budget = self._global_subagent_budget()

        prompt_kwargs = dict(
            instruction=self.instruction,
            meta=self.meta,
            prior_context="",
            attempt_index=prompt_attempt,
            max_attempts=self.max_attempts,
            sub_models=self.masked_sub_models,
            subtask_history=working_memory,
            active_subagent=active_subagent,
            active_status=self.active_status,
            model_to_alias=self.model_to_alias if self.mask_model_names else None,
            tools=self.subagent_tools,
        )
        if self.benchmark_type == "swebench":
            prompt_kwargs.update(
                subagent_steps_used=budget["used"],
                max_total_subagent_steps=budget["max"],
            )
        prompt = self.prompt_builder.build_prompt(**prompt_kwargs)

        logger.log_to_file(LogLevel.INFO, f"[POrchestra MainAgent] Prompt:\n{prompt}\n")
        _append_live(
            self.live_trace,
            "main_prompt",
            decision_step=self.decision_step,
            attempt=self.attempt,
            active_status=self.active_status,
            active_attempt=self.active_attempt,
            active_revision=self.active_revision,
            subagent_steps_used=budget["used"],
            max_total_subagent_steps=budget["max"],
            remaining_subagent_steps=budget["remaining"],
            working_memory=working_memory,
            active_subagent=active_subagent,
            prompt=prompt,
        )

        resp = await _call_main_llm_with_retry(self.llm, prompt)
        logger.log_to_file(LogLevel.INFO, f"[POrchestra MainAgent] Response:\n{resp}\n")

        decision = parse_json_response(resp)
        _append_live(
            self.live_trace,
            "main_response",
            decision_step=self.decision_step,
            response=resp,
            decision=decision,
        )
        logger.log_to_file(
            LogLevel.INFO,
            "[POrchestra MainAgent] Parsed decision:\n"
            + json.dumps(decision, ensure_ascii=False, indent=2)
            + "\n",
        )

        action_name = decision.get("action")
        params = decision.get("params", {})
        if not isinstance(params, dict):
            params = {}

        result = await self._execute_decision(action_name, params)
        _append_live(
            self.live_trace,
            "main_result",
            decision_step=self.decision_step,
            action=action_name,
            params=params,
            result=result,
            active_status=self.active_status,
        )
        return {
            "action": action_name,
            "params": params,
            "result": result,
            "working_memory": working_memory,
            "active_subagent": active_subagent,
        }, resp

    async def _execute_decision(self, action_name: str, params: dict[str, Any]) -> dict[str, Any]:
        budget = self._global_subagent_budget()
        if (
            self.benchmark_type == "swebench"
            and budget["remaining"] <= 0
            and action_name in {"delegate_task", "revise_task"}
        ):
            return {
                "error": "global SubAgent step budget exhausted; submit the current container",
                "subagent_steps_used": budget["used"],
                "max_total_subagent_steps": budget["max"],
                "remaining_subagent_steps": 0,
            }
        if action_name == "delegate_task":
            return await self._run_delegate(params)
        if action_name == "revise_task":
            return await self._run_revise(params)
        return await self._run_tool(action_name, params)

    def _global_subagent_budget(self) -> dict[str, int]:
        delegate = next(
            (tool for tool in self.tools if getattr(tool, "name", None) == "delegate_task"),
            None,
        )
        if delegate is not None and hasattr(delegate, "get_budget_status"):
            return delegate.get_budget_status()
        return {"used": 0, "max": 0, "remaining": 0}

    async def _run_delegate(self, params: dict[str, Any]) -> dict[str, Any]:
        if self.attempt >= self.max_attempts:
            return {
                "error": "max_attempts reached; cannot start a new SubAgent attempt",
                "attempt": self.attempt,
                "max_attempts": self.max_attempts,
            }

        self.attempt += 1
        self.active_attempt = self.attempt
        self.active_revision = 0
        self.active_status = "running"
        self.active_params = dict(params)

        result = await self._run_tool("delegate_task", params)
        self._record_subagent_event(
            attempt_id=self.active_attempt,
            revision_id=self.active_revision,
            event="delegate",
            params=params,
            result=result,
        )
        return result

    async def _run_revise(self, params: dict[str, Any]) -> dict[str, Any]:
        executor = params.get("executor") if isinstance(params.get("executor"), dict) else {}
        executor_operation = str(executor.get("operation", "keep")).lower()
        revise_requested = self.active_status == "revise_requested"
        replace_finished_swe = (
            self.benchmark_type == "swebench"
            and self.active_status == "finished"
            and executor_operation == "replace"
        )
        if self.active_attempt is None or not (revise_requested or replace_finished_swe):
            return {
                "error": (
                    "revise_task requires an active revise request, or a finished "
                    "SWE-bench SubAgent with executor.operation=replace"
                ),
                "active_status": self.active_status,
            }

        self.active_revision += 1
        self.active_params = _merge_active_params(self.active_params, params)

        result = await self._run_tool("revise_task", params)
        self._record_subagent_event(
            attempt_id=self.active_attempt,
            revision_id=self.active_revision,
            event="revise",
            params=self.active_params,
            result=result,
        )
        return result

    async def _run_tool(self, action_name: str, params: dict[str, Any]) -> dict[str, Any]:
        tool = next((tool for tool in self.tools if getattr(tool, "name", None) == action_name), None)
        if tool is None:
            return {"error": f"Unknown action: {action_name}"}
        filtered_params, dropped_params = _filter_tool_params(tool, params)
        if dropped_params:
            logger.warning(
                f"[POrchestra MainAgent] Ignoring unsupported {action_name} "
                f"parameter(s): {', '.join(dropped_params)}"
            )
            _append_live(
                self.live_trace,
                "tool_params_filtered",
                action=action_name,
                dropped_params=dropped_params,
                original_params=params,
                filtered_params=filtered_params,
            )
        try:
            result = await tool(**filtered_params)
        except Exception as e:
            logger.warning(f"[POrchestra MainAgent] Tool {action_name} failed: {type(e).__name__}: {e}")
            return {"error": f"{type(e).__name__}: {e}"}
        return result if isinstance(result, dict) else {"result": result}

    def _record_subagent_event(
        self,
        *,
        attempt_id: int,
        revision_id: int,
        event: str,
        params: dict[str, Any],
        result: dict[str, Any],
    ) -> None:
        self.history.append({
            "attempt": attempt_id,
            "revision": revision_id,
            "event": event,
            "action": "delegate_task" if event == "delegate" else "revise_task",
            "result": result,
        })

        sae = _extract_sae(result)
        if sae is None:
            logger.warning("[POrchestra MainAgent] SubAgent result did not contain a valid SAE message")
            self.active_status = "protocol_error"
            return

        raw_observation = (
            _latest_observation(result)
            if getattr(self.memory_bus, "include_raw_observation", False)
            else None
        )
        try:
            self.memory_bus.add_event(
                attempt_id=attempt_id,
                revision_id=revision_id,
                event=event,
                params=params,
                result=result,
                sae=sae,
                raw_observation=raw_observation,
            )
        except ValueError as e:
            logger.warning(f"[POrchestra MainAgent] Invalid SAE skipped: {e}")

        action_type = sae.get("action", {}).get("type")
        if action_type == "revise":
            self.active_status = "revise_requested"
        elif action_type == "finish":
            completion_status = sae.get("status")
            self.active_status = (
                completion_status
                if completion_status in {"done", "partial", "blocked"}
                else "finished"
            )
        elif action_type == "stop":
            self.active_status = "stopped"

    def _format_active_subagent(self) -> str:
        if self.active_attempt is None:
            return "Status: none"

        if (
            os.getenv("PORCHESTRA_GAIA_PROMPT_VARIANT", "control_skill").lower()
            == "aorch_aligned"
            and self.active_status
            not in {"running", "revise_requested"}
        ):
            return "Status: none; the latest handoff is recorded in SUBTASK HISTORY."

        latest = self.memory_bus.working_memory[-1] if self.memory_bus.working_memory else {}
        tools = self.active_params.get("tools") or latest.get("tools") or []
        if isinstance(tools, list):
            tools_text = ", ".join(str(tool) for tool in tools) or "none"
        else:
            tools_text = str(tools)

        lines = [
            f"Status: {self.active_status}",
            f"Attempt: {self.active_attempt}",
            f"Revision: {self.active_revision}",
            f"Task: {self.active_params.get('task_instruction', 'N/A')}",
            f"Context: {self.active_params.get('context', '') or 'None'}",
            f"Model: {self.active_params.get('model', latest.get('model', 'unknown'))}",
            f"Tools: {tools_text}",
            f"Used steps: {latest.get('steps', 0)}/{latest.get('max_steps', 30)}",
        ]
        executor = self.active_params.get("executor")
        if isinstance(executor, dict):
            lines.append(
                f"Executor revision: {executor.get('operation', 'keep')} "
                f"{executor.get('model', '')}".rstrip()
            )
        if latest.get("action_request"):
            lines.append(f"Latest request: {latest['action_request']}")
        if latest.get("task_scope_operation"):
            lines.append(
                "Latest task scope: "
                f"{latest['task_scope_operation']} {latest.get('task_scope_object', '')} | "
                f"{latest.get('task_scope_details', '')}"
            )
        if latest.get("resource_operation"):
            lines.append(
                "Latest resource: "
                f"{latest['resource_operation']} {latest.get('resource_object', '')} | "
                f"{latest.get('resource_details', '')}"
            )
        return "\n".join(lines)

    def _prompt_attempt_index(self) -> int:
        if self.active_status == "revise_requested" and self.active_attempt is not None:
            return self.active_attempt
        return min(self.attempt + 1, self.max_attempts)

    async def run(self, request: str | None = None) -> str:
        del request
        return "POrchestra orchestration via Runner"


def _extract_sae(result: dict[str, Any]) -> dict[str, Any] | None:
    candidates = [
        result.get("sae"),
        result.get("porchestra_sae"),
    ]
    for candidate in candidates:
        if isinstance(candidate, dict) and not validate_sae(candidate):
            return candidate
    return None


def _latest_observation(result: dict[str, Any]) -> Any | None:
    trace = result.get("trace")
    if not trace:
        return None
    last = trace[-1]
    if isinstance(last, dict):
        return last.get("observation")
    return getattr(last, "observation", None)


def _merge_active_params(active: dict[str, Any], revision: dict[str, Any]) -> dict[str, Any]:
    merged = dict(active)
    if revision.get("instruction"):
        merged["task_instruction"] = revision["instruction"]
    if revision.get("context"):
        old_context = str(merged.get("context", "") or "")
        merged["context"] = (old_context + "\n" + str(revision["context"])).strip()
    if revision.get("tools"):
        merged["tools"] = revision["tools"]
    if revision.get("model"):
        merged["model"] = revision["model"]
    if revision.get("task_scope"):
        merged["task_scope"] = revision["task_scope"]
    if revision.get("resource"):
        merged["resource"] = revision["resource"]
    if revision.get("executor"):
        merged["executor"] = revision["executor"]
    return merged


def _append_live(live_trace: Any, event_name: str, **payload: Any) -> None:
    if live_trace is None:
        return
    try:
        live_trace.append(event_name, **payload)
    except Exception as e:
        logger.debug(f"[POrchestra MainAgent] Failed to write live trace event {event_name}: {e}")
