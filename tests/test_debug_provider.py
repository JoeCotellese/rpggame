"""Unit tests for debug LLM provider."""

import pytest

from dnd_engine.llm.debug_provider import DebugProvider


class TestDebugProvider:
    """Test debug provider returns prompts for inspection."""

    @pytest.mark.asyncio
    async def test_generate_returns_prompt(self) -> None:
        """Test that generate returns the prompt wrapped in debug markers."""
        provider = DebugProvider()
        prompt = "This is a test prompt about a dragon"

        result = await provider.generate(prompt)

        assert result is not None
        assert "[DEBUG PROMPT]" in result
        assert "[/DEBUG PROMPT]" in result
        assert "This is a test prompt about a dragon" in result

    @pytest.mark.asyncio
    async def test_generate_preserves_prompt_content(self) -> None:
        """Test that the full prompt is preserved in the output."""
        provider = DebugProvider()
        prompt = """Enhance this D&D dungeon room description:

Room: Torture Chamber
Basic description: A dark room with rusty chains

Add vivid sensory details."""

        result = await provider.generate(prompt)

        assert result is not None
        assert "Torture Chamber" in result
        assert "rusty chains" in result
        assert "vivid sensory details" in result

    @pytest.mark.asyncio
    async def test_generate_with_temperature(self) -> None:
        """Test that temperature parameter is ignored but doesn't cause errors."""
        provider = DebugProvider()
        prompt = "Test prompt"

        result = await provider.generate(prompt, temperature=0.5)

        assert result is not None
        assert "Test prompt" in result

    def test_get_provider_name(self) -> None:
        """Test that provider name is correct."""
        provider = DebugProvider()

        name = provider.get_provider_name()

        assert name == "Debug (no API calls)"

    def test_init_with_default_args(self) -> None:
        """Test initialization with default arguments."""
        provider = DebugProvider()

        assert provider.api_key == "debug"
        assert provider.model == "debug"
        assert provider.timeout == 10.0
        assert provider.max_tokens == 150

    def test_init_with_custom_args(self) -> None:
        """Test that custom initialization args are accepted but ignored."""
        provider = DebugProvider(
            api_key="custom_key",
            model="custom_model",
            timeout=5.0,
            max_tokens=100
        )

        # Args are stored but not used
        assert provider.api_key == "custom_key"
        assert provider.model == "custom_model"
