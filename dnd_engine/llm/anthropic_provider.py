# ABOUTME: Anthropic Claude provider for generating narrative descriptions
# ABOUTME: Handles API calls with timeout and error handling for graceful fallback

import asyncio
from typing import Optional

from anthropic import AsyncAnthropic

from .base import LLMProvider
from dnd_engine.ui.rich_ui import print_status_message, print_error


class AnthropicProvider(LLMProvider):
    """
    Anthropic Claude provider for narrative enhancement.

    Supports: Claude 3 (Opus, Sonnet, Haiku)
    """

    def __init__(
        self,
        api_key: str,
        model: str = "claude-3-5-haiku-20241022",
        timeout: float = 10.0,
        max_tokens: int = 150
    ) -> None:
        """
        Initialize Anthropic provider.

        Args:
            api_key: Anthropic API key
            model: Model name (default: claude-3-5-haiku for cost-effectiveness)
            timeout: Request timeout in seconds
            max_tokens: Maximum tokens in response
        """
        super().__init__(api_key, model, timeout, max_tokens)
        self.client = AsyncAnthropic(api_key=api_key)

    async def generate(
        self,
        prompt: str,
        temperature: float = 0.7
    ) -> Optional[str]:
        """
        Generate text using Anthropic API.

        Args:
            prompt: The prompt to send
            temperature: Sampling temperature (0.0-1.0)

        Returns:
            Generated text or None if failed
        """
        try:
            response = await asyncio.wait_for(
                self.client.messages.create(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    temperature=temperature,
                    system=(
                        "You are a Dungeon Master narrating a D&D game. "
                        "Be vivid but concise (2-3 sentences max)."
                    ),
                    messages=[
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ]
                ),
                timeout=self.timeout
            )

            return response.content[0].text.strip()

        except asyncio.TimeoutError:
            print_status_message(f"Anthropic request timed out after {self.timeout}s", "warning")
            return None
        except Exception as e:
            print_error(f"Anthropic API error: {e}")
            return None

    def get_provider_name(self) -> str:
        """
        Return provider name for logging.

        Returns:
            Human-readable provider name
        """
        return f"Anthropic ({self.model})"
