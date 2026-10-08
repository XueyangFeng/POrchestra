"""Lifecycle-bound experiment using the actual AOrchestra prompt/finish tool."""
from are.simulation.agents.default_agent.base_agent import TerminationStep
from aorchestra.gaia2_agent.prompts import SUBAGENT_PROMPT
from aorchestra.gaia2_agent.subagent import FreshSubAgentSession, _termination_step
from aorchestra.gaia2_agent.tools import FinishTool
from porchestra.gaia2_agent.subagent import SubAgentSession
from porchestra.gaia2_agent.protocol import repair_sae


MAIN_INSTRUCTION = '''
==== Lifecycle-bound SubAgent interface ====
SubAgents use the AOrchestra finish protocol and terminate at a terminal handoff
or budget boundary. No autonomous revise or periodic polling is available.
The preceding SubAgent cannot be resumed. To continue work, use delegate_task
with a fresh SubAgent and provide the exact relevant facts from the previous
result in context. Use finalize_task only if all required work is complete.
Do not use revise_task to resume a terminated SubAgent.
'''


class CompletionSubAgentSession(SubAgentSession):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._control_tools = {'finish': FinishTool()}

    def _system_prompt(self):
        # Direct import, not a rewritten approximation of AOrchestra's prompt.
        return SUBAGENT_PROMPT.format(task_instruction=self.task_instruction,
            context=self.context or 'None',original_task=self.original_task)

    def _last_log(self, agent, log_type):
        return self._last_log_since_run_start(agent,log_type)

    def _set_termination(self, agent):
        original = _termination_step(self)
        def condition(a):
            mask = getattr(self,'_delegation_mask',None)
            return bool(mask and mask.should_stop()) or original.condition(a)
        agent.termination_step = TerminationStep(name='completion_experiment',condition=condition)

    def _make_agent(self, tools):
        agent=super()._make_agent(tools)
        self._set_termination(agent)
        return agent

    def _refresh_agent(self, agent, tools):
        # Refresh after permission removal without switching to POrchestra's
        # wait/revise termination rules.
        super()._refresh_agent(agent,tools)
        self._set_termination(agent)

    def _extract_control(self, agent, control_tools):
        control,result=FreshSubAgentSession._extract_control(self,agent,control_tools['finish'])
        return self._wrap_result(control,result)

    def _final_handoff(self, agent):
        return self._wrap_result(*FreshSubAgentSession._final_handoff(self,agent))

    @staticmethod
    def _wrap_result(control, result):
        if control=='external_turn_end':return control,None
        if not control:return '',None
        # Transport adapter only: retain the complete unmodified AOrchestra
        # result for Main inside SAE evidence, without an extra model call.
        return 'finish',repair_sae('finish',{
            'state':(result or {}).get('summary') or 'AOrchestra terminal result',
            'action':{'type':'finish','request':(result or {}).get('result') or 'See terminal result'},
            'evidence':{'summary':(result or {}).get('summary',''), 'raw':{'aorchestra_finish':result}}})
