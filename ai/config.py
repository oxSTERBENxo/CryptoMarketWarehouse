import os

from dotenv import load_dotenv

from ai.provider import AIProvider, UnknownAIProviderError

"""AI provider configuration and factory. This is the ONLY place in the app that reads
AI_PROVIDER / provider-specific env vars or instantiates a concrete AIProvider -- everything else
(routes, prompt builder, future business logic) calls get_ai_provider() and only ever touches the
AIProvider interface, so switching providers later is a config change here plus one new provider
module, never a change to callers.
"""

load_dotenv()

AI_PROVIDER = os.environ.get("AI_PROVIDER", "ollama").strip().lower()

OLLAMA_BASE_URL = os.environ.get(
    "OLLAMA_BASE_URL", os.environ.get("OLLAMA_URL", "http://localhost:11434")
).strip()
OLLAMA_URL = OLLAMA_BASE_URL
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.1:8b").strip()
OLLAMA_TIMEOUT_SECONDS = float(os.environ.get("OLLAMA_TIMEOUT_SECONDS", "60"))

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "").strip()
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile").strip()
GROQ_TIMEOUT_SECONDS = float(os.environ.get("GROQ_TIMEOUT_SECONDS", "60"))


def get_ai_provider() -> AIProvider:
    """Build the AIProvider selected by AI_PROVIDER. Raises UnknownAIProviderError if it names a
    provider with no implementation registered below."""
    if AI_PROVIDER == "ollama":
        from ai.ollama_provider import OllamaProvider

        return OllamaProvider(
            base_url=OLLAMA_BASE_URL, model=OLLAMA_MODEL, timeout_seconds=OLLAMA_TIMEOUT_SECONDS
        )
    if AI_PROVIDER == "groq":
        from ai.groq_provider import GroqProvider

        return GroqProvider(
            api_key=GROQ_API_KEY, model=GROQ_MODEL, timeout_seconds=GROQ_TIMEOUT_SECONDS
        )

    raise UnknownAIProviderError(AI_PROVIDER)
