"""
aorchestra - Unified Orchestra framework

Supports GAIA, TerminalBench, and SWE-bench benchmarks.
"""
from aorchestra.subagents import ReActAgent, SWEBenchSubAgent
from aorchestra.sub_agent import OrchestraSubAgent  # Backward compatibility
from aorchestra.config import GAIAOrchestraConfig, TerminalBenchOrchestraConfig, SWEBenchOrchestraConfig

__all__ = [
    # SubAgents
    "ReActAgent",
    "SWEBenchSubAgent",
    "OrchestraSubAgent",  # Backward compatibility alias
    # Configs
    "GAIAOrchestraConfig",
    "TerminalBenchOrchestraConfig",
    "SWEBenchOrchestraConfig",
]
