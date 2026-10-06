"""Reusable fake providers for tests.

Implement the real provider interfaces (including the async-iterator shape of the
streaming methods and `model_name`), so tests exercise the same contracts production
code depends on.
"""

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from app.integrations.base import LLMProvider, STTProvider, TelephonyProvider, TTSProvider


class FakeLLM(LLMProvider):
    """Echoes the last user message. Optionally returns a scripted JSON payload."""

    def __init__(self, *, reply: str | None = None, json_payload: dict[str, Any] | None = None):
        self.reply = reply
        self.json_payload = json_payload
        self.calls: list[dict[str, Any]] = []

    @property
    def model_name(self) -> str:
        return "fake-llm"

    async def generate(
        self,
        *,
        system_prompt: str,
        messages: list[dict[str, str]],
        temperature: float | None = None,
        max_tokens: int | None = None,
        response_format: dict[str, Any] | None = None,
    ) -> str:
        self.calls.append({"system_prompt": system_prompt, "messages": list(messages)})
        if self.json_payload is not None:
            import json

            return json.dumps(self.json_payload)
        if self.reply is not None:
            return self.reply
        last_user = messages[-1]["content"] if messages else ""
        return f"echo:{last_user}"


class FakeTTS(TTSProvider):
    """Yields one chunk per whitespace-separated token."""

    def __init__(self, *, chunk_delay: float = 0.0) -> None:
        self.chunk_delay = chunk_delay
        self.spoken: list[str] = []

    async def synthesize_stream(
        self, *, text: str, voice: str | None = None, language: str | None = None
    ) -> AsyncIterator[bytes]:
        self.spoken.append(text)
        for part in text.split(" "):
            yield part.encode()
            if self.chunk_delay:
                await asyncio.sleep(self.chunk_delay)


class ScriptedSTT(STTProvider):
    """Emits a scripted list of events, then ends the stream."""

    def __init__(self, events: list[dict[str, Any]]):
        self.events = events
        self.fed: list[bytes] = []
        self.closed = False
        self.started = False

    async def transcribe_stream(
        self, *, language: str | None = None, key_terms: list[str] | None = None
    ) -> AsyncIterator[dict[str, Any]]:
        self.started = True
        for event in self.events:
            yield event
            if event.get("event") == "pause":
                await asyncio.sleep(event.get("seconds", 0.05))

    async def feed_audio(self, chunk: bytes) -> None:
        self.fed.append(chunk)

    async def close(self) -> None:
        self.closed = True


class FinalsSTT(ScriptedSTT):
    """Convenience: finalized utterances in, `session.end` out."""

    def __init__(self, finals: list[str]):
        events: list[dict[str, Any]] = [
            {"event": "transcript.final", "text": text} for text in finals
        ]
        events.append({"event": "session.end"})
        super().__init__(events)


class FakeTelephony(TelephonyProvider):
    """Records calls instead of dialling Twilio."""

    def __init__(self, *, call_id: str = "CA00000000000000000000000000000001") -> None:
        self.call_id = call_id
        self.initiated: list[dict[str, Any]] = []
        self.ended: list[str] = []
        self.transferred: list[tuple[str, str]] = []

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
        self.initiated.append(
            {
                "to_phone": to_phone,
                "from_phone": from_phone,
                "webhook_url": webhook_url,
                "timeout_seconds": timeout_seconds,
                "stream_url": stream_url,
                "status_callback_url": status_callback_url,
            }
        )
        return self.call_id

    async def end_call(self, *, call_id: str) -> None:
        self.ended.append(call_id)

    async def transfer_call(self, *, call_id: str, to_phone: str) -> None:
        self.transferred.append((call_id, to_phone))

    async def get_call_status(self, *, call_id: str) -> dict[str, Any]:
        return {"sid": call_id, "status": "in-progress"}

    def validate_request_signature(self, url: str, params: dict[str, str], signature: str) -> bool:
        return signature == "valid"
