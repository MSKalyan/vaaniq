"""Sarvam Realtime streaming STT (WebSocket).

Endpoint: wss://api.sarvam.ai/speech-to-text-realtime/ws?<query>
Client -> server: {"event":"audio_input","audio":"<base64>"}
Server -> client: session.begin, vad.speech_start/end, transcript.partial,
                  transcript.final, session.end, error
Barge-in driven off vad.speech_start / early partials (NOT transcript.final).
Reference: https://docs.sarvam.ai/api/api-guides-tutorials/speech-to-text/realtime-streaming
"""

import asyncio
import base64
import json
from collections.abc import AsyncIterator
from typing import Any

import websockets

from app.core.config import settings
from app.integrations.base import STTProvider


class SarvamRealtimeSTT(STTProvider):
    """Realtime STT provider.

    Typical usage by the voice orchestrator:

        stt = SarvamRealtimeSTT()
        stream = stt.transcribe_stream(...)
        task = asyncio.create_task(consume(stream))
        await stt.feed_audio(pcm_chunk)
        ...
        await stt.close()

    `transcribe_stream` is the async-generator face of the interface (it yields
    server events); `feed_audio` accepts inbound audio chunks from Twilio.
    """

    def __init__(
        self,
        *,
        model: str | None = None,
        wss_url: str | None = None,
        api_key: str | None = None,
        language: str = "auto",
        encoding: str | None = None,
        sample_rate: int | None = None,
        key_terms: list[str] | None = None,
    ) -> None:
        self.model = model or settings.sarvam_stt_model
        self.wss_url = wss_url or settings.sarvam_realtime_stt_wss
        self.api_key = api_key or settings.sarvam_api_key
        self.language = language
        self.encoding = encoding or settings.sarvam_audio_encoding
        self.sample_rate = sample_rate or settings.sarvam_audio_sample_rate
        self.key_terms = key_terms or []

        self._ws: Any | None = None
        self._audio_queue: asyncio.Queue[bytes | None] | None = None
        self._send_lock = asyncio.Lock()

    def _build_url(self) -> str:
        params = {
            "model": self.model,
            "language_code": self.language,
            "endpointing": "vad",
            "encoding": self.encoding,
            "sample_rate": str(self.sample_rate),
        }
        if self.key_terms:
            params["keyterms"] = json.dumps(self.key_terms)
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{self.wss_url}?{qs}"

    async def _connect(self) -> None:
        if not self.api_key:
            raise RuntimeError("SARVAM_API_KEY is not configured")
        self._ws = await websockets.connect(
            self._build_url(),
            additional_headers={"api-subscription-key": self.api_key},
            max_size=2 * 1024 * 1024,
        )
        self._audio_queue = asyncio.Queue()

    async def feed_audio(self, pcm_chunk: bytes) -> None:
        """Queue an inbound audio chunk for transmission to Sarvam."""
        if self._audio_queue is None:
            raise RuntimeError("STT stream not started")
        await self._audio_queue.put(pcm_chunk)

    async def _sender(self) -> None:
        if self._ws is None or self._audio_queue is None:
            return
        while True:
            chunk = await self._audio_queue.get()
            if chunk is None:
                return
            payload = base64.b64encode(chunk).decode()
            msg = f'{{"event":"audio_input","audio":"{payload}"}}'
            async with self._send_lock:
                await self._ws.send(msg)

    async def transcribe_stream(
        self,
        *,
        language: str | None = None,
        key_terms: list[str] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Yield Sarvam STT events (transcript.partial/final, vad.*, session.*, error).

        Starts a background sender draining `feed_audio`. Yields until the session
        ends or `close()` is called.
        """
        if language is not None:
            self.language = language
        if key_terms is not None:
            self.key_terms = key_terms

        await self._connect()
        sender = asyncio.create_task(self._sender())

        try:
            # Consume session.begin handshake.
            first = await self._read_event()
            if first is not None:
                yield first
            while True:
                event = await self._read_event()
                if event is None:
                    break
                yield event
        finally:
            sender.cancel()
            if self._ws is not None:
                try:
                    await self._ws.close()
                except Exception:  # noqa: S110 - best-effort teardown
                    pass
                self._ws = None

    async def _read_event(self) -> dict[str, Any] | None:
        if self._ws is None:
            return None
        try:
            raw = await asyncio.wait_for(self._ws.recv(), timeout=300)
        except TimeoutError:
            # Long silence; return an empty marker rather than failing the call.
            return {"event": "timeout", "text": ""}
        if not isinstance(raw, str):
            return None
        return json.loads(raw)

    async def close(self) -> None:
        """Signal end of audio and close the WebSocket."""
        if self._audio_queue is not None:
            await self._audio_queue.put(None)
        if self._ws is not None:
            try:
                async with self._send_lock:
                    await self._ws.send('{"event":"end"}')
            except Exception:  # noqa: S110 - best-effort session end
                pass
            try:
                await self._ws.close()
            finally:
                self._ws = None
