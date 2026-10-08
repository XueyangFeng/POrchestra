"""Fail GAIA2 agents immediately when an LLM context window is exceeded."""

from __future__ import annotations

import os
from typing import Any


_CONTEXT_OVERFLOW_MARKERS = (
    "maximum context length",
    "context length exceeded",
    "context window exceeded",
    "prompt is too long",
    "too many tokens",
)


def is_context_overflow(error: BaseException) -> bool:
    """Return whether an LLM error unambiguously reports context overflow."""
    message = str(error).lower()
    return any(marker in message for marker in _CONTEXT_OVERFLOW_MARKERS)


def patch_context_overflow_failure() -> None:
    """Convert context overflow errors into ARE fatal agent failures."""
    if not _truthy(os.environ.get("PORCHESTRA_GAIA2_FAIL_ON_CONTEXT_OVERFLOW")):
        return

    from are.simulation.agents.llm.llm_engine import LLMEngineException
    from are.simulation.agents.llm.openai_compat_engine import OpenAICompatEngine
    from are.simulation.exceptions import FatalError

    if getattr(OpenAICompatEngine, "_porchestra_context_overflow_patched", False):
        return

    original = OpenAICompatEngine.chat_completion

    def chat_completion(self: Any, *args: Any, **kwargs: Any):
        try:
            return original(self, *args, **kwargs)
        except LLMEngineException as error:
            if is_context_overflow(error):
                raise FatalError(f"LLM context window exceeded: {error}") from error
            raise

    OpenAICompatEngine.chat_completion = chat_completion
    OpenAICompatEngine._porchestra_context_overflow_patched = True


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}
