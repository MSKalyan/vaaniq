"""Settings + provider status endpoints.

Read-only view of which providers are wired and whether their credentials exist.
Secrets are never returned — only booleans and model identifiers.
"""

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.models.agent import AgentVoice
from app.models.user import User

router = APIRouter()


class ProviderStatus(BaseModel):
    capability: str
    provider: str
    configured: bool
    model: str | None = None
    detail: str | None = None


class SettingsOut(BaseModel):
    app_name: str
    app_env: str
    frontend_url: str
    default_max_call_duration_seconds: int
    default_silence_timeout_seconds: int
    providers: list[ProviderStatus]


@router.get("", response_model=SettingsOut)
async def get_settings(user: User = Depends(get_current_user)) -> SettingsOut:
    """Non-secret runtime settings the dashboard displays."""
    _ = user  # authenticated access required even though values are global
    return SettingsOut(
        app_name=settings.app_name,
        app_env=settings.app_env,
        frontend_url=settings.frontend_url,
        default_max_call_duration_seconds=settings.default_max_call_duration_seconds,
        default_silence_timeout_seconds=settings.default_silence_timeout_seconds,
        providers=[
            ProviderStatus(
                capability="llm",
                provider=settings.llm_provider,
                configured=settings.has_sarvam_credentials,
                model=settings.sarvam_llm_model,
            ),
            ProviderStatus(
                capability="stt",
                provider=settings.stt_provider,
                configured=settings.has_sarvam_credentials,
                model=settings.sarvam_stt_model,
            ),
            ProviderStatus(
                capability="tts",
                provider=settings.tts_provider,
                configured=settings.has_sarvam_credentials,
                model=f"{settings.sarvam_tts_model} / {settings.sarvam_tts_voice}",
            ),
            ProviderStatus(
                capability="telephony",
                provider=settings.telephony_provider,
                configured=settings.has_twilio_credentials,
                detail=settings.twilio_phone_number or "No caller number configured",
            ),
            ProviderStatus(
                capability="embedding",
                provider=settings.embedding_provider,
                configured=True,
                model=f"{settings.embedding_dimension}-dim",
            ),
        ],
    )


@router.get("/voices", response_model=list[dict[str, Any]])
async def list_voices(
    provider: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """Voice catalog for the agent builder."""
    _ = user
    query = select(AgentVoice).order_by(AgentVoice.language, AgentVoice.voice_name)
    if provider:
        query = query.where(AgentVoice.provider == provider)
    voices = (await db.scalars(query)).all()
    return [
        {
            "id": str(voice.id),
            "provider": voice.provider,
            "voice_name": voice.voice_name,
            "language": voice.language,
            "metadata": voice.voice_metadata,
        }
        for voice in voices
    ]
