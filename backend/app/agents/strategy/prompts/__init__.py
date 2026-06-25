"""
Strategy Agent v1 - Prompts Package
====================================
LLM communication layer - system + user prompts.
"""
from app.agents.strategy.prompts.system import STRATEGY_SYSTEM_PROMPT
from app.agents.strategy.prompts.user import build_strategy_user_prompt

__all__ = [
    "STRATEGY_SYSTEM_PROMPT",
    "build_strategy_user_prompt",
]