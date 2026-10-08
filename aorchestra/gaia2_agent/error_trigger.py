"""AOrchestra with early handoff on actual business-tool execution errors.

The failed SubAgent terminates. Main may only delegate a fresh SubAgent, as in
ordinary AOrchestra; there is no POrchestra-style in-place revise action.
"""

from are.simulation.agents.default_agent.base_agent import TerminationStep
from are.simulation.agents.default_agent.tools.json_action_executor import JsonActionExecutor

from aorchestra.gaia2_agent.agent import AOrchestraAREAgent
from aorchestra.gaia2_agent.subagent import FreshSubAgentSession, _termination_step
from porchestra.gaia2_agent.failure_trigger import TRIGGER_EXCEPTIONS


class _ErrorTriggerExecutor(JsonActionExecutor):
    def __init__(self, session):
        super().__init__()
        self.session = session

    def execute_tool_call(self, parsed_action, append_agent_log, make_timestamp):
        try:
            return super().execute_tool_call(parsed_action, append_agent_log, make_timestamp)
        except TRIGGER_EXCEPTIONS as exc:
            if parsed_action.tool_name != 'finish':
                self.session.pending_tool_error = {
                    'tool': parsed_action.tool_name,
                    'exception_type': type(exc).__name__,
                    'message': str(exc),
                }
            raise


class ErrorTriggerFreshSubAgentSession(FreshSubAgentSession):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.pending_tool_error = None

    def _make_agent(self, tools):
        agent = super()._make_agent(tools)
        agent.action_executor = _ErrorTriggerExecutor(self)
        agent.action_executor.update_tools(tools)
        normal = _termination_step(self)
        agent.termination_step = TerminationStep(
            name='aorchestra_tool_error_or_finish',
            condition=lambda a: self.pending_tool_error is not None or normal.condition(a),
        )
        return agent

    def _extract_control(self, agent, finish_tool):
        error = self.pending_tool_error
        if error is not None:
            details = str(error['message']).replace('\n', ' ').strip()
            if len(details) > 600:
                details = details[:597] + '...'
            summary = (
                f"Tool execution error ({error['exception_type']}) in "
                f"{error['tool']}: {details}. The failed action did not return "
                'a successful observation. Inspect the trace before repeating any prior writes.'
            )
            return 'tool_error', {'result': '', 'status': 'partial', 'summary': summary}
        return super()._extract_control(agent, finish_tool)


class AOrchestraErrorAREAgent(AOrchestraAREAgent):
    @property
    def agent_framework(self):
        return 'AOrchestraErrorAREAgent'

    def _subagent_session_class(self):
        return ErrorTriggerFreshSubAgentSession
