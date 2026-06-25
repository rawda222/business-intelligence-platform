"""
SWOT Agent v7 - OpenAI GPT Client
==================================
OpenAI GPT provider.
"""
import os
import logging
from typing import Optional

from app.agents.swot.llm.base import LLMClient, LLMClientError
from app.agents.swot.config import DEFAULT_OPENAI_MODEL


logger = logging.getLogger("swot_agent_v7")

# Optional import guard
try:
    import openai
    _HAS_OPENAI = True
except ImportError:
    openai = None
    _HAS_OPENAI = False


class OpenAIGPTClient(LLMClient):
    """OpenAI GPT provider."""
    
    provider_name = "openai"
    
    def __init__(self, model: Optional[str] = None, api_key: Optional[str] = None):
        if not _HAS_OPENAI:
            raise LLMClientError(
                "openai SDK not installed. Install: pip install openai"
            )
        
        self.model = model or DEFAULT_OPENAI_MODEL
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        
        if not self.api_key:
            raise LLMClientError(
                "OPENAI_API_KEY not set. Set in environment or pass api_key=..."
            )
        
        try:
            self.client = openai.OpenAI(api_key=self.api_key)
        except Exception as exc:
            raise LLMClientError(f"Failed to initialize OpenAI client: {exc}")
        
        logger.info(f"[OpenAI] Initialized: model={self.model}")
    
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Generate response from GPT."""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.4,
                response_format={"type": "json_object"},
            )
            
            if response.choices and len(response.choices) > 0:
                return response.choices[0].message.content or ""
            return ""
        except Exception as exc:
            raise LLMClientError(f"OpenAI generation failed: {exc}")