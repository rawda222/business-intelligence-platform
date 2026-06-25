"""
SWOT Agent v7 - Groq Client
============================
Groq provider (free-tier safety net).
"""
import os
import logging
from typing import Optional

from app.agents.swot.llm.base import LLMClient, LLMClientError
from app.agents.swot.config import DEFAULT_GROQ_MODEL


logger = logging.getLogger("swot_agent_v7")

# Optional import guard
try:
    import groq
    _HAS_GROQ = True
except ImportError:
    groq = None
    _HAS_GROQ = False


class GroqClient(LLMClient):
    """Groq (free-tier safety net) provider."""
    
    provider_name = "groq"
    
    def __init__(self, model: Optional[str] = None, api_key: Optional[str] = None):
        if not _HAS_GROQ:
            raise LLMClientError(
                "groq SDK not installed. Install: pip install groq"
            )
        
        self.model = model or DEFAULT_GROQ_MODEL
        self.api_key = api_key or os.environ.get("GROQ_API_KEY")
        
        if not self.api_key:
            raise LLMClientError(
                "GROQ_API_KEY not set. Set in environment or pass api_key=..."
            )
        
        try:
            self.client = groq.Groq(api_key=self.api_key)
        except Exception as exc:
            raise LLMClientError(f"Failed to initialize Groq client: {exc}")
        
        logger.info(f"[Groq] Initialized: model={self.model}")
    
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Generate response from Groq."""
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
            raise LLMClientError(f"Groq generation failed: {exc}")