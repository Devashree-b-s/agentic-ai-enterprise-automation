"""LLM Provider abstraction supporting Groq (primary) and Google Gemini (secondary)."""

import logging

from langchain_core.language_models.chat_models import BaseChatModel

from app.core.config import settings

logger = logging.getLogger("app.agents.llm")

# Test override hook for dependency injection
_custom_chat_model: BaseChatModel | None = None


def set_custom_chat_model(model: BaseChatModel | None) -> None:
    """Inject a custom or mock ChatModel for automated tests.

    Pass None to reset to production environment-based initialization.
    """
    global _custom_chat_model
    _custom_chat_model = model


def get_chat_model(temperature: float = 0.0) -> BaseChatModel:
    """Retrieve the configured ChatModel based on application settings.

    Never hardcodes, logs, or exposes API keys.
    Raises ValueError with a clear, safe message if the required key is missing.
    """
    if _custom_chat_model is not None:
        return _custom_chat_model

    provider = settings.LLM_PROVIDER.lower().strip()

    if provider == "groq":
        api_key = settings.GROQ_API_KEY
        if not api_key or not api_key.strip():
            logger.warning("Groq API key not configured in environment.")
            raise ValueError(
                "GROQ_API_KEY is not configured. Please configure your Groq API key in the environment."
            )
        from langchain_groq import ChatGroq

        return ChatGroq(
            api_key=api_key.strip(),
            model_name=settings.GROQ_MODEL,
            temperature=temperature,
        )

    if provider == "gemini":
        api_key = settings.GEMINI_API_KEY
        if not api_key or not api_key.strip():
            logger.warning("Gemini API key not configured in environment.")
            raise ValueError(
                "GEMINI_API_KEY is not configured. Please configure your Gemini API key in the environment."
            )
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            google_api_key=api_key.strip(),
            model=settings.GEMINI_MODEL,
            temperature=temperature,
        )

    raise ValueError(
        f"Unsupported LLM_PROVIDER '{provider}'. Supported providers are 'groq' and 'gemini'."
    )
