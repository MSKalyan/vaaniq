"""Call lifecycle service: status webhook handling and recording updates."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.call import Call, CallRecording
from app.models.campaign import Campaign, CampaignLead
from app.models.enums import CallOutcome, CallState, LeadStatus
from app.models.lead import Lead

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
    terminal = key in ("completed", "busy", "failed", "no-answer", "canceled")

    call.state = new_state
    if outcome is not None:
        call.outcome = outcome
    if key in ("in-progress", "completed"):
        if call.started_at is None:
            call.started_at = datetime.now(UTC)
    if terminal:
        call.ended_at = datetime.now(UTC)
        if call.started_at:
            call.duration_seconds = int((call.ended_at - call.started_at).total_seconds())
        # Release the lead reserved by initiate_call() — otherwise it stays CALLING
        # forever and the campaign can never dial it again.
        await _release_reserved_lead(db, call=call, succeeded=key == "completed")

    await db.commit()
    logger.info("call_status_updated", call_id=str(call.id), status=status)


async def _release_reserved_lead(db: AsyncSession, *, call: Call, succeeded: bool) -> None:
    """Unlock the lead/campaign-lead after a terminal Twilio status.

    `initiate_call` marks both the lead and its campaign-lead as CALLING before
    dialing; nothing resets them on completion, leaving campaigns wedged. A
    successful call marks them done; anything else re-queues the campaign-lead for a
    retry (honouring the campaign's backoff) and frees the lead.
    """
    if call.campaign_lead_id is not None:
        campaign_lead = await db.get(CampaignLead, call.campaign_lead_id)
        if campaign_lead is not None:
            if succeeded:
                campaign_lead.status = LeadStatus.COMPLETED
            else:
                campaign_lead.status = LeadStatus.QUEUED
                retry_delay = 30
                if call.campaign_id is not None:
                    campaign = await db.get(Campaign, call.campaign_id)
                    if campaign is not None:
                        retry_delay = campaign.retry_delay_minutes
                campaign_lead.next_attempt_at = datetime.now(UTC) + timedelta(minutes=retry_delay)
    lead = await db.get(Lead, call.lead_id)
    if lead is not None and lead.status == LeadStatus.CALLING:
        lead.status = LeadStatus.COMPLETED if succeeded else LeadStatus.NEW


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
