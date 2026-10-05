"""Twilio media-stream WebSocket bridge.

Bridges Twilio's bidirectional media stream to the ConversationOrchestrator:

  Twilio --media(mulaw/8k)-> {WebSocket} --> orch.feed_audio(chunk)
  orch._speak-> sink(chunk)   --{event:"media"}--> Twilio

Also translates the Twilio message protocol (connected/start/media/stop) into STT
events and handles barge-in by sending Twilio a `clear` after the orchestrator
interrupts TTS.
"""

import asyncio
import base64
import json
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

from app.core.logging import get_logger
from app.voice.orchestrator import ConversationOrchestrator

logger = get_logger("voice.media_stream")


class MediaStreamBridge:
    """One bridge per live call; drives the orchestrator from the Twilio stream."""

    def __init__(
        self,
        ws: WebSocket,
        orch: ConversationOrchestrator,
        *,
        sample_rate: int = 8000,
    ) -> None:
        self.ws = ws
        self.orch = orch
        self.sample_rate = sample_rate
        self._stream_sid: str | None = None
        self._call_sid: str | None = None
        self._stop = False

    async def run(self) -> None:
        """Accept the WS, then loop bridging Twilio media <-> orchestrator."""
        await self.ws.accept()

        # Orchestrator -> Twilio sink.
        async def sink(chunk: bytes) -> None:
            if self._stream_sid is None:
                return
            payload = base64.b64encode(chunk).decode()
            await self.ws.send_text(
                json.dumps(
                    {
                        "event": "media",
                        "streamSid": self._stream_sid,
                        "media": {"payload": payload},
                    }
                )
            )

        self.orch.sink = sink

        # Bridge STT events from the orchestrator to this run loop.
        stt_task = asyncio.create_task(self.orch.run_stt())
        turn_task = asyncio.create_task(self.orch.run())

        try:
            while not self._stop:
                raw = await self.ws.receive_text()
                msg = json.loads(raw)
                await self._handle_message(msg)
        except WebSocketDisconnect:
            logger.info("twilio_ws_disconnect", call_sid=self._call_sid)
        except Exception as exc:  # noqa: BLE001
            logger.warning("media_stream_error", error=str(exc))
        finally:
            self._stop = True
            await self.orch.close()
            stt_task.cancel()
            turn_task.cancel()
            await self.ws.close()

    async def _handle_message(self, msg: dict[str, Any]) -> None:
        event = msg.get("event")
        if event == "connected":
            return
        if event == "start":
            start = msg.get("start", {})
            self._stream_sid = msg.get("streamSid")
            self._call_sid = start.get("callSid")
            logger.info(
                "twilio_stream_started",
                stream_sid=self._stream_sid,
                call_sid=self._call_sid,
            )
            return
        if event == "media":
            payload = msg.get("media", {}).get("payload", "")
            if payload:
                chunk = base64.b64decode(payload)
                await self.orch.feed_audio(chunk)
            return
        if event == "stop":
            # Call/media ended.
            self._stop = True
            return
        if event == "dtmf":
            return
