"""GAIA runner for POrchestra."""

from __future__ import annotations

import asyncio
import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from base.agent.base_action import BaseAction
from base.engine.async_llm import LLMsConfig, create_llm_instance
from base.engine.logs import logger
from benchmark.common.env import BasicInfo
from benchmark.gaia.llm_scorer import llm_semantic_score
from benchmark.gaia.scorer import question_scorer
from aorchestra.tools.complete import CompleteTool

from porchestra.main_agent import MainAgent
from porchestra.live_trace import LiveTrace
from porchestra.prompts import MainAgentPrompt
from porchestra.tools import DelegateTaskTool


class GAIARunner:
    """Run GAIA levels with POrchestra."""

    def __init__(
        self,
        benchmark,
        main_model: str,
        sub_models: list[str],
        max_attempts: int,
        gaia_tools: list[BaseAction],
        task_timeout_seconds: int | None = None,
    ) -> None:
        self.benchmark = benchmark
        self.main_model = main_model
        self.sub_models = sub_models
        self.max_attempts = max_attempts
        self.gaia_tools = gaia_tools
        self.task_timeout_seconds = task_timeout_seconds

    async def run_levels(
        self,
        levels,
        max_concurrency: int,
        csv_path: Path | None,
        trajectory_folder: Path,
        timestamp: str,
    ) -> dict[str, dict[str, Any]]:
        semaphore = asyncio.Semaphore(max(1, max_concurrency))
        csv_writer, csv_lock, csv_file = self._prepare_csv(csv_path)
        results: dict[str, dict[str, Any]] = {}
        live_root = trajectory_folder.parent / "live" / timestamp

        async def run_single(level_spec):
            level_id = level_spec.get("task_id") or level_spec.get("id") or str(level_spec)
            task_level = level_spec.get("Level")
            question = level_spec.get("Question", "")
            expected_answer = level_spec.get("Final answer", "")
            file_name = level_spec.get("file_name", "")

            async with semaphore:
                env = None
                live_trace = LiveTrace.for_task(live_root, level_id)
                start_time = datetime.now().isoformat()
                attempts_detail: list[dict[str, Any]] = []
                try:
                    live_trace.append(
                        "task_start",
                        task_id=level_id,
                        level=task_level,
                        question=question,
                        expected_answer=expected_answer,
                        file_name=file_name,
                        main_model=self.main_model,
                        sub_models=self.sub_models,
                        max_attempts=self.max_attempts,
                        task_timeout_seconds=self.task_timeout_seconds,
                    )
                    logger.info(f"[POrchestra GAIA] Starting task: {level_id} (Level {task_level})")
                    run_level_spec = dict(level_spec)
                    run_level_spec["_run_id"] = timestamp
                    env = self.benchmark.make_env(run_level_spec, tools=self.gaia_tools)
                    basic_info = env.get_basic_info()

                    main_llm = create_llm_instance(LLMsConfig.default().get(self.main_model))
                    model_to_alias = {model: f"model_{i + 1}" for i, model in enumerate(self.sub_models)}
                    alias_to_model = {alias: model for model, alias in model_to_alias.items()}

                    delegate_tool = DelegateTaskTool(
                        env=env,
                        models=self.sub_models,
                        benchmark_type="gaia",
                        alias_to_model=alias_to_model,
                        default_max_steps=getattr(getattr(env, "config", None), "max_steps", 30),
                        live_trace=live_trace,
                    )
                    revise_tool = delegate_tool.make_revise_tool()
                    complete_tool = CompleteTool()

                    main_agent = MainAgent(
                        llm=main_llm,
                        sub_models=self.sub_models,
                        tools=[delegate_tool, revise_tool, complete_tool],
                        subagent_tools=self.gaia_tools,
                        prompt_builder=MainAgentPrompt,
                        max_attempts=self.max_attempts,
                        benchmark_type="gaia",
                        mask_model_names=True,
                        live_trace=live_trace,
                    )

                    main_info = BasicInfo(
                        env_id=level_id,
                        instruction=basic_info.instruction,
                        action_space="",
                        max_steps=self.max_attempts,
                        meta_data=basic_info.meta_data,
                    )
                    main_agent.reset(main_info)
                    main_cost_before = main_agent.get_usage_cost()
                    live_trace.append(
                        "main_agent_reset",
                        instruction=basic_info.instruction,
                        meta=basic_info.meta_data or {},
                    )

                    final_answer = None

                    async def run_attempt_loop() -> None:
                        nonlocal final_answer
                        max_decision_steps = max(1, self.max_attempts * 4 + 1)
                        for step_idx in range(max_decision_steps):
                            action, resp = await main_agent.step(None, [])
                            action_name = action.get("action")
                            params = action.get("params", {})
                            result = action.get("result", {})
                            attempts_detail.append({
                                "step": step_idx + 1,
                                "action": action_name,
                                "params": params,
                                "result": result,
                                "raw_response": resp,
                                "working_memory": action.get("working_memory"),
                                "active_subagent": action.get("active_subagent"),
                            })
                            live_trace.append(
                                "runner_main_step",
                                step=step_idx + 1,
                                action=action_name,
                                params=params,
                                result=result,
                                raw_response=resp,
                                working_memory=action.get("working_memory"),
                                active_subagent=action.get("active_subagent"),
                            )
                            if action_name == "complete":
                                final_answer = params.get("answer")
                                break

                    if self.task_timeout_seconds is None:
                        await run_attempt_loop()
                    else:
                        await asyncio.wait_for(run_attempt_loop(), timeout=self.task_timeout_seconds)

                    main_cost = max(0.0, main_agent.get_usage_cost() - main_cost_before)
                    reward, success = await self._score(final_answer, expected_answer)
                    sub_cost = sum(
                        float(attempt.get("result", {}).get("cost", 0.0) or 0.0)
                        for attempt in attempts_detail
                    )
                    total_cost = sub_cost + main_cost
                    final_sub_model = _last_sub_model(attempts_detail)
                    end_time = datetime.now().isoformat()

                    self._save_trajectory(
                        trajectory_folder=trajectory_folder,
                        level_id=level_id,
                        timestamp=timestamp,
                        level=task_level,
                        question=question,
                        expected_answer=expected_answer,
                        file_name=file_name,
                        instruction=basic_info.instruction,
                        meta=basic_info.meta_data or {},
                        attempts_detail=attempts_detail,
                        success=success,
                        total_reward=reward,
                        total_cost=total_cost,
                        main_cost=main_cost,
                        sub_cost=sub_cost,
                        final_sub_model=final_sub_model,
                        final_answer=final_answer,
                        error=None,
                        start_time=start_time,
                        end_time=end_time,
                    )
                    await self._write_csv_row(
                        csv_writer=csv_writer,
                        csv_lock=csv_lock,
                        csv_file=csv_file,
                        row={
                            "task_id": level_id,
                            "level": task_level,
                            "main_model": self.main_model,
                            "sub_models": ",".join(self.sub_models),
                            "final_sub_model": final_sub_model,
                            "success": success,
                            "reward": f"{reward:.4f}",
                            "attempts": len(attempts_detail),
                            "sub_cost": f"{sub_cost:.6f}",
                            "main_cost": f"{main_cost:.6f}",
                            "total_cost": f"{total_cost:.6f}",
                            "timestamp": timestamp,
                            "start_time": start_time,
                            "end_time": end_time,
                            "error": None,
                        },
                    )
                    results[level_id] = {
                        "success": success,
                        "reward": reward,
                        "answer": final_answer,
                        "expected_answer": expected_answer,
                    }
                    live_trace.append(
                        "task_complete",
                        success=success,
                        reward=reward,
                        final_answer=final_answer,
                        expected_answer=expected_answer,
                        attempts=len(attempts_detail),
                        total_cost=total_cost,
                        main_cost=main_cost,
                        sub_cost=sub_cost,
                        end_time=end_time,
                    )
                    logger.info(
                        f"[POrchestra GAIA] Completed task: {level_id} | "
                        f"success={success} reward={reward:.4f} attempts={len(attempts_detail)}"
                    )
                except Exception as e:
                    error_msg = (
                        f"task_timeout_seconds={self.task_timeout_seconds}"
                        if isinstance(e, asyncio.TimeoutError)
                        else f"{type(e).__name__}: {e}"
                    )
                    logger.error(f"[POrchestra GAIA] Task {level_id} failed: {error_msg}")
                    end_time = datetime.now().isoformat()
                    live_trace.append(
                        "task_error",
                        error=error_msg,
                        attempts=len(attempts_detail),
                        end_time=end_time,
                    )
                    basic_info = locals().get("basic_info")
                    self._save_trajectory(
                        trajectory_folder=trajectory_folder,
                        level_id=level_id,
                        timestamp=timestamp,
                        level=task_level,
                        question=question,
                        expected_answer=expected_answer,
                        file_name=file_name,
                        instruction=getattr(basic_info, "instruction", None),
                        meta=getattr(basic_info, "meta_data", None),
                        attempts_detail=attempts_detail,
                        success=False,
                        total_reward=0.0,
                        total_cost=0.0,
                        main_cost=0.0,
                        sub_cost=0.0,
                        final_sub_model=None,
                        final_answer=None,
                        error=error_msg,
                        start_time=start_time,
                        end_time=end_time,
                    )
                    await self._write_csv_row(
                        csv_writer=csv_writer,
                        csv_lock=csv_lock,
                        csv_file=csv_file,
                        row={
                            "task_id": level_id,
                            "level": task_level,
                            "main_model": self.main_model,
                            "sub_models": ",".join(self.sub_models),
                            "final_sub_model": None,
                            "success": False,
                            "reward": "0.0000",
                            "attempts": len(attempts_detail),
                            "sub_cost": "0.000000",
                            "main_cost": "0.000000",
                            "total_cost": "0.000000",
                            "timestamp": timestamp,
                            "start_time": start_time,
                            "end_time": end_time,
                            "error": error_msg,
                        },
                    )
                    results[level_id] = {"success": False, "reward": 0.0, "error": error_msg}
                finally:
                    if env and hasattr(env, "close"):
                        try:
                            await env.close()
                        except Exception as e:
                            logger.debug(f"[POrchestra GAIA] Error closing env for {level_id}: {e}")

        tasks = [asyncio.create_task(run_single(level)) for level in levels]
        try:
            await asyncio.gather(*tasks)
        finally:
            if csv_file:
                csv_file.close()
        return results

    async def _score(self, final_answer: Any, expected_answer: str) -> tuple[float, bool]:
        if not final_answer:
            return 0.0, False
        reward = question_scorer(str(final_answer), expected_answer)
        if reward < 0.5:
            try:
                semantic_reward = await llm_semantic_score(str(final_answer), expected_answer)
                if semantic_reward > 0.5:
                    reward = semantic_reward
            except Exception as e:
                logger.warning(f"[POrchestra GAIA] LLM semantic scoring failed: {e}")
        return float(reward), bool(reward > 0.5)

    def _prepare_csv(self, csv_path: Path | None):
        if not csv_path:
            return None, None, None
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        csv_file = open(csv_path, "w", newline="", encoding="utf-8")
        csv_writer = csv.DictWriter(
            csv_file,
            fieldnames=[
                "task_id",
                "level",
                "main_model",
                "sub_models",
                "final_sub_model",
                "success",
                "reward",
                "attempts",
                "sub_cost",
                "main_cost",
                "total_cost",
                "timestamp",
                "start_time",
                "end_time",
                "error",
            ],
        )
        csv_writer.writeheader()
        csv_file.flush()
        return csv_writer, asyncio.Lock(), csv_file

    async def _write_csv_row(self, *, csv_writer, csv_lock, csv_file, row: dict[str, Any]) -> None:
        if not csv_writer or not csv_lock:
            return
        async with csv_lock:
            csv_writer.writerow(row)
            csv_file.flush()

    def _save_trajectory(
        self,
        *,
        trajectory_folder: Path,
        level_id: str,
        timestamp: str,
        level: int | None,
        question: str | None,
        expected_answer: str | None,
        file_name: str | None,
        instruction: str | None,
        meta: dict | None,
        attempts_detail: list[dict[str, Any]],
        success: bool,
        total_reward: float,
        total_cost: float,
        main_cost: float,
        sub_cost: float,
        final_sub_model: str | None,
        final_answer: Any,
        error: str | None,
        start_time: str | None,
        end_time: str | None,
    ) -> None:
        if not trajectory_folder:
            return
        trajectory_folder.mkdir(parents=True, exist_ok=True)
        trajectory_file = trajectory_folder / f"{level_id}_{timestamp}.json"
        data = {
            "task_id": level_id,
            "timestamp": timestamp,
            "start_time": start_time,
            "end_time": end_time,
            "level": level,
            "question": question,
            "expected_answer": expected_answer,
            "file_name": file_name,
            "main_model": self.main_model,
            "sub_models": self.sub_models,
            "max_attempts": self.max_attempts,
            "success": success,
            "total_reward": total_reward,
            "total_cost": total_cost,
            "main_cost": main_cost,
            "sub_cost": sub_cost,
            "attempts": len(attempts_detail),
            "trajectory": attempts_detail,
            "final_sub_model": final_sub_model,
            "final_answer": final_answer,
            "error": error,
            "instruction": instruction,
            "meta": meta or {},
        }
        with trajectory_file.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


def _last_sub_model(attempts_detail: list[dict[str, Any]]) -> str | None:
    for attempt in reversed(attempts_detail):
        result = attempt.get("result", {})
        model = result.get("model")
        if model:
            return str(model)
    return None
