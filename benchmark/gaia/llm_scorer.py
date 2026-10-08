"""
LLM-based semantic similarity scorer for GAIA/TaskCraft.

Uses LLM to judge if two answers are semantically equivalent,
handling format differences like "January 2018" vs "2018-01".
"""

from __future__ import annotations

import asyncio
import os
from typing import Optional, Tuple

from openai import AsyncOpenAI

from base.engine.async_llm import LLMsConfig, build_openai_client_kwargs
from base.engine.logs import logger


# Default model for semantic scoring
DEFAULT_JUDGE_MODEL = "deepseek-chat"

# Prompt for semantic similarity judgment
JUDGE_PROMPT = """You are a precise answer evaluator. Determine if the predicted answer is semantically equivalent to the expected answer.

IMPORTANT RULES:
1. Focus on SEMANTIC MEANING, not exact string match
2. "January 2018" and "2018-01" are EQUIVALENT (same date)
3. "$500 billion" and "500 billion dollars" are EQUIVALENT
4. "90%" and "90 percent" are EQUIVALENT
5. "nearly 90%" and "90%" are EQUIVALENT (approximate match is OK)
6. Numbers must match: "50" and "500" are NOT equivalent
7. If the predicted answer contains the expected answer as a substring with correct context, it's EQUIVALENT

Expected Answer: {expected}
Predicted Answer: {predicted}

Respond with ONLY one word: "EQUIVALENT" or "DIFFERENT"
"""


def _get_llm_config(model_name: Optional[str] = None) -> Tuple[str, str, str]:
    """Get LLM configuration from model config or environment variables."""
    model_name = model_name or DEFAULT_JUDGE_MODEL
    
    # Try to get config from LLMsConfig
    try:
        llms_config = LLMsConfig.default()
        model_config = llms_config.get(model_name)
        if model_config:
            return (
                model_config.key,
                model_config.base_url,
                model_config.model,
            )
    except Exception:
        pass
    
    # Fallback to environment variables
    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL") or os.getenv("LLM_API_BASE") or "https://api.openai.com/v1"
    
    return (api_key, base_url, model_name)


async def llm_semantic_score(
    predicted: str,
    expected: str,
    model: Optional[str] = None,
) -> float:
    """
    Use LLM to judge semantic equivalence between predicted and expected answers.
    
    Args:
        predicted: The model's predicted answer
        expected: The expected correct answer
        model: Optional model name to use for judging
        
    Returns:
        1.0 if semantically equivalent, 0.0 otherwise
    """
    if not predicted or not expected:
        return 0.0
    
    # Quick check: exact match (normalized)
    if predicted.strip().lower() == expected.strip().lower():
        return 1.0
    
    api_key, base_url, model_name = _get_llm_config(model)
    
    if not api_key:
        logger.warning("[LLM Scorer] No API key available, falling back to 0.0")
        return 0.0
    
    client = AsyncOpenAI(**build_openai_client_kwargs(api_key=api_key, base_url=base_url))
    
    prompt = JUDGE_PROMPT.format(expected=expected, predicted=predicted)
    
    try:
        completion = await client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=10,
        )
        
        response = completion.choices[0].message.content.strip().upper()
        
        if "EQUIVALENT" in response:
            logger.info(f"[LLM Scorer] EQUIVALENT: '{predicted}' ≈ '{expected}'")
            return 1.0
        else:
            logger.info(f"[LLM Scorer] DIFFERENT: '{predicted}' ≠ '{expected}'")
            return 0.0
            
    except Exception as e:
        logger.error(f"[LLM Scorer] Error: {e}")
        return 0.0


def llm_semantic_score_sync(
    predicted: str,
    expected: str,
    model: Optional[str] = None,
) -> float:
    """Synchronous wrapper for llm_semantic_score."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If we're in an async context, create a new task
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run,
                    llm_semantic_score(predicted, expected, model)
                )
                return future.result(timeout=30)
        else:
            return loop.run_until_complete(
                llm_semantic_score(predicted, expected, model)
            )
    except Exception as e:
        logger.error(f"[LLM Scorer Sync] Error: {e}")
        return 0.0
