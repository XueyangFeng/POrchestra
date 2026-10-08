"""
GAIA benchmark - Orchestra mode (MainAgent + SubAgent).

This module provides:
- GAIAOrchestraEnvironment: SubAgent uses 'finish' to report results to MainAgent
- GAIAOrchestraBenchmark: Factory for creating Orchestra environments
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from base.agent.base_action import BaseAction
from base.engine.logs import logger
from benchmark.benchmark import Benchmark, LevelSpec
from benchmark.common.env import Action, BasicInfo, Environment, Observation
from benchmark.bench_gaia import GAIAConfig, FILE_TOOL_HINTS

# Action space template for Orchestra mode (finish instead of complete)
ACTION_SPACE_TEMPLATE = """
### finish
Description: Report your result to MainAgent. Use when you have found the answer or cannot proceed.
Parameters: {{"result": "<answer>", "status": "done|partial|blocked", "summary": "<brief summary of what you did>"}}

[IMPORTANT]
- Use print() in ExecuteCodeAction to see computation results
- Use 'finish' to report your result when done
- When remaining steps < 5, finish with your best result

Action format: {{"action": "<action_name>", "params": {{...}}}}
Example: {{"action": "GoogleSearchAction", "params": {{"query": "your search query"}}}}
""".strip()


class GAIAOrchestraEnvironment(Environment):
    """
    Environment for Orchestra mode GAIA tasks.
    SubAgent uses 'finish' action to report results back to MainAgent.
    This does NOT trigger scoring - MainAgent decides when to submit final answer.
    """

    def __init__(self, level: LevelSpec, config: GAIAConfig, tools: List[BaseAction]):
        self.task_id = level.get("task_id") or level.get("id") or "unknown"
        self.config = config
        self.tools: Dict[str, BaseAction] = {t.name: t for t in tools}
        
        self.question = level.get("Question") or level.get("question") or str(level)
        self.expected_answer = level.get("Final answer") or level.get("answer")
        self.task_level = level.get("Level") or level.get("level")
        
        self.file_name = level.get("file_name") or ""
        self.file_path = self._resolve_file_path(config.attachments_dir)
        
        self.annotator_metadata = level.get("Annotator Metadata", {})
        self.level_data = level
        self.meta_data = {
            "task_id": self.task_id,
            "level": self.task_level,
            "file_name": self.file_name,
            "file_path": str(self.file_path) if self.file_path else None,
            "expected_tools": self.annotator_metadata.get("Tools", ""),
            "expected_steps": self.annotator_metadata.get("Number of steps", ""),
        }
        workspace_root = os.getenv("AORCHESTRA_TASK_WORKSPACE_ROOT")
        safe_task_id = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(self.task_id))
        self.task_workdir = (
            Path(workspace_root).resolve() / safe_task_id
            if workspace_root
            else None
        )
        
        self._steps = 0
        self._done = False

    def _resolve_file_path(self, attachments_dir):
        """Resolve and validate file attachment path."""
        if not self.file_name:
            return None
        file_path = attachments_dir / self.file_name
        if not file_path.exists():
            logger.warning(f"[GAIA Orchestra] Attachment file not found: {file_path}")
            return None
        return file_path

    def _build_action_space(self) -> str:
        """Build action space description for SubAgent."""
        tool_descriptions = []
        for name, tool in self.tools.items():
            desc = f"### {name}\nDescription: {tool.description}"
            if tool.parameters:
                desc += f"\nParameters: {json.dumps(tool.parameters, indent=2)}"
            tool_descriptions.append(desc)
        
        return "Available actions:\n\n" + "\n\n".join(tool_descriptions) + "\n\n" + ACTION_SPACE_TEMPLATE

    def _build_instruction(self) -> str:
        """Build instruction including question and file hints."""
        instruction = f"Question: {self.question}"
        
        if self.file_name and self.file_path:
            ext = self.file_path.suffix.lower()
            tool_hint = FILE_TOOL_HINTS.get(ext, "Use ExecuteCodeAction to process this file.")
            instruction += f"\n\n[ATTACHED FILE]\nFile: {self.file_name}\nPath: {self.file_path}\nHint: {tool_hint}"
        
        # Note: Detailed instructions are in Agent's prompt (ORCHESTRA_GAIA_PROMPT)
        # Environment only provides the question and file context
        return instruction

    def get_basic_info(self) -> BasicInfo:
        """Get basic information about the task."""
        return BasicInfo(
            env_id=self.task_id,
            instruction=self._build_instruction(),
            action_space=self._build_action_space(),
            max_steps=self.config.max_steps,
            meta_data=self.meta_data,
        )

    async def reset(self, seed: int | None = None) -> Observation:
        """Reset environment."""
        self._done = False
        self._steps = 0
        return {
            "message": "Environment ready. Use the available tools to answer the question.",
            "question": self.question,
            "current_step": 0,
            "max_steps": self.config.max_steps,
        }

    async def step(self, action: Action) -> Tuple[Observation, float, bool, Dict[str, Any]]:
        """Execute action and return observation."""
        if self._done:
            raise RuntimeError("Environment already finished. Call reset() first.")

        self._steps += 1
        action_type = action.get("action", "")
        params = action.get("params", {})

        if action_type == "finish":
            return self._handle_finish(params)
        if action_type == "SubmitAnswer":
            return self._handle_submit(params)
        
        return await self._handle_tool(action_type, params)

    def _handle_finish(self, params: Dict) -> Tuple[Observation, float, bool, Dict[str, Any]]:
        """Handle SubAgent finish - report to MainAgent without scoring."""
        result = params.get("result", "")
        status = params.get("status", "done")
        summary = params.get("summary", "")
        
        self._done = True
        finish_result = {"result": result, "status": status, "summary": summary}
        
        logger.info(f"[GAIA Orchestra] Task {self.task_id} finish: result='{result}', status='{status}'")
        
        return {
            "message": "Result reported to MainAgent.",
            "current_step": self._steps,
            "finish_result": finish_result,
        }, 0.0, True, {"finished": True, "finish_result": finish_result}

    def _handle_submit(self, params: Dict) -> Tuple[Observation, float, bool, Dict[str, Any]]:
        """Handle SubmitAnswer - for runner to trigger final scoring."""
        from benchmark.gaia.scorer import question_scorer
        answer = params.get("answer", "")
        reward = question_scorer(answer, self.expected_answer)
        self._done = True
        
        logger.info(f"[GAIA Orchestra] Task {self.task_id} submitted: answer='{answer}', expected='{self.expected_answer}', reward={reward}")
        
        return {
            "message": "Answer submitted",
            "submitted_answer": answer,
            "expected_answer": self.expected_answer,
            "reward": reward,
            "correct": reward == 1.0,
            "current_step": self._steps,
        }, reward, True, {"submitted": True, "correct": reward == 1.0}

    async def _handle_tool(self, action_type: str, params: Dict) -> Tuple[Observation, float, bool, Dict[str, Any]]:
        """Handle tool execution."""
        tool = self.tools.get(action_type)
        
        if tool is None:
            return self._handle_unknown_action(action_type)

        try:
            call_params = dict(params)
            if action_type == "ExecuteCodeAction" and self.task_workdir is not None:
                call_params["_workdir"] = str(self.task_workdir)
            result = await tool(**call_params)
            observation = {
                "action": action_type,
                "success": result.get("success", False),
                "output": result.get("output") if result.get("success") else None,
                "error": result.get("error") if not result.get("success") else None,
                "current_step": self._steps,
                "max_steps": self.config.max_steps,
            }
            logger.info(f"[GAIA Orchestra] Task {self.task_id} step {self._steps}: {action_type} -> success={result.get('success')}")
        except Exception as e:
            observation = {
                "action": action_type,
                "success": False,
                "error": str(e),
                "current_step": self._steps,
                "max_steps": self.config.max_steps,
            }
            logger.error(f"[GAIA Orchestra] Task {self.task_id} tool execution error: {e}")

        return self._check_max_steps(observation)

    def _handle_unknown_action(self, action_type: str) -> Tuple[Observation, float, bool, Dict[str, Any]]:
        """Handle unknown action type."""
        observation = {
            "error": f"Unknown action: {action_type}. Available actions: {list(self.tools.keys()) + ['finish']}",
            "current_step": self._steps,
            "max_steps": self.config.max_steps,
        }
        
        if self._steps >= self.config.max_steps:
            return self._timeout_response(observation, {"error": "unknown_action"})
        
        return observation, 0.0, False, {"error": "unknown_action"}

    def _check_max_steps(self, observation: Dict) -> Tuple[Observation, float, bool, Dict[str, Any]]:
        """Check if max steps reached."""
        if self._steps >= self.config.max_steps:
            return self._timeout_response(observation, {})
        return observation, 0.0, False, {}

    def _timeout_response(self, observation: Dict, extra_info: Dict) -> Tuple[Observation, float, bool, Dict[str, Any]]:
        """Generate timeout response when max steps reached."""
        self._done = True
        finish_result = {
            "result": "",
            "status": "timeout",
            "summary": f"Used all {self.config.max_steps} steps without finish",
        }
        observation["message"] = "Max steps reached"
        observation["finish_result"] = finish_result
        return observation, 0.0, True, {
            **extra_info,
            "max_steps_reached": True,
            "finished": True,
            "finish_result": finish_result,
        }

    async def close(self):
        """Clean up environment resources."""
        pass


class GAIAOrchestraBenchmark(Benchmark):
    """
    GAIA Benchmark for Orchestra mode (MainAgent + SubAgent).
    Creates GAIAOrchestraEnvironment instances where SubAgent uses 'finish'.
    """

    def __init__(self, config: GAIAConfig, tools: List[BaseAction] | None = None):
        self.config = config
        self.tools = tools or []
        self._levels: List[LevelSpec] = []
        self._load_dataset()

    def _load_dataset(self):
        """Load GAIA dataset from JSONL file."""
        if not self.config.dataset_path.exists():
            logger.warning(f"[GAIA Orchestra] Dataset not found: {self.config.dataset_path}")
            return

        self._levels = []
        with self.config.dataset_path.open("r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                if not (line := line.strip()):
                    continue
                try:
                    data = json.loads(line)
                    if "task_id" not in data and "id" not in data:
                        data["task_id"] = f"task_{line_num}"
                    
                    if self.config.level_filter is not None:
                        if data.get("Level") not in self.config.level_filter:
                            continue
                    
                    self._levels.append(data)
                except json.JSONDecodeError as e:
                    logger.warning(f"[GAIA Orchestra] Failed to parse line {line_num}: {e}")

        level_counts = {}
        for level in self._levels:
            l = level.get("Level", "unknown")
            level_counts[l] = level_counts.get(l, 0) + 1
        
        with_files = sum(1 for l in self._levels if l.get("file_name"))
        logger.info(f"[GAIA Orchestra] Loaded {len(self._levels)} tasks from {self.config.dataset_path}")
        logger.info(f"[GAIA Orchestra] Level distribution: {level_counts}, with attachments: {with_files}")

    def list_levels(self) -> List[LevelSpec]:
        """Return list of all levels/tasks."""
        levels = self._levels
        if self.config.max_tasks and len(levels) > self.config.max_tasks:
            levels = levels[:self.config.max_tasks]
        return levels

    def make_env(self, level: LevelSpec, tools: List[BaseAction] | None = None) -> GAIAOrchestraEnvironment:
        """Create GAIAOrchestraEnvironment for a specific level."""
        return GAIAOrchestraEnvironment(level, self.config, tools if tools is not None else self.tools)

    def get_level_by_id(self, task_id: str) -> Optional[LevelSpec]:
        """Get a specific task by its ID."""
        return next((l for l in self._levels if l.get("task_id") == task_id), None)
