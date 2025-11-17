# ABOUTME: Factory function for creating LLM providers from configuration
# ABOUTME: Auto-detects provider from environment or creates from explicit parameters

import os
from typing import Any, Optional

from .anthropic_provider import AnthropicProvider
from .base import LLMProvider
from .openai_provider import OpenAIProvider
from dnd_engine.ui.rich_ui import print_status_message


def create_llm_provider(
    provider_name: Optional[str] = None,
    **kwargs: Any
) -> Optional[LLMProvider]:
    """
    Factory function to create LLM provider from config.

    Args:
        provider_name: Provider name or None to auto-detect from environment
        **kwargs: Additional provider configuration (model, timeout, etc.)

    Returns:
        LLMProvider instance or None if disabled/unavailable

    Example:
        >>> provider = create_llm_provider()  # Auto-detect from env
        >>> provider = create_llm_provider("openai", model="gpt-4")
    """
    # Get provider from arg or environment
    if provider_name is None:
        provider_name = os.getenv("LLM_PROVIDER", "").lower()
    else:
        provider_name = provider_name.lower()

    # Normalize provider name
    provider_name = provider_name.strip()

    # Disabled or not configured
    if not provider_name or provider_name == "none":
        return None

    # OpenAI provider
    if provider_name == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            print_status_message("OPENAI_API_KEY not set, LLM disabled", "warning")
            return None

        model = kwargs.get("model") or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        timeout = float(os.getenv("LLM_TIMEOUT", "10"))
        max_tokens = int(os.getenv("LLM_MAX_TOKENS", "150"))

        return OpenAIProvider(
            api_key=api_key,
            model=model,
            timeout=timeout,
            max_tokens=max_tokens
        )

    # Anthropic provider
    elif provider_name == "anthropic":
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            print_status_message("ANTHROPIC_API_KEY not set, LLM disabled", "warning")
            return None

        model = kwargs.get("model") or os.getenv(
            "ANTHROPIC_MODEL",
            "claude-3-5-haiku-20241022"
        )
        timeout = float(os.getenv("LLM_TIMEOUT", "10"))
        max_tokens = int(os.getenv("LLM_MAX_TOKENS", "150"))

        return AnthropicProvider(
            api_key=api_key,
            model=model,
            timeout=timeout,
            max_tokens=max_tokens
        )

    # Unknown provider
    else:
        print_status_message(f"Unknown LLM provider '{provider_name}', LLM disabled", "warning")
        return None
