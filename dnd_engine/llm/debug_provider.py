# ABOUTME: Debug LLM provider that returns the prompt text instead of calling an API
# ABOUTME: Useful for inspecting exactly what prompts are being sent to the LLM

from typing import Optional

from .base import LLMProvider


class DebugProvider(LLMProvider):
    """
    Debug LLM provider that returns prompts for inspection.

    Instead of calling an actual LLM API, this provider returns
    the prompt text wrapped in a debug format so you can see
    exactly what would be sent to the LLM.
    """

    def __init__(
        self,
        api_key: str = "debug",
        model: str = "debug",
        timeout: float = 10.0,
        max_tokens: int = 150
    ) -> None:
        """
        Initialize debug provider.

        Args:
            api_key: Ignored for debug provider
            model: Ignored for debug provider
            timeout: Ignored for debug provider
            max_tokens: Ignored for debug provider
        """
        super().__init__(api_key, model, timeout, max_tokens)

    async def generate(
        self,
        prompt: str,
        temperature: float = 0.7
    ) -> Optional[str]:
        """
        Return the prompt text for inspection.

        Args:
            prompt: The prompt to inspect
            temperature: Ignored for debug provider

        Returns:
            The prompt text wrapped in debug formatting
        """
        # Return the prompt with clear markers
        # Use === instead of [] to avoid Rich markup conflicts
        return f"=== DEBUG PROMPT ===\n{prompt}\n=== /DEBUG PROMPT ==="

    def get_provider_name(self) -> str:
        """
        Return provider name for logging.

        Returns:
            Human-readable provider name
        """
        return "Debug (no API calls)"
