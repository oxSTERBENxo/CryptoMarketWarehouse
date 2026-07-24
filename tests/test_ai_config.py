import importlib

import pytest

from ai import config as ai_config_module
from ai.groq_provider import GroqProvider
from ai.ollama_provider import OllamaProvider
from ai.provider import UnknownAIProviderError


def _reload_ai_config():
    return importlib.reload(ai_config_module)


def test_defaults_to_ollama(monkeypatch):
    monkeypatch.delenv("AI_PROVIDER", raising=False)
    module = _reload_ai_config()

    assert module.AI_PROVIDER == "ollama"


def test_reads_ollama_settings_from_env(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://ollama.internal:11434")
    monkeypatch.setenv("OLLAMA_MODEL", "llama3:70b")
    monkeypatch.setenv("OLLAMA_TIMEOUT_SECONDS", "90")
    module = _reload_ai_config()

    assert module.OLLAMA_BASE_URL == "http://ollama.internal:11434"
    assert module.OLLAMA_URL == "http://ollama.internal:11434"
    assert module.OLLAMA_MODEL == "llama3:70b"
    assert module.OLLAMA_TIMEOUT_SECONDS == 90.0


def test_reads_legacy_ollama_url_when_base_url_is_unset(monkeypatch):
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    monkeypatch.setenv("OLLAMA_URL", "http://legacy-ollama:11434")
    module = _reload_ai_config()

    assert module.OLLAMA_BASE_URL == "http://legacy-ollama:11434"


def test_reads_groq_settings_from_env(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "groq")
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
    monkeypatch.setenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    monkeypatch.setenv("GROQ_TIMEOUT_SECONDS", "45")
    module = _reload_ai_config()

    assert module.GROQ_API_KEY == "gsk_test"
    assert module.GROQ_MODEL == "llama-3.3-70b-versatile"
    assert module.GROQ_TIMEOUT_SECONDS == 45.0


def test_get_ai_provider_builds_ollama_provider(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")
    monkeypatch.setenv("OLLAMA_MODEL", "qwen3:8b")
    module = _reload_ai_config()

    provider = module.get_ai_provider()

    assert isinstance(provider, OllamaProvider)
    assert provider.base_url == "http://localhost:11434"
    assert provider.model == "qwen3:8b"


def test_get_ai_provider_builds_groq_provider(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "groq")
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
    monkeypatch.setenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    module = _reload_ai_config()

    provider = module.get_ai_provider()

    assert isinstance(provider, GroqProvider)
    assert provider.api_key == "gsk_test"
    assert provider.model == "llama-3.3-70b-versatile"


def test_get_ai_provider_raises_for_unknown_provider(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "not-a-real-provider")
    module = _reload_ai_config()

    with pytest.raises(UnknownAIProviderError) as exc_info:
        module.get_ai_provider()
    assert exc_info.value.provider_name == "not-a-real-provider"
