"""Submit the active SWE-bench container to the official grader."""

from __future__ import annotations

import inspect
from typing import Any

from pydantic import Field

from base.agent.base_action import BaseAction
from base.engine.logs import logger


class SWEBenchSubmitTool(BaseAction):
    name: str = "submit"
    description: str = "Run the official SWE-bench grader in the current container"
    parameters: dict[str, Any] = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "reason": {"type": "string", "description": "Why the patch is ready"},
            },
            "required": ["reason"],
        }
    )

    env: Any = Field(default=None, exclude=True)

    class Config:
        arbitrary_types_allowed = True

    def __init__(self, env: Any):
        super().__init__()
        self.env = env

    async def __call__(self, reason: str = "") -> dict[str, Any]:
        logger.info(f"[POrchestra SWE] Submitting current container: {reason}")
        if not bool(getattr(self.env, "_container_started", False)):
            return {
                "success": False,
                "reward": 0.0,
                "done": True,
                "error": "No active SWE-bench container",
            }

        result = self.env.step({"action": "submit", "params": {}})
        observation, reward, done, info = (
            await result if inspect.isawaitable(result) else result
        )
        return {
            "success": float(reward) == 1.0,
            "reward": float(reward),
            "done": bool(done),
            "observation": observation,
            "info": info,
        }
