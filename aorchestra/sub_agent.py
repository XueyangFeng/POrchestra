"""
Backward compatible import proxy

OrchestraSubAgent has been moved to aorchestra.subagents.react_agent.ReActAgent
This file maintains backward compatibility.
"""
from aorchestra.subagents.react_agent import ReActAgent

# Backward compatibility alias
OrchestraSubAgent = ReActAgent

__all__ = ["OrchestraSubAgent", "ReActAgent"]
