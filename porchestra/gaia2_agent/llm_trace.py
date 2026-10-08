"""Per-scenario full LLM call traces for GAIA2-POrchestra."""

from __future__ import annotations

import json
import os
import re
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Callable

from are.simulation.agents.llm.llm_engine import LLMEngine

from porchestra.gaia2_agent.boundary_trace import serialize


_LOCK = threading.Lock()
_SEQUENCES: dict[str, int] = {}
_SENSITIVE_KEYS = {
    "access_token",
    "api_key",
    "authorization",
    "cookie",
    "password",
    "secret",
    "set-cookie",
    "token",
}


class LLMCallTrace:
    """Append complete model calls to one scenario-specific JSONL file."""

    def __init__(self, scenario_id: str) -> None:
        trace_dir = os.environ.get("PORCHESTRA_GAIA2_LLM_TRACE_DIR")
        self.scenario_id = scenario_id
        self.path: Path | None = None
        if trace_dir:
            safe_id = re.sub(r"[^A-Za-z0-9_.-]+", "_", scenario_id) or "unknown"
            self.path = Path(trace_dir) / f"{safe_id}.jsonl"

    @property
    def enabled(self) -> bool:
        return self.path is not None

    def append(self, record: dict[str, Any]) -> None:
        if self.path is None:
            return

        path_key = str(self.path)
        with _LOCK:
            sequence = _SEQUENCES.get(path_key, 0) + 1
            _SEQUENCES[path_key] = sequence
            payload = {
                "schema_version": 1,
                "scenario_id": self.scenario_id,
                "sequence": sequence,
                **record,
            }
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")


class TracingLLMEngine(LLMEngine):
    """Transparent LLMEngine wrapper that records complete request/response pairs."""

    def __init__(
        self,
        engine: LLMEngine,
        trace: LLMCallTrace,
        *,
        role: str,
        context_provider: Callable[[], dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(engine.model_name)
        self.engine = engine
        self.trace = trace
        self.role = role
        self.context_provider = context_provider

    def chat_completion(
        self,
        messages: list[dict[str, Any]],
        stop_sequences=[],
        **kwargs,
    ) -> tuple[str, dict | None]:
        call_id = uuid.uuid4().hex
        started_at = time.time()
        response: str | None = None
        metadata: dict[str, Any] | None = None
        error: dict[str, str] | None = None
        try:
            response, metadata = self.engine.chat_completion(
                messages,
                stop_sequences=stop_sequences,
                **kwargs,
            )
            return response, metadata
        except Exception as exc:
            error = {"type": type(exc).__name__, "message": str(exc)}
            raise
        finally:
            ended_at = time.time()
            self.trace.append(
                {
                    "kind": "llm_call",
                    "call_id": call_id,
                    "role": self.role,
                    "model": self.model_name,
                    "thread": threading.current_thread().name,
                    "started_at": started_at,
                    "ended_at": ended_at,
                    "elapsed_seconds": ended_at - started_at,
                    "context": self._context(),
                    "request": {
                        "messages": serialize(messages),
                        "provider_messages": self._provider_messages(messages),
                        "stop_sequences": serialize(stop_sequences),
                        "kwargs": _sanitize(kwargs),
                    },
                    "response": {
                        "text": response,
                        "metadata": _sanitize(metadata),
                    }
                    if response is not None
                    else None,
                    "error": error,
                }
            )

    def simple_call(self, prompt: str) -> str:
        response, _ = self.chat_completion([{"role": "user", "content": prompt}])
        return response

    def _context(self) -> dict[str, Any]:
        if self.context_provider is None:
            return {}
        try:
            value = self.context_provider()
        except Exception as exc:
            return {"trace_context_error": f"{type(exc).__name__}: {exc}"}
        return _sanitize(value) if isinstance(value, dict) else {"value": serialize(value)}

    def _provider_messages(self, messages: list[dict[str, Any]]) -> Any:
        converter = getattr(self.engine, "_convert_message", None)
        if not callable(converter):
            return serialize(messages)
        try:
            return serialize([converter(message) for message in messages])
        except Exception as exc:
            return {
                "conversion_error": f"{type(exc).__name__}: {exc}",
                "messages": serialize(messages),
            }

    def __getattr__(self, name: str) -> Any:
        return getattr(self.engine, name)


def _sanitize(value: Any) -> Any:
    """Serialize trace data while removing credential-like structured fields."""

    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            if key_text.lower().replace("-", "_") in _SENSITIVE_KEYS:
                result[key_text] = "[REDACTED]"
            else:
                result[key_text] = _sanitize(item)
        return result
    if isinstance(value, (list, tuple, set)):
        return [_sanitize(item) for item in value]
    return serialize(value)
