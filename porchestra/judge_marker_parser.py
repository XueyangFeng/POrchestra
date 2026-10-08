"""Robust parsing for GAIA2 soft judge markers."""

from __future__ import annotations


def patch_judge_marker_parser() -> None:
    """Make ARE soft judge marker parsing case-insensitive."""

    from are.simulation.validation.utils import llm_utils

    if getattr(llm_utils, "_porchestra_marker_parser_patched", False):
        return

    def llm_checker_call(self, user_prompt_args: dict[str, str]) -> bool | None:
        votes = []
        for _ in range(self.num_votes):
            response = self.judge(user_prompt_args)
            if response is None:
                continue
            lowered = response.lower()
            if self.success_str.lower() in lowered:
                votes.append(True)
            elif self.failure_str.lower() in lowered:
                votes.append(False)
        if not votes:
            return None
        return sum(votes) >= len(votes) / 2

    llm_utils.LLMChecker.__call__ = llm_checker_call
    llm_utils.LLMChecker._porchestra_marker_parser_call = llm_checker_call
    llm_utils._porchestra_marker_parser_patched = True
