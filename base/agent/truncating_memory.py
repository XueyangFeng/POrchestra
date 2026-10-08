"""Raw agent memory with deterministic truncation and no LLM compression."""

from __future__ import annotations

import json
from typing import Any

from base.agent.memory import Memory


TRUNCATION_MARKER = "\n...[truncated]...\n"


def truncate_text(text: Any, max_chars: int | None) -> str:
    """Keep the beginning and end of text within ``max_chars`` characters."""
    value = str(text)
    if max_chars is None or max_chars <= 0 or len(value) <= max_chars:
        return value
    if max_chars <= len(TRUNCATION_MARKER) + 2:
        return value[:max_chars]
    available = max_chars - len(TRUNCATION_MARKER)
    head = max(1, int(available * 0.6))
    tail = max(1, available - head)
    return value[:head] + TRUNCATION_MARKER + value[-tail:]


class TruncatingMemory(Memory):
    """Keep raw records, truncating fields and dropping oldest rendered records.

    Unlike :class:`Memory`, this class never calls the LLM to summarize history.
    It bounds context deterministically in two places:

    - each rendered record is capped by ``max_record_chars``;
    - the full rendered memory is capped by ``max_total_chars`` and retains the
      newest records that fit.
    """

    def __init__(
        self,
        llm: Any = None,
        *,
        max_total_chars: int = 120_000,
        max_record_chars: int = 12_000,
    ) -> None:
        # Set an unreachable record threshold for compatibility. _compress is
        # also overridden, so no summarization call can occur.
        super().__init__(llm=llm, max_memory=2**31 - 1, keep_recent=0)
        self.max_total_chars = max(1, int(max_total_chars))
        self.max_record_chars = max(1, int(max_record_chars))

    async def _compress(self) -> None:
        """Intentionally do nothing: this memory never summarizes with an LLM."""
        return None

    def _get_text(self) -> str:
        if not self._records:
            return "None"

        blocks: list[str] = []
        used = 0
        omitted = 0
        newest_first = list(reversed(self._records))
        for index, record in enumerate(newest_first, 1):
            block = self._render_record(index, record)
            separator_cost = 2 if blocks else 0
            if used + separator_cost + len(block) > self.max_total_chars:
                omitted = len(newest_first) - len(blocks)
                break
            blocks.append(block)
            used += separator_cost + len(block)
        header = "[Raw recent steps (latest first); no LLM compression]"
        if omitted:
            header += f"\n[Omitted {omitted} oldest step(s) due to context limit]"
        body = "\n\n".join(blocks)
        rendered = header + ("\n" + body if body else "")
        return truncate_text(rendered, self.max_total_chars)

    def _render_record(self, index: int, record: dict[str, Any]) -> str:
        action = _json_text(record.get("action"))
        observation = _json_text(record.get("observation"))
        thinking = _json_text(record.get("thinking"))
        reward = record.get("reward")
        block = (
            f"{index}. action={action}\n"
            f"observation={observation}\n"
            f"thinking={thinking}\n"
            f"reward={reward}"
        )
        return truncate_text(block, self.max_record_chars)


class LinearMemory(Memory):
    """Keep the complete raw trajectory in chronological order.

    This mirrors mini-SWE-agent's linear context policy: observations are
    deterministically truncated, but old interaction steps are never summarized
    or discarded.
    """

    def __init__(self, llm: Any = None, *, max_observation_chars: int = 10_000) -> None:
        super().__init__(llm=llm, max_memory=2**31 - 1, keep_recent=0)
        self.max_observation_chars = max(1, int(max_observation_chars))

    async def _compress(self) -> None:
        return None

    def _get_text(self) -> str:
        if not self._records:
            return "None"

        blocks = ["[Raw steps (oldest first); complete linear history; no LLM compression]"]
        for index, record in enumerate(self._records, 1):
            observation = truncate_text(
                _json_text(record.get("observation")),
                self.max_observation_chars,
            )
            blocks.append(
                f"{index}. action={_json_text(record.get('action'))}\n"
                f"observation={observation}\n"
                f"thinking={_json_text(record.get('thinking'))}\n"
                f"reward={record.get('reward')}"
            )
        return "\n\n".join(blocks)


def _json_text(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except Exception:
        return str(value)
