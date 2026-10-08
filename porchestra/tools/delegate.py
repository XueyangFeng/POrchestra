"""POrchestra delegation tools.

The original AOrch DelegateTaskTool runs a SubAgent until it finishes.
POrchestra adds one control action:

- revise: return control to MainAgent while keeping the same SubAgent session alive.

The environment still executes ordinary tools. The POrchestra tool layer
intercepts finish/revise/stop before env.step().
"""

from __future__ import annotations

import inspect
import os
from dataclasses import asdict, dataclass, is_dataclass
from typing import Any

from pydantic import Field, PrivateAttr

from base.agent.base_action import BaseAction
from base.agent.memory import Memory
from base.agent.truncating_memory import LinearMemory, TruncatingMemory
from base.engine.async_llm import LLMsConfig, create_llm_instance
from base.engine.logs import logger
from benchmark.common.runner import StepRecord
from aorchestra.tools.trace_formatter import create_gaia_formatter

from porchestra.protocol import validate_sae
from porchestra.mini_swe_subagent import MiniSWESubAgent
from porchestra.subagent import ReActSubAgent


def _make_serializable(obj: Any) -> Any:
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    if is_dataclass(obj) and not isinstance(obj, type):
        return {k: _make_serializable(v) for k, v in asdict(obj).items()}
    if isinstance(obj, dict):
        return {str(k): _make_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_make_serializable(item) for item in obj]
    return str(obj)


@dataclass
class _Session:
    agent: Any
    obs: Any
    history: list[StepRecord]
    total_reward: float
    max_steps: int
    model: str
    tools: list[str] | None
    task_instruction: str
    context: str
    original_instruction: str | None


class DelegateTaskTool(BaseAction):
    """Start a new SubAgent attempt."""

    name: str = "delegate_task"
    description: str = "Delegate task to a POrchestra SubAgent"
    parameters: dict[str, Any] = Field(default_factory=dict)

    env: Any = Field(default=None, exclude=True)
    models: list[str] = Field(default_factory=list)
    benchmark_type: str = Field(default="gaia")
    alias_to_model: dict[str, str] = Field(default_factory=dict)
    default_max_steps: int = Field(default=30)
    max_total_steps: int = Field(default=500)
    memory_max_records: int = Field(default=10)
    memory_mode: str = Field(default="compressed")
    subagent_backend: str = Field(default="react")
    observation_max_chars: int = Field(default=10_000)
    memory_max_chars: int = Field(default=120_000)
    memory_record_max_chars: int = Field(default=12_000)
    live_trace: Any = Field(default=None, exclude=True)

    _session: _Session | None = PrivateAttr(default=None)
    _total_steps_used: int = PrivateAttr(default=0)

    class Config:
        arbitrary_types_allowed = True

    def __init__(
        self,
        env: Any,
        models: list[str],
        benchmark_type: str = "gaia",
        alias_to_model: dict[str, str] | None = None,
        default_max_steps: int = 30,
        max_total_steps: int = 500,
        memory_max_records: int = 10,
        memory_mode: str = "compressed",
        subagent_backend: str = "react",
        observation_max_chars: int = 10_000,
        memory_max_chars: int = 120_000,
        memory_record_max_chars: int = 12_000,
        live_trace: Any = None,
    ):
        super().__init__()
        self.env = env
        self.models = models
        self.benchmark_type = benchmark_type
        self.alias_to_model = alias_to_model or {}
        self.default_max_steps = default_max_steps
        self.max_total_steps = max(1, int(max_total_steps))
        self.memory_max_records = max(2, int(memory_max_records))
        normalized_memory_mode = str(memory_mode).strip().lower()
        if normalized_memory_mode not in {"compressed", "linear", "truncate"}:
            raise ValueError(
                "memory_mode must be 'compressed', 'linear', or 'truncate'"
            )
        self.memory_mode = normalized_memory_mode
        normalized_backend = str(subagent_backend).strip().lower()
        if normalized_backend not in {"react", "mini"}:
            raise ValueError("subagent_backend must be 'react' or 'mini'")
        if normalized_backend == "mini" and benchmark_type != "swebench":
            raise ValueError("subagent_backend='mini' is currently SWE-bench-only")
        self.subagent_backend = normalized_backend
        self.observation_max_chars = max(1, int(observation_max_chars))
        self.memory_max_chars = max(1, int(memory_max_chars))
        self.memory_record_max_chars = max(1, int(memory_record_max_chars))
        self.live_trace = live_trace
        self._session = None
        self._total_steps_used = 0

        display_models = list(self.alias_to_model.keys()) if self.alias_to_model else models
        self.parameters = {
            "type": "object",
            "properties": {
                "task_instruction": {"type": "string", "description": "Task for SubAgent"},
                "context": {"type": "string", "description": "Additional context/hints"},
                "model": {
                    "type": "string",
                    "description": f"Model to use. MUST be one of: {display_models}",
                    "enum": display_models,
                },
                "tools": {"type": "array", "items": {"type": "string"}, "description": "Tools for SubAgent"},
            },
            "required": ["task_instruction", "model"],
        }

    async def __call__(
        self,
        task_instruction: str,
        model: str,
        context: str = "",
        tools: list[str] | None = None,
    ) -> dict[str, Any]:
        """Create a new SubAgent session and run until finish/revise/stop."""
        if self.remaining_steps <= 0:
            return self._budget_error()
        self._close_session()

        real_model = self.alias_to_model.get(model, model)
        if real_model not in self.models:
            return {"error": f"Invalid model: {model}", "steps_taken": 0, "done": False}

        session = await self._start_session(
            task_instruction=task_instruction,
            context=context,
            model=real_model,
            tools=tools,
        )
        self._session = session
        return await self._run_session_until_control(event="delegate")

    def make_revise_tool(self) -> "ReviseTaskTool":
        return ReviseTaskTool(delegate_tool=self)

    @property
    def total_steps_used(self) -> int:
        return self._total_steps_used

    @property
    def remaining_steps(self) -> int:
        return max(self.max_total_steps - self._total_steps_used, 0)

    def get_budget_status(self) -> dict[str, int]:
        return {
            "used": self.total_steps_used,
            "max": self.max_total_steps,
            "remaining": self.remaining_steps,
        }

    def _budget_error(self) -> dict[str, Any]:
        return {
            "error": "global SubAgent step budget exhausted; submit the current container",
            "done": True,
            "steps_taken": 0,
            "statistics": {
                "global_steps_used": self.total_steps_used,
                "max_total_steps": self.max_total_steps,
                "remaining_global_steps": 0,
            },
        }

    async def revise_active(
        self,
        *,
        executor: dict[str, Any] | None = None,
        task_scope: dict[str, Any] | None = None,
        resource: dict[str, Any] | None = None,
        context: str = "",
        tools: list[str] | None = None,
        step_budget: int | None = None,
        instruction: str = "",
    ) -> dict[str, Any]:
        """Revise the active SubAgent session and continue it."""
        if self._session is None:
            return {"error": "No active SubAgent session to revise", "done": False, "steps_taken": 0}

        session = self._session
        executor = executor if isinstance(executor, dict) else {}
        executor_operation = str(executor.get("operation", "keep")).lower()
        if executor_operation not in {"keep", "replace"}:
            return {
                "error": f"Invalid executor operation: {executor_operation}",
                "done": False,
                "steps_taken": 0,
            }
        requested_model = str(executor.get("model") or session.model)
        replacement_model = self.alias_to_model.get(requested_model, requested_model)
        if executor_operation == "replace" and replacement_model not in self.models:
            return {
                "error": f"Invalid replacement model: {requested_model}",
                "done": False,
                "steps_taken": 0,
            }

        requested_step_budget = max(int(step_budget or 0), 0)
        granted_step_budget = min(requested_step_budget, self.remaining_steps)
        if requested_step_budget and granted_step_budget <= 0:
            return self._budget_error()

        if instruction:
            session.task_instruction = instruction
            if hasattr(self.env, "instruction"):
                self.env.instruction = instruction
        revision_context = _format_revision_context(
            executor=executor,
            task_scope=task_scope,
            resource=resource,
            context=context,
            instruction=instruction,
            tools=tools,
            step_budget=granted_step_budget or None,
        )
        if executor_operation == "replace":
            session.context = revision_context or context or session.context
        elif revision_context:
            session.context = (session.context + "\n" + revision_context).strip()

        if executor_operation == "replace":
            session.agent = self._create_agent(
                task_instruction=session.task_instruction,
                context=session.context,
                model=replacement_model,
                tools=tools if tools is not None else session.tools,
                original_question=session.original_instruction or "",
            )
            session.model = replacement_model
            if tools is not None:
                session.tools = tools
        else:
            session.agent.task_instruction = session.task_instruction
            session.agent.context = session.context
            if tools is not None:
                session.tools = tools
                session.agent.allowed_tools = tools
                if isinstance(session.agent, ReActSubAgent):
                    info = self.env.get_basic_info()
                    if self.benchmark_type == "swebench":
                        session.agent.current_action_space = str(
                            (info.meta_data or {}).get("command_docs") or info.action_space
                        )
                    else:
                        session.agent.current_action_space = session.agent._filter_action_space(
                            info.action_space, tools
                        )
        if granted_step_budget:
            session.max_steps = max(
                session.max_steps,
                len(session.history) + granted_step_budget,
            )
            extend_budget = getattr(self.env, "extend_step_budget", None)
            if callable(extend_budget):
                extend_budget(granted_step_budget)

        apply_revision = getattr(session.agent, "apply_revision", None)
        if executor_operation == "keep" and callable(apply_revision):
            apply_revision(
                revision_context=revision_context,
                task_instruction=session.task_instruction,
                context=session.context,
                max_steps=session.max_steps,
            )

        _append_live(
            self.live_trace,
            "subagent_revision_applied",
            task_instruction=session.task_instruction,
            context=session.context,
            tools=session.tools,
            max_steps=session.max_steps,
            executor_operation=executor_operation,
            model=session.model,
            task_scope=task_scope,
            resource=resource,
            revision_context=revision_context,
            requested_step_budget=requested_step_budget,
            granted_step_budget=granted_step_budget,
            global_budget=self.get_budget_status(),
        )
        return await self._run_session_until_control(event="revise")

    async def _start_session(
        self,
        *,
        task_instruction: str,
        context: str,
        model: str,
        tools: list[str] | None,
    ) -> _Session:
        original_instruction = getattr(self.env, "instruction", None)
        if hasattr(self.env, "instruction"):
            self.env.instruction = task_instruction

        original_question = original_instruction or getattr(self.env, "instruction", "") or ""
        agent = self._create_agent(
            task_instruction=task_instruction,
            context=context,
            model=model,
            tools=tools,
            original_question=original_question,
        )
        info = self.env.get_basic_info()

        reset_result = self.env.reset()
        obs = await reset_result if inspect.isawaitable(reset_result) else reset_result
        # A fresh delegate resets the environment. Re-read BasicInfo afterwards
        # so it receives the benchmark's base budget rather than a prior
        # session's extended per-environment limit.
        reset_info = self.env.get_basic_info()
        base_max_steps = (
            getattr(reset_info, "max_steps", self.default_max_steps)
            or self.default_max_steps
        )
        max_steps = min(int(base_max_steps), self.remaining_steps)
        _append_live(
            self.live_trace,
            "subagent_session_start",
            task_instruction=task_instruction,
            context=context,
            model=model,
            tools=tools,
            max_steps=max_steps,
            global_budget=self.get_budget_status(),
            initial_observation=obs,
        )

        return _Session(
            agent=agent,
            obs=obs,
            history=[],
            total_reward=0.0,
            max_steps=max_steps,
            model=model,
            tools=tools,
            task_instruction=task_instruction,
            context=context,
            original_instruction=original_instruction,
        )

    def _create_agent(
        self,
        *,
        task_instruction: str,
        context: str,
        model: str,
        tools: list[str] | None,
        original_question: str,
    ) -> Any:
        """Create/reset agent-local state without resetting the environment."""
        llm = create_llm_instance(LLMsConfig.default().get(model))
        if self.benchmark_type == "gaia":
            effort = os.getenv("PORCHESTRA_GAIA_SUB_REASONING_EFFORT")
            if effort:
                llm.default_reasoning_effort = effort
        if self.subagent_backend == "mini":
            agent = MiniSWESubAgent(
                llm=llm,
                benchmark_type=self.benchmark_type,
                task_instruction=task_instruction,
                context=context,
                original_question=original_question,
                allowed_tools=tools,
                max_observation_chars=self.observation_max_chars,
                live_trace=self.live_trace,
            )
        else:
            memory = self._create_memory(llm)
            agent = ReActSubAgent(
                llm=llm,
                benchmark_type=self.benchmark_type,
                task_instruction=task_instruction,
                context=context,
                original_question=original_question,
                allowed_tools=tools,
                memory=memory,
                max_observation_chars=self.observation_max_chars,
                live_trace=self.live_trace,
            )
        info = self.env.get_basic_info()
        agent.reset(info)
        return agent

    def _create_memory(self, llm: Any) -> Memory:
        """Construct the configured SubAgent memory without changing its prompt."""
        if self.memory_mode == "linear":
            return LinearMemory(
                llm=llm,
                max_observation_chars=self.observation_max_chars,
            )
        if self.memory_mode == "truncate":
            return TruncatingMemory(
                llm=llm,
                max_total_chars=self.memory_max_chars,
                max_record_chars=self.memory_record_max_chars,
            )
        return Memory(
            llm=llm,
            max_memory=self.memory_max_records,
            max_observation_chars=self.observation_max_chars,
        )

    async def _run_session_until_control(self, *, event: str) -> dict[str, Any]:
        session = self._session
        if session is None:
            return {"error": "No active SubAgent session", "done": False, "steps_taken": 0}

        while len(session.history) < session.max_steps:
            if self.remaining_steps <= 0:
                return await self._global_budget_exhausted_result(event=event)
            current_step = len(session.history) + 1
            if current_step >= session.max_steps:
                action, raw_response, raw_input = await session.agent.final_handoff(
                    observation=session.obs,
                    history=session.history,
                    current_step=current_step,
                    max_steps=session.max_steps,
                )
            else:
                action, raw_response, raw_input = await session.agent.step(
                    observation=session.obs,
                    history=session.history,
                    current_step=current_step,
                    max_steps=session.max_steps,
                )

            action_name = str(action.get("action", ""))
            if action_name in {"finish", "revise", "stop"}:
                sae = _normalize_sae(action_name, action.get("params", {}), session.obs)
                record = StepRecord(
                    observation=session.obs,
                    action=action,
                    reward=0.0,
                    raw_response=raw_response,
                    done=action_name in {"finish", "stop"},
                    info={"porchestra_control": action_name, "sae": sae},
                    raw_input=raw_input,
                )
                session.history.append(record)
                self._total_steps_used += 1
                if self.remaining_steps <= 0 and action_name != "finish":
                    sae = _global_budget_exhausted_sae(
                        self.total_steps_used, self.max_total_steps
                    )
                    action_name = "finish"
                result = await self._build_result(
                    event=event,
                    sae=sae,
                    done=action_name in {"finish", "stop"},
                    control_action=action_name,
                )
                _append_live(
                    self.live_trace,
                    "subagent_control",
                    event=event,
                    current_step=current_step,
                    control_action=action_name,
                    sae=sae,
                    result_summary={
                        "done": result.get("done"),
                        "steps_taken": result.get("steps_taken"),
                        "trace_summary": result.get("trace_summary"),
                    },
                )
                # SWE-bench may replace a finished executor while preserving its
                # container/patch. Keep that session available until MainAgent
                # chooses submit, replace, or a fresh delegate.
                if action_name == "stop" or (
                    action_name == "finish" and self.benchmark_type != "swebench"
                ):
                    self._close_session()
                return result

            obs_next, reward, done, step_info = await self._env_step(action)
            record_transition = getattr(session.agent, "record_transition", None)
            if callable(record_transition):
                transition_result = record_transition(
                    action=action,
                    observation_after=obs_next,
                    thinking=action.get("reasoning"),
                    reward=reward,
                    raw_response=raw_response,
                )
                if inspect.isawaitable(transition_result):
                    await transition_result
            _append_live(
                self.live_trace,
                "subagent_env_step",
                event=event,
                current_step=current_step,
                action=action,
                observation_before=session.obs,
                observation_after=obs_next,
                reward=reward,
                done=done,
                info=step_info,
            )
            record = StepRecord(
                observation=session.obs,
                action=action,
                reward=reward,
                raw_response=raw_response,
                done=done,
                info=step_info,
                raw_input=raw_input,
            )
            session.history.append(record)
            self._total_steps_used += 1
            session.total_reward += reward
            session.obs = obs_next
            if done:
                # The benchmark environment can terminate on its own step
                # limit before the SubAgent gets another turn to emit a
                # finish/revise/stop handoff.  Preserve the final observation
                # as a structured SAE instead of dropping it as ``sae=None``.
                sae = _environment_done_sae(
                    latest_observation=obs_next,
                    step_info=step_info,
                    max_steps=session.max_steps,
                )
                result = await self._build_result(
                    event=event,
                    sae=sae,
                    done=True,
                    control_action="stop",
                )
                _append_live(
                    self.live_trace,
                    "subagent_control",
                    event=event,
                    current_step=current_step,
                    control_action="stop",
                    sae=sae,
                    result_summary={
                        "done": result.get("done"),
                        "steps_taken": result.get("steps_taken"),
                        "trace_summary": result.get("trace_summary"),
                    },
                )
                self._close_session()
                return result

        sae = _budget_exhausted_sae(session.max_steps)
        result = await self._build_result(
            event=event, sae=sae, done=True, control_action="stop"
        )
        _append_live(
            self.live_trace,
            "subagent_control",
            event=event,
            current_step=len(session.history),
            control_action="stop",
            sae=sae,
            result_summary={
                "done": result.get("done"),
                "steps_taken": result.get("steps_taken"),
                "trace_summary": result.get("trace_summary"),
            },
        )
        self._close_session()
        return result

    async def _global_budget_exhausted_result(self, *, event: str) -> dict[str, Any]:
        sae = _global_budget_exhausted_sae(self.total_steps_used, self.max_total_steps)
        result = await self._build_result(
            event=event,
            sae=sae,
            done=True,
            control_action="global_budget_exhausted",
        )
        _append_live(
            self.live_trace,
            "global_subagent_budget_exhausted",
            event=event,
            global_budget=self.get_budget_status(),
            result_summary=result.get("trace_summary"),
        )
        return result

    async def _env_step(self, action: dict[str, Any]) -> tuple[Any, float, bool, dict[str, Any]]:
        result = self.env.step(action)
        return await result if inspect.isawaitable(result) else result

    async def _build_result(
        self,
        *,
        event: str,
        sae: dict[str, Any] | None,
        done: bool,
        control_action: str,
    ) -> dict[str, Any]:
        session = self._session
        if session is None:
            return {"error": "No active SubAgent session", "done": done, "steps_taken": 0}

        usage = session.agent.llm.get_usage_summary() if session.agent.llm else {}
        trace_summary, trace_summary_usage = await self._summarize_trace(
            session.history,
            session.task_instruction,
            sae,
            control_action,
        )
        return {
            "model": session.model,
            "tools_assigned": session.tools,
            "steps_taken": len(session.history),
            "done": done,
            "cost": usage.get("total_cost", 0.0),
            "input_tokens": usage.get("total_input_tokens", 0),
            "output_tokens": usage.get("total_output_tokens", 0),
            "sae": sae,
            "control_action": control_action,
            "event": event,
            "trace": [_make_serializable(step) for step in session.history],
            "trace_summary": trace_summary,
            "trace_summary_model": trace_summary_usage.get("model"),
            "trace_summary_cost": trace_summary_usage.get("total_cost", 0.0),
            "trace_summary_input_tokens": trace_summary_usage.get(
                "total_input_tokens", 0
            ),
            "trace_summary_output_tokens": trace_summary_usage.get(
                "total_output_tokens", 0
            ),
            "statistics": {
                "total_steps": len(session.history),
                "max_steps": session.max_steps,
                "global_steps_used": self.total_steps_used,
                "max_total_steps": self.max_total_steps,
                "remaining_global_steps": self.remaining_steps,
                "completed": done,
            },
        }

    async def _summarize_trace(
        self,
        trace: list[StepRecord],
        task_instruction: str,
        sae: dict[str, Any] | None,
        control_action: str,
    ) -> tuple[str, dict[str, Any]]:
        """Use AOrchestra's independent GAIA trace review when configured."""
        if (
            self.benchmark_type != "gaia"
            or os.getenv("PORCHESTRA_EVIDENCE_SOURCE", "sae").lower()
            != "trace_summary"
        ):
            return _sae_trace_summary(sae, control_action), {}
        if not trace:
            return "No steps executed", {}

        trace_text = create_gaia_formatter().format_trace(trace)
        prompt = f"""You are a trajectory summarizer. Review the SubAgent's execution trace.

Task: {task_instruction[:200]}
Steps: {len(trace)}

=== Trace ===
{trace_text}
===

Summarize in 5-10 bullets: key progress, problems, remaining issues.
Output ONLY bullets."""
        model = os.getenv(
            "PORCHESTRA_TRACE_SUMMARY_MODEL", "gemini-3-flash-preview"
        )
        try:
            review_llm = create_llm_instance(LLMsConfig.default().get(model))
            summary = await review_llm(prompt)
            rendered = str(summary or "").strip() or _sae_trace_summary(
                sae, control_action
            )
            return rendered, review_llm.get_usage_summary()
        except Exception as exc:
            logger.warning(
                f"[POrchestra DelegateTaskTool] Trace summarization failed: {exc}"
            )
            return _sae_trace_summary(sae, control_action), {}

    def _close_session(self) -> None:
        session = self._session
        if session and session.original_instruction is not None and hasattr(self.env, "instruction"):
            self.env.instruction = session.original_instruction
        self._session = None


class ReviseTaskTool(BaseAction):
    """Revise the current POrchestra attempt, optionally replacing its executor."""

    name: str = "revise_task"
    description: str = "Revise the current attempt while preserving its environment"
    parameters: dict[str, Any] = Field(default_factory=lambda: {
        "type": "object",
        "properties": {
            "executor": {
                "type": "object",
                "properties": {
                    "operation": {"type": "string", "enum": ["keep", "replace"]},
                    "model": {"type": "string"},
                },
                "required": ["operation"],
            },
            "task_scope": {
                "type": "object",
                "properties": {
                    "operation": {"type": "string", "enum": ["keep", "reduce", "expand", "remove", "decompose"]},
                    "object": {"type": "string"},
                    "details": {"type": "string"},
                },
            },
            "resource": {
                "type": "object",
                "properties": {
                    "operation": {"type": "string", "enum": ["keep", "request"]},
                    "object": {
                        "type": "string",
                        "enum": ["context", "tool", "budget", "constraint", "state_handoff", "none"],
                    },
                    "details": {"type": "string"},
                },
            },
            "context": {"type": "string"},
            "tools": {"type": "array", "items": {"type": "string"}},
            "step_budget": {"type": "integer"},
            "instruction": {"type": "string"},
        },
        "required": ["task_scope", "resource"],
    })

    delegate_tool: DelegateTaskTool = Field(default=None, exclude=True)

    class Config:
        arbitrary_types_allowed = True

    def __init__(self, delegate_tool: DelegateTaskTool):
        super().__init__()
        self.delegate_tool = delegate_tool

    async def __call__(
        self,
        executor: dict[str, Any] | None = None,
        task_scope: dict[str, Any] | None = None,
        resource: dict[str, Any] | None = None,
        context: str = "",
        tools: list[str] | None = None,
        step_budget: int | None = None,
        instruction: str = "",
    ) -> dict[str, Any]:
        return await self.delegate_tool.revise_active(
            executor=executor,
            task_scope=task_scope,
            resource=resource,
            context=context,
            tools=tools,
            step_budget=step_budget,
            instruction=instruction,
        )


def _format_revision_context(
    *,
    executor: dict[str, Any] | None,
    task_scope: dict[str, Any] | None,
    resource: dict[str, Any] | None,
    context: str,
    instruction: str,
    tools: list[str] | None,
    step_budget: int | None,
) -> str:
    parts: list[str] = ["[MainAgent revision]"]
    if executor:
        model = executor.get("model")
        executor_text = f"Executor: {executor.get('operation', 'keep')}"
        if model:
            executor_text += f" using {model}"
        parts.append(executor_text)
    if task_scope:
        parts.append(
            "Task scope: "
            f"{task_scope.get('operation', 'keep')} "
            f"{task_scope.get('object', 'assigned subtask')} | "
            f"{task_scope.get('details', '')}"
        )
    if resource:
        parts.append(
            "Resource: "
            f"{resource.get('operation', 'keep')} "
            f"{resource.get('object', 'none')} | "
            f"{resource.get('details', '')}"
        )
    if instruction:
        parts.append(f"Revised instruction: {instruction}")
    if context:
        parts.append(f"Additional context: {context}")
    if tools is not None:
        parts.append("Available tools now: " + (", ".join(tools) if tools else "none"))
    if step_budget:
        parts.append(f"Additional step budget: {step_budget}")
    return "\n".join(part for part in parts if part.strip()) if len(parts) > 1 else ""


def _normalize_sae(action_name: str, params: Any, latest_observation: Any) -> dict[str, Any]:
    aligned = (
        os.getenv("PORCHESTRA_GAIA_PROMPT_VARIANT", "control_skill").lower()
        == "aorch_aligned"
    )
    if isinstance(params, dict):
        sae = _repair_sae(action_name, params, latest_observation)
        aligned_errors = []
        if aligned:
            if sae.get("status") not in {"done", "partial", "blocked"}:
                aligned_errors.append("aligned SAE requires status=done|partial|blocked")
            if not isinstance(sae.get("result"), str):
                aligned_errors.append("aligned SAE requires string result")
            if not isinstance(sae.get("summary"), str) or not sae["summary"].strip():
                aligned_errors.append("aligned SAE requires non-empty summary")
        if not validate_sae(sae) and not aligned_errors:
            return sae

    action_type = action_name if action_name in {"finish", "revise", "stop"} else "stop"
    action: dict[str, Any] = {
        "type": action_type,
        "task_scope": _default_task_scope(action_type),
        "resource": _default_resource(action_type),
        "request": _default_sae_request(action_type),
        "reason": "The SubAgent control output did not match the SAE protocol.",
    }

    fallback = {
        "state": f"SubAgent returned invalid SAE params for {action_name}.",
        "action": action,
        "evidence": {
            "summary": f"Latest observation before invalid control output: {str(latest_observation)[:500]}",
            "raw": {},
        },
    }
    if aligned:
        fallback.update({
            "result": "",
            "status": "partial",
            "summary": "The SubAgent returned an invalid aligned control message.",
        })
    return fallback


def _repair_sae(action_name: str, params: dict[str, Any], latest_observation: Any) -> dict[str, Any]:
    action = params.get("action") if isinstance(params.get("action"), dict) else {}
    action_type = action.get("type")
    if action_type not in {"finish", "revise", "stop"}:
        action_type = action_name if action_name in {"finish", "revise", "stop"} else "stop"

    state = params.get("state")
    if not isinstance(state, str) or not state.strip():
        state = f"SubAgent returned malformed {action_type} SAE params."

    request = action.get("request")
    if not isinstance(request, str) or not request.strip():
        request = _default_sae_request(action_type)

    reason = action.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        reason = f"Repaired from a malformed {action_name} SAE control output."

    repaired_action: dict[str, Any] = {
        "type": action_type,
        "task_scope": _coerce_task_scope(action.get("task_scope"), action_type),
        "resource": _coerce_resource(action.get("resource"), action_type),
        "request": request,
        "reason": reason,
    }

    evidence = params.get("evidence") if isinstance(params.get("evidence"), dict) else {}
    evidence_summary = evidence.get("summary")
    if not isinstance(evidence_summary, str) or not evidence_summary.strip():
        evidence_summary = f"Latest observation before {action_type}: {str(latest_observation)[:500]}"

    evidence_raw = evidence.get("raw") if isinstance(evidence.get("raw"), dict) else {}

    repaired = {
        "state": state.strip(),
        "action": repaired_action,
        "evidence": {
            "summary": evidence_summary.strip(),
            "raw": evidence_raw,
        },
    }
    if isinstance(params.get("result"), str):
        repaired["result"] = params["result"].strip()
    if params.get("status") in {"done", "partial", "blocked"}:
        repaired["status"] = params["status"]
    if isinstance(params.get("summary"), str) and params["summary"].strip():
        repaired["summary"] = params["summary"].strip()
    return repaired


def _default_sae_request(action_type: str) -> str:
    if action_type == "finish":
        return "Report this local result to MainAgent."
    if action_type == "revise":
        return "Ask MainAgent to revise the current contract."
    return "Stop this path and let MainAgent decide the next step."


def _default_task_scope(action_type: str) -> dict[str, str]:
    if action_type == "stop":
        return {
            "operation": "remove",
            "object": "current path",
            "details": "Remove this path from further consideration.",
        }
    if action_type == "finish":
        return {
            "operation": "keep",
            "object": "assigned subtask",
            "details": "The assigned subtask is complete or ready for handoff.",
        }
    return {
        "operation": "keep",
        "object": "assigned subtask",
        "details": "Keep the current task scope unless MainAgent decides to adjust it.",
    }


def _default_resource(action_type: str) -> dict[str, str]:
    if action_type == "revise":
        return {
            "operation": "request",
            "object": "context",
            "details": "Request MainAgent guidance for the current contract.",
        }
    return {
        "operation": "keep",
        "object": "none",
        "details": "No resource change is requested.",
    }


def _coerce_task_scope(value: Any, action_type: str) -> dict[str, str]:
    default = _default_task_scope(action_type)
    if not isinstance(value, dict):
        return default

    operation = str(value.get("operation") or default["operation"]).strip()
    if operation not in {"keep", "reduce", "expand", "remove", "decompose"}:
        operation = default["operation"]

    obj = value.get("object")
    if not isinstance(obj, str) or not obj.strip():
        obj = default["object"]

    details = value.get("details")
    if not isinstance(details, str) or not details.strip():
        details = default["details"]

    return {"operation": operation, "object": obj.strip(), "details": details.strip()}


def _coerce_resource(value: Any, action_type: str) -> dict[str, str]:
    default = _default_resource(action_type)
    if isinstance(value, dict):
        operation = str(value.get("operation") or default["operation"]).strip()
        if operation not in {"keep", "request"}:
            operation = default["operation"]

        obj = str(value.get("object") or default["object"]).strip()
        if obj not in {"context", "tool", "budget", "constraint", "state_handoff", "none"}:
            obj = default["object"]

        details = value.get("details")
        if not isinstance(details, str) or not details.strip():
            details = default["details"]
        return {"operation": operation, "object": obj, "details": details.strip()}

    return default


def _budget_exhausted_sae(max_steps: int) -> dict[str, Any]:
    return {
        "state": f"SubAgent used all {max_steps} steps without finish, revise, or stop.",
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
                "details": "No resource change is requested in this forced stop.",
            },
            "request": "Stop this path and delegate remaining work if needed.",
            "reason": "The SubAgent exhausted its step budget.",
        },
        "evidence": {
            "summary": "The step budget was exhausted before a structured handoff.",
        },
    }


def _global_budget_exhausted_sae(used_steps: int, max_total_steps: int) -> dict[str, Any]:
    return {
        "state": (
            f"The shared SubAgent step budget is exhausted "
            f"({used_steps}/{max_total_steps})."
        ),
        "action": {
            "type": "finish",
            "task_scope": {
                "operation": "keep",
                "object": "current workspace",
                "details": "Preserve the current patch for final evaluation.",
            },
            "resource": {
                "operation": "keep",
                "object": "none",
                "details": "No SubAgent steps remain.",
            },
            "request": "Submit the current container for final evaluation.",
            "reason": "The per-task global SubAgent step budget is exhausted.",
        },
        "evidence": {
            "summary": (
                f"All {max_total_steps} globally available SubAgent steps have been used."
            ),
        },
    }


def _environment_done_sae(
    *,
    latest_observation: Any,
    step_info: Any,
    max_steps: int,
) -> dict[str, Any]:
    info = step_info if isinstance(step_info, dict) else {}
    if info.get("max_steps_reached"):
        state = f"The environment reached its {max_steps}-step limit before a structured handoff."
        reason = "The environment ended because its effective step budget was exhausted."
    else:
        state = "The environment ended before the SubAgent emitted a structured handoff."
        reason = "The benchmark environment returned done=True."
    return {
        "state": state,
        "action": {
            "type": "stop",
            "task_scope": {
                "operation": "remove",
                "object": "current path",
                "details": "The current environment session has ended and cannot continue.",
            },
            "resource": {
                "operation": "keep",
                "object": "state_handoff",
                "details": "Preserve the final environment observation for MainAgent.",
            },
            "request": "Use the final observation and delegate a new attempt if more work is needed.",
            "reason": reason,
        },
        "evidence": {
            "summary": f"Final environment observation: {str(latest_observation)[:1000]}",
        },
    }


def _sae_trace_summary(sae: dict[str, Any] | None, control_action: str) -> str:
    if not sae:
        return f"SubAgent ended with control_action={control_action}."
    action = sae.get("action", {})
    evidence = sae.get("evidence", {})
    task_scope = action.get("task_scope", {})
    resource = action.get("resource", {})
    return "\n".join([
        f"State: {sae.get('state', '')}",
        f"Action: {action.get('type', control_action)} | {action.get('request', '')}",
        f"Task scope: {task_scope.get('operation', '')} {task_scope.get('object', '')} | {task_scope.get('details', '')}",
        f"Resource: {resource.get('operation', '')} {resource.get('object', '')} | {resource.get('details', '')}",
        f"Evidence: {evidence.get('summary', '')}",
    ]).strip()


def _append_live(live_trace: Any, event_name: str, **payload: Any) -> None:
    if live_trace is None:
        return
    try:
        live_trace.append(event_name, **payload)
    except Exception as e:
        logger.debug(f"[POrchestra DelegateTaskTool] Failed to write live trace event {event_name}: {e}")
