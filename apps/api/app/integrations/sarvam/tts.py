"""Sarvam streaming TTS (WebSocket) provider.

Endpoint: wss://api.sarvam.ai/text-to-speech
Client -> server: {"type":"config","data":{...}} then {"type":"text","data":{"text"}}
                  then {"type":"flush"}
Server -> client: {"type":"audio","data":{"audio":"<base64 chunk>"}} progressively,
                  then a completion event.
Incremental/chunked audio (audio arrives as generated) — ideal for conversational
turn-taking so playback can start before synthesis completes.
Reference: https://docs.sarvam.ai/api/api-guides-tutorials/text-to-speech/streaming-api/web-socket
"""

import asyncio
import base64
import json
import re
from collections.abc import AsyncIterator

import websockets

from app.core.config import settings
from app.integrations.base import TTSProvider


class SarvamTTS(TTSProvider):
    """Streaming TTS provider. Yields audio chunks for given text."""

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
        # Streaming TTS WebSocket endpoint (wss).
        host = re.sub(r"^https?://", "", settings.sarvam_base_url.rstrip("/"))
        self.wss_url = wss_url or f"wss://{host}/text-to-speech"
        self.api_key = api_key or settings.sarvam_api_key
        self.voice = voice or settings.sarvam_tts_voice
        self.language = language
        self.pace = pace
        self.output_codec = output_codec or settings.sarvam_audio_encoding.upper()
        self.sample_rate = sample_rate or settings.sarvam_audio_sample_rate

    async def synthesize_stream(
        self,
        *,
        text: str,
        voice: str | None = None,
        language: str | None = None,
    ) -> AsyncIterator[bytes]:
        if len(text) > 2500:
            raise ValueError("TTS text exceeds bulbul:v3 max of 2500 characters")

        effective_voice = voice or self.voice
        effective_language = language or self.language

        if not self.api_key:
            raise RuntimeError("SARVAM_API_KEY is not configured")

        async with websockets.connect(
            self.wss_url,
            additional_headers={"api-subscription-key": self.api_key},
            max_size=2 * 1024 * 1024,
        ) as ws:
            config = {
                "type": "config",
                "data": {
                    "model": self.model,
                    "speaker": effective_voice,
                    "language_code": effective_language,
                    "pace": self.pace,
                    "output_audio_codec": self.output_codec.lower(),
                },
            }
            if self.sample_rate:
                config["data"]["speech_sample_rate"] = self.sample_rate
            await ws.send(json.dumps(config))

            await ws.send(json.dumps({"type": "text", "data": {"text": text}}))
            await ws.send(json.dumps({"type": "flush"}))

            while True:
                raw = await asyncio.wait_for(ws.recv(), timeout=60)
                msg = json.loads(raw) if isinstance(raw, str) else raw
                if not isinstance(msg, dict):
                    continue
                if msg.get("type") == "audio":
                    audio_b64 = msg["data"].get("audio", "")
                    if audio_b64:
                        yield base64.b64decode(audio_b64)
                elif msg.get("type") in ("completion", "completed", "finish"):
                    break
                elif msg.get("event_type") == "final":
                    break
                elif msg.get("type") == "error":
                    raise RuntimeError(f"Sarvam TTS error: {msg.get('message', msg)}")
                elif msg.get("type") == "close":
                    break
