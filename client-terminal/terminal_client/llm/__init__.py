# ABOUTME: LLM wrapper that injects terminal UI callbacks into the engine's LLM providers.
# ABOUTME: This bridges the headless engine with the terminal client's status display.
"""
LLM wrapper for terminal client.

This module wraps the dnd_engine.llm module to automatically inject
the terminal UI's print_status_message callback for status updates.
"""

from typing import Any

from dnd_engine.llm import factory
from dnd_engine.llm.base import LLMProvider, StatusCallback
from terminal_client.ui.rich_ui import print_status_message

# Re-export base types for convenience
__all__ = ["LLMProvider", "StatusCallback", "create_llm_provider"]


def create_llm_provider(
    provider_name: str | None = None,
    status_callback: StatusCallback = None,
    **kwargs: Any,
) -> LLMProvider | None:
    """
    Create an LLM provider with terminal UI callbacks injected.

    This wraps dnd_engine.llm.factory.create_llm_provider to automatically
    provide the terminal's print_status_message as the status callback.

    Args:
        provider_name: Provider name or None to auto-detect from environment
        status_callback: Optional custom callback (defaults to print_status_message)
        **kwargs: Additional provider configuration

    Returns:
        LLMProvider instance or None if disabled/unavailable
    """
    # Use terminal UI callback if none provided
    if status_callback is None:
        status_callback = print_status_message

    return factory.create_llm_provider(
        provider_name=provider_name,
        status_callback=status_callback,
        **kwargs,
    )
