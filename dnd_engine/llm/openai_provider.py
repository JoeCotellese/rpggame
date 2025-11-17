# ABOUTME: OpenAI GPT provider for generating narrative descriptions
# ABOUTME: Handles API calls with timeout and error handling for graceful fallback

import asyncio
from typing import Optional

from openai import AsyncOpenAI

from .base import LLMProvider


class OpenAIProvider(LLMProvider):
    """
    OpenAI GPT provider for narrative enhancement.

    Supports: GPT-4, GPT-4-turbo, GPT-3.5-turbo, GPT-4o-mini
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        timeout: float = 10.0,
        max_tokens: int = 150
    ) -> None:
        """
        Initialize OpenAI provider.

        Args:
            api_key: OpenAI API key
            model: Model name (default: gpt-4o-mini for cost-effectiveness)
            timeout: Request timeout in seconds
            max_tokens: Maximum tokens in response
        """
        super().__init__(api_key, model, timeout, max_tokens)
        self.client = AsyncOpenAI(api_key=api_key)

    async def generate(
        self,
        prompt: str,
        temperature: float = 0.7
    ) -> Optional[str]:
        """
        Generate text using OpenAI API.

        Args:
            prompt: The prompt to send
            temperature: Sampling temperature (0.0-1.0)

        Returns:
            Generated text or None if failed
        """
        try:
            response = await asyncio.wait_for(
                self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are a Dungeon Master narrating a D&D game. "
                                "Be vivid but concise (2-3 sentences max)."
                            )
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    temperature=temperature,
                    max_tokens=self.max_tokens
                ),
                timeout=self.timeout
            )

            return response.choices[0].message.content.strip()

        except asyncio.TimeoutError:
            print(f"OpenAI request timed out after {self.timeout}s")
            return None
        except Exception as e:
            print(f"OpenAI API error: {e}")
            return None

    def get_provider_name(self) -> str:
        """
        Return provider name for logging.

        Returns:
            Human-readable provider name
        """
        return f"OpenAI ({self.model})"
