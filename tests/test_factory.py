"""Unit tests for LLM provider factory."""

import os
from unittest.mock import patch

import pytest

from dnd_engine.llm.anthropic_provider import AnthropicProvider
from dnd_engine.llm.debug_provider import DebugProvider
from dnd_engine.llm.factory import create_llm_provider
from dnd_engine.llm.openai_provider import OpenAIProvider


class TestProviderFactory:
    """Test LLM provider factory creation logic."""

    def test_create_openai_provider_with_env(self) -> None:
        """Test creating OpenAI provider from environment variables."""
        with patch.dict(os.environ, {
            "LLM_PROVIDER": "openai",
            "OPENAI_API_KEY": "sk-test123",
            "OPENAI_MODEL": "gpt-4",
            "LLM_TIMEOUT": "15",
            "LLM_MAX_TOKENS": "200"
        }):
            with patch('dnd_engine.llm.openai_provider.AsyncOpenAI'):
                provider = create_llm_provider()

                assert provider is not None
                assert isinstance(provider, OpenAIProvider)
                assert provider.model == "gpt-4"
                assert provider.timeout == 15.0
                assert provider.max_tokens == 200

    def test_create_openai_provider_with_defaults(self) -> None:
        """Test creating OpenAI provider with default settings."""
        with patch.dict(os.environ, {
            "LLM_PROVIDER": "openai",
            "OPENAI_API_KEY": "sk-test123"
        }, clear=True):
            with patch('dnd_engine.llm.openai_provider.AsyncOpenAI'):
                provider = create_llm_provider()

                assert provider is not None
                assert isinstance(provider, OpenAIProvider)
                assert provider.model == "gpt-4o-mini"  # Default
                assert provider.timeout == 10.0
                assert provider.max_tokens == 150

    def test_create_openai_provider_missing_key(self) -> None:
        """Test that missing API key returns None."""
        with patch.dict(os.environ, {"LLM_PROVIDER": "openai"}, clear=True):
            provider = create_llm_provider()

            assert provider is None

    def test_create_anthropic_provider_with_env(self) -> None:
        """Test creating Anthropic provider from environment variables."""
        with patch.dict(os.environ, {
            "LLM_PROVIDER": "anthropic",
            "ANTHROPIC_API_KEY": "sk-ant-test123",
            "ANTHROPIC_MODEL": "claude-3-opus-20240229",
            "LLM_TIMEOUT": "20",
            "LLM_MAX_TOKENS": "300"
        }):
            with patch('dnd_engine.llm.anthropic_provider.AsyncAnthropic'):
                provider = create_llm_provider()

                assert provider is not None
                assert isinstance(provider, AnthropicProvider)
                assert provider.model == "claude-3-opus-20240229"
                assert provider.timeout == 20.0
                assert provider.max_tokens == 300

    def test_create_anthropic_provider_with_defaults(self) -> None:
        """Test creating Anthropic provider with default settings."""
        with patch.dict(os.environ, {
            "LLM_PROVIDER": "anthropic",
            "ANTHROPIC_API_KEY": "sk-ant-test123"
        }, clear=True):
            with patch('dnd_engine.llm.anthropic_provider.AsyncAnthropic'):
                provider = create_llm_provider()

                assert provider is not None
                assert isinstance(provider, AnthropicProvider)
                assert provider.model == "claude-3-5-haiku-20241022"  # Default

    def test_create_anthropic_provider_missing_key(self) -> None:
        """Test that missing Anthropic API key returns None."""
        with patch.dict(os.environ, {"LLM_PROVIDER": "anthropic"}, clear=True):
            provider = create_llm_provider()

            assert provider is None

    def test_create_provider_disabled(self) -> None:
        """Test that LLM_PROVIDER=none returns None."""
        with patch.dict(os.environ, {"LLM_PROVIDER": "none"}, clear=True):
            provider = create_llm_provider()

            assert provider is None

    def test_create_provider_not_set(self) -> None:
        """Test that missing LLM_PROVIDER returns None."""
        with patch.dict(os.environ, {}, clear=True):
            provider = create_llm_provider()

            assert provider is None

    def test_create_provider_unknown(self) -> None:
        """Test that unknown provider name returns None."""
        with patch.dict(os.environ, {"LLM_PROVIDER": "unknown_provider"}, clear=True):
            provider = create_llm_provider()

            assert provider is None

    def test_create_provider_with_explicit_name(self) -> None:
        """Test creating provider with explicit provider name argument."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test123"}, clear=True):
            with patch('dnd_engine.llm.openai_provider.AsyncOpenAI'):
                provider = create_llm_provider(provider_name="openai")

                assert provider is not None
                assert isinstance(provider, OpenAIProvider)

    def test_create_provider_with_kwargs_override(self) -> None:
        """Test creating provider with kwargs overriding environment."""
        with patch.dict(os.environ, {
            "LLM_PROVIDER": "openai",
            "OPENAI_API_KEY": "sk-test123",
            "OPENAI_MODEL": "gpt-3.5-turbo"
        }):
            with patch('dnd_engine.llm.openai_provider.AsyncOpenAI'):
                provider = create_llm_provider(model="gpt-4-turbo")

                assert provider is not None
                assert isinstance(provider, OpenAIProvider)
                assert provider.model == "gpt-4-turbo"  # Override from kwargs

    def test_create_provider_case_insensitive(self) -> None:
        """Test that provider name is case-insensitive."""
        with patch.dict(os.environ, {
            "LLM_PROVIDER": "OpenAI",
            "OPENAI_API_KEY": "sk-test123"
        }):
            with patch('dnd_engine.llm.openai_provider.AsyncOpenAI'):
                provider = create_llm_provider()

                assert provider is not None
                assert isinstance(provider, OpenAIProvider)

    def test_create_debug_provider(self) -> None:
        """Test creating debug provider."""
        with patch.dict(os.environ, {"LLM_PROVIDER": "debug"}, clear=True):
            provider = create_llm_provider()

            assert provider is not None
            assert isinstance(provider, DebugProvider)
            assert provider.get_provider_name() == "Debug (no API calls)"

    def test_create_debug_provider_explicit(self) -> None:
        """Test creating debug provider with explicit name."""
        provider = create_llm_provider(provider_name="debug")

        assert provider is not None
        assert isinstance(provider, DebugProvider)
