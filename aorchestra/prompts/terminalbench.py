"""TerminalBench prompts for MainAgent."""
from typing import Any, Dict, List

from aorchestra.main_agent import build_model_pricing_table


# TerminalBench SubAgent uses shell commands, not explicit tool objects
TERMINALBENCH_TOOLS_DESCRIPTION = """
SubAgent executes shell commands in a Docker container.

Available actions for SubAgent:
- execute: Run any shell command (bash, apt, pip, python, etc.)
- finish: Report completion status to MainAgent

Example commands SubAgent can run:
- apt-get install <package>
- pip install <package>
- python script.py
- cat /etc/config
- systemctl status <service>
""".strip()


class TerminalBenchPrompt:
    """Build prompts for TerminalBench tasks."""
    
    @staticmethod
    def build_prompt(
        instruction: str,
        meta: Dict[str, Any],
        prior_context: str,
        attempt_index: int,
        max_attempts: int,
        sub_models: List[str],
        subtask_history: str = "",
        model_to_alias: Dict[str, str] = None,
        tools: List[Any] = None,
    ) -> str:
        remaining_attempts = max_attempts - attempt_index + 1
        model_pricing_table = build_model_pricing_table(sub_models, model_to_alias)
        
        # Budget warning
        if remaining_attempts <= 2:
            budget_warning = f"🚨 CRITICAL: Only {remaining_attempts} attempt(s) left! Submit now if task looks complete, or make final attempt."
        elif remaining_attempts <= 4:
            budget_warning = f"⚠️ Warning: {remaining_attempts} attempts remaining. Plan carefully."
        else:
            budget_warning = ""
        
        return f"""You are the MainAgent (Orchestrator). Your task is to complete the given software installation/configuration task by delegating to SubAgents.

CRITICAL: CONTAINER LIFECYCLE
- Each SubAgent runs in a FRESH container - if you delegate_task again, the previous work will be lost
- When SubAgent reports status="done", use 'submit' immediately to run tests in that container

==== DECISION PROCESS ====
1. READ the original TASK carefully - identify ALL requirements and edge cases
2. REVIEW SUBTASK HISTORY - check status and completed steps
3. VERIFY SubAgent's work against TASK requirements:
   - Did SubAgent test ALL requirements mentioned in TASK?
   - Did SubAgent test edge cases? (e.g., if TASK mentions "keyboard interrupt", was it actually tested?)
   - Are SubAgent's "completed" items actually addressing the TASK requirements?
4. DECIDE:
   - ✅ status="done" AND verification passes → Use 'submit'
   - ✅ status="done" BUT verification passes but some requirements are not met → Use 'delegate_task' to fix
   - ⚠️ status="partial" → Use 'delegate_task' with context about what worked/failed

{budget_warning}

==== MODEL SELECTION ====
{model_pricing_table}

==== Progress ====
[Attempt {attempt_index}/{max_attempts}] Remaining {remaining_attempts} attempts

==== TASK ====
{instruction}

==== SUBTASK HISTORY ====
{subtask_history if subtask_history else "No subtasks completed yet."}

==== AVAILABLE TOOLS ====
{TERMINALBENCH_TOOLS_DESCRIPTION}

==== OUTPUT ====
Return JSON:

If SubAgent status="done" AND you verified all TASK requirements are met:
{{
  "action": "submit",
  "reasoning": "Verified: [list which TASK requirements were addressed]. Submitting.",
  "params": {{ "reason": "Task completed: [specific accomplishments matching TASK requirements]" }}
}}

If SubAgent status="done" BUT verification shows gaps:
{{
  "action": "delegate_task",
  "reasoning": "SubAgent claimed done but [specific gap]: TASK requires [X] but SubAgent only tested [Y]",
  "params": {{
    "task_instruction": "CRITICAL: Previous attempt missed [specific requirement]. You MUST: [exact steps to fix]",
    "context": "⚠️ PREVIOUS SUBAGENT CLAIMED DONE BUT MISSED: [specific gap]\\n- ✅ WORKED: [steps to keep]\\n- ❌ MUST FIX: [what was missed]",
    "model": "one of {sub_models}"
  }}
}}

If SubAgent status="partial":
{{
  "action": "delegate_task",
  "reasoning": "SubAgent made partial progress, need to continue with [remaining work]",
  "params": {{
    "task_instruction": "Continue from where previous SubAgent left off: [specific next steps]",
    "context": "From SUBTASK HISTORY:\\n- ✅ WORKED: [steps to REPEAT]\\n- ❌ FAILED: [approaches to AVOID]",
    "model": "one of {sub_models}"
  }}
}}
""".strip()
