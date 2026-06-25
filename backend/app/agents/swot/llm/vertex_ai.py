"""
SWOT Agent v7 - Vertex AI Gemini Client
=========================================
Google Vertex AI Gemini provider using google-genai SDK.
"""
import os
import logging
from typing import Optional

from app.agents.swot.llm.base import LLMClient, LLMClientError
from app.agents.swot.config import DEFAULT_VERTEX_MODEL


logger = logging.getLogger("swot_agent_v7")

# Optional import guard
try:
    from google import genai as google_genai
    from google.genai import types as genai_types
    _HAS_VERTEX = True
except ImportError:
    google_genai = None
    genai_types = None
    _HAS_VERTEX = False


class VertexAIGeminiClient(LLMClient):
    """Vertex AI Gemini provider (google-genai SDK in vertexai mode)."""
    
    provider_name = "vertex_ai"
    
    def __init__(self, model: Optional[str] = None, project: Optional[str] = None, location: Optional[str] = None):
        if not _HAS_VERTEX:
            raise LLMClientError(
                "google-genai not installed. Install: pip install google-genai"
            )
        
        self.model = model or DEFAULT_VERTEX_MODEL
        self.project = project or os.environ.get("GOOGLE_CLOUD_PROJECT")
        self.location = location or os.environ.get("VERTEX_AI_LOCATION", "us-central1")
        
        if not self.project:
            raise LLMClientError(
                "GOOGLE_CLOUD_PROJECT not set. Set in environment or pass project=..."
            )
        
        try:
            self.client = google_genai.Client(
                vertexai=True,
                project=self.project,
                location=self.location,
            )
        except Exception as exc:
            raise LLMClientError(f"Failed to initialize Vertex AI client: {exc}")
        
        logger.info(
            f"[VertexAI] Initialized: project={self.project}, "
            f"location={self.location}, model={self.model}"
        )
    
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """
        Generate response from Gemini.
        
        Returns:
            Raw text output (JSON expected)
        """
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=user_prompt,
                config=genai_types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=0.4,
                    response_mime_type="application/json",
                ),
            )
            return response.text or ""
        except Exception as exc:
            raise LLMClientError(f"Vertex AI generation failed: {exc}")