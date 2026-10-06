"""Realtime voice WebSocket endpoint.

Twilio connects its media stream here (from the <Connect><Stream url=... /> TwiML).
The endpoint loads the call + agent configuration, builds a ConversationOrchestrator,
and bridges the Twilio stream (see app/voice/media_stream.py).

Authentication: the path carries the call's UUID, which acts as the capability token —
it is generated server-side and only ever disclosed to Twilio inside signed TwiML, so
it cannot be guessed or enumerated. When Twilio supplies `?callSid=` we additionally
require it to match the stored provider call id, which binds the stream to the exact
Twilio call it was created for.
"""

import uuid

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from app.core.database import async_session_factory
from app.core.logging import get_logger
from app.integrations.factory import get_llm, get_stt, get_tts
from app.models.call import Call
from app.voice.media_stream import MediaStreamBridge
from app.voice.orchestrator import ConversationOrchestrator
from app.voice.state import CallStateMachine

logger = get_logger("voice.ws")

router = APIRouter()


async def _load_call(call_id: str, call_sid: str | None) -> Call:
    """Load the call being streamed, rejecting a mismatched/absent call SID."""
    try:
        call_uuid = uuid.UUID(call_id)
    except ValueError as exc:
        raise ValueError("Malformed call id") from exc

    async with async_session_factory() as db:
        conditions = [Call.id == call_uuid]
        if call_sid:
            conditions.append(Call.provider_call_id == call_sid)
        call = await db.scalar(select(Call).where(*conditions))
        if call is None:
            raise ValueError("Call not found for this stream")
        if call.agent_id is None:
            raise ValueError("Call has no agent configured")
        # Detach from the session: the bridge runs on its own sessions.
        db.expunge(call)
        return call


async def _build_orchestrator(call: Call) -> ConversationOrchestrator:
    """Construct the orchestrator for a call from its agent configuration."""
    agent = call.agent

    async def noop_sink(chunk: bytes) -> None:
        """Replaced by MediaStreamBridge.run() before the loop starts."""

    orchestrator = ConversationOrchestrator(
        llm=get_llm(),
        stt=get_stt(),
        tts=get_tts(),
        system_prompt=agent.system_prompt if agent else "",
        language=agent.language if agent else "auto",
        voice=agent.voice if agent else None,
        temperature=agent.temperature if agent else 0.7,
        max_listen_s=float(call.agent.max_call_duration) if call.agent else 30.0,
        sink=noop_sink,
        state=CallStateMachine(),
        greeting=agent.greeting or "" if agent else "",
    )
    if agent is not None and agent.objectives:
        orchestrator.set_knowledge([str(item) for item in agent.objectives])
    return orchestrator


@router.websocket("/calls/{call_id}/live")
async def call_stream(
    websocket: WebSocket,
    call_id: str,
    call_sid: str | None = Query(default=None, alias="callSid"),
) -> None:
    try:
        call = await _load_call(call_id, call_sid)
        orchestrator = await _build_orchestrator(call)
        bridge = MediaStreamBridge(
            websocket,
            orchestrator,
            call_id=call.id,
            session_factory=async_session_factory,
        )
        await bridge.run()
    except ValueError as exc:
        logger.warning("ws_rejected", call_id=call_id, reason=str(exc))
        await websocket.close(code=4000, reason=str(exc))
    except WebSocketDisconnect:
        return
