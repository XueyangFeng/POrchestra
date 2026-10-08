"""Fresh ReAct SubAgent used by the GAIA2 AOrchestra baseline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from are.simulation.agents.agent_log import (
    LLMInputLog,
    LLMOutputThoughtActionLog,
    ObservationLog,
    ToolCallLog,
)
from are.simulation.agents.default_agent.base_agent import (
    BaseAgent,
    TerminationStep,
    get_offset_from_time_config_mode,
)
from are.simulation.agents.default_agent.steps.are_simulation import (
    get_are_simulation_update_pre_step,
)
from are.simulation.agents.default_agent.tools.json_action_executor import JsonActionExecutor
from are.simulation.agents.llm.llm_engine import LLMEngine
from are.simulation.agents.multimodal import Attachment
from are.simulation.notification_system import BaseNotificationSystem
from are.simulation.tools import Tool

from aorchestra.gaia2_agent.prompts import FINAL_HANDOFF_PROMPT, SUBAGENT_PROMPT
from aorchestra.gaia2_agent.tools import FinishTool
from porchestra.gaia2_agent.json_utils import parse_first_json_object


AUI_SEND_TOOL = "AgentUserInterface__send_message_to_user"


@dataclass
class SubAgentResult:
    control: str
    finish_result: dict[str, Any] | None
    steps: int
    max_steps: int
    done: bool
    task: str
    tools: list[str]
    logs: list[Any]


class FreshSubAgentSession:
    """Run exactly one fresh AOrchestra ReAct SubAgent."""

    def __init__(
        self,
        *,
        llm_engine: LLMEngine,
        all_tools: dict[str, Tool],
        task_instruction: str,
        context: str,
        original_task: str,
        tools: list[str],
        max_steps: int,
        log_callback,
        time_manager,
        notification_system: BaseNotificationSystem | None,
        pause_env=None,
        resume_env=None,
        simulated_generation_time_config=None,
        attachments: list[Attachment] | None = None,
    ) -> None:
        self.llm_engine = llm_engine
        self.all_tools = all_tools
        self.task_instruction = task_instruction
        self.context = context
        self.original_task = original_task
        self.tool_names = tools
        self.max_steps = max_steps
        self.log_callback = log_callback
        self.time_manager = time_manager
        self.notification_system = notification_system
        self.pause_env = pause_env
        self.resume_env = resume_env
        self.simulated_generation_time_config = simulated_generation_time_config
        self.attachments = attachments or []
        self._run_start_log_index = 0

    def run(self) -> SubAgentResult:
        finish_tool = FinishTool()
        selected_tools = self._selected_tools()
        tools = {**selected_tools, finish_tool.name: finish_tool}
        agent = self._make_agent(tools)
        self._run_start_log_index = len(agent.logs)
        agent.run(task=self.task_instruction, attachments=self.attachments, reset=True)

        control, finish_result = self._extract_control(agent, finish_tool)
        if not control:
            control, finish_result = self._final_handoff(agent)
        if not control:
            control = "timeout"
            finish_result = _fallback_finish(
                self._latest_observation(agent),
                "SubAgent exhausted its step budget without a valid finish action.",
            )

        status = str((finish_result or {}).get("status") or "partial")
        return SubAgentResult(
            control=control,
            finish_result=finish_result,
            steps=agent.iterations,
            max_steps=self.max_steps,
            done=control == "finish" and status == "done",
            task=self.task_instruction,
            tools=list(selected_tools),
            logs=agent.get_agent_logs(),
        )

    def _selected_tools(self) -> dict[str, Tool]:
        return {
            name: self.all_tools[name]
            for name in self.tool_names
            if name in self.all_tools
        }

    def _make_agent(self, tools: dict[str, Tool]) -> BaseAgent:
        agent = BaseAgent(
            llm_engine=self.llm_engine,
            tools=tools,
            system_prompts={"system_prompt": self._system_prompt()},
            termination_step=_termination_step(self),
            max_iterations=self.max_steps,
            total_iterations=self.max_steps + 5,
            action_executor=JsonActionExecutor(),
            conditional_pre_steps=[get_are_simulation_update_pre_step()],
            log_callback=self.log_callback,
            time_manager=self.time_manager,
            simulated_generation_time_config=self.simulated_generation_time_config,
        )
        agent.notification_system = self.notification_system
        agent.pause_env = self.pause_env
        agent.resume_env = self.resume_env
        return agent

    def _system_prompt(self) -> str:
        return SUBAGENT_PROMPT.format(
            task_instruction=self.task_instruction,
            context=self.context or "None",
            original_task=self.original_task,
        )

    def _extract_control(
        self,
        agent: BaseAgent,
        finish_tool: FinishTool,
    ) -> tuple[str, dict[str, Any] | None]:
        last_tool = self._last_log(agent, ToolCallLog)
        if last_tool is None:
            return "", None
        if last_tool.tool_name == finish_tool.name:
            payload = finish_tool.last_result
            if payload is None:
                payload = _normalize_finish(last_tool.tool_arguments)
            return "finish", payload
        if last_tool.tool_name == AUI_SEND_TOOL:
            return "external_turn_end", {
                "result": "User-facing message sent.",
                "status": "done",
                "summary": "The delegated SubAgent sent a user-facing message and ended the ARE turn.",
            }
        return "", None

    def _final_handoff(self, agent: BaseAgent) -> tuple[str, dict[str, Any] | None]:
        latest_observation = self._latest_observation(agent)
        prompt = agent.build_history_from_logs(
            exclude_log_types=["tool_call", "rationale", "action"]
        )
        prompt.append({"role": "user", "content": FINAL_HANDOFF_PROMPT})
        agent.append_agent_log(
            LLMInputLog(
                content=prompt,
                timestamp=agent.make_timestamp(),
                agent_id=agent.agent_id,
            )
        )

        if self.simulated_generation_time_config is not None:
            if self.pause_env is None:
                return "timeout", _fallback_finish(
                    latest_observation,
                    "pause_env is not set for the final handoff.",
                )
            self.pause_env()

        response: str | None = None
        metadata: dict[str, Any] = {}
        try:
            llm_response = self.llm_engine(
                prompt,
                stop_sequences=["<end_action>"],
                additional_trace_tags=["aorchestra_final_handoff"],
            )
            if isinstance(llm_response, tuple) and len(llm_response) == 2:
                response, metadata = llm_response
            else:
                response = llm_response
        except Exception as exc:
            agent.log_error(exc)
            return "timeout", _fallback_finish(
                latest_observation,
                f"Final handoff failed: {type(exc).__name__}: {exc}",
            )
        finally:
            if self.simulated_generation_time_config is not None and self.resume_env is not None:
                offset = get_offset_from_time_config_mode(
                    time_config=self.simulated_generation_time_config,
                    completion_duration=metadata.get("completion_duration", 0),
                )
                self.resume_env(offset)

        agent.append_agent_log(
            LLMOutputThoughtActionLog(
                content=response or "",
                timestamp=agent.make_timestamp(),
                agent_id=agent.agent_id,
                prompt_tokens=metadata.get("prompt_tokens", 0),
                completion_tokens=metadata.get("completion_tokens", 0),
                total_tokens=metadata.get("total_tokens", 0),
                reasoning_tokens=metadata.get("reasoning_tokens", 0),
                completion_duration=metadata.get("completion_duration", 0),
            )
        )
        parsed = parse_first_json_object(response or "")
        if parsed.get("action") != "finish":
            return "timeout", _fallback_finish(
                latest_observation,
                "Final handoff did not return finish.",
            )
        payload = parsed.get("action_input")
        if not isinstance(payload, dict):
            payload = parsed.get("params")
        return "finish", _normalize_finish(payload)

    def _latest_observation(self, agent: BaseAgent) -> Any:
        log = self._last_log(agent, ObservationLog)
        return log.content if log is not None else ""

    def _last_log(self, agent: BaseAgent, log_type: type) -> Any | None:
        for log in reversed(agent.logs[self._run_start_log_index:]):
            if isinstance(log, log_type):
                return log
        return None


def _termination_step(session: FreshSubAgentSession) -> TerminationStep:
    def condition(agent: BaseAgent) -> bool:
        if agent.iterations >= session.max_steps:
            return True
        tool_call = session._last_log(agent, ToolCallLog)
        if tool_call is None:
            return False
        return tool_call.tool_name in {"finish", AUI_SEND_TOOL}

    return TerminationStep(name="aorchestra_finish", condition=condition)


def _normalize_finish(payload: Any) -> dict[str, Any]:
    data = payload if isinstance(payload, dict) else {}
    status = str(data.get("status") or "partial")
    if status not in {"done", "partial"}:
        status = "partial"
    return {
        "result": str(data.get("result") or ""),
        "status": status,
        "summary": str(data.get("summary") or ""),
    }


def _fallback_finish(observation: Any, reason: str) -> dict[str, Any]:
    text = str(observation or "")
    if len(text) > 1000:
        text = text[:997].rstrip() + "..."
    return {
        "result": "",
        "status": "partial",
        "summary": f"{reason} Latest observation: {text}",
    }
