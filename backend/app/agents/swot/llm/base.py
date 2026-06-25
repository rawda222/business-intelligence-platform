"""
SWOT Agent v7 - LLM Base Client
===============================
Abstract base class for all LLM providers.
"""
from abc import ABC, abstractmethod


class LLMClientError(Exception):
    """Raised when an LLM call fails."""


class LLMClient(ABC):
    """Abstract base class for LLM providers."""
    
    provider_name: str = "base"

    @abstractmethod
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """
        Generate response from LLM.
        
        Returns:
            Raw text output (expected JSON string)
        """
        pass
