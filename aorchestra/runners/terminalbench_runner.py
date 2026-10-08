"""TerminalBench Runner with MainAgent orchestration."""
from __future__ import annotations

import asyncio
import csv
import json
from datetime import datetime
from pathlib import Path
from typing import List

from base.engine.async_llm import LLMsConfig, create_llm_instance
from base.engine.logs import logger
from benchmark.common.env import BasicInfo, Environment
from benchmark.common.runner import Runner, StepRecord, LevelResult
from aorchestra.main_agent import MainAgent
from aorchestra.prompts.terminalbench import TerminalBenchPrompt
from aorchestra.tools.delegate import DelegateTaskTool
from aorchestra.tools.submit import SubmitTool


class SubAgentRunner(Runner):
    """Runner for SubAgent (standard agent-environment loop)."""
    
    async def run(self, agent, env: Environment) -> LevelResult:
        """Run SubAgent with standard interaction loop."""
        import inspect
        from base.engine.logs import LogLevel
        
        logger.info(f"[SubAgentRunner] Starting SubAgent execution")
        
        try:
            info = env.get_basic_info()
            agent.reset(info)

            reset_result = env.reset()
            obs = await reset_result if inspect.isawaitable(reset_result) else reset_result

            history = []
            total_reward = 0.0
            max_steps = info.max_steps

            for t in range(max_steps):
                current_step = t + 1
                logger.log_to_file(LogLevel.INFO, f"Environment Observation:{obs}")
                
                try:
                    if self.step_timeout:
                        step_result = await asyncio.wait_for(
                            agent.step(
                                observation=obs,
                                history=history,
                                current_step=current_step,
                                max_steps=max_steps,
                            ),
                            timeout=self.step_timeout,
                        )
                    else:
                        step_result = await agent.step(
                            observation=obs,
                            history=history,
                            current_step=current_step,
                            max_steps=max_steps,
                        )
                except asyncio.TimeoutError:
                    logger.error(f"Agent step timed out after {self.step_timeout} seconds")
                    step_record = StepRecord(
                        observation=obs,
                        action={"error": "step_timeout"},
                        reward=0.0,
                        raw_response="step timeout",
                        done=True,
                        info={"error": "step_timeout"},
                        raw_input=None,
                    )
                    history.append(step_record)
                    break

                if isinstance(step_result, (list, tuple)):
                    if len(step_result) == 3:
                        action, raw_response, raw_input = step_result
                    elif len(step_result) == 2:
                        action, raw_response = step_result
                        raw_input = None
                    else:
                        raise ValueError(f"agent.step returned {len(step_result)} values")
                else:
                    raise TypeError(f"agent.step returned unsupported type: {type(step_result)}")
                
                logger.info(f"\n[SubAgent Step {current_step}/{max_steps}] ACTION: {action}")

                obs_next, reward, done, step_info = await env.step(action)

                step_record = StepRecord(
                    observation=obs,
                    action=action,
                    reward=reward,
                    raw_response=raw_response,
                    done=done,
                    info=step_info,
                    raw_input=raw_input,
                )
                history.append(step_record)
                total_reward += reward
                obs = obs_next

                if done:
                    break

            usage_summary = agent.llm.get_usage_summary()
            result = LevelResult(
                model=usage_summary.get("model", ""),
                total_reward=total_reward,
                steps=len(history),
                done=history[-1].done if history else False,
                trace=history,
                cost=usage_summary.get("total_cost", 0.0),
                input_tokens=usage_summary.get("total_input_tokens", 0),
                output_tokens=usage_summary.get("total_output_tokens", 0),
            )
            logger.info(f"[SubAgentRunner] SubAgent completed: steps={result.steps}, reward={result.total_reward}")
            return result
            
        except Exception as e:
            logger.error(f"[SubAgentRunner] SubAgent execution failed: {e}", exc_info=True)
            raise


class TerminalBenchRunner(Runner):
    """Runner for MainAgent with SubAgent delegation."""
    
    def __init__(
        self,
        main_model: str,
        sub_models: List[str],
        max_attempts: int = 10,
        prompt_builder=None,
        trajectory_dir: Path | None = None,
        csv_summary_path: Path | None = None,
    ):
        self.main_model = main_model
        self.sub_models = sub_models
        self.max_attempts = max_attempts
        self.prompt_builder = prompt_builder or TerminalBenchPrompt
        self.trajectory_dir = Path(trajectory_dir) if trajectory_dir else None
        self.csv_summary_path = Path(csv_summary_path) if csv_summary_path else None
        self._csv_lock = asyncio.Lock()
    
    async def run(self, agent, env: Environment) -> LevelResult:
        """Run MainAgent orchestration."""
        env_info = env.get_basic_info()
        logger.info(f"[Orchestra] Starting task: {env_info.env_id}")
        
        # Create MainAgent info
        main_info = BasicInfo(
            env_id=env_info.env_id,
            instruction=env_info.instruction,
            action_space="",
            max_steps=self.max_attempts,
            meta_data=env_info.meta_data,
        )
        
        # Create MainAgent with tools
        logger.info(f"[Orchestra] Creating MainAgent with model={self.main_model}")
        main_llm = create_llm_instance(LLMsConfig.default().get(self.main_model))
        sub_runner = SubAgentRunner()
        
        delegate = DelegateTaskTool(
            env=env, 
            runner=sub_runner, 
            models=self.sub_models,
            benchmark_type="terminalbench",
        )
        submit = SubmitTool(env=env)
        
        main_agent = MainAgent(
            llm=main_llm,
            sub_models=self.sub_models,
            tools=[delegate, submit],
            prompt_builder=self.prompt_builder,
            max_attempts=self.max_attempts,
            benchmark_type="terminalbench",
        )
        main_agent.reset(main_info)
        
        # Orchestration loop
        history = []
        total_reward = 0.0
        total_sub_cost = 0.0
        done = False
        level_result = None
        exception_occurred = None
        
        try:
            for attempt_idx in range(self.max_attempts):
                logger.info(f"[Orchestra] MainAgent attempt {attempt_idx + 1}/{self.max_attempts}")
                
                try:
                    action, resp = await main_agent.step(None, history)
                except Exception as step_error:
                    logger.error(f"[Orchestra] MainAgent.step() FAILED: {step_error}", exc_info=True)
                    raise
                
                action_name = action.get("action")
                result = action.get("result", {})
                reward = result.get("reward", 0.0)
                step_done = result.get("done", False)
                is_submit = action_name == "submit"
                
                if action_name == "delegate_task":
                    sub_cost = result.get("cost", 0.0)
                    total_sub_cost += sub_cost
                
                history.append(StepRecord(
                    observation={},
                    action=action,
                    reward=reward,
                    raw_response=resp,
                    done=step_done,
                    info=result,
                ))
                
                if is_submit:
                    total_reward = reward
                
                if step_done and is_submit:
                    done = True
                    break
            
            # Force submit if needed
            if not done:
                logger.info("[Orchestra] Max attempts reached without submit")
                executor = getattr(env, "_executor", None)
                container_ready = hasattr(env, '_container_started') and env._container_started
                
                if container_ready and executor and hasattr(executor, "run_tests"):
                    try:
                        reward = await executor.run_tests()
                        total_reward = float(reward or 0.0)
                        done = True
                    except Exception as e:
                        logger.error(f"[Orchestra] Forced submit failed: {e}")
                        done = True
                        total_reward = 0.0
            
        except Exception as e:
            logger.error(f"[Orchestra] Exception: {e}", exc_info=True)
            exception_occurred = e
            
        finally:
            # Cleanup
            if hasattr(env, 'close'):
                try:
                    await env.close()
                except Exception as e:
                    logger.error(f"[Orchestra] Cleanup error: {e}")
            
            # Build result
            try:
                usage = main_agent.llm.get_usage_summary() if main_agent else {}
                main_cost = usage.get("total_cost", 0.0)
                total_cost = main_cost + total_sub_cost
                
                level_result = LevelResult(
                    model=usage.get("model", self.main_model),
                    total_reward=total_reward,
                    steps=len(history),
                    done=done,
                    trace=history,
                    cost=total_cost,
                    input_tokens=usage.get("total_input_tokens", 0),
                    output_tokens=usage.get("total_output_tokens", 0),
                )
                
                if self.trajectory_dir:
                    self._save_trajectory(env_info, level_result, main_agent, history)
                
                if self.csv_summary_path:
                    await self._save_csv(env_info.env_id, level_result)
                    
            except Exception as save_error:
                logger.error(f"[Orchestra] Save error: {save_error}")
            
            if exception_occurred:
                raise exception_occurred
            
            return level_result
    
    def _save_trajectory(self, info: BasicInfo, result: LevelResult, 
                         main_agent, history: List[StepRecord]) -> None:
        """Save detailed trajectory."""
        try:
            self.trajectory_dir.mkdir(parents=True, exist_ok=True)
            
            attempts = []
            for i, record in enumerate(history):
                action_data = record.action
                action_name = action_data.get("action")
                result_data = action_data.get("result", {})
                
                attempt = {
                    "attempt": i + 1,
                    "subtask_history": action_data.get("subtask_history", ""),
                    "main_agent": {
                        "action": action_name,
                        "params": action_data.get("params", {}),
                        "raw_response": record.raw_response,
                    },
                }
                
                if action_name == "delegate_task":
                    attempt["sub_agent"] = {
                        "model": result_data.get("model"),
                        "tools_assigned": result_data.get("tools_assigned", []),
                        "steps": result_data.get("steps_taken", 0),
                        "cost": result_data.get("cost", 0.0),
                        "finish_result": result_data.get("finish_result"),
                        "trace_summary": result_data.get("trace_summary", ""),
                    }
                elif action_name == "submit":
                    attempt["submit_result"] = {
                        "success": result_data.get("success"),
                        "reward": result_data.get("reward"),
                    }
                
                attempts.append(attempt)
            
            trajectory = {
                "task_id": info.env_id,
                "instruction": info.instruction,
                "metadata": info.meta_data,
                "main_model": self.main_model,
                "sub_models": self.sub_models,
                "total_reward": result.total_reward,
                "success": result.total_reward > 0,
                "done": result.done,
                "total_attempts": len(history),
                "total_cost": result.cost,
                "timestamp": result.timestamp,
                "attempts": attempts,
            }
            
            filename = f"{info.env_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            filepath = self.trajectory_dir / filename
            
            with filepath.open("w", encoding="utf-8") as f:
                json.dump(trajectory, f, indent=2, ensure_ascii=False)
                
            logger.info(f"[Orchestra] Trajectory saved to {filepath}")
        except Exception as e:
            logger.error(f"[Orchestra] Failed to save trajectory: {e}")
    
    async def _save_csv(self, task_id: str, result: LevelResult) -> None:
        """Save summary to CSV."""
        async with self._csv_lock:
            try:
                self.csv_summary_path.parent.mkdir(parents=True, exist_ok=True)
                
                fieldnames = ["task_id", "model", "success", "reward", "attempts", "cost", "timestamp"]
                
                need_header = not self.csv_summary_path.exists() or self.csv_summary_path.stat().st_size == 0
                if need_header:
                    with self.csv_summary_path.open("w", newline="", encoding="utf-8") as f:
                        writer = csv.DictWriter(f, fieldnames=fieldnames)
                        writer.writeheader()
                
                success = result.total_reward > 0
                with self.csv_summary_path.open("a", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writerow({
                        "task_id": task_id,
                        "model": result.model,
                        "success": success,
                        "reward": f"{result.total_reward:.4f}",
                        "attempts": result.steps,
                        "cost": f"{result.cost:.6f}",
                        "timestamp": result.timestamp,
                    })
            except Exception as e:
                logger.error(f"[Orchestra] Failed to save CSV: {e}")
