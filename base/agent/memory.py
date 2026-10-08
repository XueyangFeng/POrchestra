from __future__ import annotations

from abc import ABC
from typing import List, Dict, Any, Optional

import json

from base.engine.async_llm import AsyncLLM 
from benchmark.common.env import Observation, Action


class Memory(ABC):

    def __init__(
        self,
        llm: AsyncLLM,
        max_memory: int = 10,
        keep_recent: int = 3,
        max_observation_chars: int = 10_000,
        max_thinking_chars: int = 4_000,
        max_raw_response_chars: int = 10_000,
        max_summary_chars: int = 10_000,
    ):
        self.llm = llm
        self.max_memory = max_memory
        self.keep_recent = keep_recent
        self.max_observation_chars = max(1, int(max_observation_chars))
        self.max_thinking_chars = max(1, int(max_thinking_chars))
        self.max_raw_response_chars = max(1, int(max_raw_response_chars))
        self.max_summary_chars = max(1, int(max_summary_chars))
        self._records: List[Dict[str, Any]] = []
        self._summary: Optional[str] = None

    async def add_memory(
        self,
        obs: Observation,
        action: Action,
        thinking: Optional[str] = None,
        reward: Optional[float] = None,
        raw_response: Optional[str] = None,
    ) -> None:
        """
        Add a new memory record, then trigger compression if needed.
        """
        record = {
            "observation": _bounded_value(obs, self.max_observation_chars),
            "action": action,
            "thinking": _bounded_value(thinking, self.max_thinking_chars),
            "reward": reward,
            "raw_response": _bounded_value(
                raw_response, self.max_raw_response_chars
            ),
        }
        self._records.append(record)
        await self._compress()

    def _get_text(self) -> str:
        """
        Return readable memory text for prompts.
        """
        if not self._summary and not self._records:
            return "None"

        parts: List[str] = []

        if self._records:
            parts.append("[Recent steps (latest first)]")
            for idx, r in enumerate(reversed(self._records), 1):
                act = r.get("action")
                obs = r.get("observation")
                thinking = r.get("thinking")
                reward = r.get("reward")
                parts.append(f"{idx}. act={act}, obs={obs}, thinking={thinking}, reward={reward}")

        if self._summary:
            parts.append("")
            parts.append("[Summary of earlier steps]")
            parts.append(self._summary)

        return "\n".join(parts)

    def as_text(self) -> str:
        return self._get_text()

    async def _compress(self) -> None:
        """
        When record count reaches max_memory:
        - Compress older records into the summary.
        - Keep only the most recent keep_recent raw records.
        """
        if len(self._records) < self.max_memory:
            return

        if self.keep_recent > 0:
            head = self._records[:-self.keep_recent]
            tail = self._records[-self.keep_recent:]
        else:
            head = self._records[:]
            tail = []

        if head:
            # Rewrite one bounded persistent summary instead of appending a new
            # summary forever. This keeps long-running agents from growing their
            # prompt linearly after every compression cycle.
            head_summary = await self._summarize_records(
                head, previous_summary=self._summary
            )
            self._summary = _truncate_text(
                head_summary, self.max_summary_chars
            )
                
        self._records = tail

    async def _summarize_records(
        self,
        records: List[Dict[str, Any]],
        previous_summary: Optional[str] = None,
    ) -> str:
        """
        Compress a batch of records using the LLM.
        """

        record_lines: List[str] = []
        for idx, r in enumerate(records, 1):
            act = r.get("action")
            obs = r.get("observation")
            reward = r.get("reward")
            thinking = r.get("thinking")
            record_lines.append(
                f"{idx}. action={json.dumps(act, ensure_ascii=False)}, "
                f"observation={json.dumps(obs, ensure_ascii=False)}, "
                f"thinking={json.dumps(thinking, ensure_ascii=False)}, "
                f"reward={reward}"
            )
        records_text = "\n".join(record_lines)
        previous_text = previous_summary or "None"

        summary_prompt = f"""
You are the memory compression module of a language-model-based agent.

You are given the previous persistent memory plus several newly completed
interaction transitions in chronological order (oldest first).
Each step includes:
- the agent's action,
- the environment observation,
- the reward signal.
- the agent's thinking.

Your task is to REWRITE one compact, **persistent memory** block that lets the
agent continue its work without seeing the full history. Merge useful facts from
the previous memory with new evidence. Do not append a second independent summary.

Please:
- Focus on:
  1) stable facts and rules about the environment/world,
  2) useful strategies / plans / tools the agent tried,
  3) important mistakes or failure patterns to avoid later,
  4) partial progress and remaining goals / TODOs.
- Use at most 8–10 lines.
- Use a neutral, factual tone.
- Do NOT repeat low-level JSON details unless they are crucial.
- Do NOT include meta text like "here is the summary" or any explanation.
- Output ONLY the memory lines, one per line.

===== PREVIOUS PERSISTENT MEMORY =====
{previous_text}
===== NEW COMPLETED TRANSITIONS =====
{records_text}
===== SUMMARY (start here) =====
""".strip()

        resp = await self.llm(summary_prompt)

        return resp

    def clear(self) -> None:
        """
        Clear all memories and summary.
        """
        self._records.clear()
        self._summary = None


TRUNCATION_MARKER = "\n...[truncated]...\n"


def _truncate_text(value: str, max_chars: int) -> str:
    if len(value) <= max_chars:
        return value
    if max_chars <= len(TRUNCATION_MARKER) + 2:
        return value[:max_chars]
    available = max_chars - len(TRUNCATION_MARKER)
    head = max(1, int(available * 0.6))
    tail = max(1, available - head)
    return value[:head] + TRUNCATION_MARKER + value[-tail:]


def _bounded_value(value: Any, max_chars: int) -> Any:
    if value is None:
        return None
    try:
        rendered = json.dumps(value, ensure_ascii=False, default=str)
    except Exception:
        rendered = str(value)
    if len(rendered) <= max_chars:
        return value
    return _truncate_text(rendered, max_chars)
