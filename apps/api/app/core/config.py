"""Centralized application configuration.

All settings load from environment variables / `.env` (via pydantic-settings).
Secrets never leave the server; nothing here is returned to the frontend.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- App ---
    app_name: str = "NenuAIKadu"
    app_env: str = "development"
    debug: bool = True
    api_v1_prefix: str = "/api/v1"
    frontend_url: str = "http://localhost:3000"
    backend_url: str = "http://localhost:8000"

    # --- Database ---
    database_url: str = "postgresql+asyncpg://nenu:nenu@localhost:5432/nenuaikadu"
    database_url_sync: str = "postgresql+psycopg2://nenu:nenu@localhost:5432/nenuaikadu"

    # --- Redis ---
    redis_url: str = "redis://localhost:6379/0"

    # --- JWT ---
    jwt_secret: str = "insecure-change-me"  # noqa: S105 - placeholder, must be overridden
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7
    password_bcrypt_rounds: int = 12

    # --- CORS ---
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    # --- Sarvam AI ---
    sarvam_api_key: str = ""
    sarvam_base_url: str = "https://api.sarvam.ai"
    sarvam_llm_model: str = "sarvam-105b-conversations"
    sarvam_llm_max_tokens: int = 2048
    sarvam_stt_model: str = "saaras:v4"
    sarvam_tts_model: str = "bulbul:v3"
    sarvam_realtime_stt_wss: str = "wss://api.sarvam.ai/speech-to-text-realtime/ws"
    sarvam_tts_voice: str = "shubh"
    # Twilio delivers mu-law 8kHz mono; match Sarvam STT/TTS to avoid resampling.
    sarvam_audio_encoding: str = "mulaw"
    sarvam_audio_sample_rate: int = 8000

    # --- Twilio ---
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_phone_number: str = ""
    twilio_webhook_base_url: str = "http://localhost:8000"

    # --- Object storage ---
    storage_bucket: str = ""
    storage_endpoint_url: str = ""
    storage_region: str = ""
    storage_access_key: str = ""
    storage_secret_key: str = ""
    local_storage_dir: str = "./storage"

    # --- Worker ---
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    # --- Call defaults ---
    default_max_call_duration_seconds: int = 600
    default_silence_timeout_seconds: int = 8

    @property
    def has_sarvam_credentials(self) -> bool:
        return bool(self.sarvam_api_key)

    @property
    def has_twilio_credentials(self) -> bool:
        return bool(self.twilio_account_sid and self.twilio_auth_token)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
