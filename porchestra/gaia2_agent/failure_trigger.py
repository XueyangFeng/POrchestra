"""Fixed executor failures for a MAS2-inspired trigger ablation.

This is a GAIA2 operationalization, not the complete MAS2 workflow algorithm.
"""
from are.simulation.exceptions import (
    UnavailableToolAgentError, JsonExecutionAgentError, InvalidToolCallError,
    ToolError, WebError, TimeoutAgentError,
)
from porchestra.gaia2_agent.polling import STRICT_SUB_PROMPT, MAIN_POLL_INSTRUCTION

TRIGGER_EXCEPTIONS=(UnavailableToolAgentError, JsonExecutionAgentError,
                    InvalidToolCallError, ToolError, WebError, TimeoutAgentError)

SUB_PROMPT=STRICT_SUB_PROMPT.replace(
    'The runtime periodically pauses execution so MainAgent can inspect your recent',
    'The runtime pauses execution when an explicit tool execution failure occurs so MainAgent can inspect your recent'
).replace('next periodic check','runtime error-triggered check')\
 .replace('the periodic clock','the local execution budget')

MAIN_INSTRUCTION=MAIN_POLL_INSTRUCTION.replace('Periodic polling interface','Failure-triggered interface')\
 .replace("the runtime's periodic inspection", "an executor-detected tool failure")\
 .replace('A poll does not imply there is a problem.',
          'A tool failure does not necessarily require a configuration change; inspect its cause.')\
 .replace('At this inspection','At this error inspection')
