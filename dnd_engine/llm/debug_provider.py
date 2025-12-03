# ABOUTME: Debug LLM provider that returns the prompt text instead of calling an API
# ABOUTME: Useful for inspecting exactly what prompts are being sent to the LLM

from typing import Any

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
        max_tokens: int = 1000,
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

    async def generate(self, prompt: str, temperature: float = 0.7) -> str | None:
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

    async def chat_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        temperature: float = 0.7,
    ) -> dict[str, Any] | None:
        """
        Return debug info about the chat request.

        Args:
            messages: Chat messages to inspect
            tools: Tool definitions to inspect
            temperature: Ignored

        Returns:
            Debug response showing what would be sent
        """
        # Format messages for inspection
        msg_summary = "\n".join(
            f"  [{m.get('role', '?')}]: {str(m.get('content', ''))[:100]}..." for m in messages
        )
        tool_names = [t.get("function", {}).get("name", "?") for t in tools]

        return {
            "content": (
                f"=== DEBUG CHAT ===\n"
                f"Messages ({len(messages)}):\n{msg_summary}\n"
                f"Tools: {tool_names}\n"
                f"=== /DEBUG CHAT ==="
            ),
            "tool_calls": [],
            "finish_reason": "stop",
        }
