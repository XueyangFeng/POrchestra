"""ARE-compatible GAIA2-POrchestra agent."""

from __future__ import annotations

import logging
import json
import math
import os
import time
from datetime import datetime, timezone
from typing import Any

from are.simulation.agents.agent_execution_result import AgentExecutionResult
from are.simulation.agents.are_simulation_agent import RunnableARESimulationAgent
from are.simulation.agents.llm.llm_engine import LLMEngine
from are.simulation.apps import AgentUserInterface
from are.simulation.notification_system import (
    BaseNotificationSystem,
    Message,
    MessageType,
)
from are.simulation.scenarios import Scenario
from are.simulation.tool_utils import AppTool, AppToolAdapter

from porchestra.gaia2_agent.boundary_trace import BoundaryTrace, serialize
from porchestra.gaia2_agent.json_utils import parse_first_json_object
from porchestra.gaia2_agent.memory import WorkingMemory
from porchestra.gaia2_agent.prompts import (
    MAIN_PROMPT,
    QWEN3_MAIN_FEW_SHOTS,
    format_tool_descriptions,
)
from porchestra.gaia2_agent.revision_ablation import (
    ablation_notice,
    configured_revision_ablation,
    mask_revision_params,
)
from porchestra.gaia2_agent.subagent import SubAgentResult, SubAgentSession
from porchestra.gaia2_agent.sae_ablation import configured_sae_ablation, main_visible_sae_record

logger = logging.getLogger(__name__)

EXTERNAL_TURN_TICK_SECONDS = 1.0
MAIN_LLM_MAX_ATTEMPTS = 5
MAIN_LLM_RETRY_DELAYS = (2.0, 5.0, 10.0, 20.0)


class POrchestraAREAgent(RunnableARESimulationAgent):
    """Single-active-SubAgent POrchestra agent for GAIA2."""

    def __init__(
        self,
        *,
        log_callback,
        llm_engine: LLMEngine,
        sub_llm_engine: LLMEngine | None = None,
        time_manager,
        env,
        max_turns: int | None = None,
        pause_env=None,
        resume_env=None,
        simulated_generation_time_config=None,
        max_main_decisions_per_turn: int = 8,
        max_total_steps: int = 300,
        default_subagent_steps: int = 30,
        poll_period: int = 0,
    ) -> None:
        self.log_callback = log_callback
        self.llm_engine = llm_engine
        self.sub_llm_engine = sub_llm_engine or llm_engine
        self.time_manager = time_manager
        self.env = env
        self.max_turns = max_turns
        self.pause_env = pause_env
        self.resume_env = resume_env
        self.simulated_generation_time_config = simulated_generation_time_config
        self.max_main_decisions_per_turn = max_main_decisions_per_turn
        self.max_total_steps = max_total_steps
        self.default_subagent_steps = default_subagent_steps
        self.revision_ablation = configured_revision_ablation()
        self.sae_ablation = configured_sae_ablation()
        if self.sae_ablation and (self.revision_ablation or poll_period or os.getenv("PORCHESTRA_DELEGATION_MASK_PLAN")):
            raise ValueError("SAE ablation must run without revision or controlled communication ablations")
        if type(poll_period) is not int or poll_period < 0:
            raise ValueError('poll_period must be a nonnegative integer')
        self._e2e_poll_period = poll_period
        try:
            self.no_progress_timeout_seconds = max(
                0.0,
                float(os.getenv("PORCHESTRA_NO_PROGRESS_TIMEOUT_SECONDS", "0")),
            )
        except ValueError:
            logger.warning(
                "[POrchestra GAIA2] Invalid PORCHESTRA_NO_PROGRESS_TIMEOUT_SECONDS; disabled"
            )
            self.no_progress_timeout_seconds = 0.0

        self.notification_system: BaseNotificationSystem | None = None
        self.all_tools: dict[str, Any] = {}
        self.memory = WorkingMemory(sae_ablation=self.sae_ablation)
        self.active_session: SubAgentSession | None = None
        self.active_status = "none"
        self.active_attempt = 0
        self.active_revision = 0
        self.total_subagent_steps = 0
        self._active_session_recorded_steps = 0
        self.original_task = ""
        self.current_task = ""
        self.notification_history: list[str] = []
        self._notification_history_seen: set[tuple[str, str, str]] = set()
        self.follow_up_events: list[dict[str, Any]] = []
        self.current_attachments = []
        self._initialized = False
        self._stopped = False
        self._scenario: Scenario | None = None
        self._boundary_trace = BoundaryTrace("unknown")
        self._boundary_wait_started: float | None = None
        self._boundary_wait_last_recorded: float | None = None
        self._boundary_wait_polls = 0
        self._boundary_tick_advanced = False
        self._last_progress_monotonic = time.monotonic()

    @property
    def agent_framework(self) -> str:
        return "POrchestraAREAgent"

    @property
    def model(self) -> str:
        if self.sub_llm_engine.model_name == self.llm_engine.model_name:
            return self.llm_engine.model_name
        return f"main={self.llm_engine.model_name};sub={self.sub_llm_engine.model_name}"

    def llm_trace_context(self) -> dict[str, Any]:
        """Return orchestration state attached to each Main/Sub model call."""

        return {
            "active_status": self.active_status,
            "active_attempt": self.active_attempt,
            "active_revision": self.active_revision,
            "total_subagent_steps": self.total_subagent_steps,
            "environment_time": self.time_manager.time(),
            "revision_ablation": getattr(self, "revision_ablation", ""),
            "sae_ablation": getattr(self, "sae_ablation", ""),
        }

    def run_scenario(
        self,
        scenario: Scenario,
        notification_system: BaseNotificationSystem | None,
        initial_agent_logs=None,
    ) -> AgentExecutionResult:
        del initial_agent_logs
        if not self._initialized:
            self._prepare(scenario, notification_system)

        max_turns = scenario.nb_turns if scenario.nb_turns is not None else self.max_turns
        turns = 0
        output: str | None = None
        while not self._stopped and (max_turns is None or turns < max_turns):
            user_messages, env_messages, stop_messages = self._get_messages()
            if stop_messages:
                self._trace_boundary_messages(user_messages, env_messages, stop_messages)
                logger.info("[POrchestra GAIA2] Environment stop received")
                break
            if not user_messages and not env_messages:
                if self._advance_external_turn_tick():
                    self._mark_progress()
                    continue
                if self._no_progress_timed_out():
                    elapsed = time.monotonic() - self._last_progress_monotonic
                    logger.warning(
                        "[POrchestra GAIA2] No-progress timeout after %.1f wall-clock seconds; "
                        "ending scenario instead of polling indefinitely",
                        elapsed,
                    )
                    self._stopped = True
                    return AgentExecutionResult(output="no_progress_timeout")
                self._trace_boundary_waiting()
                time.sleep(1)
                continue

            self._mark_progress()
            self._trace_boundary_messages(user_messages, env_messages, stop_messages)

            self.current_task = self._format_turn_task(user_messages, env_messages)
            self._append_messages_to_notification_history(user_messages, env_messages)
            if user_messages and not self.original_task:
                self.original_task = self._format_original_task(user_messages)
            self.current_attachments = [
                attachment
                for msg in user_messages
                for attachment in getattr(msg, "attachments", [])
            ]
            logger.info("[POrchestra GAIA2] New turn task: %s", self.current_task[:500])
            try:
                output = self._resume_active_subagent_after_external_update()
                if output is None:
                    output = self._run_main_until_turn_end()
                self._mark_progress()
            except Exception:
                logger.exception("[POrchestra GAIA2] Main loop failed")
                raise

            if output == "turn_ended":
                turns += 1
                continue
            if output == "scenario_finished":
                break
            if output == "paused":
                continue
        return AgentExecutionResult(output=output)

    def _mark_progress(self) -> None:
        self._last_progress_monotonic = time.monotonic()

    def _no_progress_timed_out(self) -> bool:
        timeout = self.no_progress_timeout_seconds
        return timeout > 0 and time.monotonic() - self._last_progress_monotonic >= timeout

    def stop(self) -> None:
        self._stopped = True

    def _prepare(
        self,
        scenario: Scenario,
        notification_system: BaseNotificationSystem | None,
    ) -> None:
        app_tools = scenario.get_tools()
        app_tools = self._remove_aui_irrelevant_tools(app_tools)
        adapted = [AppToolAdapter(tool) for tool in app_tools]
        self.all_tools = {tool.name: tool for tool in adapted}
        self.notification_system = notification_system
        self._scenario = scenario
        from porchestra.gaia2_agent.delegation_mask import DelegationMask
        self._delegation_mask = (
            DelegationMask.from_env(scenario.scenario_id)
            if type(self) is POrchestraAREAgent else None
        )
        self._boundary_trace = BoundaryTrace(scenario.scenario_id)
        self._mark_progress()
        self.total_subagent_steps = 0
        self._active_session_recorded_steps = 0
        self._initialized = True
        logger.info("[POrchestra GAIA2] Found %s tools", len(self.all_tools))

    def _remove_aui_irrelevant_tools(self, app_tools: list[AppTool]) -> list[AppTool]:
        aui_tools = [tool for tool in app_tools if "AgentUserInterface" in tool.name]
        if aui_tools:
            aui: AgentUserInterface = aui_tools[0].class_instance  # type: ignore
            aui.wait_for_user_response = False
            remove = {
                "AgentUserInterface__get_last_message_from_user",
                "AgentUserInterface__get_last_message_from_agent",
                "AgentUserInterface__get_last_unread_messages",
                "AgentUserInterface__get_all_messages",
            }
            app_tools = [tool for tool in app_tools if tool.name not in remove]
        return app_tools

    def _get_messages(self) -> tuple[list[Message], list[Message], list[Message]]:
        if self.notification_system is None:
            raise RuntimeError("notification_system is not set")
        now = datetime.fromtimestamp(self.time_manager.time(), tz=timezone.utc)
        messages = self.notification_system.message_queue.get_by_timestamp(now)
        user_messages = [m for m in messages if m.message_type == MessageType.USER_MESSAGE]
        env_messages = [m for m in messages if m.message_type == MessageType.ENVIRONMENT_NOTIFICATION]
        stop_messages = [m for m in messages if m.message_type == MessageType.ENVIRONMENT_STOP]
        return user_messages, env_messages, stop_messages

    def _format_turn_task(self, user_messages: list[Message], env_messages: list[Message]) -> str:
        parts: list[str] = []
        if user_messages:
            parts.append("User messages:")
            parts.extend(f"- {m.message}" for m in user_messages)
        if env_messages:
            parts.append("Environment notifications:")
            parts.extend(f"- {m.message}" for m in env_messages)
        return "\n".join(parts)

    def _format_original_task(self, user_messages: list[Message]) -> str:
        parts = ["Initial user task:"]
        parts.extend(f"- {m.message}" for m in user_messages)
        return "\n".join(parts)

    def _append_messages_to_notification_history(
        self,
        user_messages: list[Message],
        env_messages: list[Message],
    ) -> None:
        for message in user_messages:
            self._append_notification_history_item("USER", message)
        for message in env_messages:
            self._append_notification_history_item("ENV", message)

    def _append_notification_history_item(self, kind: str, message: Message) -> None:
        timestamp = _format_message_timestamp(message)
        text = str(message.message)
        key = (kind, timestamp, text)
        if key in self._notification_history_seen:
            return
        self._notification_history_seen.add(key)
        self.notification_history.append(f"[{timestamp}] {kind}: {text}")

    def _append_subagent_notification_logs(self, result: SubAgentResult) -> None:
        for log in result.logs:
            get_type = getattr(log, "get_type", None)
            log_type = get_type() if callable(get_type) else ""
            if log_type not in {"agent_user_interface", "environment_notifications"}:
                continue
            get_content = getattr(log, "get_content_for_llm", None)
            content = get_content() if callable(get_content) else getattr(log, "content", "")
            if not content:
                continue
            timestamp = _format_log_timestamp(log)
            kind = "USER" if log_type == "agent_user_interface" else "ENV"
            for line in str(content).splitlines():
                line = line.strip()
                if not line:
                    continue
                key = (f"SUBAGENT_{kind}", timestamp, line)
                if key in self._notification_history_seen:
                    continue
                self._notification_history_seen.add(key)
                self.notification_history.append(f"[{timestamp}] SUBAGENT {kind}: {line}")

    def _format_notification_history(self) -> str:
        if not self.notification_history:
            return "No notifications received yet."
        return "\n".join(self.notification_history)

    @property
    def poll_period(self):
        mask = getattr(self, '_delegation_mask', None)
        return getattr(self, '_e2e_poll_period', 0) or (mask.poll_period if mask is not None else 0)

    def _run_main_until_turn_end(self) -> str | None:
        experiment = getattr(self, '_delegation_mask', None)
        decision_limit = self.max_main_decisions_per_turn
        if experiment is not None and experiment.spec.get('total_execution_steps'):
            decision_limit = max(decision_limit, experiment.spec['total_execution_steps'] + 1)
        if getattr(self, '_e2e_poll_period', 0):
            decision_limit = max(decision_limit, self.max_total_steps + 8)
        for _ in range(decision_limit):
            if getattr(self, '_e2e_poll_period', 0) and self.total_subagent_steps >= self.max_total_steps:
                self._stopped = True
                logger.info('Polling execution budget exhausted (%s)', self.max_total_steps)
                return 'scenario_finished'
            decision = self._main_decision()
            action = decision.get("action")
            params = decision.get("params") if isinstance(decision.get("params"), dict) else {}
            logger.info("[POrchestra GAIA2] Main decision: %s", decision)
            mask = getattr(self, '_delegation_mask', None)
            failure_mode=mask is not None and mask.spec.get('communication_policy') in ('failure_triggered','budget_boundary')
            if (self.poll_period or failure_mode) and action in ('keep_task','stop_task'):
                if action == 'stop_task':
                    if mask is not None:
                        mask.finish('main_stopped')
                        self._stopped = True
                        return 'scenario_finished'
                    self.active_session = None
                    self.active_status = 'stopped'
                    self.memory.add_inspection(source='stop_task',target_id=str(self.active_attempt),content=json.dumps(params))
                    continue
                if self.active_session is None or self.active_status not in ('revise_requested','poll_paused','failure_paused'):
                    logger.warning('keep_task without paused SubAgent')
                    continue
                if mask is not None:
                    mask.log('keep_task', params=params)
                result=self.active_session.run_until_control(task='[MainAgent response] Keep the current configuration and continue.')
                self._record_result('keep',result)
                boundary=self._external_boundary_output()
                if boundary:
                    return boundary
                continue
            if action == "inspect_notification":
                self._inspect_notification(params)
                continue
            if action == "delegate_task":
                self._delegate(params)
                boundary = self._external_boundary_output()
                if boundary:
                    return boundary
                continue
            if action == "revise_task":
                self._revise(params)
                boundary = self._external_boundary_output()
                if boundary:
                    return boundary
                continue
            if action == "wait":
                self._wait(params)
                self.memory.add_inspection(
                    source="wait",
                    target_id=str(params.get("timeout") or 60),
                    content="Wait completed; returning to outer loop to collect new notifications.",
                )
                return "paused"
            if action == "collect_until":
                if not self._collect_until(params):
                    return "paused"
                continue
            if action == "finalize_task":
                mask = getattr(self, "_delegation_mask", None)
                if mask is not None and mask.track_sessions:
                    mask.finish("main_finalized_without_target_recovery")
                    self._stopped = True
                    return "scenario_finished"
                content = str(params.get("message") or params.get("content") or "").strip()
                tool = self.all_tools.get("AgentUserInterface__send_message_to_user")
                if tool is None:
                    logger.warning("[POrchestra GAIA2] AUI send tool unavailable")
                    continue
                if not content:
                    logger.warning("[POrchestra GAIA2] Final user message is empty")
                    continue
                tool(content=content)
                self._stopped = True
                return "scenario_finished"

            logger.warning("[POrchestra GAIA2] Unknown MainAgent action: %s", action)
            return "paused"
        logger.warning("[POrchestra GAIA2] Main decision budget exhausted")
        if getattr(self, '_e2e_poll_period', 0):
            self._stopped = True
            return 'scenario_finished'
        return "paused"

    def _inspect_notification(self, params: dict[str, Any]) -> None:
        source = str(params.get("source") or "")
        if source != "message_conversation":
            self.memory.add_inspection(
                source=source or "unknown",
                target_id=str(params.get("id") or ""),
                content=f"Unsupported inspection source: {source}",
            )
            return
        conversation_id = str(params.get("id") or params.get("conversation_id") or "").strip()
        if not conversation_id:
            self.memory.add_inspection(
                source=source,
                target_id="",
                content="Missing conversation id.",
            )
            return
        try:
            limit = int(params.get("limit") or 10)
        except (TypeError, ValueError):
            limit = 10
        content = self._read_conversation_for_main(conversation_id, limit=max(1, min(limit, 20)))
        self.memory.add_inspection(source=source, target_id=conversation_id, content=content)

    def _read_conversation_for_main(self, conversation_id: str, *, limit: int = 10) -> str:
        tool = self.all_tools.get("Messages__read_conversation")
        if tool is None:
            return "Messages__read_conversation is unavailable."
        try:
            result = tool(conversation_id=conversation_id, offset=0, limit=limit)
        except Exception as e:
            logger.warning("[POrchestra GAIA2] inspect_notification failed: %s", e)
            return f"Conversation read failed: {type(e).__name__}: {e}"
        return _format_conversation_for_main(conversation_id, result)

    def _main_decision(self) -> dict[str, Any]:
        mask = getattr(self, "_delegation_mask", None)
        if mask is not None:
            frozen = mask.frozen_decision()
            if frozen is not None:
                return frozen
        few_shot_examples = ""
        qwen_few_shots_enabled = os.getenv(
            "PORCHESTRA_QWEN_MAIN_FEW_SHOTS", "1"
        ).strip().lower() not in {"0", "false", "no", "off"}
        if qwen_few_shots_enabled and "qwen3" in self.llm_engine.model_name.lower():
            few_shot_examples = QWEN3_MAIN_FEW_SHOTS
        prompt = MAIN_PROMPT.format(
            original_task=self.original_task or self.current_task,
            notification_history=self._format_notification_history(),
            follow_up_events=self._format_follow_up_events(),
            active_status=self._format_active_status(),
            working_memory=self.memory.format() + (
                self._delegation_mask.main_memory
                if getattr(self, "_delegation_mask", None) is not None else ""
            ),
            tool_descriptions=format_tool_descriptions(list(self.all_tools.values())),
            few_shot_examples=few_shot_examples,
        )
        if self.poll_period:
            from porchestra.gaia2_agent.polling import MAIN_POLL_INSTRUCTION
            prompt += MAIN_POLL_INSTRUCTION
            if getattr(self, '_e2e_poll_period', 0):
                prompt += '\nThis is a full GAIA2 task. finish or stop_task only terminates the current SubAgent. Continue with a fresh delegation if work remains. Only finalize_task completes the overall task.'
        if mask is not None and mask.spec.get('communication_policy')=='failure_triggered':
            from porchestra.gaia2_agent.failure_trigger import MAIN_INSTRUCTION
            prompt += MAIN_INSTRUCTION
        if mask is not None and mask.spec.get('communication_policy')=='budget_boundary':
            from porchestra.gaia2_agent.budget_boundary import MAIN_INSTRUCTION
            prompt += MAIN_INSTRUCTION
        if mask is not None and mask.spec.get('communication_policy') == 'completion':
            from porchestra.gaia2_agent.completion import MAIN_INSTRUCTION
            prompt += MAIN_INSTRUCTION
        if getattr(self, "revision_ablation", ""):
            prompt += (
                "\n\n==== Revision Ablation for This Run ====\n"
                + ablation_notice(self.revision_ablation)
            )
        messages = [{"role": "user", "content": prompt}]
        logger.info("[POrchestra GAIA2] MainAgent LLM call start; prompt_chars=%s", len(prompt))
        logger.info("[POrchestra GAIA2] MainAgent raw prompt begin\n%s\n[POrchestra GAIA2] MainAgent raw prompt end", prompt)
        response = ""
        for attempt in range(3):
            response, _ = self._call_main_llm(messages)
            logger.info(
                "[POrchestra GAIA2] MainAgent LLM call done; attempt=%s response_chars=%s",
                attempt + 1,
                len(response or ""),
            )
            logger.info(
                "[POrchestra GAIA2] MainAgent raw response begin\n%s\n[POrchestra GAIA2] MainAgent raw response end",
                response or "",
            )
            decision = parse_first_json_object(response)
            if decision:
                return decision
            logger.warning(
                "[POrchestra GAIA2] MainAgent returned invalid JSON on attempt %s: %r",
                attempt + 1,
                (response or "")[:1000],
            )
            messages.extend(
                [
                    {"role": "assistant", "content": response or ""},
                    {
                        "role": "user",
                        "content": (
                            "Your previous response was not a valid JSON object. "
                            "Return ONLY one valid JSON object using action "
                            "delegate_task, revise_task, or finalize_task. "
                            "Do not include markdown, comments, or extra text."
                        ),
                    },
                ]
            )
        return {
            "action": "invalid_json",
            "params": {},
            "reasoning": "MainAgent returned invalid JSON after retries.",
        }

    def _call_main_llm(self, messages: list[dict[str, Any]]) -> tuple[Any, Any]:
        for attempt in range(1, MAIN_LLM_MAX_ATTEMPTS + 1):
            try:
                return self.llm_engine(messages, stop_sequences=[])
            except Exception as exc:
                if attempt == MAIN_LLM_MAX_ATTEMPTS:
                    logger.exception(
                        "[POrchestra GAIA2] MainAgent LLM call failed after %s attempts",
                        attempt,
                    )
                    raise
                delay = MAIN_LLM_RETRY_DELAYS[attempt - 1]
                logger.warning(
                    "[POrchestra GAIA2] MainAgent LLM call failed (%s: %s); "
                    "retrying attempt %s/%s in %.1fs",
                    type(exc).__name__,
                    exc,
                    attempt + 1,
                    MAIN_LLM_MAX_ATTEMPTS,
                    delay,
                )
                time.sleep(delay)

        raise RuntimeError("unreachable")

    def _delegate(self, params: dict[str, Any]) -> None:
        step_budget = self._bounded_subagent_budget(
            int(params.get("step_budget") or self.default_subagent_steps)
        )
        if step_budget <= 0:
            self.memory.add_inspection(
                source="budget",
                target_id="subagent",
                content=f"Global SubAgent step budget exhausted ({self.max_total_steps}).",
            )
            self.active_status = "budget_exhausted"
            return
        self.active_attempt += 1
        self.active_revision = 0
        self.active_status = "running"
        self._active_session_recorded_steps = 0
        tools = self._sanitize_tools(params.get("tools"))
        instruction = str(params.get("task_instruction") or self.current_task)
        context = str(params.get("context") or "")
        mask = getattr(self, "_delegation_mask", None)
        callback = self.log_callback
        if mask is not None and self.active_attempt == 1:
            tools, context = mask.apply(
                params, tools, instruction, context,
                self.original_task or self.current_task, self.current_attachments,
            )
            callback = mask.callback(callback)
        elif mask is not None and mask.track_sessions:
            callback = mask.callback(callback)
        session_cls = SubAgentSession
        if mask is not None and mask.spec.get('communication_policy') == 'completion':
            from porchestra.gaia2_agent.completion import CompletionSubAgentSession
            session_cls = CompletionSubAgentSession
        session = session_cls(
            llm_engine=self.sub_llm_engine,
            all_tools=self.all_tools,
            task_instruction=instruction,
            context=context,
            original_task=self.original_task or self.current_task,
            tools=tools,
            max_steps=step_budget,
            log_callback=callback,
            time_manager=self.time_manager,
            notification_system=self.notification_system,
            pause_env=self.pause_env,
            resume_env=self.resume_env,
            simulated_generation_time_config=self.simulated_generation_time_config,
            attachments=self.current_attachments,
            poll_period=getattr(self, '_e2e_poll_period', 0),
            revision_ablation=getattr(self, "revision_ablation", ""),
        )
        self.active_session = session
        if mask is not None and (self.active_attempt == 1 or mask.track_sessions):
            session._delegation_mask = mask
            if self.active_attempt > 1 and mask.track_sessions:
                mask.revision(params, session, route='delegate_task')
        result = session.run_until_control()
        self._record_result("delegate", result)

    def _revise(self, params: dict[str, Any]) -> None:
        if self.active_session is None or self.active_status not in {"revise_requested", "poll_paused", "failure_paused"}:
            logger.warning("[POrchestra GAIA2] revise_task without active revise request")
            return
        if getattr(self, "revision_ablation", ""):
            effective = mask_revision_params(params, self.revision_ablation)
            ignored = sorted(set(params) - set(effective))
            logger.info(
                "[POrchestra GAIA2] revise ablation=%s ignored_fields=%s",
                self.revision_ablation,
                ignored,
            )
            params = effective
        self.active_revision += 1
        tools = self._sanitize_tools(params.get("tools"), allow_empty=True)
        step_budget = params.get("step_budget")
        if step_budget is not None:
            step_budget = self._bounded_subagent_budget(int(step_budget))
            if step_budget <= 0:
                self.memory.add_inspection(
                    source="budget",
                    target_id="subagent",
                    content=f"Global SubAgent step budget exhausted ({self.max_total_steps}).",
                )
                self.active_status = "budget_exhausted"
                return
        self.active_session.revise(
            instruction=str(params.get("instruction") or ""),
            context=str(params.get("context") or ""),
            tools=tools if tools else None,
            step_budget=step_budget,
            task_scope=params.get("task_scope") if isinstance(params.get("task_scope"), dict) else None,
            resource=params.get("resource") if isinstance(params.get("resource"), dict) else None,
        )
        mask = getattr(self, "_delegation_mask", None)
        if mask is not None and (self.active_attempt == 1 or mask.track_sessions):
            mask.revision(params, self.active_session)
        result = self.active_session.run_until_control()
        self._record_result("revise", result)

    def _record_result(self, event: str, result: SubAgentResult) -> None:
        mask = getattr(self, "_delegation_mask", None)
        if mask is not None and (self.active_attempt == 1 or mask.track_sessions):
            mask.result(event, result)
            if mask.should_stop():
                self.active_status = "experiment_complete"
                self._stopped = True
                return
        delta_steps = max(0, result.steps - self._active_session_recorded_steps)
        self.total_subagent_steps += delta_steps
        self._active_session_recorded_steps = result.steps
        self._append_subagent_notification_logs(result)
        if result.control in ('poll','failure','budget'):
            feedback = self.active_session.take_poll_feedback()
            logger.info('[POrchestra polling] attempt=%s iteration=%s period=%s',
                        self.active_attempt, result.steps, self.poll_period)
            source={'poll':'periodic_poll','failure':'executor_failure','budget':'local_budget'}[result.control]
            self.memory.add_inspection(source=source,target_id=str(self.active_attempt),
                content=json.dumps(feedback,ensure_ascii=False,default=str))
            if mask is not None:
                mask.log({'poll':'poll','failure':'failure_inspection','budget':'budget_inspection'}[result.control],attempt=self.active_attempt,iterations=result.steps,feedback=feedback)
        if result.sae is not None:
            self.memory.add(
                attempt=self.active_attempt,
                revision=self.active_revision,
                event=event,
                task=result.task,
                tools=result.tools,
                steps=result.steps,
                max_steps=result.max_steps,
                sae=result.sae,
            )
            if getattr(self, "sae_ablation", ""):
                logger.info(
                    "[POrchestra GAIA2] SAE ablation=%s control=%s main_visible_fields=%s",
                    self.sae_ablation, result.control, sorted(self.memory.items[-1]),
                )
        self._record_follow_up_event(event, result)
        control = result.control
        if control in ('failure','budget'):
            self.active_status = 'failure_paused'
        elif control == "poll":
            self.active_status = "poll_paused"
        elif control == "revise":
            self.active_status = "revise_requested"
        elif control == "finish":
            self.active_status = "finished"
            self.active_session = None
        elif control == "stop":
            self.active_status = "stopped"
            self.active_session = None
        elif control == "external_turn_end":
            self.active_status = "external_turn_end"
            self._start_boundary_trace(event, result)
            if mask is not None and mask.spec.get('communication_policy') == 'completion':
                self.active_session = None
        elif control == "external_pause":
            self.active_status = "external_pause"
            self._start_boundary_trace(event, result)
        else:
            self.active_status = "unknown"

    def _bounded_subagent_budget(self, requested_steps: int) -> int:
        remaining = self.max_total_steps - self.total_subagent_steps
        if remaining <= 0:
            return 0
        return max(0, min(requested_steps, remaining))

    def _external_boundary_output(self) -> str | None:
        if self.active_status == "experiment_complete":
            return "scenario_finished"
        if self.active_status == "external_turn_end":
            logger.info("[POrchestra GAIA2] SubAgent yielded at an ARE turn boundary")
            return "turn_ended"
        if self.active_status == "external_pause":
            logger.info("[POrchestra GAIA2] SubAgent paused for an ARE notification")
            return "paused"
        return None

    def _resume_active_subagent_after_external_update(self) -> str | None:
        if self.active_status not in {"external_turn_end", "external_pause"}:
            return None
        if self.active_session is None:
            logger.warning(
                "[POrchestra GAIA2] Missing active SubAgent session for status %s",
                self.active_status,
            )
            self.active_status = "unknown"
            return None
        result = self.active_session.resume_after_external_update(
            self.current_task,
            attachments=self.current_attachments,
        )
        self._record_result("resume", result)
        return self._external_boundary_output()

    def _start_boundary_trace(self, event: str, result: SubAgentResult) -> None:
        self._boundary_tick_advanced = False
        trace = getattr(self, "_boundary_trace", None)
        if trace is None or not trace.enabled:
            return
        self._boundary_wait_started = time.monotonic()
        self._boundary_wait_last_recorded = None
        self._boundary_wait_polls = 0
        trace.append(
            "external_boundary",
            source_event=event,
            control=result.control,
            agent=self._agent_trace_state(),
            subagent_logs=self._serialize_subagent_logs(result.logs),
            environment=self._environment_snapshot(full=True),
            notification_queue=self._notification_queue_snapshot(),
            oracle=self._oracle_snapshot(),
        )

    def _advance_external_turn_tick(self) -> bool:
        """Advance at most one tick, then let ARE's event thread run normally."""
        if self.active_status != "external_turn_end" or self._boundary_tick_advanced:
            return False
        if self.resume_env is None:
            return False

        self._boundary_tick_advanced = True
        before = self.time_manager.time()
        self.resume_env(EXTERNAL_TURN_TICK_SECONDS)
        after = self.time_manager.time()
        logger.info(
            "[POrchestra GAIA2] Advanced external turn boundary by at most %.1f simulated second "
            "(%.3f -> %.3f)",
            EXTERNAL_TURN_TICK_SECONDS,
            before,
            after,
        )
        return True

    def _trace_boundary_waiting(self) -> None:
        trace = getattr(self, "_boundary_trace", None)
        started = getattr(self, "_boundary_wait_started", None)
        if trace is None or not trace.enabled or started is None:
            return
        self._boundary_wait_polls += 1
        now = time.monotonic()
        last = self._boundary_wait_last_recorded
        if last is not None and now - last < 30:
            return
        self._boundary_wait_last_recorded = now
        trace.append(
            "waiting_for_external_update",
            waited_wall_seconds=round(now - started, 3),
            empty_polls=self._boundary_wait_polls,
            agent=self._agent_trace_state(),
            environment=self._environment_snapshot(full=False),
            notification_queue=self._notification_queue_snapshot(),
        )

    def _trace_boundary_messages(
        self,
        user_messages: list[Message],
        env_messages: list[Message],
        stop_messages: list[Message],
    ) -> None:
        trace = getattr(self, "_boundary_trace", None)
        started = getattr(self, "_boundary_wait_started", None)
        if trace is None or not trace.enabled or started is None:
            return
        trace.append(
            "external_update_received" if not stop_messages else "environment_stop_received",
            waited_wall_seconds=round(time.monotonic() - started, 3),
            empty_polls=self._boundary_wait_polls,
            user_messages=serialize(user_messages),
            environment_messages=serialize(env_messages),
            stop_messages=serialize(stop_messages),
            agent=self._agent_trace_state(),
            environment=self._environment_snapshot(full=True),
            notification_queue=self._notification_queue_snapshot(),
        )
        self._boundary_wait_started = None
        self._boundary_wait_last_recorded = None
        self._boundary_wait_polls = 0

    def _agent_trace_state(self) -> dict[str, Any]:
        return {
            "active_status": self.active_status,
            "active_attempt": self.active_attempt,
            "active_revision": self.active_revision,
            "total_subagent_steps": self.total_subagent_steps,
            "current_task": self.current_task,
        }

    def _environment_snapshot(self, *, full: bool) -> dict[str, Any]:
        env = self.env
        event_log = getattr(env, "event_log", None)
        event_queue = getattr(env, "event_queue", None)
        past_events = self._event_collection(event_log, "list_view")
        future_events = self._event_collection(event_queue, "list_view")
        past_event_records = [_flat_event(event) for event in past_events]
        future_event_records = [_flat_event(event) for event in future_events]
        snapshot = {
            "state": serialize(getattr(env, "state", None)),
            "stop_event_set": _event_is_set(getattr(env, "stop_event", None)),
            "pause_event_set": _event_is_set(getattr(env, "pause_event", None)),
            "waiting_for_notification": getattr(env, "waiting_for_notification", None),
            "tick_count": getattr(env, "tick_count", None),
            "current_time": getattr(env, "current_time", None),
            "time_manager_time": _safe_time(getattr(env, "time_manager", None)),
            "past_event_count": len(past_events),
            "future_event_count": len(future_events),
            "past_events_tail": past_event_records[-20:],
            "future_events_head": future_event_records[:20],
        }
        if full:
            snapshot["past_events"] = past_event_records
            snapshot["future_events"] = future_event_records
        return snapshot

    def _notification_queue_snapshot(self) -> list[Any]:
        notification_system = self.notification_system
        queue = getattr(notification_system, "message_queue", None)
        return serialize(self._event_collection(queue, "list_view"))

    def _oracle_snapshot(self) -> dict[str, Any]:
        scenario = getattr(self, "_scenario", None)
        if scenario is None:
            return {}
        oracle_log = getattr(scenario, "oracle_run_event_log", None)
        return {
            "scenario_id": getattr(scenario, "scenario_id", None),
            "nb_turns": getattr(scenario, "nb_turns", None),
            "oracle_run_event_log": [_flat_event(event) for event in (oracle_log or [])],
            "declared_events": [
                _flat_event(event)
                for event in getattr(scenario, "events", [])
            ],
        }

    def _serialize_subagent_logs(self, logs: list[Any]) -> list[Any]:
        selected = []
        for log in logs:
            get_type = getattr(log, "get_type", None)
            log_type = get_type() if callable(get_type) else ""
            if log_type in {
                "tool_call",
                "observation",
                "error",
                "agent_user_interface",
                "environment_notifications",
            }:
                selected.append(log)
        return serialize(selected[-100:])

    @staticmethod
    def _event_collection(owner: Any, method_name: str) -> list[Any]:
        method = getattr(owner, method_name, None)
        if not callable(method):
            return []
        try:
            return list(method())
        except Exception as exc:
            return [{"snapshot_error": f"{type(exc).__name__}: {exc}"}]

    def _wait(self, params: dict[str, Any]) -> Any:
        timeout = int(params.get("timeout") or 60)
        tool = self.all_tools.get("SystemApp__wait_for_notification")
        if tool is None:
            logger.warning("[POrchestra GAIA2] SystemApp__wait_for_notification unavailable")
            return "SystemApp__wait_for_notification unavailable."
        try:
            return tool(timeout=timeout)
        except Exception as e:
            logger.warning("[POrchestra GAIA2] wait failed: %s", e)
            return f"wait failed: {type(e).__name__}: {e}"

    def _collect_until(self, params: dict[str, Any]) -> bool:
        target_timestamp = self._resolve_collect_until_target(params)
        if target_timestamp is None:
            self.memory.add_inspection(
                source="collect_until",
                target_id=str(params.get("target_time") or params.get("timeout") or ""),
                content="Invalid collect_until target.",
            )
            return False

        started_at = self.time_manager.time()
        collected_batches = 0
        target_text = datetime.fromtimestamp(target_timestamp, tz=timezone.utc).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        while not self._stopped and self.time_manager.time() < target_timestamp:
            remaining = max(1, math.ceil(target_timestamp - self.time_manager.time()))
            before_wait = self.time_manager.time()
            self._wait({"timeout": remaining})
            user_messages, env_messages, stop_messages = self._get_messages()
            if stop_messages:
                logger.info("[POrchestra GAIA2] Environment stop received during collect_until")
                self._stopped = True
                return False
            if user_messages or env_messages:
                collected_batches += 1
                self.current_task = self._format_turn_task(user_messages, env_messages) or self.current_task
                self._append_messages_to_notification_history(user_messages, env_messages)
                if user_messages and not self.original_task:
                    self.original_task = self._format_original_task(user_messages)
            if self.time_manager.time() <= before_wait and not (user_messages or env_messages):
                self.memory.add_inspection(
                    source="collect_until",
                    target_id=target_text,
                    content="Stopped because wait did not advance time or return notifications.",
                )
                return False

        elapsed = max(0.0, self.time_manager.time() - started_at)
        self.memory.add_inspection(
            source="collect_until",
            target_id=target_text,
            content=(
                f"Collected notifications until {target_text}. "
                f"Elapsed simulated seconds: {elapsed:.0f}. "
                f"Notification batches collected: {collected_batches}."
            ),
        )
        return True

    def _resolve_collect_until_target(self, params: dict[str, Any]) -> float | None:
        for key in ("target_timestamp", "until_timestamp"):
            value = params.get(key)
            if isinstance(value, (int, float)):
                return float(value)
            if isinstance(value, str) and value.strip():
                try:
                    return float(value)
                except ValueError:
                    pass

        text = str(params.get("target_time") or params.get("until") or "").strip()
        if text:
            for value in (text, text.replace("Z", "+00:00")):
                try:
                    dt = datetime.fromisoformat(value)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    return dt.timestamp()
                except ValueError:
                    pass
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S"):
                try:
                    dt = datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
                    return dt.timestamp()
                except ValueError:
                    pass

        timeout = params.get("timeout")
        if timeout is not None:
            try:
                return self.time_manager.time() + max(0, float(timeout))
            except (TypeError, ValueError):
                return None
        return None

    def _sanitize_tools(self, raw: Any, allow_empty: bool = False) -> list[str]:
        requested = raw if isinstance(raw, list) else []
        selected: list[str] = []
        for item in requested:
            name = str(item)
            if name in self.all_tools and name not in selected:
                selected.append(name)
                continue
            prefix = name.rstrip("_")
            for tool_name in self.all_tools:
                if tool_name.startswith(prefix + "__") and tool_name not in selected:
                    selected.append(tool_name)
        if not selected and not allow_empty:
            selected = list(self.all_tools.keys())
        return selected

    def _format_active_status(self) -> str:
        if self.active_attempt == 0:
            return "Status: none"
        return "\n".join(
            [
                f"Status: {self.active_status}",
                f"Attempt: {self.active_attempt}",
                f"Revision: {self.active_revision}",
            ]
        )

    def _record_follow_up_event(self, event: str, result: SubAgentResult) -> None:
        sae = result.sae
        if not isinstance(sae, dict):
            return
        action = sae.get("action") if isinstance(sae, dict) else {}
        task_scope = action.get("task_scope") if isinstance(action, dict) else {}
        if not isinstance(task_scope, dict) or task_scope.get("operation") != "follow_up":
            return
        evidence = sae.get("evidence") if isinstance(sae.get("evidence"), dict) else {}
        self.follow_up_events.append(main_visible_sae_record(
            {
                "attempt": self.active_attempt,
                "revision": self.active_revision,
                "event": event,
                "control": result.control,
                "task": result.task,
                "state": str(sae.get("state") or ""),
                "request": str(action.get("request") or ""),
                "reason": str(action.get("reason") or ""),
                "summary": str(evidence.get("summary") or ""),
                "raw": evidence.get("raw") if isinstance(evidence.get("raw"), dict) else {},
            }, getattr(self, "sae_ablation", "")
        ))

    def _format_follow_up_events(self) -> str:
        if not self.follow_up_events:
            return "No follow-up events reported yet."
        blocks: list[str] = []
        for item in self.follow_up_events:
            raw = item.get("raw")
            raw_text = ""
            if isinstance(raw, dict) and raw:
                raw_text = _truncate_text(json.dumps(raw, ensure_ascii=False, default=str), 4000)
            lines = [
                (
                    f"[Attempt {item['attempt']} revision {item['revision']} via {item['event']}] "
                    f"{item['control']}"
                ),
                f"Task: {item['task']}",
            ]
            for key, label in (("state", "State"), ("request", "Request"),
                               ("reason", "Reason"), ("summary", "Evidence")):
                if key in item:
                    lines.append(f"{label}: {item[key]}")
            if raw_text:
                lines.append(f"Raw: {raw_text}")
            blocks.append("\n".join(lines))
        return "\n\n".join(blocks)


def _format_conversation_for_main(conversation_id: str, result: Any) -> str:
    lines = [f"Conversation {conversation_id} latest messages:"]
    messages: Any = None
    metadata: Any = None
    if isinstance(result, dict):
        messages = result.get("messages")
        metadata = result.get("metadata")
    if not isinstance(messages, list):
        return "\n".join([*lines, _truncate_text(str(result), 4000)])

    for index, message in enumerate(messages[:10], 1):
        sender = _get_message_attr(message, "sender_id") or _get_message_attr(message, "sender") or "unknown"
        timestamp = _get_message_attr(message, "timestamp")
        content = _get_message_attr(message, "content") or str(message)
        prefix = f"{index}. {sender}"
        if timestamp is not None:
            prefix += f" @ {timestamp}"
        lines.append(f"- {prefix}: {_truncate_text(str(content), 1000)}")
    if metadata:
        lines.append(f"Metadata: {_truncate_text(str(metadata), 1000)}")
    return "\n".join(lines)


def _get_message_attr(message: Any, name: str) -> Any:
    if isinstance(message, dict):
        return message.get(name)
    return getattr(message, name, None)


def _format_message_timestamp(message: Message) -> str:
    timestamp = getattr(message, "timestamp", None)
    if hasattr(timestamp, "strftime"):
        return timestamp.strftime("%Y-%m-%d %H:%M:%S")
    return str(timestamp or "unknown-time")


def _format_log_timestamp(log: Any) -> str:
    timestamp = getattr(log, "timestamp", None)
    if isinstance(timestamp, (int, float)):
        return datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    if hasattr(timestamp, "strftime"):
        return timestamp.strftime("%Y-%m-%d %H:%M:%S")
    return str(timestamp or "unknown-time")


def _truncate_text(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."


def _event_is_set(event: Any) -> bool | None:
    is_set = getattr(event, "is_set", None)
    if not callable(is_set):
        return None
    try:
        return bool(is_set())
    except Exception:
        return None


def _safe_time(time_manager: Any) -> float | None:
    get_time = getattr(time_manager, "time", None)
    if not callable(get_time):
        return None
    try:
        return float(get_time())
    except Exception:
        return None


def _flat_event(event: Any) -> dict[str, Any]:
    action = getattr(event, "action", None)
    return {
        "class_name": type(event).__name__,
        "event_id": getattr(event, "event_id", None) or getattr(event, "id", None),
        "event_type": serialize(getattr(event, "event_type", None)),
        "event_time": serialize(getattr(event, "event_time", None)),
        "event_relative_time": serialize(getattr(event, "event_relative_time", None)),
        "action": serialize(action),
        "metadata": serialize(getattr(event, "metadata", None)),
        "dependency_ids": [
            getattr(item, "event_id", None) or getattr(item, "id", None)
            for item in getattr(event, "dependencies", [])
        ],
        "successor_ids": [
            getattr(item, "event_id", None) or getattr(item, "id", None)
            for item in getattr(event, "successors", [])
        ],
    }
