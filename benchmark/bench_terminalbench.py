"""Terminal Bench benchmark implementation."""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import toml
import yaml

from base.engine.logs import logger
from base.agent.base_agent import BaseAgent
from benchmark.benchmark import Benchmark, LevelSpec
from benchmark.common.env import Action, BasicInfo, Environment, Observation
from benchmark.common.incremental_runner import IncrementalRunner
from benchmark.common.runner import LevelResult, StepRecord
from benchmark.terminalbench.base_executor import BaseExecutor
from benchmark.terminalbench.daytona_executor import DaytonaExecutor
from benchmark.terminalbench.docker_executor import DockerExecutor
from benchmark.terminalbench.docker_manager import DockerComposeManager
from benchmark.terminalbench.e2b_executor import E2BExecutor
from benchmark.terminalbench.utils import resolve_path

# Project root
PROJECT_ROOT = Path(__file__).parent.parent
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config/benchmarks/terminalbench.yaml"
DOCKER_COMPOSE_BUILD_PATH = PROJECT_ROOT / "benchmark/terminalbench/docker-compose-build.yaml"

# Global docker manager
_docker_manager = DockerComposeManager(DOCKER_COMPOSE_BUILD_PATH)


@dataclass
class TerminalBenchConfig:
    """Configuration for Terminal Bench benchmark."""

    tasks_dir: Path
    max_steps: int = 30
    max_tasks: Optional[int] = None
    docker_timeout: int = 600
    model: Optional[str] = None
    result_folder: Path = PROJECT_ROOT / "workspace/logs"
    trajectory_dir: Optional[Path] = None  # If None, defaults to result_folder/trajectories
    csv_summary_path: Optional[Path] = None  # If None, defaults to result_folder/results.csv
    timestamp: Optional[str] = None  # Optional timestamp for run
    env_init: Optional[dict[str, str]] = None
    sandbox: str = "docker"  # "docker", "e2b", or "daytona"
    e2b_api_key: Optional[str] = None  # E2B API key (if not set, use E2B_API_KEY env var)
    daytona_api_key: Optional[str] = None  # Daytona API key
    daytona_api_url: Optional[str] = None  # Daytona API URL
    daytona_target: Optional[str] = None  # Daytona target region

    @classmethod
    def load(cls, config_path: Path | str = DEFAULT_CONFIG_PATH) -> "TerminalBenchConfig":
        """Load configuration from YAML file."""
        config_path = Path(config_path)
        with config_path.open("r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}

        tasks_dir = resolve_path(raw.get("tasks_dir"), config_path, PROJECT_ROOT)
        if not tasks_dir:
            raise ValueError("tasks_dir is required in config")

        max_steps = int(raw.get("max_steps", 30))
        max_tasks = raw.get("max_tasks")
        if max_tasks is not None:
            max_tasks = int(max_tasks)

        docker_timeout = int(raw.get("docker_timeout", 600))
        model = raw.get("model")
        env_init = raw.get("env_init")
        sandbox = raw.get("sandbox", "docker")
        e2b_api_key = raw.get("e2b_api_key")
        daytona_api_key = raw.get("daytona_api_key")
        daytona_api_url = raw.get("daytona_api_url")
        daytona_target = raw.get("daytona_target")

        result_folder = resolve_path(
            raw.get("result_folder", "workspace/logs"), config_path, PROJECT_ROOT
        )
        
        trajectory_dir = raw.get("trajectory_dir")
        if trajectory_dir:
            trajectory_dir = resolve_path(trajectory_dir, config_path, PROJECT_ROOT)
        
        csv_summary_path = raw.get("csv_summary_path")
        if csv_summary_path:
            csv_summary_path = resolve_path(csv_summary_path, config_path, PROJECT_ROOT)
        
        timestamp = raw.get("timestamp")

        return cls(
            tasks_dir=tasks_dir,
            max_steps=max_steps,
            max_tasks=max_tasks,
            docker_timeout=docker_timeout,
            model=str(model) if model is not None else None,
            result_folder=result_folder or PROJECT_ROOT / "workspace/logs",
            trajectory_dir=trajectory_dir,
            csv_summary_path=csv_summary_path,
            timestamp=timestamp,
            env_init=env_init,
            sandbox=sandbox,
            e2b_api_key=e2b_api_key,
            daytona_api_key=daytona_api_key,
            daytona_api_url=daytona_api_url,
            daytona_target=daytona_target,
        )


class TerminalBenchEnvironment(Environment):
    """Environment for a single Terminal Bench task."""

    def __init__(self, level: LevelSpec, config: TerminalBenchConfig):
        self.task_id: str = level["id"]
        self.task_dir: Path = level["_task_dir"]
        self.config = config

        # Load task configuration from task.toml
        task_config_path = self.task_dir / "task.toml"
        if task_config_path.exists():
            self.task_config = toml.load(task_config_path)
        else:
            self.task_config = {}

        # Load instruction from instruction.md
        instruction_path = self.task_dir / "instruction.md"
        if instruction_path.exists():
            self.instruction = instruction_path.read_text(encoding="utf-8").strip()
        else:
            self.instruction = "Complete the task."

        # State
        self._steps = 0
        self._done = False
        self._command_history: List[str] = []
        self._container_started: bool = False

        # Logs directories for this task (separate verifier and agent logs)
        if config.timestamp:
            task_folder_name = f"{self.task_id}_{config.timestamp}"
        else:
            task_folder_name = self.task_id
        self._task_logs_dir = config.result_folder / task_folder_name / "logs"
        self._verifier_logs_dir = self._task_logs_dir / "verifier"
        self._agent_logs_dir = self._task_logs_dir / "agent"
        self._verifier_logs_dir.mkdir(parents=True, exist_ok=True)
        self._agent_logs_dir.mkdir(parents=True, exist_ok=True)

        # Create executor based on config.sandbox
        self._executor: BaseExecutor
        if config.sandbox == "e2b":
            self._executor = E2BExecutor(
                task_id=self.task_id,
                task_dir=self.task_dir,
                task_config=self.task_config,
                verifier_logs_dir=self._verifier_logs_dir,
                agent_logs_dir=self._agent_logs_dir,
                timeout=config.docker_timeout,
                env_init=config.env_init,
                api_key=config.e2b_api_key,
            )
        elif config.sandbox == "daytona":
            self._executor = DaytonaExecutor(
                task_id=self.task_id,
                task_dir=self.task_dir,
                task_config=self.task_config,
                verifier_logs_dir=self._verifier_logs_dir,
                agent_logs_dir=self._agent_logs_dir,
                timeout=config.docker_timeout,
                env_init=config.env_init,
                api_key=config.daytona_api_key,
                api_url=config.daytona_api_url,
                target=config.daytona_target,
            )
        else:  # default to docker
            self._executor = DockerExecutor(
                task_id=self.task_id,
                task_dir=self.task_dir,
                task_config=self.task_config,
                verifier_logs_dir=self._verifier_logs_dir,
                agent_logs_dir=self._agent_logs_dir,
                docker_manager=_docker_manager,
                docker_timeout=config.docker_timeout,
                env_init=config.env_init,
            )

    def get_basic_info(self) -> BasicInfo:
        """Get basic information about the task."""
        metadata = self.task_config.get("metadata", {})
        return BasicInfo(
            env_id=self.task_id,
            instruction=self.instruction,
            action_space=(
                "Execute shell commands in a Docker container.\n"
                'Actions:\n'
                '  - {"action": "execute", "params": {"command": "your shell command"}}\n'
                '  - {"action": "finish", "params": {"status": "...", "completed": [...], "issues": [...], "message": "..."}}\n'
                '\n'
                '[ACTION GUIDE]\n'
                '- "execute": Run a shell command and observe the result\n'
                '- "finish": Summarize your work and report to MainAgent. You MUST provide:\n'
                '    * status: "done" (subtask completed), "partial" (progress made), or "blocked" (cannot proceed)\n'
                '    * completed: list of specific actions completed\n'
                '    * issues: list of problems encountered\n'
                '    * message: brief summary of current state\n'
                '  IMPORTANT: Use "finish" before running out of steps!\n'
                '  NOTE: You CANNOT submit - only MainAgent can submit. Use "finish" to report progress.\n'
            ),
            max_steps=self.config.max_steps,
            meta_data={
                "task_dir": str(self.task_dir),
                "difficulty": metadata.get("difficulty", "unknown"),
                "category": metadata.get("category", ""),
                "tags": metadata.get("tags", []),
            },
        )

    async def cleanup_container_if_exists(self) -> None:
        """Clean up existing container before starting a new SubAgent."""
        if self._container_started:
            logger.info(f"[TerminalBench] Cleaning up existing container for task {self.task_id}")
            try:
                await self._executor.cleanup()
                self._container_started = False
            except Exception as e:
                logger.warning(f"[TerminalBench] Failed to cleanup existing container: {e}")

    async def reset(self, seed: int | None = None) -> Observation:
        """Reset environment by starting Docker container."""
        self._done = False
        self._steps = 0
        self._command_history = []

        await self.cleanup_container_if_exists()

        # Start Docker container (async, runs in thread pool)
        await self._executor.start_container()
        self._container_started = True

        return {
            "message": "Environment ready. You can execute shell commands.",
            "instruction": self.instruction,
            "current_step": 0,
            "max_steps": self.config.max_steps,
        }



    async def step(self, action: Action) -> Tuple[Observation, float, bool, Dict[str, Any]]:
        """Execute action and return observation, reward, done, info."""
        self._steps += 1
        action_type = action.get("action", "")
        params = action.get("params", {})

        if self._done and action_type != "submit":
            raise RuntimeError("Environment already finished. Call reset() first.")

        if action_type == "execute":
            command = params.get("command", "")
            if not command:
                return (
                    {"error": "No command provided"},
                    0.0,
                    False,
                    {"error": "No command provided"},
                )

            self._command_history.append(command)
            output, exit_code = await self._executor.execute_command(command)

            # Save command to agent log file
            command_log = self._agent_logs_dir / "commands.log"
            with command_log.open("a", encoding="utf-8") as f:
                f.write(f"[Step {self._steps}] {command}\n")
                f.write(f"Exit Code: {exit_code}\n")
                f.write(f"Output:\n{output}\n")
                f.write("-" * 80 + "\n")

            observation = {
                "command": command,
                "output": output,
                "exit_code": exit_code,
                "current_step": self._steps,
                "max_steps": self.config.max_steps,
            }

            if self._steps >= self.config.max_steps:
                self._done = True
                observation["message"] = "Max steps reached, subtask finished"
                observation["finish_result"] = {
                    "status": "timeout",
                    "completed": [],
                    "issues": ["Max steps reached before subtask completion"],
                    "message": f"SubAgent used all {self.config.max_steps} steps without explicit finish",
                }
                return observation, 0.0, True, {
                    "command_executed": command,
                    "max_steps_reached": True,
                    "finished": True,
                    "finish_result": {
                        "status": "timeout",
                        "completed": [],
                        "issues": ["Max steps reached before subtask completion"],
                        "message": f"SubAgent used all {self.config.max_steps} steps without explicit finish",
                    },
                }

            return observation, 0.0, self._done, {"command_executed": command}

        elif action_type == "finish":
            finish_status = params.get("status", "done")
            finish_completed = params.get("completed", [])
            finish_issues = params.get("issues", [])
            finish_message = params.get("message", "")

            self._done = True
            observation = {
                "message": "Subtask finished. Awaiting next instruction.",
                "current_step": self._steps,
                "finish_result": {
                    "status": finish_status,
                    "completed": finish_completed,
                    "issues": finish_issues,
                    "message": finish_message,
                },
            }
            return observation, 0.0, True, {
                "finished": True,
                "finish_result": {
                    "status": finish_status,
                    "completed": finish_completed,
                    "issues": finish_issues,
                    "message": finish_message,
                },
            }

        elif action_type == "submit":
            reward = await self._executor.run_tests()
            self._done = True

            observation = {
                "message": "Solution submitted",
                "reward": reward,
                "current_step": self._steps,
            }

            return observation, reward, True, {"submitted": True}

        else:
            return (
                {"error": f"Unknown action type: {action_type}"},
                0.0,
                False,
                {"error": f"Unknown action type: {action_type}"},
            )

    async def close(self):
        """Close environment and cleanup resources."""
        await self._executor.cleanup()
        self._container_started = False


class TerminalBenchRunner(IncrementalRunner):
    """Runner for TerminalBench: incremental save + container cleanup."""
    
    async def run(self, agent: BaseAgent, env: Environment) -> LevelResult:
        result = None
        try:
            result = await super().run(agent, env)
            return result
        except Exception as e:
            logger.error(f"TerminalBench task failed: {type(e).__name__}: {e}")
            info = env.get_basic_info()
            result = LevelResult(
                model=getattr(agent.llm, "model_name", "unknown"),
                total_reward=0.0,
                steps=0,
                done=False,  # Mark failed tasks as done=False
                trace=[StepRecord(
                    observation={"error": str(e)},
                    action={"error": "task_failed"},
                    reward=0.0,
                    raw_response="",
                    done=False,
                    info={"error": str(e), "error_type": type(e).__name__},
                )],
                cost=0.0,
            )
            # Record failed task to CSV
            if self.csv_summary_path:
                self._append_csv_row(info.env_id, result)
            return result
        finally:
            # Cleanup containers/sandboxes
            if hasattr(env, 'close'):
                try:
                    await env.close()
                except Exception as cleanup_error:
                    logger.error(f"Container cleanup failed: {cleanup_error}")


class TerminalBenchBenchmark(Benchmark):
    """Terminal Bench benchmark."""

    def __init__(self, config: TerminalBenchConfig):
        self.config = config
        # Get trajectory_dir and csv_summary_path from config with defaults
        # Use parent of result_folder for trajectories/csv if result_folder is 'results' subdir
        base_dir = config.result_folder.parent if config.result_folder.name == "results" else config.result_folder
        trajectory_dir = config.trajectory_dir or (base_dir / "trajectories")
        csv_summary_path = config.csv_summary_path or (base_dir / "results.csv")
        self._runner = TerminalBenchRunner(
            trajectory_dir=trajectory_dir,
            csv_summary_path=csv_summary_path
        )

    def list_levels(self) -> List[LevelSpec]:
        """List all available tasks."""
        if not self.config.tasks_dir.exists():
            raise FileNotFoundError(
                f"\n{'='*70}\n"
                f"Terminal Bench tasks directory not found!\n"
                f"{'='*70}\n"
                f"Expected location: {self.config.tasks_dir}\n\n"
                f"To download the dataset, run:\n"
                f"  python run_terminalbench.py --download\n\n"
                f"Or manually:\n"
                f"  git clone --depth=1 \\\n"
                f"    https://github.com/laude-institute/terminal-bench-2.git \\\n"
                f"    {self.config.tasks_dir}\n"
                f"{'='*70}\n"
            )

        levels = []
        for task_dir in sorted(self.config.tasks_dir.iterdir()):
            if not task_dir.is_dir():
                continue
            if task_dir.name.startswith('.'):
                continue

            # Check for task.toml
            task_config_path = task_dir / "task.toml"
            if not task_config_path.exists():
                continue

            levels.append({
                "id": task_dir.name,
                "_task_dir": task_dir,  # Internal: used by make_env
            })

            if self.config.max_tasks and len(levels) >= self.config.max_tasks:
                break

        return levels

    def make_env(self, level: LevelSpec) -> Environment:
        """Create environment for a specific task."""
        return TerminalBenchEnvironment(level, self.config)
    
    async def run(self, agent_cls, agent_kwargs=None, runner=None, **kwargs):
        """Run benchmark with TerminalBenchRunner as default."""
        runner = runner or self._runner
        return await super().run(agent_cls, agent_kwargs, runner, **kwargs)


def load_benchmark(config_path: Path | str = DEFAULT_CONFIG_PATH) -> TerminalBenchBenchmark:
    """Load Terminal Bench benchmark from config file."""
    cfg = TerminalBenchConfig.load(config_path)
    return TerminalBenchBenchmark(cfg)
