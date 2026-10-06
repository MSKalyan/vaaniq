"""Provider registry.

Central place to build provider instances. Business logic asks for a provider by
capability and a configured name; adding a new provider means registering it here,
not scattering construction across the codebase.

Each getter is cached, so a single provider instance (and its HTTP client pool) is
reused across a request.
"""

from functools import lru_cache

from app.core.config import settings
from app.integrations.base import (
    EmbeddingProvider,
    LLMProvider,
    ProviderError,
    STTProvider,
    TelephonyProvider,
    TTSProvider,
)


class ProviderNotConfiguredError(ProviderError):
    """Raised when a capability is requested but its provider is not configured."""


@lru_cache
def get_llm() -> LLMProvider:
    provider = settings.llm_provider.lower()
    if provider != "sarvam":
        raise ProviderNotConfiguredError(
            f"LLM provider '{provider}' is not implemented; available: sarvam"
        )
    from app.integrations.sarvam.llm import SarvamLLM

    return SarvamLLM(model=settings.sarvam_llm_model)


@lru_cache
def get_stt() -> STTProvider:
    provider = settings.stt_provider.lower()
    if provider != "sarvam":
        raise ProviderNotConfiguredError(
            f"STT provider '{provider}' is not implemented; available: sarvam"
        )
    from app.integrations.sarvam.stt import SarvamRealtimeSTT

    return SarvamRealtimeSTT(model=settings.sarvam_stt_model)


@lru_cache
def get_tts() -> TTSProvider:
    provider = settings.tts_provider.lower()
    if provider != "sarvam":
        raise ProviderNotConfiguredError(
            f"TTS provider '{provider}' is not implemented; available: sarvam"
        )
    from app.integrations.sarvam.tts import SarvamTTS

    return SarvamTTS(model=settings.sarvam_tts_model, voice=settings.sarvam_tts_voice)


@lru_cache
def get_telephony() -> TelephonyProvider:
    provider = settings.telephony_provider.lower()
    if provider != "twilio":
        raise ProviderNotConfiguredError(
            f"Telephony provider '{provider}' is not implemented; available: twilio"
        )
    if not (settings.twilio_account_sid and settings.twilio_auth_token):
        raise ProviderNotConfiguredError("Twilio credentials are not configured")
    from app.integrations.twilio.provider import TwilioProvider

    return TwilioProvider(
        account_sid=settings.twilio_account_sid,
        auth_token=settings.twilio_auth_token,
        from_phone=settings.twilio_phone_number,
        webhook_base_url=settings.twilio_webhook_base_url,
    )


@lru_cache
def get_embedding_model() -> EmbeddingProvider:
    provider = settings.embedding_provider.lower()
    if provider == "hashing":
        from app.integrations.embeddings.hashing import HashingEmbedding

        return HashingEmbedding(dimension=settings.embedding_dimension)
    raise ProviderNotConfiguredError(
        f"Embedding provider '{provider}' is not implemented; available: hashing"
    )


def reset_provider_cache() -> None:
    """Clear cached instances (used by tests and after a settings reload)."""
    for getter in (get_llm, get_stt, get_tts, get_telephony, get_embedding_model):
        getter.cache_clear()
