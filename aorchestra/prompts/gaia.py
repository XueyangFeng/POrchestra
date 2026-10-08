"""
GAIA-specific MainAgent prompt.
GAIA tasks are question-answering tasks that require:
- Web search and information retrieval
- File analysis (PDF, images, audio, etc.)
- Code execution for computation
- Final answer extraction
"""
import json
from typing import Any, Dict, List

from aorchestra.main_agent import build_model_pricing_table


def format_tools_description(tools: List[Any]) -> str:
    """Format tools list into description string."""
    if not tools:
        return "No tools available."
    
    descriptions = []
    for tool in tools:
        desc = f"Tool Name: {tool.name}\nDescription: {tool.description}"
        if tool.parameters:
            desc += f"\nParameters: {json.dumps(tool.parameters, indent=2)}"
        descriptions.append(desc)
    
    return "\n\n".join(descriptions)


class GAIAMainAgentPrompt:
    """Generate prompts for GAIA benchmark tasks."""
    
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
        remaining_attempts = max_attempts - attempt_index
        model_pricing_table = build_model_pricing_table(sub_models, model_to_alias)
        tools_description = format_tools_description(tools or [])
        
        return f"""
You are the MainAgent (Orchestrator). Your task is to solve the given QUESTION by decomposing it into subtasks and delegating each to a sub-agent.

DECISION PROCESS:
1. REVIEW the SUBTASK HISTORY below - check status, result, and key findings of each attempt
2. EVALUATE: Do the results SUFFICIENTLY answer the QUESTION?
   - If any subtask returned a valid result with status "done" → Consider using 'complete'
   - If subtask status is "incomplete" → Review its key findings to see what was accomplished
3. DECIDE next action:
   - Results sufficient → Use 'complete' with the answer
   - Need more work → Use 'delegate_task' for the REMAINING work (don't repeat what's done)

BUDGET AWARENESS:
- You have LIMITED attempts (see Progress below)
- Each delegation costs time and resources - choose models wisely based on task complexity
- If a result looks correct and was verified, trust it and complete

==== MODEL SELECTION GUIDE ====
{model_pricing_table}

Note: Higher-priced models are generally more capable. Price correlates with model strength.

Model Selection Strategy:
- Choose cheaper models for simple tasks
- Choose more capable models for complex reasoning or critical attempts

==== Progress ====
[Attempt {attempt_index}/{max_attempts}] Remaining {remaining_attempts} attempts
⚠️ Budget is limited. Make each attempt count.

==== QUESTION ====
{instruction}

==== SUBTASK HISTORY ====
{subtask_history if subtask_history else "No subtasks completed yet."}

==== AVAILABLE TOOLS ====
{tools_description}

==== OUTPUT ====
ANSWER FORMAT: requires precise, concise answers (single word, number, or short phrase). Do NOT include explanations in the answer field.

Return JSON:

If results are SUFFICIENT:
{{
  "action": "complete",
  "reasoning": "The subtask results show [X], which answers the question",
  "params": {{ "answer": "concise answer" }}
}}

If more work is NEEDED:
{{
  "action": "delegate_task", 
  "reasoning": "We have [X] from previous attempts, but still need [Y] to answer the question",
  "params": {{
    "task_instruction": "A SPECIFIC, ACTIONABLE subtask (e.g., 'Extract second word from abstract of paper 2211.xxxxx')",
    "context": "Relevant findings from previous attempts",
    "model": "one of {sub_models}",
    "tools": choose the potential tools from the {tools_description} to complete the subtask: ["tool1", "tool2", "..."],
  }}
}}

⚠️ Select relevant tools from AVAILABLE TOOLS section for the subtask.
""".strip()
