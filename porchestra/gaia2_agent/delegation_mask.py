"""Opt-in first-delegation masking on the real ARE execution path.

Audit information never enters SubAgent inputs. This is not a snapshot restorer.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import time
from pathlib import Path


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def load_plan(path):
    data = json.loads(Path(path).read_text())
    if data.get('schema_version') != 1 or not isinstance(data.get('cases'), dict):
        raise ValueError('mask plan requires schema_version=1 and cases mapping')
    for sid, spec in data['cases'].items():
        if not re.fullmatch(r'scenario_[A-Za-z0-9_]+', sid):
            raise ValueError('Invalid scenario ID')
        kind = spec.get('kind')
        targets = spec.get('targets')
        if kind not in ('tools', 'context', 'collect') or not isinstance(targets, list) or (not targets and kind != 'collect'):
            raise ValueError(f'{sid}: specify kind tools/context and nonempty targets')
        if any(not isinstance(t, str) or not t.strip() for t in targets):
            raise ValueError(f'{sid}: empty target')
        if not spec.get('rationale'):
            raise ValueError(f'{sid}: describe why targets are necessary')
        if spec.get('trigger','at_delivery') not in ('at_delivery','before_target_call','silent_at_delivery'):
            raise ValueError('Unknown mask injection trigger')
        frozen = spec.get('frozen_delegate')
        policy=spec.get('communication_policy','proactive')
        if policy not in ('proactive','polling','completion','failure_triggered','budget_boundary'):
            raise ValueError('communication_policy must be proactive or polling')
        if policy=='polling' and (type(spec.get('poll_period',10)) is not int or spec.get('poll_period',10)<1):
            raise ValueError('poll_period must be a positive integer')
        if frozen is not None and (frozen.get('action') != 'delegate_task' or not isinstance(frozen.get('params'), dict)):
            raise ValueError('frozen_delegate must be a delegation decision')
    return data


class DelegationMask:
    def __init__(self, scenario_id, spec, arm, output, plan_hash):
        if arm not in ('mask', 'control'):
            raise ValueError('mask arm must be mask or control')
        self.sid, self.spec, self.arm = scenario_id, copy.deepcopy(spec), arm
        self.path = Path(output) / f'{scenario_id}.jsonl'
        self.plan_hash = plan_hash
        self.original = None
        self.eligible = False
        self.active = False
        self.tool_steps = 0
        self.idle_steps = 0
        self.local_decisions = 0
        self.repaired = False
        self.last_tool = None
        self.main_memory = ''
        self.done = None
        self.delivery_time = None
        self.last_error = False
        self.trigger_time = None
        self.trigger_decisions = None
        self.trigger_tools = None
        self.execution_steps = 0
        self._session_iterations = {}
        self.recovery_verified = False

    def sync_iterations(self, agent):
        key = getattr(agent, 'agent_id', str(id(agent)))
        current = agent.iterations
        previous = self._session_iterations.get(key, 0)
        self.execution_steps += max(0, current-previous)
        self._session_iterations[key] = current

    @property
    def before_tool(self):
        return self.spec.get('trigger') == 'before_target_call'

    @property
    def track_sessions(self):
        return self.before_tool or self.spec.get('total_execution_steps') is not None

    @property
    def poll_period(self):
        return self.spec.get('poll_period',10) if self.spec.get('communication_policy')=='polling' else 0

    def inject_before_call(self, session, name, arguments):
        if not (self.before_tool and self.eligible and self.arm=='mask'
                and self.trigger_time is None and name in self.spec['targets']):
            return False
        self.trigger_time=time.monotonic()
        self.trigger_decisions=self.local_decisions
        self.trigger_tools=self.tool_steps
        self.active=True
        # Execute neither the proposed write nor its side effect. Refresh both
        # the physical executor tools and the next LLM-visible tool inventory.
        session.tool_names=[t for t in session.tool_names if t not in self.spec['targets']]
        agent=session._agent
        self.log('need_point', target=name, arguments=arguments,
                 environment_time=getattr(agent.time_manager,'time',lambda:None)(),
                 subagent_id=getattr(agent,'agent_id',None))
        session._refresh_agent(agent,{**session._selected_tools(),**session._control_tools})
        return True

    def frozen_decision(self):
        decision = self.spec.get('frozen_delegate')
        if self.original is None and decision is not None:
            self.log('frozen_delegate_replay', source=self.spec.get('source'))
            return copy.deepcopy(decision)
        return None

    def finish(self, status):
        if self.done is None:
            self.done = status
            self.log('local_end', status=status, configuration_restored=self.repaired)

    def should_stop(self):
        if not self.spec.get('local_only'):
            return False
        if self.delivery_time is not None and self.done is None:
            total_limit = self.spec.get('total_execution_steps')
            if total_limit is not None:
                if self.execution_steps >= total_limit:
                    self.finish('total_step_limit')
                elif time.monotonic()-self.delivery_time >= self.spec.get('max_wall_seconds',1200):
                    self.finish('wall_timeout')
                return self.done is not None
            elapsed_steps=self.local_decisions-(self.trigger_decisions or 0)
            elapsed_time=time.monotonic()-(self.trigger_time or self.delivery_time)
            step_limit=self.spec.get('max_local_decisions',20)
            if self.before_tool and self.trigger_time is None:
                step_limit=self.spec.get('max_pretrigger_decisions',40)
            if elapsed_steps >= step_limit:
                self.finish('window_exhausted')
            elif elapsed_time >= self.spec.get('max_wall_seconds',300):
                self.finish('wall_timeout')
        return self.done is not None

    @classmethod
    def from_env(cls, scenario_id):
        path = os.getenv('PORCHESTRA_DELEGATION_MASK_PLAN')
        if not path:
            return None
        plan = load_plan(path)
        spec = plan['cases'].get(scenario_id)
        if spec is None:
            return None
        output = os.environ['PORCHESTRA_DELEGATION_MASK_TRACE_DIR']
        return cls(scenario_id,spec,os.getenv('PORCHESTRA_DELEGATION_MASK_ARM','mask'),output,digest(plan))

    def log(self, event, **fields):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.path.open('a') as f:
            f.write(json.dumps({'event':event,'scenario_id':self.sid,'arm':self.arm,
                'wall_time':time.time(),'tool_steps':self.tool_steps,
                'idle_steps':self.idle_steps,
                'execution_steps':self.execution_steps,
                'local_decisions':self.local_decisions,**fields},ensure_ascii=False,default=str)+'\n')

    def apply(self, params, tools, instruction, context, original_task, attachments):
        if self.original is not None:
            return tools, context
        self.original = copy.deepcopy(params)
        targets = self.spec['targets']
        reason = None
        if self.spec['kind']=='tools':
            if any(t not in tools for t in targets):
                reason = 'target_not_assigned'
        elif self.spec['kind']=='context':
            if any(t not in context for t in targets):
                reason = 'target_not_in_context'
            elif any(t.casefold() in (instruction+'\n'+original_task).casefold() for t in targets):
                reason = 'target_leaks_in_instruction_or_original_task'
            elif attachments:
                reason = 'attachments_not_audited_for_context_leakage'
        self.eligible = reason is None
        self.delivery_time = time.monotonic()
        delivered_tools, delivered_context = list(tools), context
        if self.eligible and self.arm=='mask' and self.spec['kind']!='collect' and not self.before_tool:
            self.active = True
            if self.spec['kind']=='tools':
                delivered_tools = [t for t in tools if t not in targets]
            else:
                # Remove all case-insensitive occurrences, not just the first.
                for t in sorted(targets,key=len,reverse=True):
                    delivered_context = re.sub(re.escape(t),'',delivered_context,flags=re.I)
        # Main remembers its own issued action in BOTH experimental arms. Never
        # give Main the mask specification or the delivered-vs-original diff.
        self.main_memory = '\n[Previously issued delegation]\n'+json.dumps(self.original,ensure_ascii=False)
        self.log('delivery',eligible=self.eligible,skip_reason=reason,
            plan_sha256=self.plan_hash,original_delegate_sha256=digest(params),
            original_delegate=params,original_task=original_task,
            delivered={'instruction':instruction,'context':delivered_context,'tools':delivered_tools},
            intervention=self.spec)
        if self.active and self.spec.get('trigger')=='silent_at_delivery':
            self.log('silent_mask',targets=targets,
                     generated_tool_error=False,measurement_origin='configuration_delivery_not_first_tool_need')
        if not self.eligible and self.spec.get('local_only'):
            self.finish('ineligible')
        return delivered_tools, delivered_context

    def callback(self, original_callback):
        def record(log):
            get_type=getattr(log,'get_type',None)
            kind=get_type() if callable(get_type) else type(log).__name__
            if kind=='llm_output_thought_action' or type(log).__name__=='LLMOutputThoughtActionLog':
                self.local_decisions+=1
            if kind=='tool_call':
                name=log.tool_name
                self.last_tool=name
                self.last_error=False
                if name not in ('finish','revise','stop','idle'):
                    self.tool_steps+=1
                elif name == 'idle':
                    self.idle_steps+=1
                self.log('tool_call',tool=name,arguments=log.tool_arguments,
                    environment_time=getattr(log,'timestamp',None))
            elif kind in ('observation','error'):
                content=str(getattr(log,'content',''))
                self.log(kind,tool=self.last_tool,content=content,
                    environment_time=getattr(log,'timestamp',None),
                    target_tool=self.last_tool in self.spec['targets'] if self.spec['kind']=='tools' else False)
                if kind=='error':
                    self.last_error=True
                if (self.spec.get('local_only') and kind=='observation' and not self.last_error
                    and self.spec['kind']=='tools' and self.last_tool in self.spec['targets']
                    and (self.repaired or self.arm=='control')):
                    if not self.recovery_verified:
                        self.recovery_verified=True
                        self.log('recovery_verified', tool=self.last_tool)
                    if not self.spec.get('continue_after_recovery',False):
                        self.finish('recovered' if self.arm=='mask' else 'control_target_executed')
            if original_callback is not None:
                return original_callback(log)
        return record

    def revision(self, params, session, route='revise_task'):
        if not self.active:
            return
        if self.spec['kind']=='tools':
            restored=all(t in session.tool_names for t in self.spec['targets'])
        else:
            visible=session.context+'\n'+session.task_instruction
            restored=all(t in visible for t in self.spec['targets'])
        first=restored and not self.repaired
        self.repaired |= restored
        self.log('revision',params=params,configuration_restored=restored,first_restore=first,route=route)

    def result(self, event, result):
        if self.original is not None:
            self.log('handoff',source=event,control=result.control,sae=result.sae,
                     iterations=result.steps,configuration_restored=self.repaired)
            if self.spec.get('local_only') and self.spec['kind']=='collect':
                self.finish('collected_'+result.control)
            elif self.spec.get('stop_on_subagent_finish') and result.control in ('finish','stop'):
                self.finish('subagent_'+result.control)
            elif self.before_tool and result.control in ('finish','stop'):
                # Retain boundary feedback: Main may respond through a fresh
                # delegation. This route is logged distinctly from revise_task.
                if self.trigger_time is None:
                    self.finish('target_not_reached')
            elif self.spec.get('local_only') and result.control in ('finish','stop'):
                self.finish('terminal_without_target_recovery')
