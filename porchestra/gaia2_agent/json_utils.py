"""Small JSON helpers for LLM outputs."""

from __future__ import annotations

import json
import re
from typing import Any


def parse_first_json_object(text: str) -> dict[str, Any]:
    cleaned = text.replace("```json", "").replace("```", "")
    decoder = json.JSONDecoder(strict=False)
    for match in re.finditer(r"{", cleaned):
        try:
            value, _ = decoder.raw_decode(cleaned[match.start() :])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    return {}
