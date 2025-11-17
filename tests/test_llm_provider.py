"""Unit tests for LLM providers with mocked API calls."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from dnd_engine.llm.base import LLMProvider


class TestOpenAIProvider:
    """Test OpenAI provider implementation with mocked responses."""

    @pytest.mark.asyncio
    async def test_openai_provider_successful_generation(self) -> None:
        """Test successful text generation from OpenAI API."""
        from dnd_engine.llm.openai_provider import OpenAIProvider

        # Mock the OpenAI client response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "A dark and foreboding chamber."

        with patch('dnd_engine.llm.openai_provider.AsyncOpenAI') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            provider = OpenAIProvider(
                api_key="test-key",
                model="gpt-4o-mini",
                timeout=10.0,
                max_tokens=150
            )

            result = await provider.generate("Describe a dungeon room")

            assert result == "A dark and foreboding chamber."
            assert mock_client.chat.completions.create.called

    @pytest.mark.asyncio
    async def test_openai_provider_timeout(self) -> None:
        """Test that OpenAI provider handles timeouts gracefully."""
        from dnd_engine.llm.openai_provider import OpenAIProvider

        with patch('dnd_engine.llm.openai_provider.AsyncOpenAI') as mock_client_class:
            mock_client = AsyncMock()
            # Simulate a timeout
            mock_client.chat.completions.create = AsyncMock(
                side_effect=asyncio.TimeoutError()
            )
            mock_client_class.return_value = mock_client

            provider = OpenAIProvider(
                api_key="test-key",
                model="gpt-4o-mini",
                timeout=1.0
            )

            result = await provider.generate("Test prompt")

            assert result is None

    @pytest.mark.asyncio
    async def test_openai_provider_api_error(self) -> None:
        """Test that OpenAI provider handles API errors gracefully."""
        from dnd_engine.llm.openai_provider import OpenAIProvider

        with patch('dnd_engine.llm.openai_provider.AsyncOpenAI') as mock_client_class:
            mock_client = AsyncMock()
            # Simulate an API error
            mock_client.chat.completions.create = AsyncMock(
                side_effect=Exception("API Error")
            )
            mock_client_class.return_value = mock_client

            provider = OpenAIProvider(
                api_key="test-key",
                model="gpt-4o-mini"
            )

            result = await provider.generate("Test prompt")

            assert result is None

    @pytest.mark.asyncio
    async def test_openai_provider_temperature_parameter(self) -> None:
        """Test that temperature parameter is passed correctly."""
        from dnd_engine.llm.openai_provider import OpenAIProvider

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Test response"

        with patch('dnd_engine.llm.openai_provider.AsyncOpenAI') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            provider = OpenAIProvider(api_key="test-key", model="gpt-4o-mini")
            await provider.generate("Test prompt", temperature=0.9)

            # Verify temperature was passed
            call_args = mock_client.chat.completions.create.call_args
            assert call_args.kwargs['temperature'] == 0.9

    def test_openai_provider_name(self) -> None:
        """Test that provider name is returned correctly."""
        from dnd_engine.llm.openai_provider import OpenAIProvider

        with patch('dnd_engine.llm.openai_provider.AsyncOpenAI'):
            provider = OpenAIProvider(api_key="test-key", model="gpt-4o-mini")
            assert "OpenAI" in provider.get_provider_name()
            assert "gpt-4o-mini" in provider.get_provider_name()


class TestAnthropicProvider:
    """Test Anthropic provider implementation with mocked responses."""

    @pytest.mark.asyncio
    async def test_anthropic_provider_successful_generation(self) -> None:
        """Test successful text generation from Anthropic API."""
        from dnd_engine.llm.anthropic_provider import AnthropicProvider

        # Mock the Anthropic client response
        mock_response = MagicMock()
        mock_response.content = [MagicMock()]
        mock_response.content[0].text = "The goblin sneers menacingly."

        with patch('dnd_engine.llm.anthropic_provider.AsyncAnthropic') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            provider = AnthropicProvider(
                api_key="test-key",
                model="claude-3-5-haiku-20241022",
                timeout=10.0,
                max_tokens=150
            )

            result = await provider.generate("Describe a goblin")

            assert result == "The goblin sneers menacingly."
            assert mock_client.messages.create.called

    @pytest.mark.asyncio
    async def test_anthropic_provider_timeout(self) -> None:
        """Test that Anthropic provider handles timeouts gracefully."""
        from dnd_engine.llm.anthropic_provider import AnthropicProvider

        with patch('dnd_engine.llm.anthropic_provider.AsyncAnthropic') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(side_effect=asyncio.TimeoutError())
            mock_client_class.return_value = mock_client

            provider = AnthropicProvider(
                api_key="test-key",
                model="claude-3-5-haiku-20241022",
                timeout=1.0
            )

            result = await provider.generate("Test prompt")

            assert result is None

    @pytest.mark.asyncio
    async def test_anthropic_provider_api_error(self) -> None:
        """Test that Anthropic provider handles API errors gracefully."""
        from dnd_engine.llm.anthropic_provider import AnthropicProvider

        with patch('dnd_engine.llm.anthropic_provider.AsyncAnthropic') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(side_effect=Exception("API Error"))
            mock_client_class.return_value = mock_client

            provider = AnthropicProvider(
                api_key="test-key",
                model="claude-3-5-haiku-20241022"
            )

            result = await provider.generate("Test prompt")

            assert result is None

    def test_anthropic_provider_name(self) -> None:
        """Test that provider name is returned correctly."""
        from dnd_engine.llm.anthropic_provider import AnthropicProvider

        with patch('dnd_engine.llm.anthropic_provider.AsyncAnthropic'):
            provider = AnthropicProvider(
                api_key="test-key",
                model="claude-3-5-haiku-20241022"
            )
            assert "Anthropic" in provider.get_provider_name()
            assert "claude-3-5-haiku-20241022" in provider.get_provider_name()
