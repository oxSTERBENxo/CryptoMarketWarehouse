import time

import requests

from ai.provider import (
    AIGenerationResult,
    AIInvalidResponseError,
    AIModelNotFoundError,
    AIProvider,
    AIProviderConfigurationError,
    AIProviderUnavailableError,
    AITimeoutError,
)
from utils.logging_config import get_logger

logger = get_logger("ai.groq")

GROQ_CHAT_COMPLETIONS_URL = "https://api.groq.com/openai/v1/chat/completions"


class GroqProvider(AIProvider):
    """AIProvider backed by Groq's OpenAI-compatible chat completions endpoint."""

    name = "groq"

    def __init__(self, api_key: str, model: str, timeout_seconds: float) -> None:
        self.api_key = api_key.strip()
        self.model = model
        self.timeout_seconds = timeout_seconds

    def generate(self, system_prompt: str, user_prompt: str) -> AIGenerationResult:
        if not self.api_key:
            raise AIProviderConfigurationError("GROQ_API_KEY is required when AI_PROVIDER=groq")

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        started = time.monotonic()
        try:
            response = requests.post(
                GROQ_CHAT_COMPLETIONS_URL,
                headers=headers,
                json=payload,
                timeout=self.timeout_seconds,
            )
        except requests.exceptions.Timeout as exc:
            raise AITimeoutError(
                f"Groq did not respond within {self.timeout_seconds}s (model={self.model!r})"
            ) from exc
        except requests.exceptions.ConnectionError as exc:
            raise AIProviderUnavailableError(f"Could not reach Groq API: {exc}") from exc
        except requests.exceptions.RequestException as exc:
            raise AIProviderUnavailableError(f"Groq request failed: {exc}") from exc
        response_time_ms = (time.monotonic() - started) * 1000

        if response.status_code == 401:
            raise AIProviderConfigurationError("Groq rejected GROQ_API_KEY")
        if response.status_code == 403:
            raise AIProviderConfigurationError("Groq API access is forbidden for this API key")
        if response.status_code == 404:
            raise AIModelNotFoundError(f"Groq has no model {self.model!r} available")

        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as exc:
            raise AIInvalidResponseError(f"Groq returned an HTTP error: {exc}") from exc

        try:
            data = response.json()
        except ValueError as exc:
            raise AIInvalidResponseError("Groq response was not valid JSON") from exc

        text = _extract_completion_text(data)
        usage = data.get("usage") if isinstance(data, dict) else None
        response_model = data.get("model") if isinstance(data, dict) else None
        model = response_model if isinstance(response_model, str) and response_model else self.model
        prompt_tokens = usage.get("prompt_tokens") if isinstance(usage, dict) else None
        completion_tokens = usage.get("completion_tokens") if isinstance(usage, dict) else None

        logger.info(
            "AI generate: provider=%s model=%s response_time_ms=%.1f prompt_tokens=%s completion_tokens=%s",
            self.name,
            model,
            response_time_ms,
            prompt_tokens,
            completion_tokens,
        )

        return AIGenerationResult(
            text=text,
            provider=self.name,
            model=model,
            response_time_ms=response_time_ms,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )


def _extract_completion_text(data: object) -> str:
    if not isinstance(data, dict):
        raise AIInvalidResponseError(f"Groq response was not a JSON object: {data!r}")

    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        raise AIInvalidResponseError(f"Groq response missing choices: {data!r}")

    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        raise AIInvalidResponseError(f"Groq response choice was not an object: {data!r}")

    message = first_choice.get("message")
    if not isinstance(message, dict):
        raise AIInvalidResponseError(f"Groq response missing message: {data!r}")

    content = message.get("content")
    if not isinstance(content, str):
        raise AIInvalidResponseError(f"Groq response missing message content: {data!r}")

    return content
