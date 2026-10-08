"""Remove one SAE information channel from MainAgent-visible records.

Apply after SAE repair/validation. Raw SubAgent traces and prompts are kept
intact; this projection must be shared by working memory and follow-up memory.
"""

from __future__ import annotations

from copy import deepcopy
import os
from typing import Any


SAE_ABLATION_FIELDS = {
    "state": frozenset({"state"}),
    "request": frozenset({"request", "reason", "task_scope", "resource"}),
    # Follow-up memory uses summary/raw; working memory uses evidence/evidence_raw.
    "evidence": frozenset({"evidence", "evidence_raw", "summary", "raw"}),
}


def validate_sae_ablation(mode: str) -> str:
    if mode and mode not in SAE_ABLATION_FIELDS:
        raise ValueError(f"Invalid PORCHESTRA_SAE_ABLATION={mode!r}")
    return mode


def configured_sae_ablation() -> str:
    return validate_sae_ablation(os.getenv("PORCHESTRA_SAE_ABLATION", "").strip().lower())


def main_visible_sae_record(record: dict[str, Any], mode: str) -> dict[str, Any]:
    """Project a flattened SAE record without touching the producer's payload."""
    validate_sae_ablation(mode)
    removed = SAE_ABLATION_FIELDS.get(mode, frozenset())
    return {key: deepcopy(value) for key, value in record.items() if key not in removed}
