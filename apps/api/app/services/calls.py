"""Call lifecycle service: status webhook handling and recording updates."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.call import Call, CallRecording
from app.models.enums import CallOutcome, CallState

logger = get_logger("calls")

# Map Twilio call status -> internal state/outcome labels.
_TWILIO_STATE: dict[str, tuple[CallState, CallOutcome | None]] = {
    "queued": (CallState.INITIALIZING, None),
    "ringing": (CallState.RINGING, None),
    "in-progress": (CallState.CONNECTED, None),
    "completed": (CallState.COMPLETED, None),
    "busy": (CallState.FAILED, CallOutcome.BUSY),
    "failed": (CallState.FAILED, CallOutcome.FAILED),
    "no-answer": (CallState.FAILED, CallOutcome.NO_ANSWER),
    "canceled": (CallState.FAILED, CallOutcome.FAILED),
}


async def get_by_provider_id(db: AsyncSession, provider_call_id: str) -> Call | None:
    return await db.scalar(select(Call).where(Call.provider_call_id == provider_call_id))


async def update_from_status_webhook(
    db: AsyncSession, *, provider_call_id: str, status: str | None
) -> None:
    call = await get_by_provider_id(db, provider_call_id)
    if call is None:
        logger.warning("status_webhook_unknown_call", provider_call_id=provider_call_id)
        return

    key = (status or "").lower()
    new_state, outcome = _TWILIO_STATE.get(key, (CallState.COMPLETED, None))

    call.state = new_state
    if outcome is not None:
        call.outcome = outcome
    if key in ("in-progress", "completed"):
        if call.started_at is None:
            call.started_at = datetime.now(UTC)
    if key in ("completed", "busy", "failed", "no-answer", "canceled"):
        call.ended_at = datetime.now(UTC)
        if call.started_at:
            call.duration_seconds = int((call.ended_at - call.started_at).total_seconds())

    await db.commit()
    logger.info("call_status_updated", call_id=str(call.id), status=status)


async def update_recording_from_webhook(
    db: AsyncSession,
    *,
    provider_call_id: str,
    recording_url: str | None,
    duration: int | None,
) -> None:
    call = await get_by_provider_id(db, provider_call_id)
    if call is None:
        logger.warning("recording_webhook_unknown_call", provider_call_id=provider_call_id)
        return

    recording = call.recording
    if recording is None:
        recording = CallRecording(call_id=call.id)
        db.add(recording)
    recording.recording_url = recording_url
    if duration is not None:
        recording.duration = duration
    recording.status = "AVAILABLE"
    await db.commit()
    logger.info("recording_updated", call_id=str(call.id))
