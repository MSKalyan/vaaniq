"""Sarvam streaming TTS (WebSocket) provider.

Endpoint: wss://api.sarvam.ai/text-to-speech/ws
Client -> server: {"type": "config", "data": {...}} then {"type": "text", "data": {"text"}}
                  then {"type": "flush"}
Server -> client: {"type": "audio", "data": {"audio": "<base64 chunk>"}} progressively,
                  then an event message with event_type "final" (when the connection was
                  opened with send_completion_event).

Text is capped at 2500 characters per `convert`; keep replies short so a barge-in
discards less already-generated audio (the API has no server-side cancel message).
Reference: https://docs.sarvam.ai/api/api-guides-tutorials/text-to-speech/streaming-api/web-socket
"""

import asyncio
import base64
import json
import re
from collections.abc import AsyncIterator
from typing import Any
from urllib.parse import urlencode

import websockets
from websockets.exceptions import ConnectionClosed

from app.core.config import settings
from app.integrations.base import TTSProvider
from app.integrations.sarvam.client import SarvamError

MAX_CHARS = 2500
# No audio for this long after the last chunk means synthesis is finished.
_IDLE_TIMEOUT_SECONDS = 3.0


class SarvamTTS(TTSProvider):
    """Streaming TTS provider yielding provider-format audio chunks."""

    def __init__(
        self,
        *,
        model: str | None = None,
        wss_url: str | None = None,
        api_key: str | None = None,
        voice: str | None = None,
        language: str = "en-IN",
        pace: float = 1.0,
        output_codec: str | None = None,
        sample_rate: int | None = None,
    ) -> None:
        self.model = model or settings.sarvam_tts_model
        host = re.sub(r"^https?://", "", settings.sarvam_base_url.rstrip("/"))
        self.wss_url = wss_url or f"wss://{host}/text-to-speech/ws"
        self.api_key = api_key if api_key is not None else settings.sarvam_api_key
        self.voice = voice or settings.sarvam_tts_voice
        self.language = language
        self.pace = pace
        self.output_codec = output_codec or settings.sarvam_audio_encoding.lower()
        self.sample_rate = sample_rate or settings.sarvam_audio_sample_rate

    def _build_url(self) -> str:
        # websockets.connect() has no additional_query argument, so query parameters
        # have to be part of the URI. send_completion_event asks the server for a
        # terminal "final" message instead of an idle socket.
        params = {"model": self.model, "send_completion_event": "true"}
        return f"{self.wss_url}?{urlencode(params)}"

    async def synthesize_stream(
        self,
        *,
        text: str,
        voice: str | None = None,
        language: str | None = None,
    ) -> AsyncIterator[bytes]:
        if len(text) > MAX_CHARS:
            raise ValueError(f"TTS text exceeds the {MAX_CHARS}-character limit per request")

        if not self.api_key:
            raise SarvamError("SARVAM_API_KEY is not configured")

        lang: str | None = language or self.language
        if lang == "auto":
            # "auto" is meaningful for STT/LLM dispatch, but Sarvam TTS needs a
            # concrete BCP-47 code; fall back to the provider default (en-IN).
            lang = self.language

        config_data: dict[str, Any] = {
            "speaker": voice or self.voice,
            "language_code": lang,
            "pace": self.pace,
            "output_audio_codec": self.output_codec,
            "speech_sample_rate": self.sample_rate,
        }
        # bulbul:v3 defaults to 24kHz, so the telephony rate (8kHz) must be sent
        # explicitly or Twilio will play 24kHz-sampled audio ~3x too slow (growl).

        try:
            async with websockets.connect(
                self._build_url(),
                additional_headers={"api-subscription-key": self.api_key},
                max_size=2 * 1024 * 1024,
            ) as ws:
                await ws.send(json.dumps({"type": "config", "data": config_data}))
                await ws.send(json.dumps({"type": "text", "data": {"text": text}}))
                await ws.send(json.dumps({"type": "flush"}))

                while True:
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=_IDLE_TIMEOUT_SECONDS)
                    except TimeoutError:
                        # No further audio will arrive for this utterance.
                        return
                    except ConnectionClosed:
                        return

                    kind, payload = _classify(raw)
                    if kind == "audio" and payload:
                        yield base64.b64decode(payload)
                    elif kind == "error":
                        raise SarvamError(str(payload))
                    elif kind in ("completion", "close", "final"):
                        return
        except ConnectionClosed:
            return

    async def aclose(self) -> None:
        """No-op: each utterance owns its own short-lived connection."""


def _classify(raw: str | bytes) -> tuple[str, str]:
    """Return (message_kind, payload) for one server message.

    Kinds: "audio" (base64 payload), "error" (message), "completion"/"close"/"final"
    (end of stream), or "unknown".
    """
    if not isinstance(raw, str):
        return "unknown", ""
    try:
        msg = json.loads(raw)
    except json.JSONDecodeError:
        return "unknown", ""
    if not isinstance(msg, dict):
        return "unknown", ""

    msg_type = msg.get("type")
    if msg_type == "audio":
        data = msg.get("data")
        audio = data.get("audio", "") if isinstance(data, dict) else ""
        return "audio", str(audio)
    if msg_type == "error":
        return "error", str(msg.get("message", msg))
    if msg_type in ("completion", "close"):
        return str(msg_type), ""
    if msg.get("event_type") == "final":
        return "final", ""
    return "unknown", ""
