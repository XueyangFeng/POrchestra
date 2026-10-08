"""Standalone SWE-bench runner for SWEBenchSubAgent."""
from __future__ import annotations

import asyncio
import inspect
from datetime import datetime
from pathlib import Path
from typing import Any

from base.engine.logs import LogLevel, logger
from benchmark.common.env import Environment
from benchmark.common.incremental_runner import IncrementalRunner
from benchmark.common.runner import LevelResult, StepRecord


class DirectSWEBenchSubAgentRunner(IncrementalRunner):
    """Run a SWEBenchSubAgent directly and evaluate its final workspace."""

    def __init__(
        self,
        trajectory_dir: Path | None = None,
        csv_summary_path: Path | None = None,
        *,
        auto_evaluate: bool = True,
    ) -> None:
        super().__init__(trajectory_dir=trajectory_dir, csv_summary_path=csv_summary_path)
        self.auto_evaluate = auto_evaluate
        self._save_lock = asyncio.Lock()

    async def run(self, agent, env: Environment) -> LevelResult:
        """Run the SubAgent loop without a MainAgent delegation layer."""
        info = env.get_basic_info()
        start_time = datetime.now().isoformat()
        history: list[StepRecord] = []
        total_reward = 0.0
        done = False

        try:
            agent.reset(info)
            reset_result = env.reset()
            obs = await reset_result if inspect.isawaitable(reset_result) else reset_result

            for step_index in range(info.max_steps):
                current_step = step_index + 1
                logger.info(
                    f"[DirectSWEBenchSubAgent] Step {current_step}/{info.max_steps}"
                )
                logger.log_to_file(LogLevel.INFO, f"Environment Observation:{obs}")

                try:
                    step_call = agent.step(
                        observation=obs,
                        history=history,
                        current_step=current_step,
                        max_steps=info.max_steps,
                    )
                    if self.step_timeout:
                        step_result = await asyncio.wait_for(
                            step_call,
                            timeout=self.step_timeout,
                        )
                    else:
                        step_result = await step_call
                    action, raw_response, raw_input = self._unpack_step_result(step_result)
                except asyncio.TimeoutError:
                    message = f"Agent LLM step timed out after {self.step_timeout}s"
                    logger.warning(f"[DirectSWEBenchSubAgent] {message}; continuing")
                    action = {
                        "action": "error",
                        "params": {
                            "message": message,
                            "error_type": "step_timeout",
                            "infrastructure_error": True,
                            "retryable": True,
                            "attempts": 1,
                            "exclude_from_scoring": False,
                        },
                        "reasoning": "Transient step timeout; preserve workspace and continue.",
                    }
                    raw_response = message
                    raw_input = None
                obs_next, reward, done, step_info = await env.step(action)
                step_info = dict(step_info or {})

                record_transition = getattr(agent, "record_transition", None)
                if callable(record_transition) and action.get("action") not in {
                    "finish", "revise", "stop"
                }:
                    transition_result = record_transition(
                        action=action,
                        observation_after=obs_next,
                        thinking=action.get("reasoning"),
                        reward=float(reward or 0.0),
                        raw_response=raw_response,
                    )
                    if inspect.isawaitable(transition_result):
                        await transition_result

                if action.get("action") == "finish" and self.auto_evaluate:
                    reward, evaluation = await self._evaluate_workspace(env)
                    done = True
                    step_info.update(
                        {
                            "auto_evaluated": True,
                            "test_results": evaluation,
                        }
                    )
                    obs_next = {
                        **(obs_next if isinstance(obs_next, dict) else {}),
                        "reward": reward,
                        "test_results": evaluation,
                        "message": "SubAgent finished; official evaluation completed.",
                    }

                history.append(
                    StepRecord(
                        observation=obs,
                        action=action,
                        reward=float(reward or 0.0),
                        raw_response=raw_response,
                        done=done,
                        info=step_info,
                        raw_input=raw_input,
                    )
                )
                total_reward += float(reward or 0.0)
                obs = obs_next

                if done:
                    break

        except Exception as exc:
            logger.error(
                f"[DirectSWEBenchSubAgent] Task failed: {type(exc).__name__}: {exc}",
                exc_info=True,
            )
            history.append(
                StepRecord(
                    observation={"error": str(exc)},
                    action={"action": "error", "params": {"message": str(exc)}},
                    reward=0.0,
                    raw_response="",
                    done=True,
                    info={"error": str(exc), "error_type": type(exc).__name__},
                )
            )
            done = True
        finally:
            if hasattr(env, "close"):
                try:
                    close_result = env.close()
                    if inspect.isawaitable(close_result):
                        await close_result
                except Exception as cleanup_error:
                    logger.error(
                        f"[DirectSWEBenchSubAgent] Container cleanup failed: {cleanup_error}"
                    )

        end_time = datetime.now().isoformat()
        result = self._build_result(
            agent,
            history,
            total_reward,
            start_time=start_time,
            end_time=end_time,
        )
        result.done = done

        async with self._save_lock:
            if self.trajectory_dir:
                self._save_trajectory(info, result, agent)
            if self.csv_summary_path:
                self._append_csv_row(info.env_id, result)

        return result

    @staticmethod
    def _unpack_step_result(step_result: Any) -> tuple[dict, str, str | None]:
        if not isinstance(step_result, (list, tuple)):
            raise TypeError(f"agent.step returned unsupported type: {type(step_result)}")
        if len(step_result) == 3:
            action, raw_response, raw_input = step_result
        elif len(step_result) == 2:
            action, raw_response = step_result
            raw_input = None
        else:
            raise ValueError(f"agent.step returned {len(step_result)} values")
        return action, raw_response, raw_input

    @staticmethod
    async def _evaluate_workspace(env: Environment) -> tuple[float, dict[str, Any]]:
        executor = getattr(env, "_executor", None)
        if executor is None or not hasattr(executor, "run_tests"):
            raise RuntimeError("SWE-bench environment has no test executor")

        if hasattr(executor, "execute_command"):
            patch, exit_code = await executor.execute_command(
                "cd /testbed && git diff --binary"
            )
            logs_dir = getattr(executor, "logs_dir", None)
            if logs_dir:
                Path(logs_dir).mkdir(parents=True, exist_ok=True)
                Path(logs_dir, "model.patch").write_text(
                    patch if exit_code == 0 else "",
                    encoding="utf-8",
                )

        reward, test_results = await executor.run_tests()
        return float(reward or 0.0), test_results
