"""Twilio media-stream WebSocket bridge.

Bridges Twilio's bidirectional media stream to the ConversationOrchestrator:

  Twilio --media(mulaw/8k)-> {WebSocket} --> orch.feed_audio(chunk)
  orch._speak -> sink(chunk)   --{event:"media"}--> Twilio

Also translates the Twilio message protocol (connected/start/media/mark/stop) into STT
events, handles barge-in by sending Twilio a `clear` after the orchestrator interrupts
TTS, and persists finalized transcript turns as they happen.

Twilio message reference:
  https://www.twilio.com/docs/voice/media-streams/websocket-messages
"""

import asyncio
import base64
import contextlib
import json
import uuid
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.logging import get_logger
from app.models.call import Call
from app.models.enums import Speaker
from app.services import transcripts as transcript_service
from app.voice.orchestrator import ConversationOrchestrator

logger = get_logger("voice.media_stream")


def _as_speaker(value: str) -> Speaker:
    try:
        return Speaker(value)
    except ValueError:
        return Speaker.SYSTEM


class MediaStreamBridge:
    """One bridge per live call; drives the orchestrator from the Twilio stream."""

    def __init__(
        self,
        ws: WebSocket,
        orch: ConversationOrchestrator,
        *,
        call_id: uuid.UUID | None = None,
        session_factory: async_sessionmaker[AsyncSession] | None = None,
        sample_rate: int = 8000,
    ) -> None:
        self.ws = ws
        self.orch = orch
        self.call_id = call_id
        self.session_factory = session_factory
        self.sample_rate = sample_rate
        self._stream_sid: str | None = None
        self._call_sid: str | None = None
        self._stop = False
        # How many of the orchestrator's transcript entries are already persisted.
        self._persisted = 0

    async def run(self) -> None:
        """Accept the WS, then loop bridging Twilio media <-> orchestrator."""
        await self.ws.accept()

        async def sink(chunk: bytes) -> None:
            await self._send_media(chunk)

        self.orch.sink = sink
        self.orch.on_interrupt = self._clear_buffer
        self.orch.on_transcript = self._on_transcript

        stt_task = asyncio.create_task(self.orch.run_stt())
        turn_task = asyncio.create_task(self.orch.run())

        try:
            while not self._stop:
                raw = await self.ws.receive_text()
                await self._dispatch(json.loads(raw))
        except WebSocketDisconnect:
            logger.info("twilio_ws_disconnect", call_sid=self._call_sid)
        except json.JSONDecodeError:
            logger.warning("media_stream_bad_json")
        except Exception as exc:  # noqa: BLE001 - never let the bridge kill the worker
            logger.warning("media_stream_error", error=str(exc))

        # NOTE: a message-handling error must never close this websocket, because a
        # closed media stream makes Twilio hang up the call. Only the until-loop
        # above exiting (disconnect or Twilio's `stop`) reaches the teardown below.

        finally:
            self._stop = True
            await self.orch.close()
            for task in (stt_task, turn_task):
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    try:
                        await task
                    except Exception as exc:  # noqa: BLE001 - surface pipeline failures
                        logger.error("orchestrator_task_error", error=str(exc))
            await self._flush_latency()
            await self._flush_transcript()
            with contextlib.suppress(Exception):
                await self.ws.close()

    async def _dispatch(self, msg: dict[str, Any]) -> None:
        """Handle one Twilio message, isolating per-message failures."""
        try:
            await self._handle_message(msg)
        except Exception as exc:  # noqa: BLE001 - skip the bad message, keep the call live
            logger.warning("media_stream_msg_error", error=str(exc))

    # ----- outbound -----
    async def _send_json(self, message: dict[str, Any]) -> None:
        await self.ws.send_text(json.dumps(message))

    async def _send_media(self, chunk: bytes) -> None:
        if self._stream_sid is None:
            return
        await self._send_json(
            {
                "event": "media",
                "streamSid": self._stream_sid,
                "media": {"payload": base64.b64encode(chunk).decode()},
            }
        )

    async def _clear_buffer(self) -> None:
        """Tell Twilio to drop buffered audio so the AI stops mid-sentence."""
        if self._stream_sid is None:
            return
        with contextlib.suppress(Exception):
            await self._send_json({"event": "clear", "streamSid": self._stream_sid})

    # ----- inbound -----
    async def _handle_message(self, msg: dict[str, Any]) -> None:
        event = msg.get("event")

        if event == "connected":
            return

        if event == "start":
            start = msg.get("start", {})
            self._stream_sid = msg.get("streamSid")
            self._call_sid = start.get("callSid")
            media_format = start.get("mediaFormat", {})
            self.sample_rate = int(media_format.get("sampleRate", self.sample_rate))
            logger.info(
                "twilio_stream_started",
                stream_sid=self._stream_sid,
                call_sid=self._call_sid,
                sample_rate=self.sample_rate,
            )
            return

        if event == "media":
            payload = msg.get("media", {}).get("payload", "")
            if payload:
                await self.orch.feed_audio(base64.b64decode(payload))
            return

        if event == "mark":
            # A mark is delivered once everything sent before it has been played,
            # so it is the natural checkpoint for flushing latency metrics.
            await self._flush_latency()
            return

        if event == "stop":
            self._stop = True
            return

        # `dtmf` and any future event types are ignored deliberately.

    # ----- persistence -----
    async def _on_transcript(self, speaker: str, text: str, is_final: bool) -> None:
        """Persist one finalized turn as the conversation progresses."""
        if not is_final or not text or self.call_id is None or self.session_factory is None:
            return
        async with self.session_factory() as db:
            await transcript_service.append_turn(
                db,
                call_id=self.call_id,
                turn=transcript_service.TranscriptTurn(speaker=_as_speaker(speaker), text=text),
            )
        self._persisted += 1

    async def _flush_transcript(self) -> None:
        """Persist anything captured after the last live write (e.g. during teardown)."""
        if self.call_id is None or self.session_factory is None:
            return
        pending = self.orch.transcript[self._persisted :]
        if not pending:
            return
        turns = [
            transcript_service.TranscriptTurn(
                speaker=_as_speaker(entry["speaker"]),
                text=entry["text"],
                language=entry.get("language") or None,
            )
            for entry in pending
        ]
        async with self.session_factory() as db:
            await transcript_service.append_many(db, call_id=self.call_id, turns=turns)
        self._persisted += len(turns)
        logger.info("call_transcript_persisted", call_id=str(self.call_id), turns=len(turns))

    async def _flush_latency(self) -> None:
        """Store per-stage latency (STT/LLM/TTS) on the call row."""
        if self.call_id is None or self.session_factory is None:
            return
        latency = self.orch.latency
        if not latency:
            return
        async with self.session_factory() as db:
            call = await db.get(Call, self.call_id)
            if call is None:
                return
            call.latency_ms = {**call.latency_ms, **latency}
            await db.commit()
