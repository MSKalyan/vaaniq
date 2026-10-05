"""Provider registry.

Central place to build provider instances. Business logic asks for a provider by
capability and a configured name; adding a new provider means registering it here,
not scattering construction across the codebase.
"""

from functools import lru_cache

from app.core.config import settings
from app.integrations.base import (
    EmbeddingProvider,
    LLMProvider,
    STTProvider,
    TelephonyProvider,
    TTSProvider,
)


class ProviderNotConfiguredError(Exception):
    pass


@lru_cache
def get_llm() -> LLMProvider:
    # Only Sarvam is wired initially; a settings key (LLM_PROVIDER) will select
    # among OpenAI/Anthropic/etc. later without touching call sites.
    from app.integrations.sarvam.llm import SarvamLLM

    return SarvamLLM(model=settings.sarvam_llm_model)


@lru_cache
def get_stt() -> STTProvider:
    from app.integrations.sarvam.stt import SarvamRealtimeSTT

    return SarvamRealtimeSTT(model=settings.sarvam_stt_model)


@lru_cache
def get_tts() -> TTSProvider:
    from app.integrations.sarvam.tts import SarvamTTS

    return SarvamTTS(model=settings.sarvam_tts_model, voice=settings.sarvam_tts_voice)


@lru_cache
def get_telephony() -> TelephonyProvider:
    if not (settings.twilio_account_sid and settings.twilio_auth_token):
        raise ProviderNotConfiguredError("Twilio credentials are not configured")
    from app.integrations.twilio.provider import TwilioProvider

    return TwilioProvider(
        account_sid=settings.twilio_account_sid,
        auth_token=settings.twilio_auth_token,
        from_phone=settings.twilio_phone_number,
        webhook_base_url=settings.twilio_webhook_base_url,
    )


def get_embedding_model() -> EmbeddingProvider:
    raise ProviderNotConfiguredError(
        "Embedding provider is not configured; configure one for knowledge-base RAG."
    )
