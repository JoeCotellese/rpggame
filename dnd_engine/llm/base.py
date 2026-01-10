# ABOUTME: Abstract base class for LLM providers that enhance game narrative
# ABOUTME: Defines interface for text generation with timeout and error handling

from abc import ABC, abstractmethod
from typing import Any, Callable

# Type alias for status callback function
# Signature: (message: str, message_type: str) -> None
# message_type is one of: "info", "success", "warning", "error"
StatusCallback = Callable[[str, str], None] | None


class LLMProvider(ABC):
    """
    Abstract base class for LLM providers.

    All providers must implement these methods for narrative enhancement.
    LLM providers generate atmospheric descriptions, combat narration,
    and NPC dialogue without affecting game mechanics.
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        timeout: float = 10.0,
        max_tokens: int = 1000,
        status_callback: StatusCallback = None,
    ) -> None:
        """
        Initialize LLM provider.

        Args:
            api_key: API key for the provider
            model: Model name/ID to use
            timeout: Request timeout in seconds
            max_tokens: Maximum tokens in response
            status_callback: Optional callback for status messages (msg, type)
        """
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.max_tokens = max_tokens
        self.status_callback = status_callback

    def _emit_status(self, message: str, message_type: str = "info") -> None:
        """
        Emit status message via callback if available, fallback to print.

        Args:
            message: Status message text
            message_type: One of "info", "success", "warning", "error"
        """
        if self.status_callback:
            self.status_callback(message, message_type)
        else:
            # Fallback during transition - remove in Phase 5
            from dnd_engine.ui.rich_ui import print_status_message

            print_status_message(message, message_type)

    @abstractmethod
    async def generate(self, prompt: str, temperature: float = 0.7) -> str | None:
        """
        Generate text from prompt.

        Args:
            prompt: The prompt to send to LLM
            temperature: Sampling temperature (0.0-1.0)

        Returns:
            Generated text or None if failed

        Raises:
            asyncio.TimeoutError: If request exceeds timeout
            Exception: For API errors (should be caught by caller)
        """
        pass

    @abstractmethod
    def get_provider_name(self) -> str:
        """
        Return provider name for logging.

        Returns:
            Human-readable provider name
        """
        pass

    @abstractmethod
    async def chat_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        temperature: float = 0.7,
    ) -> dict[str, Any] | None:
        """
        Send a chat request with tool calling support.

        Args:
            messages: List of chat messages (role, content)
            tools: OpenAI-format tool definitions
            temperature: Sampling temperature (0.0-1.0)

        Returns:
            Response dict with:
                - content: str | None (assistant's text response)
                - tool_calls: list[dict] | None (tool calls to execute)
                - finish_reason: str ("stop", "tool_use", etc.)
            Returns None on error
        """
        pass
