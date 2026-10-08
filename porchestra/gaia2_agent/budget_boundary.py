"""Budget-boundary triggered resumable local execution (not MAS2 error detection)."""
from porchestra.gaia2_agent.polling import STRICT_SUB_PROMPT

SUB_PROMPT=STRICT_SUB_PROMPT.replace(
    'The runtime periodically pauses execution so MainAgent can inspect your recent',
    'The runtime pauses execution only at finish or local execution budget exhaustion so MainAgent can inspect your recent'
).replace('next periodic check','local budget boundary')

MAIN_INSTRUCTION='''
==== Local budget boundary ====
The active SubAgent has exhausted its local execution budget and is paused,
not terminated. Recent execution records and current configuration are in working
memory. Tool errors did not trigger this handoff. You may revise_task to restore
resources and continue the SAME SubAgent: params.step_budget must provide a
positive additional number of steps (at most 50). Alternatively use stop_task.
The experiment has a separate total execution cap; additional local budget cannot
increase that total cap.
'''
