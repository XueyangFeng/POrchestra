"""
GAIA benchmark - Baseline mode (single-layer Agent).

This module provides:
- GAIAConfig: Configuration for GAIA benchmark
- GAIAEnvironment: Agent uses 'complete' to submit answer and trigger scoring
- GAIABenchmark: Factory for creating Baseline environments
- GAIARunner: Runner with incremental trajectory saving
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

from base.agent.base_action import BaseAction
from base.agent.base_agent import BaseAgent
from base.engine.logs import logger
from benchmark.benchmark import Benchmark, LevelSpec
from benchmark.common.env import Action, BasicInfo, Environment, Observation
from benchmark.common.incremental_runner import IncrementalRunner
from benchmark.common.runner import LevelResult, StepRecord
from benchmark.gaia.scorer import question_scorer

PROJECT_ROOT = Path(__file__).parent.parent
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config/benchmarks/gaia.yaml"

# File extension to tool hint mapping
FILE_TOOL_HINTS = {
    '.png': "Use ImageAnalysisAction to analyze this image.",
    '.jpg': "Use ImageAnalysisAction to analyze this image.",
    '.jpeg': "Use ImageAnalysisAction to analyze this image.",
    '.gif': "Use ImageAnalysisAction to analyze this image.",
    '.webp': "Use ImageAnalysisAction to analyze this image.",
    '.mp3': "Use ParseAudioAction to transcribe this audio file.",
    '.wav': "Use ParseAudioAction to transcribe this audio file.",
    '.m4a': "Use ParseAudioAction to transcribe this audio file.",
    '.ogg': "Use ParseAudioAction to transcribe this audio file.",
    '.xlsx': "Use ExecuteCodeAction with pandas to read and analyze this spreadsheet.",
    '.csv': "Use ExecuteCodeAction with pandas to read and analyze this spreadsheet.",
    '.pdf': "Use ExecuteCodeAction with appropriate libraries to extract text from this document.",
    '.docx': "Use ExecuteCodeAction with appropriate libraries to extract text from this document.",
    '.pptx': "Use ExecuteCodeAction with appropriate libraries to extract text from this document.",
    '.py': "Use ExecuteCodeAction to run or analyze this Python script.",
    '.txt': "Use ExecuteCodeAction to read and process this text/JSON file.",
    '.json': "Use ExecuteCodeAction to read and process this text/JSON file.",
    '.jsonld': "Use ExecuteCodeAction to read and process this text/JSON file.",
    '.pdb': "Use ExecuteCodeAction with Biopython to parse this PDB protein structure file.",
    '.zip': "Use ExecuteCodeAction to extract and examine the contents of this archive.",
}

ACTION_SPACE_TEMPLATE = """
### complete
Description: Submit your final answer. This will trigger scoring against the expected answer.
Parameters: {{"answer": "<final answer to the question without any explanation>"}}

[IMPORTANT]
- Use print() in ExecuteCodeAction to see computation results
- Use 'complete' to submit your final answer when you have found it
- When remaining steps < 5, complete with your best answer

Action format: {{"action": "<action_name>", "params": {{...}}}}
Example: {{"action": "GoogleSearchAction", "params": {{"query": "your search query"}}}}
""".strip()


@dataclass
class GAIAConfig:
    """Configuration for GAIA benchmark."""
    dataset_path: Path
    attachments_dir: Path
    max_steps: int = 30
    max_tasks: Optional[int] = None
    level_filter: Optional[List[int]] = None
    split: str = "validation"
    result_folder: Path = PROJECT_ROOT / "workspace/logs/gaia_results"
    trajectory_folder: Path = PROJECT_ROOT / "workspace/logs/gaia_trajectories"
    timestamp: Optional[str] = None

    @classmethod
    def load(cls, config_path: Path | str = DEFAULT_CONFIG_PATH) -> "GAIAConfig":
        """Load configuration from YAML file."""
        config_path = Path(config_path)
        with config_path.open("r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}

        gaia_root = raw.get("gaia_root", "benchmark/gaia/data/Gaia")
        if not Path(gaia_root).is_absolute():
            gaia_root = PROJECT_ROOT / gaia_root
        gaia_root = Path(gaia_root)

        year = raw.get("year", "2023")
        split = raw.get("split", "validation")

        dataset_path = raw.get("dataset_path")
        if dataset_path:
            dataset_path = PROJECT_ROOT / dataset_path if not Path(dataset_path).is_absolute() else Path(dataset_path)
        else:
            dataset_path = gaia_root / year / split / "metadata.jsonl"

        attachments_dir = raw.get("attachments_dir")
        if attachments_dir:
            attachments_dir = PROJECT_ROOT / attachments_dir if not Path(attachments_dir).is_absolute() else Path(attachments_dir)
        else:
            attachments_dir = gaia_root / year / split

        level_filter = raw.get("level_filter")
        if level_filter is not None:
            level_filter = [level_filter] if isinstance(level_filter, int) else [int(l) for l in level_filter]

        def resolve_path(key, default):
            path = raw.get(key, default)
            return PROJECT_ROOT / path if not Path(path).is_absolute() else Path(path)

        return cls(
            dataset_path=Path(dataset_path),
            attachments_dir=Path(attachments_dir),
            max_steps=int(raw.get("max_steps", 30)),
            max_tasks=int(raw["max_tasks"]) if raw.get("max_tasks") else None,
            level_filter=level_filter,
            split=split,
            result_folder=resolve_path("result_folder", "workspace/logs/gaia_results"),
            trajectory_folder=resolve_path("trajectory_folder", "workspace/logs/gaia_trajectories"),
        )


class GAIAEnvironment(Environment):
    """
    Environment for Baseline mode GAIA tasks.
    Agent uses 'complete' action to submit answer and trigger scoring directly.
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
        
        self._steps = 0
        self._done = False

    def _resolve_file_path(self, attachments_dir: Path) -> Optional[Path]:
        """Resolve and validate file attachment path."""
        if not self.file_name:
            return None
        file_path = attachments_dir / self.file_name
        if not file_path.exists():
            logger.warning(f"[GAIA] Attachment file not found: {file_path}")
            return None
        return file_path

    def _build_action_space(self) -> str:
        """Build action space description."""
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
        
        instruction += (
            "\n\n[INSTRUCTIONS]\n"
            "Your task is to answer the question above. Use the available tools to gather information, "
            "analyze data, or execute code as needed. When you have determined the answer, "
            "use 'complete' to submit your final answer for scoring."
        )
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
        """Execute action with 'complete' triggering scoring."""
        if self._done:
            raise RuntimeError("Environment already finished. Call reset() first.")

        self._steps += 1
        action_type = action.get("action", "")
        params = action.get("params", {})

        # Handle complete/SubmitAnswer (both trigger scoring)
        if action_type in ("complete", "SubmitAnswer"):
            return self._handle_submit(params.get("answer", ""))

        # Handle tool execution
        return await self._handle_tool(action_type, params)

    def _handle_submit(self, answer: str) -> Tuple[Observation, float, bool, Dict[str, Any]]:
        """Handle answer submission and scoring."""
        reward = question_scorer(answer, self.expected_answer)
        self._done = True
        
        logger.info(f"[GAIA] Task {self.task_id} complete: answer='{answer}', expected='{self.expected_answer}', reward={reward}")
        
        return {
            "message": "Answer submitted and scored.",
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
            result = await tool(**params)
            observation = {
                "action": action_type,
                "success": result.get("success", False),
                "output": result.get("output") if result.get("success") else None,
                "error": result.get("error") if not result.get("success") else None,
                "current_step": self._steps,
                "max_steps": self.config.max_steps,
            }
            logger.info(f"[GAIA] Task {self.task_id} step {self._steps}: {action_type} -> success={result.get('success')}")
        except Exception as e:
            observation = {
                "action": action_type,
                "success": False,
                "error": str(e),
                "current_step": self._steps,
                "max_steps": self.config.max_steps,
            }
            logger.error(f"[GAIA] Task {self.task_id} tool execution error: {e}")

        return self._check_max_steps(observation)

    def _handle_unknown_action(self, action_type: str) -> Tuple[Observation, float, bool, Dict[str, Any]]:
        """Handle unknown action type."""
        observation = {
            "error": f"Unknown action: {action_type}. Available actions: {list(self.tools.keys()) + ['complete']}",
            "current_step": self._steps,
            "max_steps": self.config.max_steps,
        }
        
        if self._steps >= self.config.max_steps:
            self._done = True
            observation["message"] = "Max steps reached without submitting an answer"
            return observation, 0.0, True, {"error": "unknown_action", "max_steps_reached": True}
        
        return observation, 0.0, False, {"error": "unknown_action"}

    def _check_max_steps(self, observation: Dict) -> Tuple[Observation, float, bool, Dict[str, Any]]:
        """Check if max steps reached and return appropriate response."""
        if self._steps >= self.config.max_steps:
            self._done = True
            observation["message"] = "Max steps reached without submitting an answer"
            return observation, 0.0, True, {"max_steps_reached": True}
        return observation, 0.0, False, {}

    async def close(self):
        """Clean up environment resources."""
        pass


class GAIARunner(IncrementalRunner):
    """Runner for GAIA baseline with error handling and cleanup."""

    async def run(self, agent: BaseAgent, env: Environment) -> LevelResult:
        """Run with proper error handling and cleanup."""
        try:
            return await super().run(agent, env)
        except Exception as e:
            logger.error(f"[GAIA Runner] Task failed: {type(e).__name__}: {e}")
            return LevelResult(
                model=getattr(agent.llm, "model_name", "unknown") if hasattr(agent, "llm") else "unknown",
                total_reward=0.0,
                steps=0,
                done=True,
                trace=[StepRecord(
                    observation={"error": str(e)},
                    action={"error": "task_failed"},
                    reward=0.0,
                    raw_response="",
                    done=True,
                    info={"error": str(e), "error_type": type(e).__name__},
                )],
                cost=0.0,
            )
        finally:
            if hasattr(env, 'close'):
                try:
                    await env.close()
                except Exception as cleanup_error:
                    logger.error(f"[GAIA Runner] Environment cleanup failed: {cleanup_error}")


class GAIABenchmark(Benchmark):
    """
    GAIA Benchmark for Baseline mode (single-layer agent).
    Creates GAIAEnvironment instances where agent uses 'complete' action.
    """

    def __init__(self, config: GAIAConfig, tools: List[BaseAction] | None = None):
        self.config = config
        self.tools = tools or []
        self._levels: List[LevelSpec] = []
        self._load_dataset()
        
        base_dir = config.result_folder.parent if config.result_folder.name == "results" else config.result_folder
        self._runner = GAIARunner(
            trajectory_dir=config.trajectory_folder or (base_dir / "trajectories"),
            csv_summary_path=base_dir / "results.csv"
        )

    def _load_dataset(self):
        """Load GAIA dataset from JSONL file."""
        if not self.config.dataset_path.exists():
            logger.warning(f"[GAIA] Dataset not found: {self.config.dataset_path}")
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
                        try:
                            task_level = int(data.get("Level"))
                        except (TypeError, ValueError):
                            task_level = data.get("Level")
                        if task_level not in self.config.level_filter:
                            continue
                    
                    self._levels.append(data)
                except json.JSONDecodeError as e:
                    logger.warning(f"[GAIA] Failed to parse line {line_num}: {e}")

        # Log statistics
        level_counts = {}
        for level in self._levels:
            l = level.get("Level", "unknown")
            level_counts[l] = level_counts.get(l, 0) + 1
        
        with_files = sum(1 for l in self._levels if l.get("file_name"))
        logger.info(f"[GAIA] Loaded {len(self._levels)} tasks from {self.config.dataset_path}")
        logger.info(f"[GAIA] Level distribution: {level_counts}, with attachments: {with_files}")

    def list_levels(self) -> List[LevelSpec]:
        """Return list of all levels/tasks."""
        levels = self._levels
        if self.config.max_tasks and len(levels) > self.config.max_tasks:
            levels = levels[:self.config.max_tasks]
        return levels

    def make_env(self, level: LevelSpec, tools: List[BaseAction] | None = None) -> GAIAEnvironment:
        """Create GAIAEnvironment for a specific level."""
        return GAIAEnvironment(level, self.config, tools if tools is not None else self.tools)

    def get_level_by_id(self, task_id: str) -> Optional[LevelSpec]:
        """Get a specific task by its ID."""
        return next((l for l in self._levels if l.get("task_id") == task_id), None)

    async def run(self, agent_cls, agent_kwargs=None, runner=None, **kwargs):
        """Run benchmark with GAIARunner as default."""
        return await super().run(agent_cls, agent_kwargs, runner or self._runner, **kwargs)
