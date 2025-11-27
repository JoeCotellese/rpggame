# ABOUTME: OpenAI GPT provider for generating narrative descriptions
# ABOUTME: Handles API calls with timeout and error handling for graceful fallback

import asyncio
import json
from typing import Any

from openai import AsyncOpenAI

from dnd_engine.ui.rich_ui import print_error, print_status_message

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
        max_tokens: int = 1000
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
    ) -> str | None:
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
                                "You are a narrator for a classic radio drama adventure serial. "
                                "Your audience cannot see - they can only hear your words. "
                                "Paint vivid pictures using rich sensory details: sights, sounds, smells, textures, atmosphere. "
                                "Write in present tense, second person (\"you step into...\", \"the air hangs heavy...\"). "
                                "Be dramatic and atmospheric, but keep it concise (2-3 sentences). "
                                "Make every word count to transport listeners into the scene."
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

        except TimeoutError:
            print_status_message(f"OpenAI request timed out after {self.timeout}s", "warning")
            return None
        except Exception as e:
            print_error(f"OpenAI API error: {e}")
            return None

    def get_provider_name(self) -> str:
        """
        Return provider name for logging.

        Returns:
            Human-readable provider name
        """
        return f"OpenAI ({self.model})"

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
            Response dict with content, tool_calls, finish_reason
            or None on error
        """
        try:
            response = await asyncio.wait_for(
                self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=tools if tools else None,
                    temperature=temperature,
                    max_tokens=500,  # More tokens for conversational responses
                ),
                timeout=self.timeout,
            )

            message = response.choices[0].message
            tool_calls = []

            if message.tool_calls:
                for tc in message.tool_calls:
                    tool_calls.append(
                        {
                            "id": tc.id,
                            "name": tc.function.name,
                            "arguments": json.loads(tc.function.arguments),
                        }
                    )

            return {
                "content": message.content,
                "tool_calls": tool_calls,
                "finish_reason": response.choices[0].finish_reason,
            }

        except TimeoutError:
            print_status_message(
                f"OpenAI request timed out after {self.timeout}s", "warning"
            )
            return None
        except Exception as e:
            print_error(f"OpenAI API error: {e}")
            return None
