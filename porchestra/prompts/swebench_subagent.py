"""SWE-bench-specific POrchestra SubAgent prompts and response parsing."""

from __future__ import annotations

import json
import re
from typing import Any


SWE_SAE_SCHEMA = """{
  "state": "Concise factual local state.",
  "action": {
    "type": "finish|revise|stop",
    "task_scope": {
      "operation": "keep|reduce|expand|remove|decompose",
      "object": "task object",
      "details": "how the task scope should change"
    },
    "resource": {
      "operation": "keep|request",
      "object": "context|tool|budget|constraint|state_handoff|none",
      "details": "needed resource or no resource change"
    },
    "request": "Concrete request to MainAgent.",
    "reason": "Why this request is justified."
  },
  "evidence": {
    "summary": "Observed evidence supporting the state and request."
  }
}"""


SWE_REVISE_EXAMPLE = """DISCUSSION
The patch is useful, but verification is incomplete and the current workspace should be preserved.

COMMAND
revise {"state":"The source patch is applied but tests are incomplete.","action":{"type":"revise","task_scope":{"operation":"keep","object":"current patch","details":"Continue verification in the same workspace."},"resource":{"operation":"request","object":"budget","details":"Additional execution budget is needed."},"request":"Preserve the workspace and continue the current task.","reason":"The implementation is promising but not fully verified."},"evidence":{"summary":"git diff is non-empty; the relevant test has not completed."}}"""


NATIVE_TOOL_CALLING_SUFFIX = """==== Ordinary Environment Action Output ====
For an ACI or Bash environment action, call the native `aci_command` tool:

  aci_command({"discussion": "concise purpose", "command": "one ACI or Bash command"})

For finish, revise, or stop, do NOT call `aci_command`. Use the textual SAE control
action format and complete JSON schema shown above.

IMPORTANT TOOL NAMESPACE RULE:
`open`, `scroll_down`, `scroll_up`, `goto`, `search_file`, `search_dir`,
`find_file`, `str_replace`, `edit`, `delete_lines`, `insert`, and `create` are
ACI command-language keywords. They are NOT native function tools. Never call
them as tool names. Wrap them inside `aci_command.command`.

Correct native call shape:
  aci_command({"discussion": "Inspect ModelForm.", "command": "open django/forms/models.py 100"})
  aci_command({"discussion": "Find ModelForm.", "command": "search_file ModelForm django/forms/models.py"})

Incorrect native call shape:
  open({"file": "django/forms/models.py", "line_number": 100})
  search_file({"pattern": "ModelForm", "file": "django/forms/models.py"})

==== Strict Output Rules ====
- Choose exactly one path per turn: one native `aci_command` call, or one textual
  finish/revise/stop SAE control action.
- Never represent an environment command with a DISCUSSION/COMMAND text block.
- A textual control action's SAE JSON must be compact and remain on one line.
- Do not output Markdown tool simulations, fabricated stdout, exit codes, or future
  tool results. Tool output is returned by the real environment on the next turn.
- Never claim an edit or test succeeded without a corresponding environment observation.
"""


def build_swebench_native_tools(*, include_aci_command: bool = True) -> list[dict[str, Any]]:
    tools: list[dict[str, Any]] = []
    if include_aci_command:
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": "aci_command",
                    "description": (
                        "The only native environment tool. Execute one real ACI or Bash "
                        "command in /testbed. ACI keywords such as open, search_file, "
                        "str_replace, edit, and create must be placed inside command; "
                        "they are not separate native tools."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "discussion": {
                                "type": "string",
                                "description": "Concise judgment and purpose of this command.",
                            },
                            "command": {
                                "type": "string",
                                "description": "Exactly one ACI or Bash command to execute.",
                            }
                        },
                        "required": ["discussion", "command"],
                    },
                },
            }
        )
    return tools


SWEBENCH_SUBAGENT_PROMPT = """You are a POrchestra SubAgent responsible for a local software-engineering task.
Your goal is to complete the GitHub issue subtask assigned by MainAgent.

You can use the ACI command interface to browse, inspect, edit, and test code.
You are already inside a Docker container. The repository is cloned at the correct commit.

==== Progress ====
[Step {current_step}/{max_steps}] Remaining: {remaining_steps} step(s)
{budget_warning}
Do not wait for budget exhaustion. If the current path is promising but needs more
steps, proactively use revise to request additional budget.

==== Original GitHub Issue ====
{original_question}

==== Execution Contract from MainAgent ====
Subtask:
{task_instruction}

Context:
{context}

==== Current Environment State ====
{state_info}

==== Command Reference ====
{command_docs}

==== Execution and Communication Policy ====
Use ordinary ACI or Bash commands while the current task and resources are sufficient.
Handle ordinary command errors and test failures locally first; do not request revise
merely because a command or test failed.

At any appropriate logical point, you may communicate with MainAgent using:
- finish: the assigned subtask is complete. For a coding task, the current patch is
  ready for MainAgent to submit, with relevant test evidence in the SAE.
- revise: MainAgent must adjust task scope, context, tools, constraints, step budget,
  or state handoff. If requesting budget, set resource.object="budget".
- stop: the current path is invalid, unsafe, ambiguous, or should be abandoned.

Never execute the environment's submit command yourself. When the patch is ready,
use finish; MainAgent owns the official SWE-bench submission.

==== Memory ====
{memory}

==== Current Observation ====
{observation}

==== SAE Control Action Output ====
For finish, revise, or stop, output exactly:

DISCUSSION
<a concise explanation of the current judgment>

COMMAND
<finish|revise|stop> <single-line SAE JSON>

SAE JSON schema:
{sae_schema}

Canonical revise example (copy this command shape exactly):
{revise_example}

==== Ordinary Command Output ====
Output exactly:

DISCUSSION
<a concise explanation of the next command's purpose>

COMMAND
<one ACI or Bash command>

==== Strict Output Rules ====
- DISCUSSION must concisely explain the current judgment and next objective.
- COMMAND must contain exactly one environment command or one control action.
- A control action's SAE JSON must be compact and remain on the same line.
- An environment command may span lines only when its ACI payload requires it
  (for example str_replace, create, edit, or insert).
- Do not add explanations, examples, comments, or any other text after COMMAND.
"""


SWEBENCH_FINAL_HANDOFF_PROMPT = """You are a POrchestra SWE-bench SubAgent at the final step boundary.
Do not execute another environment command. Make one final evidence-backed handoff
to MainAgent using finish, revise, or stop.

- Use finish only when the assigned subtask is complete and the current patch is ready.
- Use revise when the work is incomplete but the current path, patch, or observations
  are worth preserving. Request the task/resource adjustment needed to continue.
- Use stop only when the current path and workspace changes should be abandoned.

==== Original GitHub Issue ====
{original_question}

==== Assigned Subtask ====
{task_instruction}

==== MainAgent Context ====
{context}

==== Memory ====
{memory}

==== Current Observation ====
{observation}

==== Output ====
DISCUSSION
<a concise explanation of the final status>

COMMAND
<finish|revise|stop> <single-line SAE JSON>

SAE JSON schema:
{sae_schema}

Canonical revise example (copy this command shape exactly):
{revise_example}

The action.type must match finish, revise, or stop. Use task_scope.operation="keep"
for finish, and "remove" only for a genuine stop. A revise may request context,
tools, budget, constraints, or state handoff. Do not output anything after COMMAND.
"""


def build_swebench_subagent_prompt(
    *,
    task_instruction: str,
    context: str,
    original_question: str,
    command_docs: str,
    state_info: str,
    memory: str,
    observation: Any,
    current_step: int,
    max_steps: int,
    remaining_steps: int,
    budget_warning: str,
    native_tool_calling: bool = False,
) -> str:
    prompt = SWEBENCH_SUBAGENT_PROMPT.format(
        task_instruction=task_instruction,
        context=context or "No additional context provided.",
        original_question=original_question,
        command_docs=command_docs,
        state_info=state_info,
        memory=memory or "No previous observations.",
        observation=_observation_text(observation),
        current_step=current_step,
        max_steps=max_steps,
        remaining_steps=remaining_steps,
        budget_warning=budget_warning,
        sae_schema=SWE_SAE_SCHEMA,
        revise_example=SWE_REVISE_EXAMPLE,
    )
    if native_tool_calling:
        prompt = prompt.replace(
            "==== Command Reference ====",
            "==== ACI Command String Syntax (inside aci_command.command) ====\n"
            "ACI command keywords (NOT native function tools):",
            1,
        )
        prompt = prompt.replace("Available commands:", "", 1)
        prompt = prompt.split("==== Ordinary Command Output ====", 1)[0]
        prompt += NATIVE_TOOL_CALLING_SUFFIX
    return prompt


def build_swebench_final_handoff_prompt(
    *,
    task_instruction: str,
    context: str,
    original_question: str,
    memory: str,
    observation: Any,
    native_tool_calling: bool = False,
) -> str:
    prompt = SWEBENCH_FINAL_HANDOFF_PROMPT.format(
        task_instruction=task_instruction,
        context=context or "No additional context provided.",
        original_question=original_question,
        memory=memory or "No previous observations.",
        observation=_observation_text(observation),
        sae_schema=SWE_SAE_SCHEMA,
        revise_example=SWE_REVISE_EXAMPLE,
    )
    return prompt


def parse_swebench_native_tool_response(response: dict[str, Any]) -> dict[str, Any]:
    """Convert one OpenAI-compatible native tool call into an agent action."""
    reasoning = str(response.get("content") or "").strip()
    tool_calls = response.get("tool_calls") or []
    if len(tool_calls) != 1:
        return {
            "action": "error",
            "params": {
                "message": f"Expected exactly one native tool call, got {len(tool_calls)}"
            },
            "reasoning": reasoning,
            "_parse_error": "invalid_native_tool_count",
        }
    call = tool_calls[0] if isinstance(tool_calls[0], dict) else {}
    name = str(call.get("name") or "").lower()
    arguments = call.get("arguments")
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            return {
                "action": "error",
                "params": {"message": f"Invalid native tool JSON for {name}: {exc}"},
                "reasoning": reasoning,
                "_parse_error": "invalid_native_tool_json",
            }
    if not isinstance(arguments, dict):
        arguments = {}
    if name == "aci_command":
        discussion = arguments.get("discussion")
        command = arguments.get("command")
        if not isinstance(command, str) or not command.strip():
            return {
                "action": "error",
                "params": {"message": "aci_command requires a non-empty command"},
                "reasoning": reasoning,
                "_parse_error": "invalid_native_command",
            }
        return {
            "action": "aci_command",
            "params": {"command": command.strip()},
            "reasoning": (
                discussion.strip()
                if isinstance(discussion, str) and discussion.strip()
                else reasoning
            ),
            "_native_tool_call": True,
        }
    return {
        "action": "error",
        "params": {"message": f"Unknown native tool: {name or 'missing'}"},
        "reasoning": reasoning,
        "_parse_error": "unknown_native_tool",
    }


def parse_swebench_hybrid_response(response: dict[str, Any]) -> dict[str, Any]:
    """Parse native environment calls or textual SAE control actions."""
    tool_calls = response.get("tool_calls") or []
    if tool_calls:
        return parse_swebench_native_tool_response(response)

    content = str(response.get("content") or "")
    action = parse_swebench_subagent_response(content)
    if action.get("action") == "aci_command":
        return {
            "action": "error",
            "params": {
                "message": "Environment commands must use the native aci_command tool"
            },
            "reasoning": action.get("reasoning", ""),
            "_parse_error": "text_environment_command",
        }
    return action


def parse_swebench_subagent_response(response: str) -> dict[str, Any]:
    """Parse DISCUSSION/COMMAND output into an environment or SAE action."""
    discussion = _section(response, "DISCUSSION", "COMMAND")
    command = _command_section(response)
    if not command:
        return {
            "action": "error",
            "params": {"message": "Missing COMMAND section"},
            "reasoning": discussion,
            "_parse_error": "missing_command",
        }

    control = re.match(r"^(finish|revise|stop)\b", command, re.IGNORECASE)
    if control:
        action_name = control.group(1).lower()
        payload_text = command[control.end():].strip()
        try:
            params = json.loads(payload_text)
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            return {
                "action": "error",
                "params": {"message": f"Invalid {action_name} SAE JSON: {exc}"},
                "reasoning": discussion,
                "_parse_error": "invalid_sae_json",
            }
        if not isinstance(params, dict):
            return {
                "action": "error",
                "params": {"message": f"{action_name} SAE payload must be a JSON object"},
                "reasoning": discussion,
                "_parse_error": "invalid_sae_type",
            }
        return {"action": action_name, "params": params, "reasoning": discussion}

    # Compatibility: models sometimes omit the redundant textual prefix and
    # return the SAE object directly. Recover the control action from the
    # structured action.type instead of discarding an otherwise valid handoff.
    try:
        bare_payload = json.loads(command)
    except (TypeError, ValueError, json.JSONDecodeError):
        bare_payload = None
    if isinstance(bare_payload, dict):
        nested_action = bare_payload.get("action")
        if isinstance(nested_action, dict):
            action_name = str(nested_action.get("type", "")).lower()
            if action_name in {"finish", "revise", "stop"}:
                return {
                    "action": action_name,
                    "params": bare_payload,
                    "reasoning": discussion,
                    "_recovered_control_prefix": True,
                }
        elif isinstance(nested_action, str):
            action_name = nested_action.lower()
            params = bare_payload.get("params", bare_payload.get("action_input"))
            if action_name in {"finish", "revise", "stop"} and isinstance(params, dict):
                return {
                    "action": action_name,
                    "params": params,
                    "reasoning": discussion,
                    "_recovered_control_prefix": True,
                }

    return {
        "action": "aci_command",
        "params": {"command": command},
        "reasoning": discussion,
    }


def _section(response: str, start: str, end: str) -> str:
    match = re.search(
        rf"{re.escape(start)}\s*\n(.*?)(?=\n{re.escape(end)}\s*\n|\Z)",
        response or "",
        re.DOTALL | re.IGNORECASE,
    )
    return match.group(1).strip() if match else ""


def _command_section(response: str) -> str:
    match = re.search(r"COMMAND\s*\n([\s\S]*)\Z", response or "", re.IGNORECASE)
    return match.group(1).strip() if match else ""


def _observation_text(observation: Any) -> str:
    if isinstance(observation, dict):
        return str(observation.get("output") or observation.get("message") or observation)
    return str(observation)


def observation_state_info(observation: Any) -> str:
    if isinstance(observation, dict) and observation.get("state_info"):
        return str(observation["state_info"])
    return "(Open file: n/a) (Current directory: /testbed)"
