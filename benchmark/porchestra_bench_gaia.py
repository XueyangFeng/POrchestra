"""
GAIA benchmark adapter for POrchestra.

This intentionally does not reuse benchmark.aorchestra_bench_gaia because that
adapter injects the old finish(result/status/summary) action into action_space.
POrchestra control actions are specified by the SubAgent SAE prompt instead.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from base.agent.base_action import BaseAction
from base.engine.logs import logger
from benchmark.benchmark import Benchmark, LevelSpec
from benchmark.bench_gaia import FILE_TOOL_HINTS, GAIAConfig
from benchmark.common.env import Action, BasicInfo, Environment, Observation


class PorchestraGAIAEnvironment(Environment):
    """GAIA environment for POrchestra SubAgents."""

    def __init__(self, level: LevelSpec, config: GAIAConfig, tools: List[BaseAction]):
        self.task_id = level.get("task_id") or level.get("id") or "unknown"
        self.config = config
        self.tools: Dict[str, BaseAction] = {tool.name: tool for tool in tools}
        self._base_max_steps = max(1, int(config.max_steps))
        self._max_steps = self._base_max_steps

        run_id = _safe_path_component(level.get("_run_id") or "adhoc")
        task_dir = _safe_path_component(self.task_id)
        self.execution_dir = (
            Path(config.result_folder).parent
            / "task_workspaces"
            / run_id
            / task_dir
        )

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

        self._steps = 0
        self._done = False

    def _resolve_file_path(self, attachments_dir):
        if not self.file_name:
            return None
        file_path = attachments_dir / self.file_name
        if not file_path.exists():
            logger.warning(f"[POrchestra GAIA] Attachment file not found: {file_path}")
            return None
        return file_path

    def _build_action_space(self) -> str:
        tool_descriptions = []
        for name, tool in self.tools.items():
            desc = f"### {name}\nDescription: {tool.description}"
            if tool.parameters:
                desc += f"\nParameters: {json.dumps(tool.parameters, indent=2)}"
            tool_descriptions.append(desc)
        return "Available actions:\n\n" + "\n\n".join(tool_descriptions)

    def _build_instruction(self) -> str:
        instruction = f"Question: {self.question}"

        if self.file_name and self.file_path:
            ext = self.file_path.suffix.lower()
            tool_hint = FILE_TOOL_HINTS.get(ext, "Use ExecuteCodeAction to process this file.")
            instruction += (
                f"\n\n[ATTACHED FILE]\n"
                f"File: {self.file_name}\n"
                f"Path: {self.file_path}\n"
                f"Hint: {tool_hint}"
            )
        return instruction

    def get_basic_info(self) -> BasicInfo:
        return BasicInfo(
            env_id=self.task_id,
            instruction=self._build_instruction(),
            action_space=self._build_action_space(),
            max_steps=self._max_steps,
            meta_data=self.meta_data,
        )

    async def reset(self, seed: int | None = None) -> Observation:
        self._done = False
        self._steps = 0
        self._max_steps = self._base_max_steps
        return {
            "message": "Environment ready. Use the available tools to answer the question.",
            "question": self.question,
            "current_step": 0,
            "max_steps": self._max_steps,
        }

    def extend_step_budget(self, additional_steps: int) -> int:
        """Extend this environment's real, task-local step limit."""
        self._max_steps += max(0, int(additional_steps))
        return self._max_steps

    async def step(self, action: Action) -> Tuple[Observation, float, bool, Dict[str, Any]]:
        if self._done:
            raise RuntimeError("Environment already finished. Call reset() first.")

        self._steps += 1
        action_type = action.get("action", "")
        params = action.get("params", {})

        if action_type == "SubmitAnswer":
            return self._handle_submit(params)

        return await self._handle_tool(action_type, params)

    def _handle_submit(self, params: Dict) -> Tuple[Observation, float, bool, Dict[str, Any]]:
        from benchmark.gaia.scorer import question_scorer

        answer = params.get("answer", "")
        reward = question_scorer(answer, self.expected_answer)
        self._done = True

        logger.info(
            f"[POrchestra GAIA] Task {self.task_id} submitted: "
            f"answer='{answer}', expected='{self.expected_answer}', reward={reward}"
        )

        return {
            "message": "Answer submitted",
            "submitted_answer": answer,
            "expected_answer": self.expected_answer,
            "reward": reward,
            "correct": reward == 1.0,
            "current_step": self._steps,
        }, reward, True, {"submitted": True, "correct": reward == 1.0}

    async def _handle_tool(self, action_type: str, params: Dict) -> Tuple[Observation, float, bool, Dict[str, Any]]:
        tool = self.tools.get(action_type)
        if tool is None:
            return self._handle_unknown_action(action_type)

        try:
            call_params = dict(params)
            if action_type == "ExecuteCodeAction":
                call_params["_workdir"] = str(self.execution_dir)
            result = await tool(**call_params)
            observation = {
                "action": action_type,
                "success": result.get("success", False),
                "output": result.get("output") if result.get("success") else None,
                "error": result.get("error") if not result.get("success") else None,
                "current_step": self._steps,
                "max_steps": self._max_steps,
            }
            logger.info(
                f"[POrchestra GAIA] Task {self.task_id} step {self._steps}: "
                f"{action_type} -> success={result.get('success')}"
            )
        except Exception as e:
            observation = {
                "action": action_type,
                "success": False,
                "error": str(e),
                "current_step": self._steps,
                "max_steps": self._max_steps,
            }
            logger.error(f"[POrchestra GAIA] Task {self.task_id} tool execution error: {e}")

        return self._check_max_steps(observation)

    def _handle_unknown_action(self, action_type: str) -> Tuple[Observation, float, bool, Dict[str, Any]]:
        observation = {
            "error": f"Unknown action: {action_type}. Available actions: {list(self.tools.keys())}",
            "current_step": self._steps,
            "max_steps": self._max_steps,
        }
        if self._steps >= self._max_steps:
            return self._timeout_response(observation, {"error": "unknown_action"})
        return observation, 0.0, False, {"error": "unknown_action"}

    def _check_max_steps(self, observation: Dict) -> Tuple[Observation, float, bool, Dict[str, Any]]:
        if self._steps >= self._max_steps:
            return self._timeout_response(observation, {})
        return observation, 0.0, False, {}

    def _timeout_response(self, observation: Dict, extra_info: Dict) -> Tuple[Observation, float, bool, Dict[str, Any]]:
        self._done = True
        observation["message"] = "Max steps reached"
        return observation, 0.0, True, {
            **extra_info,
            "max_steps_reached": True,
        }

    async def close(self):
        pass


def _safe_path_component(value: Any) -> str:
    text = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value or "unknown")).strip("._")
    return text or "unknown"


class PorchestraGAIABenchmark(Benchmark):
    """Factory for POrchestra GAIA environments."""

    def __init__(self, config: GAIAConfig, tools: List[BaseAction] | None = None):
        self.config = config
        self.tools = tools or []
        self._levels: List[LevelSpec] = []
        self._load_dataset()

    def _load_dataset(self) -> None:
        if not self.config.dataset_path.exists():
            logger.warning(f"[POrchestra GAIA] Dataset not found: {self.config.dataset_path}")
            return

        self._levels = []
        with self.config.dataset_path.open("r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
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
                    logger.warning(f"[POrchestra GAIA] Failed to parse line {line_num}: {e}")

        level_counts: dict[Any, int] = {}
        for level in self._levels:
            level_name = level.get("Level", "unknown")
            level_counts[level_name] = level_counts.get(level_name, 0) + 1

        with_files = sum(1 for level in self._levels if level.get("file_name"))
        logger.info(f"[POrchestra GAIA] Loaded {len(self._levels)} tasks from {self.config.dataset_path}")
        logger.info(f"[POrchestra GAIA] Level distribution: {level_counts}, with attachments: {with_files}")

    def list_levels(self) -> List[LevelSpec]:
        levels = self._levels
        if self.config.max_tasks and len(levels) > self.config.max_tasks:
            levels = levels[: self.config.max_tasks]
        return levels

    def make_env(self, level: LevelSpec, tools: List[BaseAction] | None = None) -> PorchestraGAIAEnvironment:
        return PorchestraGAIAEnvironment(level, self.config, tools if tools is not None else self.tools)

    def get_level_by_id(self, task_id: str) -> Optional[LevelSpec]:
        return next((level for level in self._levels if level.get("task_id") == task_id), None)
