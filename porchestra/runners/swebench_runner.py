"""SWE-bench runner for POrchestra."""

from __future__ import annotations

import asyncio
import csv
import json
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from base.engine.async_llm import LLMsConfig, create_llm_instance
from base.engine.logs import logger
from benchmark.common.env import BasicInfo

from porchestra.live_trace import LiveTrace
from porchestra.main_agent import MainAgent
from porchestra.prompts.swebench_main_agent import SWEBenchMainAgentPrompt
from porchestra.tools import DelegateTaskTool, SWEBenchSubmitTool


class SWEBenchPOrchestraRunner:
    """Run SWE-bench levels with delegate/revise/submit orchestration."""

    def __init__(
        self,
        *,
        benchmark: Any,
        main_model: str,
        sub_models: list[str],
        max_attempts: int = 10,
        max_total_steps: int = 500,
        subagent_memory_max_records: int = 10,
        subagent_memory_mode: str = "compressed",
        subagent_backend: str = "react",
        subagent_observation_max_chars: int = 10_000,
        subagent_memory_max_chars: int = 120_000,
        subagent_memory_record_max_chars: int = 12_000,
        task_timeout_seconds: int | None = None,
    ) -> None:
        self.benchmark = benchmark
        self.main_model = main_model
        self.sub_models = sub_models
        self.max_attempts = max_attempts
        self.max_total_steps = max_total_steps
        self.subagent_memory_max_records = max(2, int(subagent_memory_max_records))
        self.subagent_memory_mode = str(subagent_memory_mode).strip().lower()
        self.subagent_backend = str(subagent_backend).strip().lower()
        self.subagent_observation_max_chars = max(
            1, int(subagent_observation_max_chars)
        )
        self.subagent_memory_max_chars = max(1, int(subagent_memory_max_chars))
        self.subagent_memory_record_max_chars = max(
            1, int(subagent_memory_record_max_chars)
        )
        self.task_timeout_seconds = task_timeout_seconds

    async def run_levels(
        self,
        *,
        levels: list[Any],
        max_concurrency: int,
        csv_path: Path,
        trajectory_folder: Path,
        timestamp: str,
    ) -> dict[str, dict[str, Any]]:
        semaphore = asyncio.Semaphore(max(1, max_concurrency))
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        trajectory_folder.mkdir(parents=True, exist_ok=True)
        live_root = trajectory_folder.parent / "live" / timestamp
        csv_lock = asyncio.Lock()
        results: dict[str, dict[str, Any]] = {}

        fieldnames = [
            "instance_id",
            "main_model",
            "sub_models",
            "success",
            "reward",
            "new_attempts",
            "revisions",
            "subagent_steps",
            "main_decisions",
            "total_cost",
            "timestamp",
            "error",
        ]
        csv_file = csv_path.open("w", encoding="utf-8", newline="")
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        csv_file.flush()

        async def run_one(level: Any) -> None:
            instance_id = str(level.get("id") or level.get("task_id"))
            async with semaphore:
                result = await self._run_one(
                    level=level,
                    instance_id=instance_id,
                    trajectory_folder=trajectory_folder,
                    live_root=live_root,
                    timestamp=timestamp,
                )
                results[instance_id] = result
                row = {key: result.get(key) for key in fieldnames}
                async with csv_lock:
                    writer.writerow(row)
                    csv_file.flush()

        try:
            await asyncio.gather(*(run_one(level) for level in levels))
        finally:
            csv_file.close()
        return results

    async def _run_one(
        self,
        *,
        level: Any,
        instance_id: str,
        trajectory_folder: Path,
        live_root: Path,
        timestamp: str,
    ) -> dict[str, Any]:
        env = None
        attempts_detail: list[dict[str, Any]] = []
        live_trace = LiveTrace.for_task(live_root, instance_id)
        start_time = datetime.now().isoformat()
        reward = 0.0
        error: str | None = None
        main_agent: MainAgent | None = None
        delegate: DelegateTaskTool | None = None

        try:
            env = self.benchmark.make_env(level)
            basic_info = env.get_basic_info()
            main_llm = create_llm_instance(LLMsConfig.default().get(self.main_model))
            aliases = {f"model_{index + 1}": model for index, model in enumerate(self.sub_models)}

            delegate = DelegateTaskTool(
                env=env,
                models=self.sub_models,
                benchmark_type="swebench",
                alias_to_model=aliases,
                default_max_steps=int(getattr(env.config, "max_steps", 50)),
                max_total_steps=self.max_total_steps,
                memory_max_records=self.subagent_memory_max_records,
                memory_mode=self.subagent_memory_mode,
                subagent_backend=self.subagent_backend,
                observation_max_chars=self.subagent_observation_max_chars,
                memory_max_chars=self.subagent_memory_max_chars,
                memory_record_max_chars=self.subagent_memory_record_max_chars,
                live_trace=live_trace,
            )
            revise = delegate.make_revise_tool()
            submit = SWEBenchSubmitTool(env)

            main_agent = MainAgent(
                llm=main_llm,
                sub_models=self.sub_models,
                tools=[delegate, revise, submit],
                subagent_tools=[],
                prompt_builder=SWEBenchMainAgentPrompt,
                max_attempts=self.max_attempts,
                benchmark_type="swebench",
                mask_model_names=True,
                live_trace=live_trace,
            )
            main_agent.reset(
                BasicInfo(
                    env_id=instance_id,
                    instruction=basic_info.instruction,
                    action_space="",
                    max_steps=self.max_attempts,
                    meta_data=basic_info.meta_data,
                )
            )
            main_cost_before = main_agent.get_usage_cost()

            async def decision_loop() -> None:
                nonlocal reward
                max_decisions = max(4, self.max_attempts * 4 + 2)
                for decision_index in range(max_decisions):
                    action, raw_response = await main_agent.step(None, [])
                    action_name = action.get("action")
                    action_result = action.get("result") or {}
                    attempts_detail.append(
                        {
                            "decision": decision_index + 1,
                            "action": action_name,
                            "params": action.get("params") or {},
                            "result": _jsonable(action_result),
                            "raw_response": raw_response,
                            "active_subagent": action.get("active_subagent"),
                        }
                    )
                    if action_name == "submit":
                        reward = float(action_result.get("reward", 0.0) or 0.0)
                        return

                logger.warning(
                    f"[POrchestra SWE] Decision limit reached for {instance_id}; "
                    "submitting the current container if available"
                )
                forced = await submit(reason="MainAgent decision limit reached")
                reward = float(forced.get("reward", 0.0) or 0.0)
                attempts_detail.append(
                    {
                        "decision": max_decisions + 1,
                        "action": "forced_submit",
                        "params": {},
                        "result": _jsonable(forced),
                        "raw_response": "",
                        "active_subagent": None,
                    }
                )

            if self.task_timeout_seconds is None:
                await decision_loop()
            else:
                await asyncio.wait_for(decision_loop(), timeout=self.task_timeout_seconds)

            main_cost = max(0.0, main_agent.get_usage_cost() - main_cost_before)
            sub_cost = sum(
                float(item.get("result", {}).get("cost", 0.0) or 0.0)
                for item in attempts_detail
            )
            total_cost = main_cost + sub_cost
        except Exception as exc:
            error = (
                f"task_timeout_seconds={self.task_timeout_seconds}"
                if isinstance(exc, asyncio.TimeoutError)
                else f"{type(exc).__name__}: {exc}"
            )
            logger.error(f"[POrchestra SWE] {instance_id} failed: {error}")
            main_cost = 0.0
            sub_cost = 0.0
            total_cost = 0.0
        finally:
            if env is not None and hasattr(env, "close"):
                try:
                    await env.close()
                except Exception as exc:
                    logger.warning(f"[POrchestra SWE] Cleanup failed for {instance_id}: {exc}")

        new_attempts = sum(item.get("action") == "delegate_task" for item in attempts_detail)
        revisions = sum(item.get("action") == "revise_task" for item in attempts_detail)
        subagent_steps = delegate.total_steps_used if delegate is not None else 0
        success = reward == 1.0
        result = {
            "instance_id": instance_id,
            "main_model": self.main_model,
            "sub_models": ",".join(self.sub_models),
            "success": success,
            "reward": reward,
            "new_attempts": new_attempts,
            "revisions": revisions,
            "subagent_steps": subagent_steps,
            "main_decisions": len(attempts_detail),
            "total_cost": f"{total_cost:.6f}",
            "timestamp": timestamp,
            "error": error or "",
        }
        trajectory = {
            **result,
            "start_time": start_time,
            "end_time": datetime.now().isoformat(),
            "attempts": attempts_detail,
        }
        path = trajectory_folder / f"{instance_id}_{timestamp}.json"
        path.write_text(json.dumps(trajectory, ensure_ascii=False, indent=2), encoding="utf-8")
        return result


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if is_dataclass(value) and not isinstance(value, type):
        return _jsonable(asdict(value))
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return str(value)
