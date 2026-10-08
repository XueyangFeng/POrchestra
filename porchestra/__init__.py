"""POrchestra package."""

__all__ = ["MainAgent", "ReActSubAgent"]


def __getattr__(name):
    if name == "MainAgent":
        from porchestra.main_agent import MainAgent

        return MainAgent
    if name == "ReActSubAgent":
        from porchestra.subagent import ReActSubAgent

        return ReActSubAgent
    raise AttributeError(name)
