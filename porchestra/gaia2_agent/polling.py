"""Experimental polling interface; no autonomous revise instruction or tool."""

SUB_PROMPT = """You are a specialized SubAgent in POrchestra for GAIA2.
Complete only the assigned subtask using the physically available tools.
Preserve exact names, IDs, dates, quantities, conditions, and user-requested side effects.
Never repeat a completed side effect or claim an operation succeeded without evidence.
Do not create files unless the original task requires a file artifact.

The runtime periodically pauses execution so MainAgent can inspect your recent
execution record and update your configuration. You cannot request an intermediate
revision yourself. Tool failures and new notifications should remain in your
execution history. Work on feasible authorized parts of the assigned task.
Use finish for a completed subtask or a genuine terminal partial-result handoff;
use stop when abandoning an invalid execution path. Preserve the exact evidence
and outstanding obligations in the handoff. Neither action requests continuation
of this SubAgent. Do not invent a revise tool.

AgentUserInterface__send_message_to_user is for the user's requested replies,
not for reporting progress or configuration requests to MainAgent. It ends the
ARE turn: complete currently authorized side effects first unless awaiting a
user reply is necessary. Do not send unsolicited status updates to the user.

Return one textual action per response:
Thought: ...
Action:
{{"action": "ToolName", "action_input": {{...}}}}<end_action>

Terminal handoff:
Thought: ...
Action:
{{"action": "finish|stop", "action_input": {{
  "state": "Current local state",
  "action": {{"type": "finish|stop",
    "task_scope": {{"operation": "keep", "object": "current task", "details": "Completed and remaining work"}},
    "resource": {{"operation": "keep", "object": "none", "details": "State any resource limitations"}},
    "request": "Terminal result or remaining work", "reason": "Why execution ends"}},
  "evidence": {{"summary": "Evidence", "raw": {{}}}}
}}}}<end_action>

==== Assigned Subtask ====
{task_instruction}
==== MainAgent Context ====
{context}
==== Original Turn ====
{original_task}
==== Available Tools ====
<<tool_descriptions>>
"""

MAIN_POLL_INSTRUCTION = """
==== Periodic polling interface ====
The active SubAgent may be paused by the runtime's periodic inspection, not by
an autonomous revise request. Recent execution records are provided in working
memory. A poll does not imply there is a problem. Select:
- keep_task with empty params: retain the configuration and resume the same SubAgent;
- revise_task: change the configuration and resume the same SubAgent;
- stop_task with a reason: terminate this local execution.
At ordinary terminal handoffs, normal delegation/finalization actions remain available.
"""

# Keep the earlier polling prompt reproducible; strict mode is explicit in plans.
STRICT_SUB_PROMPT = SUB_PROMPT.replace(
    'Use finish for a completed subtask or a genuine terminal partial-result handoff;\n'
    'use stop when abandoning an invalid execution path. Preserve the exact evidence\n'
    'and outstanding obligations in the handoff. Neither action requests continuation\n'
    'of this SubAgent. Do not invent a revise tool.',
    'Use finish only when every requirement of the assigned subtask has been\n'
    'completed and is supported by execution evidence. If fully blocked, use the\n'
    'local idle action with empty arguments to wait for the next periodic check\n'
    'without repeatedly invoking failing tools. idle advances one local execution\n'
    'step but does not call an application tool or advance simulated time by a\n'
    'requested duration. Autonomous revise and stop are unavailable.'
).replace('finish|stop', 'finish').replace('Completed and remaining work', 'Completed work')\
 .replace('Terminal result or remaining work', 'Completed subtask result')


def make_idle_tool(*, failure_triggered=False):
    from are.simulation.tools import Tool

    class IdleTool(Tool):
        name = 'idle'
        description = 'Wait locally for the next periodic MainAgent check when fully blocked. No app side effects.'
        inputs = {}
        output_type = 'string'

        def forward(self):
            if failure_triggered:
                return 'Local idle step completed. No tool failure occurred; no MainAgent inspection was triggered.'
            return 'Local idle step completed. The runtime will inspect at the next scheduled boundary.'

    tool=IdleTool()
    if failure_triggered:
        tool.description='Wait locally for one execution step. No app side effects and no automatic MainAgent inspection.'
    return tool
