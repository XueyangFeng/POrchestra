"""ARE-compatible GAIA2 implementation of the AOrchestra baseline."""

from __future__ import annotations

import logging
import time
from typing import Any

from are.simulation.agents.llm.llm_engine import LLMEngine

from aorchestra.gaia2_agent.memory import TaskEntryMemory
from aorchestra.gaia2_agent.prompts import (
    MAIN_PROMPT,
    TRACE_SUMMARY_PROMPT,
    format_tool_descriptions,
)
from aorchestra.gaia2_agent.subagent import FreshSubAgentSession, SubAgentResult
from porchestra.gaia2_agent.agent import POrchestraAREAgent
from porchestra.gaia2_agent.json_utils import parse_first_json_object


logger = logging.getLogger(__name__)


class AOrchestraAREAgent(POrchestraAREAgent):
    """AOrchestra's fresh-SubAgent delegation loop on the GAIA2 ARE shell."""

    def __init__(
        self,
        *,
        summary_llm_engine: LLMEngine | None = None,
        max_attempts: int = 10,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.summary_llm_engine = summary_llm_engine or self.llm_engine
        self.max_attempts = max_attempts
        self.main_attempt = 0
        self.task_memory = TaskEntryMemory()

    @property
    def agent_framework(self) -> str:
        return "AOrchestraAREAgent"

    def _run_main_until_turn_end(self) -> str | None:
        while self.main_attempt < self.max_attempts:
            decision = self._main_decision()
            action = str(decision.get("action") or "")
            params = decision.get("params")
            if not isinstance(params, dict):
                params = {}
            logger.info("[AOrchestra GAIA2] Main decision: %s", decision)

            if action == "delegate_task":
                result = self._delegate_fresh(params)
                if result.control == "external_turn_end":
                    return "turn_ended"
                continue

            if action == "complete":
                answer = str(params.get("answer") or params.get("message") or "").strip()
                tool = self.all_tools.get("AgentUserInterface__send_message_to_user")
                if tool is None:
                    logger.warning("[AOrchestra GAIA2] AUI send tool unavailable")
                    continue
                if not answer:
                    logger.warning("[AOrchestra GAIA2] complete returned an empty answer")
                    continue
                tool(content=answer)
                self._stopped = True
                return "scenario_finished"

            logger.warning("[AOrchestra GAIA2] Unknown MainAgent action: %s", action)

        logger.warning("[AOrchestra GAIA2] MainAgent attempt budget exhausted")
        self._stopped = True
        return "scenario_finished"

    def _main_decision(self) -> dict[str, Any]:
        self.main_attempt += 1
        prompt = MAIN_PROMPT.format(
            attempt_index=self.main_attempt,
            max_attempts=self.max_attempts,
            remaining_attempts=max(0, self.max_attempts - self.main_attempt),
            original_task=self.original_task or self.current_task,
            current_task=self.current_task or "No new notifications.",
            notification_history=self._format_notification_history(),
            subtask_history=self.task_memory.format(),
            tool_descriptions=format_tool_descriptions(list(self.all_tools.values())),
        )
        messages = [{"role": "user", "content": prompt}]
        logger.info(
            "[AOrchestra GAIA2] MainAgent LLM call start; attempt=%s prompt_chars=%s",
            self.main_attempt,
            len(prompt),
        )
        logger.info(
            "[AOrchestra GAIA2] MainAgent raw prompt begin\n%s\n"
            "[AOrchestra GAIA2] MainAgent raw prompt end",
            prompt,
        )

        response = ""
        for parse_attempt in range(3):
            response, _ = self._call_engine(self.llm_engine, messages)
            logger.info(
                "[AOrchestra GAIA2] MainAgent raw response begin\n%s\n"
                "[AOrchestra GAIA2] MainAgent raw response end",
                response or "",
            )
            decision = parse_first_json_object(response or "")
            if decision:
                return decision
            messages.extend(
                [
                    {"role": "assistant", "content": response or ""},
                    {
                        "role": "user",
                        "content": (
                            "Your previous response was not valid JSON. Return ONLY one JSON "
                            "object using action delegate_task or complete."
                        ),
                    },
                ]
            )
            logger.warning(
                "[AOrchestra GAIA2] Invalid MainAgent JSON on parse attempt %s",
                parse_attempt + 1,
            )
        return {"action": "invalid_json", "params": {}}

    def _delegate_fresh(self, params: dict[str, Any]) -> SubAgentResult:
        requested_steps = _safe_int(
            params.get("step_budget"),
            self.default_subagent_steps,
        )
        step_budget = self._bounded_subagent_budget(requested_steps)
        task_instruction = str(params.get("task_instruction") or self.current_task)
        tools = self._sanitize_tools(params.get("tools"))
        self.active_attempt += 1
        self.active_revision = 0
        self.active_status = "running"

        if step_budget <= 0:
            result = SubAgentResult(
                control="timeout",
                finish_result={
                    "result": "",
                    "status": "partial",
                    "summary": "Global SubAgent step budget exhausted.",
                },
                steps=0,
                max_steps=0,
                done=False,
                task=task_instruction,
                tools=tools,
                logs=[],
            )
            self._record_fresh_result(params, result, "No steps executed")
            return result

        session = self._subagent_session_class()(
            llm_engine=self.sub_llm_engine,
            all_tools=self.all_tools,
            task_instruction=task_instruction,
            context=str(params.get("context") or ""),
            original_task=self.original_task or self.current_task,
            tools=tools,
            max_steps=step_budget,
            log_callback=self.log_callback,
            time_manager=self.time_manager,
            notification_system=self.notification_system,
            pause_env=self.pause_env,
            resume_env=self.resume_env,
            simulated_generation_time_config=self.simulated_generation_time_config,
            attachments=self.current_attachments,
        )
        result = session.run()
        self.total_subagent_steps += result.steps
        self._append_subagent_notification_logs(result)
        trace_summary = self._summarize_trace(result)
        self._record_fresh_result(params, result, trace_summary)

        if result.control == "external_turn_end":
            self.active_status = "external_turn_end"
            self._start_boundary_trace("delegate", result)
        elif result.control == "finish":
            self.active_status = "finished"
        else:
            self.active_status = "stopped"
        return result

    def _subagent_session_class(self):
        return FreshSubAgentSession

    def _record_fresh_result(
        self,
        params: dict[str, Any],
        result: SubAgentResult,
        trace_summary: str,
    ) -> None:
        finish = result.finish_result or {}
        model = str(params.get("model") or "model_1")
        self.task_memory.add(
            {
                "attempt": self.main_attempt,
                "status": str(finish.get("status") or "partial"),
                "instruction": result.task,
                "model": model,
                "steps_taken": result.steps,
                "max_steps": result.max_steps,
                "result": str(finish.get("result") or ""),
                "summary": str(finish.get("summary") or ""),
                "trace_summary": trace_summary,
            }
        )

    def _summarize_trace(self, result: SubAgentResult) -> str:
        if not result.logs:
            return "No steps executed."
        trace_text = _format_trace(result.logs)
        prompt = TRACE_SUMMARY_PROMPT.format(
            task_instruction=result.task[:1000],
            steps=result.steps,
            trace_text=trace_text,
        )
        try:
            response, _ = self._call_engine(
                self.summary_llm_engine,
                [{"role": "user", "content": prompt}],
            )
            return str(response or "").strip() or f"Steps: {result.steps}"
        except Exception as exc:
            logger.warning("[AOrchestra GAIA2] Trace summarization failed: %s", exc)
            return f"Steps: {result.steps}"

    def _call_engine(
        self,
        engine: LLMEngine,
        messages: list[dict[str, Any]],
    ) -> tuple[Any, Any]:
        for attempt in range(1, 4):
            try:
                return engine(messages, stop_sequences=[])
            except Exception:
                if attempt == 3:
                    raise
                time.sleep(float(attempt))
        raise RuntimeError("unreachable")

    def _resume_active_subagent_after_external_update(self) -> str | None:
        """AOrchestra starts a fresh SubAgent after every external turn."""
        if self.active_status in {"external_turn_end", "external_pause"}:
            self.active_status = "none"
        return None


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _format_trace(logs: list[Any], max_output_len: int = 300) -> str:
    lines: list[str] = []
    step = 0
    for log in logs:
        get_type = getattr(log, "get_type", None)
        log_type = get_type() if callable(get_type) else type(log).__name__
        if log_type not in {
            "tool_call",
            "observation",
            "error",
            "agent_user_interface",
            "environment_notifications",
        }:
            continue
        if log_type == "tool_call":
            step += 1
            name = getattr(log, "tool_name", "unknown")
            arguments = getattr(log, "tool_arguments", {})
            lines.append(f"Step {step}: {name}({arguments})")
            continue
        get_content = getattr(log, "get_content_for_llm", None)
        content = get_content() if callable(get_content) else getattr(log, "content", "")
        text = str(content or "").replace("\n", " ").strip()
        if len(text) > max_output_len:
            text = text[:max_output_len] + f"...[+{len(text) - max_output_len} chars]"
        lines.append(f"  -> {log_type}: {text}")
    return "\n".join(lines) if lines else "No tool steps recorded."
