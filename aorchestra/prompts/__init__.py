"""Prompts for different benchmarks."""
from aorchestra.prompts.gaia import GAIAMainAgentPrompt
from aorchestra.prompts.terminalbench import TerminalBenchPrompt
from aorchestra.prompts.swebench import SWEBenchMainAgentPrompt

__all__ = ["GAIAMainAgentPrompt", "TerminalBenchPrompt", "SWEBenchMainAgentPrompt"]
