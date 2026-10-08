"""GAIA benchmark adapter for Orchestra-o1 inference-only reproduction."""
from __future__ import annotations

from typing import List

from base.agent.base_action import BaseAction
from benchmark.aorchestra_bench_gaia import GAIAOrchestraBenchmark, GAIAOrchestraEnvironment
from benchmark.benchmark import LevelSpec
from benchmark.bench_gaia import GAIAConfig
from benchmark.common.env import BasicInfo


class OrchestraO1GAIAEnvironment(GAIAOrchestraEnvironment):
    """GAIA environment with SubAgent finish support and clone().

    Orchestra-o1's parallel delegate tool expects each SubAgent to receive an
    independent environment clone. GAIA tasks are read-mostly here, so cloning
    the task metadata and reusing stateless tool objects is sufficient.
    """

    def __init__(self, level: LevelSpec, config: GAIAConfig, tools: List[BaseAction]):
        super().__init__(level, config, tools)
        self.instruction = self._build_instruction()

    def get_basic_info(self) -> BasicInfo:
        info = super().get_basic_info()
        instruction = getattr(self, "instruction", None) or info.instruction
        return BasicInfo(
            env_id=info.env_id,
            instruction=instruction,
            action_space=info.action_space,
            max_steps=info.max_steps,
            meta_data=info.meta_data,
        )

    def clone(self) -> "OrchestraO1GAIAEnvironment":
        cloned = type(self)(self.level_data, self.config, list(self.tools.values()))
        cloned.instruction = getattr(self, "instruction", self._build_instruction())
        return cloned


class OrchestraO1GAIABenchmark(GAIAOrchestraBenchmark):
    """Factory for Orchestra-o1 GAIA environments."""

    def make_env(self, level: LevelSpec, tools: List[BaseAction] | None = None) -> OrchestraO1GAIAEnvironment:
        return OrchestraO1GAIAEnvironment(level, self.config, tools if tools is not None else self.tools)
