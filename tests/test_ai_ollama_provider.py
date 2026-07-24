import pytest
import requests

from ai.ollama_provider import OllamaProvider
from ai.provider import (
    AIInvalidResponseError,
    AIModelNotFoundError,
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


def _provider() -> OllamaProvider:
    return OllamaProvider(base_url="http://localhost:11434", model="qwen3:8b", timeout_seconds=5)


def test_generate_returns_text_and_token_counts(monkeypatch):
    body = {
        "response": "Bitcoin is up today.",
        "done": True,
        "prompt_eval_count": 12,
        "eval_count": 34,
    }
    monkeypatch.setattr(requests, "post", lambda url, json, timeout: _FakeResponse(body))

    result = _provider().generate("system", "user")

    assert result.text == "Bitcoin is up today."
    assert result.provider == "ollama"
    assert result.model == "qwen3:8b"
    assert result.prompt_tokens == 12
    assert result.completion_tokens == 34
    assert result.response_time_ms >= 0


def test_generate_sends_model_and_prompts_to_ollama(monkeypatch):
    captured = {}

    def _fake_post(url, json, timeout):
        captured["url"] = url
        captured["json"] = json
        captured["timeout"] = timeout
        return _FakeResponse({"response": "ok"})

    monkeypatch.setattr(requests, "post", _fake_post)

    _provider().generate("be terse", "hello")

    assert captured["url"] == "http://localhost:11434/api/generate"
    assert captured["json"] == {
        "model": "qwen3:8b",
        "prompt": "hello",
        "system": "be terse",
        "stream": False,
    }
    assert captured["timeout"] == 5


def test_generate_raises_unavailable_on_connection_error(monkeypatch):
    def _raise(url, json, timeout):
        raise requests.exceptions.ConnectionError("refused")

    monkeypatch.setattr(requests, "post", _raise)

    with pytest.raises(AIProviderUnavailableError):
        _provider().generate("system", "user")


def test_generate_raises_timeout_on_timeout(monkeypatch):
    def _raise(url, json, timeout):
        raise requests.exceptions.Timeout("too slow")

    monkeypatch.setattr(requests, "post", _raise)

    with pytest.raises(AITimeoutError):
        _provider().generate("system", "user")


def test_generate_raises_model_not_found_on_404(monkeypatch):
    monkeypatch.setattr(requests, "post", lambda url, json, timeout: _FakeResponse(status_code=404))

    with pytest.raises(AIModelNotFoundError):
        _provider().generate("system", "user")


def test_generate_raises_invalid_response_on_bad_json(monkeypatch):
    monkeypatch.setattr(
        requests, "post", lambda url, json, timeout: _FakeResponse(raise_json_error=True)
    )

    with pytest.raises(AIInvalidResponseError):
        _provider().generate("system", "user")


def test_generate_raises_invalid_response_when_response_field_missing(monkeypatch):
    monkeypatch.setattr(requests, "post", lambda url, json, timeout: _FakeResponse({"done": True}))

    with pytest.raises(AIInvalidResponseError):
        _provider().generate("system", "user")


def test_generate_raises_invalid_response_on_server_error(monkeypatch):
    monkeypatch.setattr(requests, "post", lambda url, json, timeout: _FakeResponse(status_code=500))

    with pytest.raises(AIInvalidResponseError):
        _provider().generate("system", "user")
