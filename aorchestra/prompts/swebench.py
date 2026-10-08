"""SWE-bench prompts for MainAgent."""
from typing import Any, Dict, List

from aorchestra.main_agent import build_model_pricing_table


# SWE-bench SubAgent uses ACI commands, not explicit tool objects
SWEBENCH_TOOLS_DESCRIPTION = """
SubAgent uses ACI (Agentic Code Interface) commands to navigate and edit code.

=== FILE VIEWING ===
- open <file> [line]: Open file at specified line
- scroll_down/scroll_up: Navigate within open file
- goto <line>: Jump to specific line

=== FILE EDITING ===
- str_replace <file>: Replace exact text match (preferred for edits)
- edit <start>:<end>: Edit line range with syntax check
- insert <file> <line>: Insert content after line
- create <file>: Create new file

=== SEARCHING ===
- search_file <pattern> [file]: Search content in file
- search_dir <pattern> [dir]: Search in directory
- find_file <name> [dir]: Find files by name

=== BASH ===
- Any bash command (ls, cat, grep, python, pytest, etc.)

=== SUBMIT ===
- submit: Submit fix and run official tests
""".strip()


class SWEBenchMainAgentPrompt:
    """Build prompts for SWE-bench tasks (GitHub issue fixing)."""
    
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
        enable_rco: bool = False,
    ) -> str:
        remaining_attempts = max_attempts - attempt_index + 1
        model_pricing_table = build_model_pricing_table(sub_models, model_to_alias)
        
        # Extract repository info from metadata
        repo = meta.get("repo", "unknown")
        instance_id = meta.get("instance_id", "unknown")
        
        # Budget warning
        if remaining_attempts <= 2:
            budget_warning = f"🚨 CRITICAL: Only {remaining_attempts} attempt(s) left! Submit now if fix is verified, or make final attempt."
        elif remaining_attempts <= 4:
            budget_warning = f"⚠️ Warning: {remaining_attempts} attempts remaining. Plan carefully."
        else:
            budget_warning = ""
        
        return f"""You are the MainAgent (Orchestrator) for a SWE-bench task. Your goal is to fix a GitHub issue by delegating work to SubAgents.


==== TASK ====
{instruction}

REPOSITORY: {repo}
INSTANCE: {instance_id}

==== DECISION PROCESS ====
1. READ the TASK carefully - understand the GitHub issue and what needs to be fixed
2. REVIEW SUBTASK HISTORY - check SubAgent's progress, completed steps, and test results
3. VERIFY against TASK requirements:
   - Did SubAgent locate the buggy code?
   - Did SubAgent make appropriate code changes?
   - Did SubAgent run tests and confirm the fix works?
4. DECIDE:
   - ✅ status="done" AND tests pass → Use 'submit'
   - ⚠️ status="done" BUT tests fail or incomplete → Use 'delegate_task' to fix remaining issues
   - ⚠️ status="partial" → Use 'delegate_task' with guidance on next steps

CRITICAL: SWE-BENCH CONTAINER BEHAVIOR
- Every 'delegate_task' starts a FRESH container. Delegating again permanently loses
  all unsubmitted code changes from the previous SubAgent container.
- When SubAgent reports status="done" with passing tests, use 'submit' IMMEDIATELY
  to evaluate the current container. Do not delegate another SubAgent merely to
  verify a completed fix, because that would discard the working patch.
- If SubAgent reports status="partial", a later SubAgent cannot continue from the
  previous workspace. Instruct it to reimplement the required changes from scratch
  using the textual history and context.
- 'submit' runs the official test suite (FAIL_TO_PASS + PASS_TO_PASS tests) to determine success


==== MODEL SELECTION ====
{model_pricing_table}

==== Progress ====
[Attempt {attempt_index}/{max_attempts}] Remaining {remaining_attempts} attempts
{budget_warning}


==== SUBTASK HISTORY ====
{subtask_history if subtask_history else "No subtasks completed yet."}

==== AVAILABLE TOOLS ====
{SWEBENCH_TOOLS_DESCRIPTION}

==== OUTPUT ====
Return JSON:

If SubAgent status="done" AND tests pass:
{{
  "action": "submit",
  "reasoning": "Verified: [what was fixed, which tests passed]. Submitting for evaluation.",
  "params": {{ "reason": "Fix verified: [specific fix description]" }}
}}

If SubAgent status="done" BUT tests fail or incomplete:
{{
  "action": "delegate_task",
  "reasoning": "SubAgent reported done but [specific issue]: tests show [failure details]",
  "params": {{
    "task_instruction": "CRITICAL: Previous fix incomplete. [specific next steps needed]",
    "context": "⚠️ ISSUE: [what failed]\\n- ✅ DONE: [completed work]\\n- ❌ TODO: [remaining work]",
    "model": "one of {sub_models}"
  }}
}}

If SubAgent status="partial":
{{
  "action": "delegate_task",
  "reasoning": "SubAgent made partial progress: [summary]. Need to [next steps]",
  "params": {{
    "task_instruction": "Continue: [specific next steps based on SUBTASK HISTORY]",
    "context": "From previous attempt:\\n- ✅ WORKED: [keep these]\\n- ❌ FAILED: [avoid these]",
    "model": "one of {sub_models}"
  }}
}}
""".strip()
