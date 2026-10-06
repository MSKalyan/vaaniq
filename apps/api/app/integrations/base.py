"""Provider interfaces.

Every external AI/telephony service implements one of these interfaces. Business
logic depends only on the interface, never on a concrete provider — so providers
(Sarvam, Twilio today; OpenAI, Deepgram, ElevenLabs, Exotel later) can be swapped
without rewriting core code.

Note on streaming providers: `transcribe_stream` / `synthesize_stream` are declared
as plain (non-async) methods returning an `AsyncIterator`, because the concrete
providers are async generators. Declaring them `async def` would type them as
coroutines and make `async for` over them a type error.
"""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any


class ProviderError(Exception):
    """Base class for provider-level failures (transport, auth, bad response)."""


class LLMProvider(ABC):
    """Conversational LLM producing structured responses."""

    @abstractmethod
    async def generate(
        self,
        *,
        system_prompt: str,
        messages: list[dict[str, str]],
        temperature: float | None = None,
        max_tokens: int | None = None,
        response_format: dict[str, Any] | None = None,
    ) -> str:
        """Return the assistant text response.

        `response_format` is an OpenAI-compatible dict, e.g.
        `{"type": "json_schema", "json_schema": {...}}`.
        """

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Identifier of the underlying model (recorded on calls for traceability)."""


class STTProvider(ABC):
    """Speech-to-text. Realtime implementations stream partial/final transcripts."""

    @abstractmethod
    def transcribe_stream(
        self,
        *,
        language: str | None = None,
        key_terms: list[str] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Yield transcription events: {"event", "text", "is_final", "language", ...}.

        Documented server events: `session.begin`, `vad.speech_start`,
        `vad.speech_end`, `transcript.partial`, `transcript.final`, `config.updated`,
        `pong`, `session.end`, `error`.
        """

    @abstractmethod
    async def feed_audio(self, chunk: bytes) -> None:
        """Feed a raw audio chunk into the streaming recognizer."""

    @abstractmethod
    async def close(self) -> None:
        """Signal end of audio and tear down the underlying connection."""


class TTSProvider(ABC):
    """Text-to-speech. Streaming implementations yield audio chunks."""

    @abstractmethod
    def synthesize_stream(
        self, *, text: str, voice: str | None = None, language: str | None = None
    ) -> AsyncIterator[bytes]:
        """Yield raw audio chunks (provider format) for the given text."""


class TelephonyProvider(ABC):
    """Telephony lifecycle: call initiation, status, transfer, teardown, webhooks."""

    @abstractmethod
    async def initiate_call(
        self,
        *,
        to_phone: str,
        from_phone: str,
        webhook_url: str,
        timeout_seconds: int | None = None,
        stream_url: str | None = None,
        status_callback_url: str | None = None,
    ) -> str:
        """Start an outbound call; return the provider call id (e.g. Twilio Call SID)."""

    @abstractmethod
    async def end_call(self, *, call_id: str) -> None:
        """Terminate an active call."""

    @abstractmethod
    async def transfer_call(self, *, call_id: str, to_phone: str) -> None:
        """Transfer a live call to a human/different destination."""

    @abstractmethod
    async def get_call_status(self, *, call_id: str) -> dict[str, Any]:
        """Return provider call state/status metadata."""

    @abstractmethod
    def validate_request_signature(self, url: str, params: dict[str, str], signature: str) -> bool:
        """Verify the provider's webhook signature for an inbound request."""


class EmbeddingProvider(ABC):
    """Embeddings for knowledge-base retrieval."""

    @abstractmethod
    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Return one embedding vector per input text."""

    @abstractmethod
    async def embed_query(self, text: str) -> list[float]:
        """Embed a search query (may use a different model)."""

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Embedding vector dimension (must match the pgvector column)."""
