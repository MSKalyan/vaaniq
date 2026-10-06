"""Sarvam Realtime streaming STT (WebSocket).

Endpoint: GET wss://api.sarvam.ai/speech-to-text-realtime/ws?<query>
Client -> server: {"event": "audio_input", "audio": "<base64>"}
                  {"event": "end"} (graceful close)
Server -> client: session.begin, vad.speech_start, vad.speech_end,
                  transcript.partial, transcript.final, config.updated,
                  pong, session.end, error

Barge-in is driven off `vad.speech_start` / early partials, NOT `transcript.final`.
Only `sample_rate` 8000 or 16000 is accepted; `mulaw` 8kHz matches what Twilio
delivers so no resampling is needed on our side.
Reference: https://docs.sarvam.ai/api/api-guides-tutorials/speech-to-text/realtime-streaming
"""

import asyncio
import base64
import json
from collections.abc import AsyncIterator
from typing import Any, cast
from urllib.parse import urlencode

import websockets
from websockets.exceptions import ConnectionClosed

from app.core.config import settings
from app.integrations.base import STTProvider
from app.integrations.sarvam.client import SarvamError

_MAX_MESSAGE_BYTES = 2 * 1024 * 1024


class SarvamRealtimeSTT(STTProvider):
    """Realtime STT provider.

    Typical usage by the voice orchestrator:

        stt = SarvamRealtimeSTT(language="te-IN")
        task = asyncio.create_task(pump(stt.transcribe_stream()))
        await stt.feed_audio(chunk)
        ...
        await stt.close()
    """

    def __init__(
        self,
        *,
        model: str | None = None,
        wss_url: str | None = None,
        api_key: str | None = None,
        language: str = "en-IN",
        encoding: str | None = None,
        sample_rate: int | None = None,
        stream_type: str = "fast",
        key_terms: list[str] | None = None,
        recv_timeout_seconds: float = 300.0,
    ) -> None:
        self.model = model or settings.sarvam_stt_model
        self.wss_url = wss_url or settings.sarvam_realtime_stt_wss
        self.api_key = api_key or settings.sarvam_api_key
        self.language = language
        self.encoding = encoding or settings.sarvam_audio_encoding
        self.sample_rate = sample_rate or settings.sarvam_audio_sample_rate
        self.stream_type = stream_type
        self.key_terms = key_terms or []
        self.recv_timeout_seconds = recv_timeout_seconds

        self._ws: Any | None = None
        self._audio_queue: asyncio.Queue[bytes | None] | None = None
        self._send_lock = asyncio.Lock()

    def _build_url(self) -> str:
        if self.sample_rate not in (8000, 16000):
            raise SarvamError(
                f"Sarvam STT only accepts sample_rate 8000 or 16000, got {self.sample_rate}"
            )
        params: dict[str, str] = {
            "model": self.model,
            "language_code": self.language,
            "stream_type": self.stream_type,
            "endpointing": "vad",
            "encoding": self.encoding,
            "sample_rate": str(self.sample_rate),
        }
        if self.key_terms:
            # keyterms is only supported on saaras:v4.
            params["keyterms"] = json.dumps(self.key_terms)
        # urlencode matters here: keyterms is JSON and would otherwise inject raw
        # quotes/brackets into the query string.
        return f"{self.wss_url}?{urlencode(params)}"

    async def _connect(self) -> None:
        if not self.api_key:
            raise SarvamError("SARVAM_API_KEY is not configured")
        self._ws = await websockets.connect(
            self._build_url(),
            additional_headers={"api-subscription-key": self.api_key},
            max_size=_MAX_MESSAGE_BYTES,
        )
        self._audio_queue = asyncio.Queue()

    async def feed_audio(self, chunk: bytes) -> None:
        """Queue an inbound audio chunk for transmission to Sarvam."""
        if self._audio_queue is None:
            raise RuntimeError("STT stream not started: await transcribe_stream() first")
        await self._audio_queue.put(chunk)

    async def _sender(self) -> None:
        if self._ws is None or self._audio_queue is None:
            return
        while True:
            chunk = await self._audio_queue.get()
            if chunk is None:
                return
            payload = base64.b64encode(chunk).decode()
            message = json.dumps({"event": "audio_input", "audio": payload})
            try:
                async with self._send_lock:
                    await self._ws.send(message)
            except ConnectionClosed:
                return

    async def transcribe_stream(
        self,
        *,
        language: str | None = None,
        key_terms: list[str] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Yield Sarvam STT events until `session.end`, `close()`, or a fatal error."""
        if language is not None:
            self.language = language
        if key_terms is not None:
            self.key_terms = key_terms

        await self._connect()
        sender = asyncio.create_task(self._sender())
        try:
            while True:
                event = await self._read_event()
                if event is None:
                    break
                if event.get("event") == "session.end":
                    yield event
                    break
                if event.get("event") == "error":
                    error_code = event.get("code")
                    is_fatal = bool(event.get("is_fatal", False))
                    logger_event = {
                        "event": "error",
                        "text": "",
                        "code": error_code,
                        "message": str(event.get("message", "unknown Sarvam STT error")),
                        "is_fatal": is_fatal,
                    }
                    yield cast(dict[str, Any], logger_event)
                    if is_fatal:
                        break
                    continue
                yield event
        finally:
            sender.cancel()
            await self._close_socket()

    async def _read_event(self) -> dict[str, Any] | None:
        if self._ws is None:
            return None
        try:
            raw = await asyncio.wait_for(self._ws.recv(), timeout=self.recv_timeout_seconds)
        except TimeoutError:
            # Long silence: emit a keepalive marker so the call is not torn down.
            return {"event": "timeout", "text": ""}
        except ConnectionClosed:
            return None
        if not isinstance(raw, str):
            return None
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return None
        return cast(dict[str, Any], data) if isinstance(data, dict) else None

    async def close(self) -> None:
        """Signal end of audio and close the WebSocket."""
        if self._audio_queue is not None and not self._audio_queue.full():
            await self._audio_queue.put(None)
        if self._ws is not None:
            try:
                async with self._send_lock:
                    await self._ws.send(json.dumps({"event": "end"}))
            except Exception:  # noqa: S110 - best-effort graceful close
                pass
        await self._close_socket()

    async def _close_socket(self) -> None:
        if self._ws is None:
            return
        try:
            await self._ws.close()
        except Exception:  # noqa: S110 - best-effort teardown
            pass
        finally:
            self._ws = None
            self._audio_queue = None
