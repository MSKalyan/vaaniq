"""Centralized application configuration.

All settings load from environment variables / `.env` (via pydantic-settings).
Secrets never leave the server; nothing here is returned to the frontend.
"""

from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- App ---
    app_name: str = "VoiceAI"
    app_env: str = "development"
    debug: bool = True
    api_v1_prefix: str = "/api/v1"
    frontend_url: str = "http://localhost:3000"
    backend_url: str = "http://localhost:8000"

    # --- Database ---
    database_url: str = "postgresql+asyncpg://nenu:nenu@localhost:5432/VoiceAI"
    database_url_sync: str = "postgresql+psycopg2://nenu:nenu@localhost:5432/VoiceAI"

    database_host: str | None = None
    database_port: int = 5432
    database_user: str = "nenu"
    database_password: str = "nenu"
    database_name: str = "VoiceAI"

    @model_validator(mode="after")
    def build_database_urls(self) -> "Settings":
        if self.database_host is not None:
            self.database_url = URL.create(
                "postgresql+asyncpg",
                username=self.database_user,
                password=self.database_password,
                host=self.database_host,
                port=self.database_port,
                database=self.database_name,
            ).render_as_string(hide_password=False)
            self.database_url_sync = URL.create(
                "postgresql+psycopg2",
                username=self.database_user,
                password=self.database_password,
                host=self.database_host,
                port=self.database_port,
                database=self.database_name,
            ).render_as_string(hide_password=False)
        return self

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

    # --- Provider selection ---
    # Swap a capability by changing one env var; no call site changes.
    llm_provider: str = "sarvam"
    stt_provider: str = "sarvam"
    tts_provider: str = "sarvam"
    telephony_provider: str = "twilio"
    # `hashing` is the offline default (no API key, lexical only).
    embedding_provider: str = "hashing"
    # Must match knowledge_chunks.embedding's width in migration 0001 (Vector(1536)),
    # which is also the width of common hosted embedding models.
    embedding_dimension: int = 1536

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
