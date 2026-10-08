"""GAIA benchmark scoring utilities.

Provides scoring functions for comparing model answers against ground truth.
"""

from __future__ import annotations

import os
import re
import string
from typing import Any, Tuple


def normalize_number_str(number_str: str) -> float:
    """Normalize a number string by removing common formatting characters."""
    s = str(number_str or "")
    for ch in ["$", "%", ","]:
        s = s.replace(ch, "")
    try:
        return float(s)
    except Exception:
        return float("inf")


def normalize_str(input_str: str, remove_punct: bool = True) -> str:
    """Normalize a string by removing whitespace and optionally punctuation."""
    s = re.sub(r"\s", "", str(input_str or ""))
    if remove_punct:
        table = str.maketrans("", "", string.punctuation)
        return s.lower().translate(table)
    return s.lower()


def split_string(s: str, char_list: list[str] | None = None) -> list[str]:
    """Split a string by multiple delimiters."""
    chars = char_list or [",", ";"]
    pattern = f"[{''.join(chars)}]"
    return re.split(pattern, str(s or ""))


def question_scorer(model_answer: str | None, ground_truth: str | None) -> float:
    """
    Score model answer against ground truth.
    
    Handles:
    - Numeric comparisons
    - List comparisons (comma/semicolon separated)
    - String comparisons (normalized)
    
    Args:
        model_answer: The model's predicted answer
        ground_truth: The expected correct answer
        
    Returns:
        1.0 if correct, 0.0 if incorrect
    """
    def is_float(elem: Any) -> bool:
        try:
            float(elem)
            return True
        except Exception:
            return False

    ma = "None" if model_answer is None else str(model_answer)
    gt = "" if ground_truth is None else str(ground_truth)

    # numeric comparison
    if is_float(gt):
        return 1.0 if normalize_number_str(ma) == float(gt) else 0.0
    
    # list-like comparison
    if any(ch in gt for ch in [",", ";"]):
        gt_elems = split_string(gt)
        ma_elems = split_string(ma)
        if len(gt_elems) != len(ma_elems):
            return 0.0
        cmp_list: list[bool] = []
        for a, b in zip(ma_elems, gt_elems):
            if is_float(b):
                cmp_list.append(normalize_number_str(a) == float(b))
            else:
                cmp_list.append(
                    normalize_str(a, remove_punct=False)
                    == normalize_str(b, remove_punct=False)
                )
        return 1.0 if all(cmp_list) else 0.0
    
    # string comparison
    return 1.0 if normalize_str(ma) == normalize_str(gt) else 0.0


def extract_pred_text(prediction: Any) -> str:
    """
    Extract prediction text from various formats.
    
    Handles:
    - None -> ""
    - dict with keys: final_answer, output, result, text
    - str -> str
    - other -> str(other)
    
    Args:
        prediction: The model's prediction in various formats
        
    Returns:
        Extracted text string
    """
    if prediction is None:
        return ""
    if isinstance(prediction, dict):
        # Try common keys in order of preference
        for key in ("final_answer", "answer", "output", "result", "text"):
            if key in prediction and prediction.get(key) is not None:
                return str(prediction.get(key))
        # If has success=False, return empty
        if "success" in prediction and not prediction.get("success"):
            return ""
        return str(prediction)
    return str(prediction)


def calculate_score(expected_output: Any, prediction: Any) -> Tuple[float, str]:
    """
    Calculate score with prediction extraction.
    
    Args:
        expected_output: The expected correct answer
        prediction: The model's prediction (can be dict, str, or None)
        
    Returns:
        Tuple of (score, extracted_text)
    """
    pred_text = extract_pred_text(prediction)
    if expected_output is None:
        return (1.0 if pred_text else 0.0, pred_text)
    score = question_scorer(pred_text, str(expected_output))
    return (score, pred_text)


def resolve_gaia_attachment_path(file_name: str, file_root: str | None = None) -> str:
    """
    Resolve GAIA attachment file path.
    
    Args:
        file_name: The attachment file name
        file_root: Optional root directory for attachments
        
    Returns:
        Resolved file path
    """
    if not file_name:
        return ""

    # If it's already an absolute path, keep it
    if os.path.isabs(file_name):
        return file_name

    # If caller supplied a root, use it
    if file_root:
        root = str(file_root).rstrip("/\\")
        return os.path.join(root, file_name)

    # Default GAIA validation attachment root
    default_root = os.path.join("benchmark", "gaia", "data", "Gaia", "2023", "validation")
    return os.path.join(default_root, file_name)


def preprocess_file(task: str, file_name: str | None, file_root: str | None = None) -> str:
    """
    Preprocess task description with file attachment hint.
    
    Args:
        task: The task description
        file_name: Optional attachment file name
        file_root: Optional root directory for attachments
        
    Returns:
        Task description with file hint appended if file_name is provided
    """
    if not file_name:
        return task
    hint_path = resolve_gaia_attachment_path(file_name, file_root=file_root)
    return (
        f"{task}\n"
        f"(* LOCAL FILES attached: {hint_path} - "
        f"Use ImageAnalysisAction for images, ParseAudioAction for audio, "
        f"ExecuteCodeAction for other files like txt/csv/xlsx/json/pdb)"
    )

