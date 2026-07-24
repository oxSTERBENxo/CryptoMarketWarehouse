from abc import ABC, abstractmethod
from dataclasses import dataclass

"""Provider-agnostic AI interface. Every AI request in the app must go through an AIProvider
subclass obtained from ai_config.get_ai_provider() -- nothing else should instantiate a concrete
provider (OllamaProvider, and later GroqProvider/OpenAIProvider/GeminiProvider) directly. That
keeps the rest of the backend (routes, prompt builder, business logic) unaware of which backend
is actually serving requests, so swapping providers is a config change, not a code change.
"""


class AIProviderError(Exception):
    """Base for every AI-provider failure. Callers that don't care about the specific cause can
    catch just this."""


class AIProviderUnavailableError(AIProviderError):
    """The provider's endpoint could not be reached at all (connection refused, DNS failure,
    network down, ...)."""


class AITimeoutError(AIProviderError):
    """The provider did not respond within the configured timeout."""


class AIModelNotFoundError(AIProviderError):
    """The configured model is not available on the provider (e.g. not pulled in Ollama, or an
    invalid model name for a hosted provider)."""


class AIInvalidResponseError(AIProviderError):
    """The provider responded, but the response body didn't match the expected shape."""


class AIProviderConfigurationError(AIProviderError):
    """The selected provider is missing required configuration, such as an API key."""


class UnknownAIProviderError(AIProviderError):
    """Raised by the factory (ai_config.get_ai_provider) when AI_PROVIDER names a provider that
    has no implementation registered."""

    def __init__(self, provider_name: str) -> None:
        super().__init__(f"Unknown AI_PROVIDER: {provider_name!r}")
        self.provider_name = provider_name


@dataclass
class AIGenerationResult:
    """The outcome of one AIProvider.generate() call, including the metadata routes/logging need
    (response time, token counts) alongside the text itself."""

    text: str
    provider: str
    model: str
    response_time_ms: float
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


class AIProvider(ABC):
    """Common interface every AI backend must implement."""

    name: str

    @abstractmethod
    def generate(self, system_prompt: str, user_prompt: str) -> AIGenerationResult:
        """Run one prompt through the model and return the completion plus timing/token metadata.

        Must raise one of AIProviderUnavailableError, AITimeoutError, AIModelNotFoundError,
        AIProviderConfigurationError, or AIInvalidResponseError (all AIProviderError) on failure --
        never let a raw exception from the underlying HTTP client / SDK escape, so callers only
        ever need to handle this module's exception hierarchy regardless of which provider is
        active.
        """
