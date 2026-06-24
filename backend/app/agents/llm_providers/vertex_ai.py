"""
Vertex AI / Gemini Provider
Wraps google-genai SDK for clean async usage.
"""
import asyncio
import json
from typing import Any

from google import genai
from google.genai import types

from app.core.config import settings


# ============================================================
# Gemini Client (singleton)
# ============================================================
class GeminiProvider:
    """
    Production-grade wrapper around Vertex AI Gemini.
    
    Usage:
        provider = GeminiProvider()
        response = await provider.generate("Hello")
        json_response = await provider.generate_json("...prompt...")
    """
    
    def __init__(self):
        self.client = genai.Client(
            vertexai=True,
            project=settings.GOOGLE_CLOUD_PROJECT,
            location=settings.VERTEX_AI_LOCATION,
        )
        self.model = settings.VERTEX_AI_MODEL
    
    # ========================================================
    # Generate Plain Text
    # ========================================================
    async def generate(
        self,
        prompt: str,
        system_instruction: str | None = None,
        temperature: float = 0.7,
        max_output_tokens: int = 8192,
    ) -> str:
        """
        Generate a plain text response.
        
        Args:
            prompt: User prompt
            system_instruction: Optional system message
            temperature: 0.0 (deterministic) to 1.0 (creative)
            max_output_tokens: Max response length
        
        Returns:
            Generated text
        """
        config = types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            system_instruction=system_instruction,
        )
        
        # Run sync call in executor (genai SDK doesn't support async natively yet)
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=config,
            ),
        )
        
        return response.text
    
    # ========================================================
    # Generate JSON Response (Structured)
    # ========================================================
    async def generate_json(
        self,
        prompt: str,
        system_instruction: str | None = None,
        temperature: float = 0.4,
        max_output_tokens: int = 8192,
    ) -> dict[str, Any]:
        """
        Generate a JSON response (parsed to dict).
        Forces Gemini to output valid JSON.
        
        Returns:
            Parsed JSON as dict
        """
        config = types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            system_instruction=system_instruction,
            response_mime_type="application/json",
        )
        
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=config,
            ),
        )
        
        # Parse JSON
        try:
            return json.loads(response.text)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"Gemini returned invalid JSON: {e}\nResponse: {response.text[:500]}"
            )
    
    # ========================================================
    # Health Check
    # ========================================================
    async def health_check(self) -> bool:
        """Quick test that Gemini responds."""
        try:
            response = await self.generate(
                "Say 'ok' if you can hear me.",
                max_output_tokens=10,
            )
            return "ok" in response.lower()
        except Exception:
            return False


# ============================================================
# Singleton instance
# ============================================================
# Global Gemini provider (initialized once)
gemini_provider = GeminiProvider()