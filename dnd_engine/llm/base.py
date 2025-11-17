# ABOUTME: Abstract base class for LLM providers that enhance game narrative
# ABOUTME: Defines interface for text generation with timeout and error handling

from abc import ABC, abstractmethod
from typing import Optional


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
        max_tokens: int = 150
    ) -> None:
        """
        Initialize LLM provider.

        Args:
            api_key: API key for the provider
            model: Model name/ID to use
            timeout: Request timeout in seconds
            max_tokens: Maximum tokens in response
        """
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.max_tokens = max_tokens

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        temperature: float = 0.7
    ) -> Optional[str]:
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
