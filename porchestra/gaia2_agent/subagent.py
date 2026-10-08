"""SubAgent session runner for GAIA2-POrchestra."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from are.simulation.agents.agent_log import (
    LLMInputLog,
    LLMOutputThoughtActionLog,
    ObservationLog,
    SystemPromptLog,
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

from porchestra.gaia2_agent.json_utils import parse_first_json_object
from porchestra.gaia2_agent.prompts import FINAL_HANDOFF_PROMPT, SUBAGENT_PROMPT
from porchestra.gaia2_agent.protocol import budget_exhausted_sae, repair_sae
from porchestra.gaia2_agent.revision_ablation import ablation_notice
from porchestra.gaia2_agent.tools import make_control_tools


CONTROL_TOOLS = {"finish", "revise", "stop"}
AUI_SEND_TOOL = "AgentUserInterface__send_message_to_user"
WAIT_TOOL = "SystemApp__wait_for_notification"
EXTERNAL_BOUNDARIES = {"external_turn_end", "external_pause"}


class _PreCallMaskExecutor(JsonActionExecutor):
    def __init__(self, session):
        super().__init__()
        self.session=session

    def execute_tool_call(self, parsed_action, append_agent_log, make_timestamp):
        mask=getattr(self.session, '_delegation_mask', None)
        if mask is not None and mask.inject_before_call(self.session,parsed_action.tool_name,parsed_action.arguments):
            from are.simulation.exceptions import UnavailableToolAgentError
            raise UnavailableToolAgentError(f'Tool authorization unavailable: {parsed_action.tool_name}.')
        return super().execute_tool_call(parsed_action,append_agent_log,make_timestamp)


class _FailureTriggerExecutor(_PreCallMaskExecutor):
    def execute_tool_call(self, parsed_action, append_agent_log, make_timestamp):
        from porchestra.gaia2_agent.failure_trigger import TRIGGER_EXCEPTIONS
        try:
            return super().execute_tool_call(parsed_action, append_agent_log, make_timestamp)
        except TRIGGER_EXCEPTIONS as exc:
            if parsed_action.tool_name not in CONTROL_TOOLS | {'idle'}:
                self.session._pending_failure = {
                    'tool':parsed_action.tool_name,'arguments':parsed_action.arguments,
                    'exception_type':type(exc).__name__,'message':str(exc)}
            raise


@dataclass
class SubAgentResult:
    control: str
    sae: dict[str, Any] | None
    steps: int
    max_steps: int
    done: bool
    task: str
    tools: list[str]
    logs: list[Any]


class SubAgentSession:
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
        poll_period: int = 0,
        revision_ablation: str = "",
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
        if type(poll_period) is not int or poll_period < 0:
            raise ValueError('poll_period must be a nonnegative integer')
        self._e2e_poll_period = poll_period
        self.revision_ablation = revision_ablation
        self.revision_notes: list[str] = []
        self._agent: BaseAgent | None = None
        self._control_tools: dict[str, Any] | None = None
        self._needs_refresh = False
        self._run_start_log_index = 0
        self._next_poll = None
        self._poll_log_index = 0
        self._pending_failure = None

    @property
    def failure_triggered(self):
        mask=getattr(self,'_delegation_mask',None)
        return bool(mask is not None and mask.spec.get('communication_policy')=='failure_triggered')

    @property
    def budget_boundary(self):
        mask=getattr(self,'_delegation_mask',None)
        return bool(mask is not None and mask.spec.get('communication_policy')=='budget_boundary')

    @property
    def poll_period(self):
        mask = getattr(self, '_delegation_mask', None)
        return getattr(self, '_e2e_poll_period', 0) or (mask.poll_period if mask is not None else 0)

    def _poll_due(self, agent):
        return bool(self.poll_period and agent.iterations >= (self._next_poll or self.poll_period))

    @property
    def strict_polling(self):
        mask = getattr(self, '_delegation_mask', None)
        return bool(self.poll_period and mask is not None and mask.spec.get('polling_strict_finish', False))

    def _autonomous_control_disabled(self, name):
        return ((self.failure_triggered or self.budget_boundary) and name in ('revise','stop')) or bool(self.poll_period and (name == 'revise' or (self.strict_polling and name == 'stop')))

    def _advance_poll_clock(self, agent):
        if self.poll_period:
            self._next_poll = (agent.iterations // self.poll_period + 1) * self.poll_period

    def take_poll_feedback(self):
        from porchestra.gaia2_agent.boundary_trace import serialize
        agent = self._agent
        allowed = {'tool_call','observation','error','environment_notifications','llm_output_thought_action','agent_user_interface'}
        records = [serialize(log) for log in agent.logs[self._poll_log_index:]
                   if log.get_type() in allowed or isinstance(log, LLMOutputThoughtActionLog)]
        self._poll_log_index = len(agent.logs)
        return {'iterations':agent.iterations,'task':self.task_instruction,
                'context':self.context,'tools':list(self.tool_names),'recent_execution':records}

    def revise(
        self,
        *,
        instruction: str = "",
        context: str = "",
        tools: list[str] | None = None,
        step_budget: int | None = None,
        task_scope: dict[str, Any] | None = None,
        resource: dict[str, Any] | None = None,
    ) -> None:
        if instruction:
            self.task_instruction = instruction
        if context:
            self.context = (self.context + "\n" + context).strip()
        if tools is not None:
            self.tool_names = tools
        if step_budget:
            self.max_steps += int(step_budget)
        self._needs_refresh = True
        note_parts = ["[MainAgent revision]"]
        if task_scope:
            note_parts.append(f"Task scope: {task_scope}")
        if resource:
            note_parts.append(f"Resource: {resource}")
        if context:
            note_parts.append(f"Context: {context}")
        if tools is not None:
            note_parts.append(f"Tools: {tools}")
        if step_budget:
            note_parts.append(f"Additional step budget: {step_budget}")
        self.revision_notes.append("\n".join(note_parts))

    def run_until_control(
        self,
        *,
        task: str | None = None,
        attachments: list[Attachment] | None = None,
    ) -> SubAgentResult:
        if self._control_tools is None:
            self._control_tools = make_control_tools()
            if self.poll_period or self.failure_triggered or self.budget_boundary:
                self._control_tools.pop('revise')
            if self.strict_polling or self.failure_triggered or self.budget_boundary:
                from porchestra.gaia2_agent.polling import make_idle_tool
                self._control_tools.pop('stop')
                self._control_tools['idle'] = make_idle_tool(failure_triggered=self.failure_triggered)
                if self.budget_boundary:
                    self._control_tools['idle'].description='Wait locally for one execution step. Only finish or local budget exhaustion hands control to MainAgent.'
                    self._control_tools['idle'].forward=lambda:'Local idle step completed. MainAgent is called only at finish or local budget exhaustion.'
            elif getattr(self, '_e2e_poll_period', 0):
                from porchestra.gaia2_agent.polling import make_idle_tool
                self._control_tools['idle'] = make_idle_tool()
        control_tools = self._control_tools
        selected_tools = self._selected_tools()
        tools = {**selected_tools, **control_tools}

        if self._agent is None:
            agent = self._make_agent(tools)
            reset = True
        else:
            agent = self._agent
            if self._needs_refresh:
                self._refresh_agent(agent, tools)
                self._needs_refresh = False
            reset = False

        self._run_start_log_index = len(agent.logs)
        run_task = task if task is not None else self.task_instruction
        run_attachments = attachments if attachments is not None else self.attachments
        # An external wait/user boundary at a scheduled poll must not silently
        # advance the clock. Deliver the due inspection before further execution.
        if getattr(self, '_e2e_poll_period', 0) and not reset and self._poll_due(agent) and agent.iterations < self.max_steps:
            from are.simulation.agents.agent_log import ObservationLog
            if task is not None:
                agent.append_agent_log(ObservationLog(content=task,timestamp=agent.make_timestamp(),agent_id=agent.agent_id,attachments=run_attachments))
            self._advance_poll_clock(agent)
            return SubAgentResult(control='poll',sae=None,steps=agent.iterations,
                max_steps=self.max_steps,done=False,task=self.task_instruction,
                tools=list(self._selected_tools()),logs=agent.get_agent_logs())
        self._run_agent(agent, task=run_task, attachments=run_attachments, reset=reset)

        mask = getattr(self, "_delegation_mask", None)
        if mask is not None:
            mask.sync_iterations(agent)
        if mask is not None and mask.should_stop():
            return SubAgentResult(control="experiment_complete", sae=None,
                steps=agent.iterations, max_steps=self.max_steps, done=True,
                task=self.task_instruction, tools=list(selected_tools), logs=agent.get_agent_logs())

        if self.failure_triggered and self._pending_failure is not None:
            failure=self._pending_failure
            self._pending_failure=None
            mask.log('executor_failure_trigger',failure=failure,iterations=agent.iterations)
            return SubAgentResult(control='failure',sae=None,steps=agent.iterations,
                max_steps=self.max_steps,done=False,task=self.task_instruction,
                tools=list(self._selected_tools()),logs=agent.get_agent_logs())

        control, sae = self._extract_control(agent, control_tools)
        if self.budget_boundary and control not in {'finish','stop'} and agent.iterations >= self.max_steps:
            mask.log('budget_boundary',iterations=agent.iterations,local_limit=self.max_steps)
            return SubAgentResult(control='budget',sae=None,steps=agent.iterations,max_steps=self.max_steps,
                done=False,task=self.task_instruction,tools=list(self._selected_tools()),logs=agent.get_agent_logs())
        if self.poll_period and control in EXTERNAL_BOUNDARIES | {'finish','stop'}:
            if not (getattr(self, '_e2e_poll_period', 0) and control in EXTERNAL_BOUNDARIES):
                self._advance_poll_clock(agent)
        elif self._poll_due(agent) and agent.iterations < self.max_steps:
            self._advance_poll_clock(agent)
            return SubAgentResult(control='poll',sae=None,steps=agent.iterations,
                max_steps=self.max_steps,done=False,task=self.task_instruction,
                tools=list(self._selected_tools()),logs=agent.get_agent_logs())
        if control not in EXTERNAL_BOUNDARIES and sae is None:
            control, sae = self._final_handoff(agent)
        if control not in EXTERNAL_BOUNDARIES and sae is None:
            sae = budget_exhausted_sae(self.max_steps)
            control = "stop"
        return SubAgentResult(
            control=control,
            sae=sae,
            steps=agent.iterations,
            max_steps=self.max_steps,
            done=control in {"finish", "stop"},
            task=self.task_instruction,
            tools=list(self._selected_tools().keys()),
            logs=agent.get_agent_logs(),
        )

    def resume_after_external_update(
        self,
        update: str,
        *,
        attachments: list[Attachment] | None = None,
    ) -> SubAgentResult:
        """Resume this logical SubAgent with the next ARE turn/update."""
        return self.run_until_control(task=update, attachments=attachments)

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
            termination_step=_control_termination_step(self),
            max_iterations=self.max_steps,
            total_iterations=self.max_steps + 5,
            action_executor=(_FailureTriggerExecutor(self) if self.failure_triggered else _PreCallMaskExecutor(self)
                if getattr(self, '_delegation_mask', None) is not None and self._delegation_mask.before_tool
                else JsonActionExecutor()),
            conditional_pre_steps=[get_are_simulation_update_pre_step()],
            log_callback=self.log_callback,
            time_manager=self.time_manager,
            simulated_generation_time_config=self.simulated_generation_time_config,
        )
        agent.notification_system = self.notification_system
        agent.pause_env = self.pause_env
        agent.resume_env = self.resume_env
        self._agent = agent
        return agent

    def _run_agent(self, agent, *, task, attachments, reset):
        agent.run(task=task, attachments=attachments, reset=reset)

    def _refresh_agent(self, agent: BaseAgent, tools: dict[str, Tool]) -> None:
        agent.tools = tools
        agent.max_iterations = self.max_steps
        agent.total_iterations = self.max_steps + 5
        agent.termination_step = _control_termination_step(self)
        agent.init_system_prompts = {"system_prompt": self._system_prompt()}
        tool_values = agent.init_tools()
        agent.system_prompts = agent.update_system_prompt_tools(agent.init_system_prompts, tool_values)
        agent.system_prompt = "\n\n".join(prompt for prompt in agent.init_system_prompts.values())
        agent.append_agent_log(
            SystemPromptLog(
                content=agent.system_prompt,
                timestamp=agent.make_timestamp(),
                agent_id=agent.agent_id,
            )
        )

    def _system_prompt(self) -> str:
        template = SUBAGENT_PROMPT
        if self.poll_period:
            from porchestra.gaia2_agent.polling import SUB_PROMPT, STRICT_SUB_PROMPT
            template = STRICT_SUB_PROMPT if self.strict_polling else SUB_PROMPT
            if getattr(self, '_e2e_poll_period', 0):
                template += '\nLocal idle with empty arguments is available when temporarily blocked. It consumes one execution step, has no app side effects, and does not request a simulated-time jump. You may still finish with a genuine terminal partial result when no useful work remains.'
        if self.failure_triggered:
            from porchestra.gaia2_agent.failure_trigger import SUB_PROMPT
            template=SUB_PROMPT
        if self.budget_boundary:
            from porchestra.gaia2_agent.budget_boundary import SUB_PROMPT
            template=SUB_PROMPT
        if self.revision_ablation:
            template += (
                "\n\n==== Revision Ablation for This Run ====\n"
                + ablation_notice(self.revision_ablation)
            )
        return template.format(
            task_instruction=self.task_instruction,
            context=self._context_text(),
            original_task=self.original_task,
        )

    def _context_text(self) -> str:
        chunks = []
        if self.context:
            chunks.append(self.context)
        chunks.extend(self.revision_notes)
        return "\n\n".join(chunks) if chunks else "None"

    def _extract_control(self, agent: BaseAgent, control_tools: dict[str, Any]) -> tuple[str, dict[str, Any] | None]:
        last_tool = self._last_log_since_run_start(agent, ToolCallLog)
        control = last_tool.tool_name if last_tool else ""
        if self._autonomous_control_disabled(control):
            return '', None
        if control in CONTROL_TOOLS and control in control_tools and control_tools[control].last_sae:
            return control, control_tools[control].last_sae
        last_obs = self._last_log_since_run_start(agent, ObservationLog)
        latest = last_obs.content if last_obs else ""
        if control == AUI_SEND_TOOL:
            return "external_turn_end", None
        if control == WAIT_TOOL:
            return "external_pause", None
        if control in CONTROL_TOOLS:
            args = last_tool.tool_arguments if last_tool else {}
            return control, repair_sae(control, args, latest)
        return "", None

    def _final_handoff(self, agent: BaseAgent) -> tuple[str, dict[str, Any] | None]:
        latest_observation = self._latest_observation(agent)
        instruction = FINAL_HANDOFF_PROMPT
        prompt = agent.build_history_from_logs(
            exclude_log_types=["tool_call", "rationale", "action"]
        )
        prompt.append({"role": "user", "content": instruction})
        agent.append_agent_log(
            LLMInputLog(
                content=prompt,
                timestamp=agent.make_timestamp(),
                agent_id=agent.agent_id,
            )
        )

        if self.simulated_generation_time_config is not None:
            if self.pause_env is None:
                return "stop", _invalid_final_handoff_sae(
                    latest_observation,
                    "pause_env is not set for simulated generation time",
                )
            self.pause_env()

        response: str | None = None
        metadata: dict[str, Any] = {}
        try:
            llm_response = self.llm_engine(
                prompt,
                stop_sequences=["<end_action>"],
                additional_trace_tags=["final_handoff"],
            )
            if isinstance(llm_response, tuple) and len(llm_response) == 2:
                response, metadata = llm_response
            else:
                response = llm_response
                metadata = {}
        except Exception as e:
            agent.log_error(e)
            return "stop", _invalid_final_handoff_sae(latest_observation, f"{type(e).__name__}: {e}")
        finally:
            if self.simulated_generation_time_config is not None and self.resume_env is not None:
                completion_duration = metadata.get("completion_duration", 0) if metadata else 0
                offset = get_offset_from_time_config_mode(
                    time_config=self.simulated_generation_time_config,
                    completion_duration=completion_duration,
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
        control = str(parsed.get("action") or "")
        if control not in {"finish", "stop"}:
            return "stop", _invalid_final_handoff_sae(
                latest_observation,
                "final handoff did not return finish or stop",
            )

        payload = parsed.get("action_input")
        if not isinstance(payload, dict):
            payload = parsed.get("params")
        return control, repair_sae(control, payload, latest_observation)

    def _latest_observation(self, agent: BaseAgent) -> Any:
        last_obs = self._last_log_since_run_start(agent, ObservationLog)
        return last_obs.content if last_obs else ""

    def _last_log_since_run_start(self, agent: BaseAgent, log_type: type) -> Any | None:
        for log in reversed(agent.logs[self._run_start_log_index:]):
            if isinstance(log, log_type):
                return log
        return None


def _control_termination_step(session: SubAgentSession) -> TerminationStep:
    def condition(agent: BaseAgent) -> bool:
        mask = getattr(session, "_delegation_mask", None)
        if mask is not None:
            mask.sync_iterations(agent)
        if mask is not None and mask.should_stop():
            return True
        if session.failure_triggered and session._pending_failure is not None:
            return True
        if agent.iterations >= session.max_steps:
            return True
        if session._poll_due(agent):
            return True
        tool_call = session._last_log_since_run_start(agent, ToolCallLog)
        if not tool_call:
            return False
        if tool_call.tool_name in CONTROL_TOOLS and not session._autonomous_control_disabled(tool_call.tool_name):
            return True
        return tool_call.tool_name in {AUI_SEND_TOOL, WAIT_TOOL}

    return TerminationStep(name="porchestra_control", condition=condition)


def _invalid_final_handoff_sae(latest_observation: Any, reason: str) -> dict[str, Any]:
    return {
        "state": "SubAgent reached the final step boundary but did not produce a valid final handoff.",
        "action": {
            "type": "stop",
            "task_scope": {
                "operation": "remove",
                "object": "current path",
                "details": "The current path reached its step boundary without a valid finish handoff.",
            },
            "resource": {
                "operation": "keep",
                "object": "none",
                "details": "No resource change is requested after invalid final handoff.",
            },
            "request": "Stop this path and let MainAgent decide the next action.",
            "reason": reason,
        },
        "evidence": {
            "summary": f"Latest observation before invalid final handoff: {str(latest_observation)[:1000]}",
            "raw": {},
        },
    }
