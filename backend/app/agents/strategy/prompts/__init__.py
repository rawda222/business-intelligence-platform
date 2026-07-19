"""
Strategy Agent v1 - Prompts Package
====================================
LLM communication layer - system + user prompts.
"""
from app.agents.strategy.prompts.system import (
    STRATEGY_SYSTEM_PROMPT as BASE_STRATEGY_SYSTEM_PROMPT,
)
from app.agents.strategy.prompts.brand_foundation import (
    BRAND_FOUNDATION_PROMPT_RULES,
)
from app.agents.strategy.prompts.user import build_strategy_user_prompt

STRATEGY_SYSTEM_PROMPT = (
    f"{BASE_STRATEGY_SYSTEM_PROMPT}\n\n"
    f"{BRAND_FOUNDATION_PROMPT_RULES}"
)

__all__ = [
    "BASE_STRATEGY_SYSTEM_PROMPT",
    "BRAND_FOUNDATION_PROMPT_RULES",
    "STRATEGY_SYSTEM_PROMPT",
    "build_strategy_user_prompt",
]