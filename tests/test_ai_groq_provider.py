import pytest
import requests

from ai.groq_provider import GROQ_CHAT_COMPLETIONS_URL, GroqProvider
from ai.provider import (
    AIInvalidResponseError,
    AIModelNotFoundError,
    AIProviderConfigurationError,
    AIProviderUnavailableError,
    AITimeoutError,
)


class _FakeResponse:
    def __init__(self, json_body=None, status_code=200, raise_json_error=False):
        self._json_body = json_body
        self.status_code = status_code
        self._raise_json_error = raise_json_error

    def raise_for_status(self):
        if self.status_code >= 400:
            response = requests.Response()
            response.status_code = self.status_code
            raise requests.exceptions.HTTPError(response=response)

    def json(self):
        if self._raise_json_error:
            raise ValueError("not json")
        return self._json_body


def _provider(api_key="gsk_test") -> GroqProvider:
    return GroqProvider(
        api_key=api_key, model="llama-3.3-70b-versatile", timeout_seconds=5
    )


def _success_body():
    return {
        "model": "llama-3.3-70b-versatile",
        "choices": [{"message": {"role": "assistant", "content": "Bitcoin is up today."}}],
        "usage": {"prompt_tokens": 12, "completion_tokens": 34},
    }


def test_generate_returns_text_model_and_token_counts(monkeypatch):
    monkeypatch.setattr(
        requests,
        "post",
        lambda url, headers, json, timeout: _FakeResponse(_success_body()),
    )

    result = _provider().generate("system", "user")

    assert result.text == "Bitcoin is up today."
    assert result.provider == "groq"
    assert result.model == "llama-3.3-70b-versatile"
    assert result.prompt_tokens == 12
    assert result.completion_tokens == 34
    assert result.response_time_ms >= 0


def test_generate_sends_model_prompts_and_auth_to_groq(monkeypatch):
    captured = {}

    def _fake_post(url, headers, json, timeout):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return _FakeResponse(_success_body())

    monkeypatch.setattr(requests, "post", _fake_post)

    _provider().generate("be terse", "hello")

    assert captured["url"] == GROQ_CHAT_COMPLETIONS_URL
    assert captured["headers"]["Authorization"] == "Bearer gsk_test"
    assert captured["json"] == {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": "be terse"},
            {"role": "user", "content": "hello"},
        ],
        "stream": False,
    }
    assert captured["timeout"] == 5


def test_generate_raises_configuration_error_when_api_key_missing():
    with pytest.raises(AIProviderConfigurationError):
        _provider(api_key="").generate("system", "user")


def test_generate_raises_unavailable_on_connection_error(monkeypatch):
    def _raise(url, headers, json, timeout):
        raise requests.exceptions.ConnectionError("refused")

    monkeypatch.setattr(requests, "post", _raise)

    with pytest.raises(AIProviderUnavailableError):
        _provider().generate("system", "user")


def test_generate_raises_timeout_on_timeout(monkeypatch):
    def _raise(url, headers, json, timeout):
        raise requests.exceptions.Timeout("too slow")

    monkeypatch.setattr(requests, "post", _raise)

    with pytest.raises(AITimeoutError):
        _provider().generate("system", "user")


def test_generate_raises_configuration_error_on_401(monkeypatch):
    monkeypatch.setattr(
        requests,
        "post",
        lambda url, headers, json, timeout: _FakeResponse(status_code=401),
    )

    with pytest.raises(AIProviderConfigurationError):
        _provider().generate("system", "user")


def test_generate_raises_model_not_found_on_404(monkeypatch):
    monkeypatch.setattr(
        requests,
        "post",
        lambda url, headers, json, timeout: _FakeResponse(status_code=404),
    )

    with pytest.raises(AIModelNotFoundError):
        _provider().generate("system", "user")


def test_generate_raises_invalid_response_on_bad_json(monkeypatch):
    monkeypatch.setattr(
        requests,
        "post",
        lambda url, headers, json, timeout: _FakeResponse(raise_json_error=True),
    )

    with pytest.raises(AIInvalidResponseError):
        _provider().generate("system", "user")


def test_generate_raises_invalid_response_when_choices_missing(monkeypatch):
    monkeypatch.setattr(
        requests,
        "post",
        lambda url, headers, json, timeout: _FakeResponse({"model": "llama"}),
    )

    with pytest.raises(AIInvalidResponseError):
        _provider().generate("system", "user")


def test_generate_raises_invalid_response_on_server_error(monkeypatch):
    monkeypatch.setattr(
        requests,
        "post",
        lambda url, headers, json, timeout: _FakeResponse(status_code=500),
    )

    with pytest.raises(AIInvalidResponseError):
        _provider().generate("system", "user")
