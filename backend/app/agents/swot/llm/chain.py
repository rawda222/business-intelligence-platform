"""
SWOT Agent v7 - LLM Chain & Factory
=====================================
Build LLM provider chains with fallback support.
"""
import logging
import time
from typing import List, Optional, Tuple

from app.agents.swot.llm.base import LLMClient, LLMClientError
from app.agents.swot.config import (
    MAX_RETRIES_PER_PROVIDER,
    RETRY_BACKOFF_BASE_SECONDS,
)
from app.agents.swot.enums import LLMProvider


logger = logging.getLogger("swot_agent_v7")


class LLMClientFactory:
    """Builds the provider fallback chain."""

    @staticmethod
    def build_chain(preferred=LLMProvider.AUTO, model=None):
        """Build a chain of LLM clients in fallback order."""
        chain = []

        if preferred == LLMProvider.AUTO:
            order = [
                LLMProvider.VERTEX_AI,
                LLMProvider.ANTHROPIC,
                LLMProvider.OPENAI,
                LLMProvider.GROQ,
            ]
        else:
            order = [preferred]

        for provider in order:
            try:
                client = LLMClientFactory._create_client(provider, model)
                if client:
                    chain.append(client)
                    logger.info(f"[Chain] Added provider: {provider.value}")
            except LLMClientError as exc:
                logger.warning(f"[Chain] Skipped {provider.value}: {exc}")
            except Exception as exc:
                logger.warning(f"[Chain] Failed {provider.value}: {exc}")

        return chain

    @staticmethod
    def _create_client(provider, model):
        """Create a single LLM client based on provider type."""
        if provider == LLMProvider.VERTEX_AI:
            from app.agents.swot.llm.vertex_ai import VertexAIGeminiClient
            return VertexAIGeminiClient(model=model)

        elif provider == LLMProvider.ANTHROPIC:
            from app.agents.swot.llm.anthropic import AnthropicClaudeClient
            return AnthropicClaudeClient(model=model)

        elif provider == LLMProvider.OPENAI:
            from app.agents.swot.llm.openai import OpenAIGPTClient
            return OpenAIGPTClient(model=model)

        elif provider == LLMProvider.GROQ:
            from app.agents.swot.llm.groq import GroqClient
            return GroqClient(model=model)

        return None


def call_llm_chain(chain, system, user):
    """Try each client in order until one succeeds."""
    if not chain:
        logger.error("[Chain] Empty chain - no providers available")
        return None, None

    for client in chain:
        logger.info(f"[Chain] Trying provider: {client.provider_name}")

        for attempt in range(MAX_RETRIES_PER_PROVIDER):
            try:
                response = client.generate(system, user)
                if response:
                    logger.info(
                        f"[Chain] Success with {client.provider_name} "
                        f"(attempt {attempt + 1})"
                    )
                    return response, client
            except LLMClientError as exc:
                wait = RETRY_BACKOFF_BASE_SECONDS * (2 ** attempt)
                logger.warning(
                    f"[Chain] {client.provider_name} attempt {attempt + 1} "
                    f"failed: {exc}. Waiting {wait}s..."
                )
                if attempt < MAX_RETRIES_PER_PROVIDER - 1:
                    time.sleep(wait)
            except Exception as exc:
                logger.warning(
                    f"[Chain] {client.provider_name} unexpected error: {exc}"
                )
                break

        logger.warning(
            f"[Chain] Provider {client.provider_name} exhausted retries"
        )

    logger.error("[Chain] All providers failed")
    return None, None