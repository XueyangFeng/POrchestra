"""AOrchestra with periodic in-lifecycle inspection, no extra SubAgent actions."""
import json
import logging

from aorchestra.gaia2_agent.agent import AOrchestraAREAgent, _safe_int
from aorchestra.gaia2_agent.prompts import MAIN_PROMPT, format_tool_descriptions
from aorchestra.gaia2_agent.subagent import SubAgentResult, _termination_step
from porchestra.gaia2_agent.completion import CompletionSubAgentSession
from porchestra.gaia2_agent.json_utils import parse_first_json_object
from are.simulation.agents.default_agent.base_agent import TerminationStep, RunningState, get_offset_from_time_config_mode
from are.simulation.agents.agent_log import ObservationLog

logger=logging.getLogger(__name__)


class AOrchestraPollingSession(CompletionSubAgentSession):
    # CompletionSubAgentSession directly imports AOrchestra SUBAGENT_PROMPT and
    # FinishTool. Its resumable engine is used only at a runtime poll boundary.
    def _set_termination(self, agent):
        boundary=_termination_step(self)
        agent.termination_step=TerminationStep(name='aorchestra_periodic_inspection',
            condition=lambda a: boundary.condition(a) or self._poll_due(a))

    def _run_agent(self, agent, *, task, attachments, reset):
        if reset:
            return super()._run_agent(agent, task=task, attachments=attachments, reset=True)
        # A scheduled inspection is not a new user turn. BaseAgent.run would
        # append a fresh TaskLog even with reset=False, replaying the whole task
        # after every keep_task. Resume the existing loop and history instead.
        if task != agent.task:
            agent.append_agent_log(ObservationLog(
                content="[MainAgent task update]\n" + task,
                timestamp=agent.make_timestamp(), agent_id=agent.agent_id,
            ))
        agent.task = task
        agent.attachments = attachments
        agent.custom_state["running_state"] = RunningState.RUNNING
        return agent.execute_agent_loop()


class AOrchestraPollingAREAgent(AOrchestraAREAgent):
    @property
    def agent_framework(self):
        return 'AOrchestraPollingAREAgent'

    def __init__(self, *, poll_period=5, **kwargs):
        if poll_period<1:raise ValueError('poll_period must be positive')
        super().__init__(poll_period=poll_period,**kwargs)
        self.poll_count=0
        self.poll_memory=[]

    def _poll_decision(self, session, feedback):
        self.poll_count+=1
        self.poll_memory.append(feedback)
        # Keep AOrchestra's task/history/tool context. The added block changes
        # only the available Main action interface while the SubAgent is paused.
        prompt=MAIN_PROMPT.format(attempt_index=self.main_attempt,max_attempts=self.max_attempts,
            remaining_attempts=max(0,self.max_attempts-self.main_attempt),
            original_task=self.original_task or self.current_task,current_task=self.current_task,
            notification_history=self._format_notification_history(),
            subtask_history=self.task_memory.format(),
            tool_descriptions=format_tool_descriptions(list(self.all_tools.values())))
        prompt+='\n[Periodic inspection of the still-active SubAgent]\n'+json.dumps(self.poll_memory,ensure_ascii=False,default=str)
        prompt+='''
This is a scheduled inspection, not evidence of failure. The current SubAgent
has not finished. At this inspection override the ordinary action menu:
- keep_task: params={} to continue this same SubAgent unchanged;
- revise_task: params may contain instruction, context, tools (full replacement
  list), and step_budget (additional steps), to update and resume the same SubAgent;
- stop_task: params={"reason":"..."} to end this SubAgent with a partial result.
Return one JSON object with action, reasoning, params. Do not use delegate_task
or complete during this inspection. Ordinary AOrchestra planning resumes after
the SubAgent ends. Preserve exact completed side effects.
'''
        messages=[{'role':'user','content':prompt}]
        for _ in range(3):
            text,_=self._call_poll_engine(self.llm_engine,messages)
            d=parse_first_json_object(text or '')
            if d.get('action') in ('keep_task','revise_task','stop_task'):
                logger.info('[AOrchestra polling] decision=%s',d)
                return d
            messages.extend([{'role':'assistant','content':text or ''},{'role':'user','content':'Use keep_task, revise_task, or stop_task for this periodic inspection.'}])
        raise ValueError('Invalid Main polling decision after three attempts')

    def _call_poll_engine(self, engine, messages):
        # Only the additional periodic inspection uses ARE generation timing.
        # Ordinary planning and summarization retain the baseline's behavior.
        config = self.simulated_generation_time_config
        if config is None:
            return self._call_engine(engine, messages)
        if self.pause_env is None or self.resume_env is None:
            raise ValueError('Simulated generation requires pause_env and resume_env')
        offset = 0.0
        self.pause_env()
        try:
            result = self._call_engine(engine, messages)
            metadata = result[1] if isinstance(result, tuple) and len(result) == 2 else {}
            offset = get_offset_from_time_config_mode(
                time_config=config,
                completion_duration=(metadata or {}).get('completion_duration', 0),
            )
            return result
        finally:
            self.resume_env(offset)

    def _delegate_fresh(self, params):
        budget=self._bounded_subagent_budget(_safe_int(params.get('step_budget'),self.default_subagent_steps))
        if budget<=0:return super()._delegate_fresh(params)
        self.active_attempt+=1;self.active_revision=0;self.active_status='running'
        self.poll_memory=[]
        session=AOrchestraPollingSession(llm_engine=self.sub_llm_engine,all_tools=self.all_tools,
            task_instruction=str(params.get('task_instruction') or self.current_task),
            context=str(params.get('context') or ''),original_task=self.original_task or self.current_task,
            tools=self._sanitize_tools(params.get('tools')),max_steps=budget,
            log_callback=self.log_callback,time_manager=self.time_manager,notification_system=self.notification_system,
            pause_env=self.pause_env,resume_env=self.resume_env,
            simulated_generation_time_config=self.simulated_generation_time_config,
            attachments=self.current_attachments,poll_period=self.poll_period)
        recorded=0
        for _ in range(self.max_total_steps+1):
            result=session.run_until_control()
            self.total_subagent_steps+=max(0,result.steps-recorded);recorded=result.steps
            if result.control!='poll':break
            self._append_subagent_notification_logs(result)
            feedback=session.take_poll_feedback()
            logger.info('[AOrchestra polling] attempt=%s iteration=%s period=%s',self.main_attempt,result.steps,self.poll_period)
            decision=self._poll_decision(session,feedback)
            p=decision.get('params') or {}
            if not isinstance(p,dict):p={}
            if decision['action']=='stop_task':
                result.control='finish'
                result.sae={'evidence':{'raw':{'aorchestra_finish':{'result':'','status':'partial','summary':str(p.get('reason') or decision.get('reasoning') or 'Stopped by Main')}}}}
                break
            if decision['action']=='revise_task':
                self.active_revision+=1
                tools=self._sanitize_tools(p['tools'],allow_empty=True) if isinstance(p.get('tools'),list) else None
                # Existing local budget plus any extension cannot exceed the
                # remaining system-wide budget.
                extra=max(0,_safe_int(p.get('step_budget'),0))
                cap=max(0,self.max_total_steps-self.total_subagent_steps-max(0,session.max_steps-result.steps))
                session.revise(instruction=str(p.get('instruction') or p.get('task_instruction') or ''),context=str(p.get('context') or ''),
                    tools=tools,step_budget=min(extra,cap) or None)
            # keep_task requires no mutation or additional reporting call.
        finish=((result.sae or {}).get('evidence') or {}).get('raw',{}).get('aorchestra_finish')
        if result.control=='external_turn_end':
            finish={'result':'User-facing message sent.','status':'done','summary':'SubAgent ended the ARE turn.'}
        finish=finish or {'result':'','status':'partial','summary':'SubAgent stopped without a terminal result.'}
        final=SubAgentResult(control=result.control,finish_result=finish,steps=result.steps,
            max_steps=session.max_steps,done=result.control=='finish' and finish.get('status')=='done',
            task=session.task_instruction,tools=list(session.tool_names),logs=result.logs)
        self._append_subagent_notification_logs(final)
        self._record_fresh_result(params,final,self._summarize_trace(final))
        if final.control=='external_turn_end':
            self.active_status='external_turn_end';self._start_boundary_trace('delegate',final)
        else:self.active_status='finished' if final.control=='finish' else 'stopped'
        return final
