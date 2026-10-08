"""
SWE-bench SubAgent for aorchestra framework.

Uses DISCUSSION + COMMAND format (same as baseline SWEAgent),
with 'finish' command for reporting back to MainAgent.
"""
import asyncio
import re
from typing import Any, Dict, Optional

from pydantic import Field

from base.agent.base_agent import BaseAgent
from base.agent.memory import Memory
from base.agent.truncating_memory import truncate_text
from base.engine.logs import logger, LogLevel
from benchmark.common.env import BasicInfo


LLM_CALL_ATTEMPTS = 3
LLM_RETRY_DELAYS = (2.0, 4.0)


def classify_llm_error(exc: Exception) -> str:
    """Classify an LLM failure as retryable, non-retryable infra, or unknown."""
    text = f"{type(exc).__name__}: {exc}".lower()
    non_retryable_markers = (
        "balance is not sufficient",
        "账户余额过低",
        "insufficient balance",
        "insufficient_quota",
        "invalid api key",
        "invalid_api_key",
        "authentication",
        "unauthorized",
        "401",
    )
    if any(marker in text for marker in non_retryable_markers):
        return "non_retryable_infrastructure"

    retryable_markers = (
        "timeout",
        "timed out",
        "connection error",
        "connection reset",
        "apiconnectionerror",
        "apitimeouterror",
        "ratelimiterror",
        "too many requests",
        "429",
        "502",
        "503",
        "504",
    )
    if any(marker in text for marker in retryable_markers):
        return "retryable_infrastructure"
    return "unknown"


def make_llm_error_action(
    exc: Exception,
    *,
    retryable: bool,
    attempts: int,
) -> Dict[str, Any]:
    """Build an error action that never masquerades as successful completion."""
    error_type = type(exc).__name__
    message = str(exc) or error_type
    return {
        "action": "error",
        "params": {
            "message": f"LLM {error_type} after {attempts} attempt(s): {message}",
            "error_type": error_type,
            "infrastructure_error": True,
            "retryable": retryable,
            "attempts": attempts,
            "exclude_from_scoring": not retryable,
        },
        "reasoning": (
            "Transient LLM infrastructure failure; keep the current workspace and continue."
            if retryable
            else "Non-retryable LLM infrastructure failure; stop without evaluating the task."
        ),
    }


# =============================================================================
# SWEBENCH SUBAGENT PROMPT
# =============================================================================
SWEBENCH_SUBAGENT_PROMPT = """
You are an autonomous software engineering agent tasked with solving GitHub issues.
You have access to a specialized command interface (ACI) for navigating, viewing, editing, and testing code.
You will work in a Docker container with the repository already cloned and checked out to the correct commit.

==== Progress ====
[Step {current_step}/{max_steps}] Remaining: {remaining_steps} step(s)
{budget_warning}
If you run out of steps without "finish", your work is lost and marked as timeout.

==== Your Task (from MainAgent) ====
{task_instruction}

==== Context (from previous attempts) ====
{context}

==== Current State ====
{state_info}

==== Command Reference ====
{command_docs}

=== FINISH (Report to MainAgent) ===
finish <status> <message>
    Report your progress back to MainAgent. Status MUST be one of:
    - done: Task completed successfully, tests pass
    - partial: Made progress but not finished (e.g., found bug but fix not working)

==== Memory ====
Recent memory:
{memory}

==== Current Observation ====
{observation}

==== OUTPUT FORMAT (STRICT) ====
You MUST output EXACTLY two sections in this order. No other text allowed.

DISCUSSION
<your reasoning here>

COMMAND
<single command here>

RULES:
- DISCUSSION must contain your step-by-step reasoning
- COMMAND must contain exactly ONE command on a single line
- After COMMAND line, do NOT add any explanation, examples, or comments
- Do NOT output anything after the command
"""


def build_subagent_prompt(
    task_instruction: str,
    context: str,
    command_docs: str,
    state_info: str,
    memory: str,
    observation: str,
    current_step: int,
    max_steps: int,
) -> str:
    """Build the complete prompt for SubAgent."""
    remaining_steps = max_steps - current_step
    
    # Budget warning
    if remaining_steps <= 3:
        budget_warning = "🚨 CRITICAL: Only {} steps left! Use 'finish' NOW to report your progress!".format(remaining_steps)
    elif remaining_steps <= 5:
        budget_warning = "⚠️ Warning: {} steps remaining. Plan to finish soon.".format(remaining_steps)
    else:
        budget_warning = ""
    
    return SWEBENCH_SUBAGENT_PROMPT.format(
        task_instruction=task_instruction,
        context=context if context else "No additional context provided.",
        command_docs=command_docs,
        state_info=state_info,
        memory=memory,
        observation=observation,
        current_step=current_step,
        max_steps=max_steps,
        remaining_steps=remaining_steps,
        budget_warning=budget_warning,
    )


def parse_subagent_response(response: str) -> Dict[str, Any]:
    """
    Parse SubAgent response to extract DISCUSSION and COMMAND.
    Handles 'finish' command for reporting back to MainAgent.
    """
    discussion = ""
    command = ""
    
    # Pattern for DISCUSSION section
    discussion_match = re.search(
        r'DISCUSSION\s*\n(.*?)(?=\nCOMMAND|\Z)', 
        response, 
        re.DOTALL | re.IGNORECASE
    )
    if discussion_match:
        discussion = discussion_match.group(1).strip()
    
    # Pattern for COMMAND section - extract all content after COMMAND
    command_match = re.search(
        r'COMMAND\s*\n(.*?)(?=\n(?:DISCUSSION|OUTPUT)|\Z)',
        response,
        re.DOTALL | re.IGNORECASE
    )
    if command_match:
        raw_command = command_match.group(1).strip()
        
        # Only take the first meaningful line as the command
        # This prevents LLM's extra text/thoughts from being included
        lines = raw_command.split('\n')
        for line in lines:
            line = line.strip()
            # Skip empty lines and comment-like lines
            if line and not line.startswith('#') and not line.startswith('('):
                # For multi-line commands like str_replace, create, edit, etc.
                # we need to capture the full block
                if any(line.startswith(cmd) for cmd in ['str_replace', 'create', 'edit', 'insert', 'delete_lines']):
                    # These commands may span multiple lines - use the full raw content
                    # but stop at obvious non-command text (parenthetical notes, etc.)
                    clean_lines = []
                    for l in lines:
                        # Stop if we hit a line that looks like commentary
                        if l.strip().startswith('(') or l.strip().startswith('**') or l.strip().startswith('Wait'):
                            break
                        clean_lines.append(l)
                    command = '\n'.join(clean_lines).strip()
                else:
                    # Single-line commands: just take the first line
                    command = line
                break
        
        # If no command found, use the first line anyway
        if not command and lines:
            command = lines[0].strip()
    
    # Handle finish command (SubAgent specific)
    # Format: finish <status> <message>
    # status: done | partial
    if command.lower().startswith('finish'):
        # Extract content after 'finish'
        finish_content = command[6:].strip() if len(command) > 6 else ""
        
        # Parse status and message
        status = "done"  # default
        message = finish_content or discussion
        
        # Check if content starts with a valid status (done or partial)
        content_lower = finish_content.lower()
        if content_lower.startswith('done'):
            status = "done"
            message = finish_content[4:].strip() or discussion
        elif content_lower.startswith('partial'):
            status = "partial"
            message = finish_content[7:].strip() or discussion
        
        return {
            "action": "finish",
            "params": {
                "status": status,
                "message": message,
                "completed": [],
                "issues": [],
            },
            "reasoning": discussion
        }
    
    # Handle submit command (should not be used by SubAgent, convert to finish)
    if command.lower() == 'submit':
        return {
            "action": "finish",
            "params": {
                "status": "done",
                "message": "SubAgent attempted to submit - converting to finish",
                "completed": [],
                "issues": [],
            },
            "reasoning": discussion
        }
    
    # Regular ACI or bash command - use aci_command like Baseline
    if command:
        return {
            "action": "aci_command",
            "params": {"command": command},
            "reasoning": discussion
        }
    
    # Fallback: extract any command-like content
    lines = response.strip().split('\n')
    for line in lines:
        line = line.strip()
        if line and not line.startswith('#') and not line.startswith('DISCUSSION'):
            return {
                "action": "aci_command",
                "params": {"command": line},
                "reasoning": response
            }
    
    return {
        "action": "error",
        "params": {"message": "Could not parse response"},
        "reasoning": response
    }


class SWEBenchSubAgent(BaseAgent):
    """
    SubAgent for SWE-bench in aorchestra framework.
    
    Uses DISCUSSION + COMMAND format (same as baseline SWEAgent),
    with 'finish' command for reporting back to MainAgent.
    """
    name: str = Field(default="SWEBenchSubAgent")
    description: str = Field(default="SubAgent for SWE-bench with ACI tools")
    
    # Task context from MainAgent
    task_instruction: str = Field(default="")
    context: str = Field(default="")
    original_question: str = Field(default="")
    
    # Internal state
    current_instruction: str = Field(default="")
    command_docs: str = Field(default="")
    state_info: str = Field(default="(Open file: n/a) (Current directory: /testbed)")
    memory: Optional[Memory] = Field(default=None)
    max_observation_chars: Optional[int] = Field(default=None)
    
    class Config:
        arbitrary_types_allowed = True

    def reset(self, env_info: BasicInfo) -> None:
        """Reset agent state for new task."""
        if self.memory is None:
            self.memory = Memory(llm=self.llm, max_memory=20)
        else:
            self.memory.clear()
        
        # Use task_instruction if set by MainAgent, otherwise use env instruction
        self.current_instruction = self.task_instruction or env_info.instruction
        self.command_docs = env_info.meta_data.get("command_docs", env_info.action_space)
        self.state_info = "(Open file: n/a) (Current directory: /testbed)"
        
        # Store original question for reference
        if not self.original_question:
            self.original_question = env_info.instruction
        
        logger.info(f"[SWEBenchSubAgent] Reset for task")

    def parse_action(self, resp: str) -> Dict[str, Any]:
        """Parse LLM response using DISCUSSION + COMMAND format."""
        return parse_subagent_response(resp)

    def _get_memory(self) -> str:
        """Get formatted memory context."""
        if self.memory:
            return self.memory.as_text()
        return "No previous observations."

    async def step(self, observation: Any, history: Any, current_step: int = 1, max_steps: int = 50) -> tuple:
        """Execute one step of the agent loop.
        
        Returns:
            tuple: (action, raw_response, raw_input_prompt)
        """
        # Format observation
        if isinstance(observation, dict):
            obs_str = observation.get("output", str(observation))
            if "state_info" in observation:
                self.state_info = observation["state_info"]
        else:
            obs_str = str(observation)
        # Compatibility shims may install this newer step() implementation on
        # an older AOrchestra Pydantic model that predates this field.
        obs_str = truncate_text(
            obs_str,
            getattr(self, "max_observation_chars", None),
        )
        
        # Build prompt
        prompt = build_subagent_prompt(
            task_instruction=self.current_instruction,
            context=self.context,
            command_docs=self.command_docs,
            state_info=self.state_info,
            memory=self._get_memory(),
            observation=obs_str,
            current_step=current_step,
            max_steps=max_steps,
        )
        
        logger.log_to_file(LogLevel.INFO, f"[SWEBenchSubAgent] Step {current_step} Input:\n{prompt}\n")
        
        # Query LLM. Transient API failures retry in-place and never become finish.
        resp = ""
        action = None
        last_error: Exception | None = None
        attempts_used = 0
        for attempt in range(1, LLM_CALL_ATTEMPTS + 1):
            attempts_used = attempt
            try:
                resp = await self.llm(prompt)
                last_error = None
                break
            except Exception as exc:
                last_error = exc
                error_class = classify_llm_error(exc)
                logger.warning(
                    f"[SWEBenchSubAgent] LLM call failed "
                    f"(attempt {attempt}/{LLM_CALL_ATTEMPTS}, class={error_class}): {exc}"
                )
                if error_class == "non_retryable_infrastructure":
                    action = make_llm_error_action(
                        exc,
                        retryable=False,
                        attempts=attempt,
                    )
                    break
                if error_class == "unknown":
                    raise
                if attempt < LLM_CALL_ATTEMPTS:
                    await asyncio.sleep(LLM_RETRY_DELAYS[attempt - 1])

        if action is None and last_error is not None:
            action = make_llm_error_action(
                last_error,
                retryable=True,
                attempts=attempts_used,
            )
        elif action is None:
            action = self.parse_action(resp)

        logger.agent_action(f"[SWEBenchSubAgent] Action: {action}")
        
        # Extract reasoning for memory
        reasoning = action.get("reasoning", "")
        
        return action, resp, prompt

    async def record_transition(
        self,
        *,
        action: Any,
        observation_after: Any,
        thinking: str | None = None,
        reward: float | None = None,
        raw_response: str | None = None,
    ) -> None:
        """Store an executed action with the observation returned by the environment."""
        if not self.memory:
            return
        if isinstance(observation_after, dict):
            obs_text = observation_after.get("output", str(observation_after))
        else:
            obs_text = str(observation_after)
        obs_text = truncate_text(
            obs_text,
            getattr(self, "max_observation_chars", None),
        )
        await self.memory.add_memory(
            obs=obs_text,
            action=action,
            thinking=thinking,
            reward=reward,
            raw_response=raw_response,
        )

    async def run(self, request: Optional[str] = None) -> str:
        """Main run method (not used in benchmark loop)."""
        return ""
