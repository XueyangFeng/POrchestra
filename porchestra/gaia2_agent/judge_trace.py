"""Trace GAIA2 judge LLM calls without changing ARE scoring behavior."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any


_LOCK = threading.Lock()
_LOGGER = logging.getLogger(__name__)
_MAX_JUDGE_RETRIES = 10
_RETRY_DELAYS_SECONDS = (1.0, 2.0, 4.0, 8.0, 15.0, 30.0)


def patch_judge_tracing() -> None:
    """Patch ARE's soft judge calls with tracing and transient-error retries."""

    from are.simulation.scenarios.utils.personalization.utils import jinja_format
    from are.simulation.validation.utils import llm_utils

    if getattr(llm_utils, "_porchestra_judge_tracing_patched", False):
        return

    original_llm_function_call = llm_utils.LLMFunction.__call__
    original_llm_checker_call = llm_utils.LLMChecker.__call__

    def llm_function_call(self, user_prompt_args: dict[str, str]) -> str | None:
        call_id = uuid.uuid4().hex
        messages = [{"role": "system", "content": self.system_prompt}]
        messages.extend(self.examples)
        user_prompt = _render_prompt(self.user_prompt_template, user_prompt_args)
        messages.append({"role": "user", "content": user_prompt})

        response = None
        error = None
        attempt_errors: list[dict[str, Any]] = []
        started_at = time.time()
        try:
            response, attempt_errors = _call_judge_with_retry(self.engine, messages)
            return response
        except Exception as exc:
            attempt_errors = getattr(exc, "_porchestra_attempt_errors", attempt_errors)
            error = {"type": type(exc).__name__, "message": str(exc)}
            raise
        finally:
            elapsed = time.time() - started_at
            self._porchestra_last_call_id = call_id
            _write_trace(
                {
                    "kind": "llm_function",
                    "call_id": call_id,
                    "scenario_id": _current_scenario_id(),
                    "thread": threading.current_thread().name,
                    "checker": getattr(self, "_porchestra_checker_name", None)
                    or _infer_checker_name(self.prompt_templates),
                    "model": getattr(self.engine, "model_name", None),
                    "elapsed_seconds": elapsed,
                    "messages": messages,
                    "response": response,
                    "error": error,
                    "attempt_count": len(attempt_errors) if error else len(attempt_errors) + 1,
                    "attempt_errors": attempt_errors,
                    "prompt_sha256": _hash_json(messages),
                }
            )

    def llm_checker_call(self, user_prompt_args: dict[str, str]) -> bool | None:
        checker_name = _infer_checker_name(self.prompt_templates)
        votes: list[bool] = []
        responses: list[dict[str, Any]] = []
        for vote_index in range(self.num_votes):
            self.judge._porchestra_checker_name = checker_name
            response = self.judge(user_prompt_args)
            call_id = getattr(self.judge, "_porchestra_last_call_id", None)
            parsed: bool | None = None
            if response is not None:
                if _contains_marker(response, self.success_str):
                    parsed = True
                    votes.append(True)
                elif _contains_marker(response, self.failure_str):
                    parsed = False
                    votes.append(False)
            responses.append(
                {
                    "vote_index": vote_index,
                    "call_id": call_id,
                    "parsed": parsed,
                    "response": response,
                }
            )

        result = None if not votes else sum(votes) >= len(votes) / 2
        _write_trace(
            {
                "kind": "llm_checker",
                "checker": checker_name,
                "scenario_id": _current_scenario_id(),
                "thread": threading.current_thread().name,
                "success_marker": self.success_str,
                "failure_marker": self.failure_str,
                "votes": votes,
                "result": result,
                "responses": responses,
            }
        )
        return result

    llm_utils.LLMFunction.__call__ = llm_function_call
    llm_utils.LLMChecker.__call__ = llm_checker_call
    llm_utils.LLMFunction._porchestra_original_call = original_llm_function_call
    llm_utils.LLMChecker._porchestra_original_call = original_llm_checker_call
    llm_utils._porchestra_judge_tracing_patched = True


def _call_judge_with_retry(
    engine: Any,
    messages: list[dict[str, Any]],
) -> tuple[str, list[dict[str, Any]]]:
    """Call a judge, retrying transient failures ten times after the first call."""

    attempt_errors: list[dict[str, Any]] = []
    for attempt in range(_MAX_JUDGE_RETRIES + 1):
        try:
            response, _ = engine(messages, additional_trace_tags=["judge_llm"])
            return response, attempt_errors
        except Exception as exc:
            error = {"type": type(exc).__name__, "message": str(exc)}
            if attempt >= _MAX_JUDGE_RETRIES or not _is_retryable_judge_error(exc):
                setattr(exc, "_porchestra_attempt_errors", attempt_errors + [error])
                raise

            attempt_errors.append(error)
            delay = _RETRY_DELAYS_SECONDS[min(attempt, len(_RETRY_DELAYS_SECONDS) - 1)]
            _LOGGER.warning(
                "GAIA2 judge call failed with a transient error; retrying %s/%s in %.1fs: %s",
                attempt + 1,
                _MAX_JUDGE_RETRIES,
                delay,
                exc,
            )
            time.sleep(delay)

    raise AssertionError("unreachable")


def _is_retryable_judge_error(error: Exception) -> bool:
    message = str(error).lower()
    transient_markers = (
        "status=429",
        "status=500",
        "status=502",
        "status=503",
        "status=504",
        "request failed",
        "connection error",
        "connection reset",
        "connection aborted",
        "read timed out",
        "timeout",
        "temporarily unavailable",
        "service_unavailable",
        "no response, please try again",
    )
    return any(marker in message for marker in transient_markers)


def _write_trace(record: dict[str, Any]) -> None:
    trace_dir = os.environ.get("PORCHESTRA_GAIA2_JUDGE_TRACE_DIR")
    record.setdefault("timestamp", time.time())
    if trace_dir:
        path = Path(trace_dir)
        path.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record, ensure_ascii=False, default=str)
        with _LOCK:
            with (path / "judge_llm_calls.jsonl").open("a", encoding="utf-8") as f:
                f.write(line + "\n")

    scenario_id = record.get("scenario_id")
    if scenario_id:
        from porchestra.gaia2_agent.llm_trace import LLMCallTrace

        LLMCallTrace(str(scenario_id)).append(
            {
                **record,
                "kind": "judge_" + str(record.get("kind") or "event"),
                "role": "judge",
            }
        )


def _current_scenario_id() -> str | None:
    try:
        from are.simulation.logging_config import get_logger_scenario_id

        return get_logger_scenario_id()
    except Exception:
        return None


def _infer_checker_name(prompt_templates: Any) -> str:
    try:
        from are.simulation.validation import prompts

        mapping = {
            "content_checker": prompts.CONTENT_CHECKER_PROMPT_TEMPLATES,
            "signature_checker": prompts.SIGNATURE_CHECKER_TEMPLATES,
            "sanity_checker": prompts.SANITY_CHECKER_PROMPT_TEMPLATES,
            "cab_checker": prompts.CAB_CHECKER_PROMPT_TEMPLATES,
            "email_checker": prompts.EMAIL_CHECKER_PROMPT_TEMPLATES,
            "message_checker": prompts.MESSAGE_CHECKER_PROMPT_TEMPLATES,
            "user_message_checker": prompts.USER_MESSAGE_CHECKER_PROMPT_TEMPLATES,
            "event_checker": prompts.EVENT_CHECKER_PROMPT_TEMPLATES,
            "tone_checker": prompts.TONE_CHECKER_PROMPT_TEMPLATES,
            "subtask_extractor": prompts.SUBTASK_EXTRACTOR_PROMPT_TEMPLATES,
            "event_subtask_extractor": prompts.EVENT_SUBTASK_EXTRACTOR_PROMPT_TEMPLATES,
            "user_message_subtask_extractor": prompts.USER_MESSAGE_SUBTASK_EXTRACTOR_PROMPT_TEMPLATES,
        }
        for name, value in mapping.items():
            if prompt_templates is value:
                return name
    except Exception:
        pass
    try:
        from gaia2_core.judge import prompts as cli_prompts

        mapping = {
            "content_checker": cli_prompts.CONTENT_CHECKER_PROMPT_TEMPLATES,
            "signature_checker": cli_prompts.SIGNATURE_CHECKER_TEMPLATES,
            "sanity_checker": cli_prompts.SANITY_CHECKER_PROMPT_TEMPLATES,
            "cab_checker": cli_prompts.CAB_CHECKER_PROMPT_TEMPLATES,
            "email_checker": cli_prompts.EMAIL_CHECKER_PROMPT_TEMPLATES,
            "message_checker": cli_prompts.MESSAGE_CHECKER_PROMPT_TEMPLATES,
            "user_message_checker": cli_prompts.USER_MESSAGE_CHECKER_PROMPT_TEMPLATES,
            "event_checker": cli_prompts.EVENT_CHECKER_PROMPT_TEMPLATES,
            "tone_checker": cli_prompts.TONE_CHECKER_PROMPT_TEMPLATES,
            "subtask_extractor": cli_prompts.SUBTASK_EXTRACTOR_PROMPT_TEMPLATES,
            "event_subtask_extractor": cli_prompts.EVENT_SUBTASK_EXTRACTOR_PROMPT_TEMPLATES,
            "user_message_subtask_extractor": cli_prompts.USER_MESSAGE_SUBTASK_EXTRACTOR_PROMPT_TEMPLATES,
        }
        for name, value in mapping.items():
            if prompt_templates is value:
                return name
    except Exception:
        pass
    return type(prompt_templates).__name__


def _render_prompt(template: str, args: dict[str, str]) -> str:
    if _truthy(os.environ.get("PORCHESTRA_GAIA2_CLI_JUDGE_PROMPTS")):
        try:
            from jinja2 import Template

            return Template(template, keep_trailing_newline=True).render(**args)
        except Exception:
            result = template
            for key, value in args.items():
                result = result.replace("{{" + key + "}}", str(value))
            return result

    from are.simulation.scenarios.utils.personalization.utils import jinja_format

    return jinja_format(template=template, skip_validation=False, **args)


def _truthy(value: str | None) -> bool:
    return value is not None and value.strip().lower() not in {"", "0", "false", "no", "off"}


def _contains_marker(response: str, marker: str) -> bool:
    return marker.lower() in response.lower()


def _hash_json(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
