"""Optional ablation of ARE metadata injected only into the default React agent."""

from __future__ import annotations

import logging
import os


ENV_NAME = "PORCHESTRA_GAIA2_REACT_ABLATE_SYSTEM_INFO"


def _enabled() -> bool:
    return os.environ.get(ENV_NAME, "").strip().lower() in {"1", "true", "yes", "on"}


def _strip_extra_system_info(system_prompt: str) -> str:
    """Remove ARE placeholders for metadata not supplied to POrchestra."""
    for placeholder in (
        "<<notification_system_description>>",
        "<<agent_reminder_description>>",
        "<<curent_time_description>>",
    ):
        system_prompt = system_prompt.replace(placeholder, "")
    return system_prompt


def patch_react_system_info_ablation() -> None:
    """Gate the default React system-information ablation behind an environment flag."""
    from are.simulation.agents.default_agent.are_simulation_main import ARESimulationAgent

    if getattr(ARESimulationAgent, "_porchestra_system_ablation_patched", False):
        return

    original_init_system_prompt = ARESimulationAgent.init_system_prompt

    def init_system_prompt(self, scenario):
        if not _enabled():
            return original_init_system_prompt(self, scenario)

        logging.getLogger(__name__).info(
            "React system-info ablation enabled: omitting scenario additional prompt, "
            "notification policy, and current-date injection"
        )
        prompt = self.react_agent.init_system_prompts["system_prompt"]
        self.react_agent.init_system_prompts["system_prompt"] = _strip_extra_system_info(
            str(prompt)
        )

    ARESimulationAgent.init_system_prompt = init_system_prompt
    ARESimulationAgent._porchestra_system_ablation_patched = True

