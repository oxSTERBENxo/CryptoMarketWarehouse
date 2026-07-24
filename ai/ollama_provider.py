import time

import requests

from ai.provider import (
    AIGenerationResult,
    AIInvalidResponseError,
    AIModelNotFoundError,
    AIProvider,
    AIProviderUnavailableError,
    AITimeoutError,
)
from utils.logging_config import get_logger

logger = get_logger("ai.ollama")


class OllamaProvider(AIProvider):
    """AIProvider backed by a local Ollama server's /api/generate endpoint."""

    name = "ollama"

    def __init__(self, base_url: str, model: str, timeout_seconds: float) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds

    def generate(self, system_prompt: str, user_prompt: str) -> AIGenerationResult:
        payload = {
            "model": self.model,
            "prompt": user_prompt,
            "system": system_prompt,
            "stream": False,
        }

        started = time.monotonic()
        try:
            response = requests.post(
                f"{self.base_url}/api/generate", json=payload, timeout=self.timeout_seconds
            )
        except requests.exceptions.Timeout as exc:
            raise AITimeoutError(
                f"Ollama did not respond within {self.timeout_seconds}s (model={self.model!r})"
            ) from exc
        except requests.exceptions.ConnectionError as exc:
            raise AIProviderUnavailableError(
                f"Could not reach Ollama at {self.base_url}: {exc}"
            ) from exc
        except requests.exceptions.RequestException as exc:
            raise AIProviderUnavailableError(f"Ollama request failed: {exc}") from exc
        response_time_ms = (time.monotonic() - started) * 1000

        # Ollama returns 404 both for an unknown route and for a model that hasn't been pulled;
        # in practice the latter is what callers hit, so surface it as a model-config problem
        # rather than a generic HTTP error.
        if response.status_code == 404:
            raise AIModelNotFoundError(
                f"Ollama has no model {self.model!r} available at {self.base_url} "
                f"(is it pulled? try: ollama pull {self.model})"
            )
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as exc:
            raise AIInvalidResponseError(f"Ollama returned an HTTP error: {exc}") from exc

        try:
            data = response.json()
        except ValueError as exc:
            raise AIInvalidResponseError("Ollama response was not valid JSON") from exc

        text = data.get("response")
        if not isinstance(text, str):
            raise AIInvalidResponseError(
                f"Ollama response missing a string 'response' field: {data!r}"
            )

        prompt_tokens = data.get("prompt_eval_count")
        completion_tokens = data.get("eval_count")

        logger.info(
            "AI generate: provider=%s model=%s response_time_ms=%.1f prompt_tokens=%s completion_tokens=%s",
            self.name,
            self.model,
            response_time_ms,
            prompt_tokens,
            completion_tokens,
        )

        return AIGenerationResult(
            text=text,
            provider=self.name,
            model=self.model,
            response_time_ms=response_time_ms,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
