"""
SWOT Agent v7 - Anthropic Claude Client
========================================
Direct Anthropic SDK provider for Claude models.
"""
import os
import logging
from typing import Optional

from app.agents.swot.llm.base import LLMClient, LLMClientError
from app.agents.swot.config import DEFAULT_ANTHROPIC_MODEL


logger = logging.getLogger("swot_agent_v7")

# Optional import guard
try:
    import anthropic
    _HAS_ANTHROPIC = True
except ImportError:
    anthropic = None
    _HAS_ANTHROPIC = False


class AnthropicClaudeClient(LLMClient):
    """Anthropic Claude provider (direct SDK)."""
    
    provider_name = "anthropic"
    
    def __init__(self, model: Optional[str] = None, api_key: Optional[str] = None):
        if not _HAS_ANTHROPIC:
            raise LLMClientError(
                "anthropic SDK not installed. Install: pip install anthropic"
            )
        
        self.model = model or DEFAULT_ANTHROPIC_MODEL
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        
        if not self.api_key:
            raise LLMClientError(
                "ANTHROPIC_API_KEY not set. Set in environment or pass api_key=..."
            )
        
        try:
            self.client = anthropic.Anthropic(api_key=self.api_key)
        except Exception as exc:
            raise LLMClientError(f"Failed to initialize Anthropic client: {exc}")
        
        logger.info(f"[Anthropic] Initialized: model={self.model}")
    
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Generate response from Claude."""
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
                temperature=0.4,
            )
            
            # Extract text from content blocks
            if response.content and len(response.content) > 0:
                return response.content[0].text or ""
            return ""
        except Exception as exc:
            raise LLMClientError(f"Anthropic generation failed: {exc}")