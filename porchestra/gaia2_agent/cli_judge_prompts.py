"""Patch ARE's GAIA2 judge prompts to use gaia2-cli prompt templates.

ARE and gaia2-cli define checker prompts with the same names, but the prompt
text is not identical. This hook lets POrchestra run ARE rollouts while using
the gaia2-cli judge prompt wording for soft LLM checkers.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any


_TEMPLATE_NAMES = (
    "CONTENT_CHECKER_PROMPT_TEMPLATES",
    "SANITY_CHECKER_PROMPT_TEMPLATES",
    "SIGNATURE_CHECKER_TEMPLATES",
    "CAB_CHECKER_PROMPT_TEMPLATES",
    "SUBTASK_EXTRACTOR_PROMPT_TEMPLATES",
    "USER_MESSAGE_SUBTASK_EXTRACTOR_PROMPT_TEMPLATES",
    "EVENT_SUBTASK_EXTRACTOR_PROMPT_TEMPLATES",
    "EMAIL_CHECKER_PROMPT_TEMPLATES",
    "EVENT_CHECKER_PROMPT_TEMPLATES",
    "MESSAGE_CHECKER_PROMPT_TEMPLATES",
    "USER_MESSAGE_CHECKER_PROMPT_TEMPLATES",
    "TONE_CHECKER_PROMPT_TEMPLATES",
)


def patch_cli_judge_prompts() -> None:
    """Replace ARE soft-judge prompt templates with gaia2-cli templates.

    The patch is enabled only when ``PORCHESTRA_GAIA2_CLI_JUDGE_PROMPTS`` is
    truthy. It updates both the public ARE prompt module and the already-bound
    defaults used by ``validation.utils.llm_utils``.
    """

    if not _truthy(os.environ.get("PORCHESTRA_GAIA2_CLI_JUDGE_PROMPTS")):
        return

    from are.simulation.validation import prompts as are_prompts
    from are.simulation.validation.utils import llm_utils
    from porchestra.judge_marker_parser import patch_judge_marker_parser

    if getattr(llm_utils, "_porchestra_cli_judge_prompts_patched", False):
        return

    patch_judge_marker_parser()
    cli_prompts = _load_cli_prompts()

    for name in _TEMPLATE_NAMES:
        if hasattr(cli_prompts, name):
            value = getattr(cli_prompts, name)
            setattr(are_prompts, name, value)
            setattr(llm_utils, name, value)

    original_build_llm_checkers = llm_utils.build_llm_checkers
    original_build_subtask_extractor = llm_utils.build_subtask_extractor
    _patch_llm_function_renderer(llm_utils)

    def build_llm_checkers(engine: Any, **kwargs: Any) -> dict[str, Any]:
        values = {name: getattr(cli_prompts, name) for name in _TEMPLATE_NAMES if hasattr(cli_prompts, name)}
        return original_build_llm_checkers(
            engine=engine,
            content_checker_prompt_templates=kwargs.get(
                "content_checker_prompt_templates",
                values["CONTENT_CHECKER_PROMPT_TEMPLATES"],
            ),
            signature_checker_prompt_templates=kwargs.get(
                "signature_checker_prompt_templates",
                values["SIGNATURE_CHECKER_TEMPLATES"],
            ),
            sanity_checker_prompt_templates=kwargs.get(
                "sanity_checker_prompt_templates",
                values["SANITY_CHECKER_PROMPT_TEMPLATES"],
            ),
            cab_checker_prompt_templates=kwargs.get(
                "cab_checker_prompt_templates",
                values["CAB_CHECKER_PROMPT_TEMPLATES"],
            ),
            email_checker_prompt_templates=kwargs.get(
                "email_checker_prompt_templates",
                values["EMAIL_CHECKER_PROMPT_TEMPLATES"],
            ),
            message_checker_prompt_templates=kwargs.get(
                "message_checker_prompt_templates",
                values["MESSAGE_CHECKER_PROMPT_TEMPLATES"],
            ),
            user_message_checker_prompt_templates=kwargs.get(
                "user_message_checker_prompt_templates",
                values["USER_MESSAGE_CHECKER_PROMPT_TEMPLATES"],
            ),
            event_checker_prompt_templates=kwargs.get(
                "event_checker_prompt_templates",
                values["EVENT_CHECKER_PROMPT_TEMPLATES"],
            ),
            tone_checker_prompt_templates=kwargs.get(
                "tone_checker_prompt_templates",
                values["TONE_CHECKER_PROMPT_TEMPLATES"],
            ),
            num_votes=kwargs.get("num_votes", 1),
        )

    def build_subtask_extractor(engine: Any, tool_name: str) -> Any:
        # The original function reads module globals, which were replaced above.
        return original_build_subtask_extractor(engine, tool_name)

    llm_utils.build_llm_checkers = build_llm_checkers
    llm_utils.build_subtask_extractor = build_subtask_extractor
    _patch_tool_judge_imports(build_llm_checkers, build_subtask_extractor)
    llm_utils._porchestra_cli_judge_prompts_patched = True


def _load_cli_prompts() -> Any:
    _ensure_gaia2_cli_core_on_path()
    from gaia2_core.judge import prompts as cli_prompts

    return cli_prompts


def _ensure_gaia2_cli_core_on_path() -> None:
    candidates: list[Path] = []
    if raw := os.environ.get("PORCHESTRA_GAIA2_CLI_CORE"):
        candidates.append(Path(raw))

    try:
        import are

        are_root = Path(are.__file__).resolve().parents[1]
        candidates.append(are_root / "gaia2-cli" / "core")
    except Exception:
        pass

    candidates.append(Path("/data0/fengxueyang/gaia2/meta-agents-research-environments/gaia2-cli/core"))

    for path in candidates:
        if (path / "gaia2_core" / "judge" / "prompts.py").exists():
            text = str(path)
            if text not in sys.path:
                sys.path.insert(0, text)
            return

    searched = ", ".join(str(path) for path in candidates)
    raise ImportError(f"Could not locate gaia2-cli core prompts.py. Searched: {searched}")


def _patch_llm_function_renderer(llm_utils: Any) -> None:
    """Use gaia2-cli style template rendering for checker prompts.

    gaia2-cli uses plain Jinja rendering, where missing variables become empty
    strings. ARE's renderer validates that every ``{{var}}`` is provided, which
    makes a few gaia2-cli examples fail during checker construction.
    """

    if getattr(llm_utils.LLMFunction, "_porchestra_cli_renderer_patched", False):
        return

    def llm_function_init(self: Any, engine: Any, prompt_templates: Any) -> None:
        self.engine = engine
        self.prompt_templates = prompt_templates
        system_prompt_args = prompt_templates.system_prompt_args or {}
        self.system_prompt = _render_template(
            prompt_templates.system_prompt_template,
            **system_prompt_args,
        )
        self.user_prompt_template = prompt_templates.user_prompt_template
        self.examples = []
        if prompt_templates.assistant_prompt_template and prompt_templates.examples:
            for example in prompt_templates.examples:
                self.examples.extend(
                    [
                        {
                            "role": "user",
                            "content": _render_template(
                                self.user_prompt_template,
                                **example["input"],
                            ),
                        },
                        {
                            "role": "assistant",
                            "content": _render_template(
                                prompt_templates.assistant_prompt_template,
                                **example["output"],
                            ),
                        },
                    ]
                )

    def llm_function_call(self: Any, user_prompt_args: dict[str, str]) -> str | None:
        messages = [{"role": "system", "content": self.system_prompt}]
        messages.extend(self.examples)
        messages.append(
            {
                "role": "user",
                "content": _render_template(self.user_prompt_template, **user_prompt_args),
            }
        )
        response, _ = self.engine(messages, additional_trace_tags=["judge_llm"])
        return response

    llm_utils.LLMFunction.__init__ = llm_function_init
    llm_utils.LLMFunction.__call__ = llm_function_call
    llm_utils.LLMFunction._porchestra_cli_renderer_patched = True


def _patch_tool_judge_imports(build_llm_checkers: Any, build_subtask_extractor: Any) -> None:
    """Patch names imported directly into ARE's tool_judge module.

    ``tool_judge.py`` imports these builders with ``from ... import ...`` at
    module import time. If it was imported before this hook runs, updating only
    ``llm_utils`` is not enough.
    """

    try:
        from are.simulation.validation import tool_judge

        tool_judge.build_llm_checkers = build_llm_checkers
        tool_judge.build_subtask_extractor = build_subtask_extractor
    except Exception:
        return


def _render_template(template: str, **kwargs: Any) -> str:
    try:
        from jinja2 import Template

        return Template(template, keep_trailing_newline=True).render(**kwargs)
    except Exception:
        result = template
        for key, value in kwargs.items():
            result = result.replace("{{" + key + "}}", str(value))
        return result


def _truthy(value: str | None) -> bool:
    return value is not None and value.strip().lower() not in {"", "0", "false", "no", "off"}
