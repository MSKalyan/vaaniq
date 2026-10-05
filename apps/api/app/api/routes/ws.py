"""Realtime voice WebSocket endpoint.

Twilio connects its media stream here (from the <Connect><Stream url=... /> TwiML).
The endpoint loads the call + agent configuration, builds a ConversationOrchestrator,
and bridges the Twilio stream (see app/voice/media_stream.py).
"""

import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.database import async_session_factory
from app.core.logging import get_logger
from app.integrations.factory import get_llm, get_stt, get_tts
from app.models.call import Call
from app.voice.media_stream import MediaStreamBridge
from app.voice.orchestrator import ConversationOrchestrator
from app.voice.state import CallStateMachine

logger = get_logger("voice.ws")

router = APIRouter()


async def _build_orchestrator(call_id: str, sink=None) -> ConversationOrchestrator:
    """Construct the orchestrator for a call from its agent configuration."""
    call_uuid = uuid.UUID(call_id)
    async with async_session_factory() as db:
        call = await db.get(Call, call_uuid)
        if call is None or call.agent_id is None:
            raise ValueError("Call or agent not found")

        async def noop_sink(chunk: bytes) -> None:  # placeholder; set by bridge
            pass

        return ConversationOrchestrator(
            llm=get_llm(),
            stt=get_stt(),
            tts=get_tts(),
            system_prompt=call.agent.system_prompt if call.agent else "",
            language=call.agent.language if call.agent else "auto",
            voice=call.agent.voice if call.agent else None,
            temperature=call.agent.temperature if call.agent else 0.7,
            sink=sink or noop_sink,
            state=CallStateMachine(),
        )


@router.websocket("/calls/{call_id}/live")
async def call_stream(websocket: WebSocket, call_id: str) -> None:
    try:
        orch = await _build_orchestrator(call_id)
        bridge = MediaStreamBridge(websocket, orch)
        await bridge.run()
    except ValueError as exc:
        await websocket.close(code=4000, reason=str(exc))
    except WebSocketDisconnect:
        return
