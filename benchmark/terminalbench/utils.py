"""Utility functions for Terminal Bench."""
from pathlib import Path


def resolve_path(path_str: str | None, config_path: Path, project_root: Path) -> Path | None:
    """Resolve path relative to config file or project root."""
    if not path_str:
        return None
    path = Path(path_str)
    if path.is_absolute():
        return path
    # Try relative to config file first
    relative_to_config = config_path.parent / path
    if relative_to_config.exists():
        return relative_to_config
    # Try relative to project root
    relative_to_root = project_root / path
    if relative_to_root.exists():
        return relative_to_root
    # Return relative to project root even if doesn't exist yet
    return relative_to_root

