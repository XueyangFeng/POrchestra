"""Common utility functions"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List


def _repair_invalid_json_escapes(text: str) -> str:
    """Remove backslashes before characters that JSON cannot escape."""
    text = re.sub(r"\\u(?![0-9a-fA-F]{4})", "u", text)
    return re.sub(r"\\(?![\"\\/bfnrtu])", "", text)


def _escape_unescaped_inner_quotes(text: str) -> str:
    """Escape quote characters that are likely inside JSON string values."""
    out: List[str] = []
    in_string = False
    escape = False
    length = len(text)

    for i, ch in enumerate(text):
        if escape:
            out.append(ch)
            escape = False
            continue
        if ch == "\\":
            out.append(ch)
            escape = True
            continue
        if ch == '"':
            if not in_string:
                in_string = True
                out.append(ch)
                continue

            j = i + 1
            next_nonspace = None
            while j < length and text[j].isspace():
                j += 1
            if j < length:
                next_nonspace = text[j]

            if next_nonspace in (":", ",", "}", "]", None):
                in_string = False
                out.append(ch)
            else:
                out.append('\\"')
            continue

        out.append(ch)

    return "".join(out)


def _loads_json_with_repairs(text: str) -> tuple[Dict[str, Any] | None, str | None]:
    candidates = [text]
    repaired = _repair_invalid_json_escapes(text)
    if repaired != text:
        candidates.append(repaired)

    for cand in list(candidates):
        escaped = _escape_unescaped_inner_quotes(cand)
        if escaped != cand:
            candidates.append(escaped)

    errors: List[str] = []
    seen = set()
    for cand in candidates:
        if cand in seen:
            continue
        seen.add(cand)
        try:
            parsed = json.loads(cand)
        except json.JSONDecodeError as e:
            errors.append(f"{type(e).__name__}: {e}")
            continue
        if isinstance(parsed, dict):
            return parsed, None
        errors.append(f"Expected dict, got {type(parsed).__name__}")

    return None, "; ".join(errors)


def parse_json_response(resp: str) -> Dict[str, Any]:
    """Parse JSON response that may contain markdown code blocks
    
    Args:
        resp: LLM response string, possibly wrapped in ```json
        
    Returns:
        Parsed dict
    """
    s = resp.strip()
    if "```" in s:
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", s, re.DOTALL)
        if match:
            s = match.group(1)
    else:
        start = s.find("{")
        end = s.rfind("}")
        if start != -1 and end != -1 and end > start:
            s = s[start : end + 1]
    parsed, error = _loads_json_with_repairs(s)
    if parsed is not None:
        return parsed

    return {"action": "Invalid", "params": {}, "_parse_error": error or "json_parse_failed"}


def indent_text(text: str, indent: str = "   ") -> str:
    """Add indentation to each line of text
    
    Args:
        text: Original text
        indent: Indentation string
        
    Returns:
        Indented text
    """
    return "\n".join(indent + line for line in text.strip().split("\n"))


def format_tools_description(tools: List[Any], verbose: bool = False) -> str:
    """Generate tool description text for prompt usage
    
    Args:
        tools: List of tools, each tool needs name, description, parameters attributes
        verbose: Whether to use verbose format
        
    Returns:
        Formatted tool description string
    """
    if not tools:
        return "No tools available."
    
    if verbose:
        descriptions = []
        for tool in tools:
            desc = f"""Tool Name: {tool.name}
Description: {tool.description}
Parameters: {json.dumps(tool.parameters, indent=2)}"""
            descriptions.append(desc)
        return "\n\n".join(descriptions)
    else:
        return "\n\n".join([
            f"{t.name}: {t.description}\nParams: {json.dumps(t.parameters, indent=2)}"
            for t in tools
        ])
