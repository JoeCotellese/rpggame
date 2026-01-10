# ABOUTME: Factory function for creating LLM providers from configuration
# ABOUTME: Auto-detects provider from environment or creates from explicit parameters

import os
from typing import Any

from .anthropic_provider import AnthropicProvider
from .base import LLMProvider, StatusCallback
from .debug_provider import DebugProvider
from .openai_provider import OpenAIProvider


def _emit_factory_status(
    message: str, message_type: str, callback: StatusCallback
) -> None:
    """Emit status from factory, with fallback to print."""
    if callback:
        callback(message, message_type)
    else:
        # Fallback during transition - remove in Phase 5
        from dnd_engine.ui.rich_ui import print_status_message

        print_status_message(message, message_type)


def create_llm_provider(
    provider_name: str | None = None,
    status_callback: StatusCallback = None,
    **kwargs: Any,
) -> LLMProvider | None:
    """
    Factory function to create LLM provider from config.

    Args:
        provider_name: Provider name or None to auto-detect from environment
        status_callback: Optional callback for status messages (msg, type)
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

    # Debug provider (no API calls)
    if provider_name == "debug":
        return DebugProvider()

    # OpenAI provider
    if provider_name == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            _emit_factory_status("OPENAI_API_KEY not set, LLM disabled", "warning", status_callback)
            return None

        model = kwargs.get("model") or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        timeout = float(os.getenv("LLM_TIMEOUT", "20"))
        max_tokens = int(os.getenv("LLM_MAX_TOKENS", "1000"))

        return OpenAIProvider(
            api_key=api_key,
            model=model,
            timeout=timeout,
            max_tokens=max_tokens,
            status_callback=status_callback,
        )

    # Anthropic provider
    elif provider_name == "anthropic":
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            _emit_factory_status("ANTHROPIC_API_KEY not set, LLM disabled", "warning", status_callback)
            return None

        model = kwargs.get("model") or os.getenv("ANTHROPIC_MODEL", "claude-3-5-haiku-20241022")
        timeout = float(os.getenv("LLM_TIMEOUT", "20"))
        max_tokens = int(os.getenv("LLM_MAX_TOKENS", "1000"))

        return AnthropicProvider(
            api_key=api_key,
            model=model,
            timeout=timeout,
            max_tokens=max_tokens,
            status_callback=status_callback,
        )

    # Unknown provider
    else:
        _emit_factory_status(f"Unknown LLM provider '{provider_name}', LLM disabled", "warning", status_callback)
        return None
