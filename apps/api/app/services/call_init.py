"""Call initiation orchestration used by the campaign worker.

Creates a Call row, then tells the telephony provider to dial, storing the
provider call id. DO_NOT_CALL is honored before initiating.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.integrations.factory import get_telephony
from app.models.call import Call
from app.models.campaign import Campaign, CampaignLead
from app.models.enums import CallState, LeadStatus
from app.models.lead import Lead
from app.services.calls import get_by_provider_id

logger = get_logger("calls.init")


class CallInitError(Exception):
    pass


async def initiate_call(
    db: AsyncSession,
    *,
    campaign: Campaign,
    campaign_lead: CampaignLead,
    user_id: uuid.UUID,
) -> Call | None:
    """Reserve + dial a lead. Returns the Call or None if not callable."""
    lead = await db.get(Lead, campaign_lead.lead_id)
    if lead is None:
        return None
    if lead.status == LeadStatus.DO_NOT_CALL:
        logger.info("skip_do_not_call", lead_id=str(lead.id))
        return None

    # Ensure we never double-dial the same lead concurrently.
    # Reserve by setting status to CALLING (optimistic guard).
    if lead.status == LeadStatus.CALLING:
        return None
    lead.status = LeadStatus.CALLING
    campaign_lead.status = LeadStatus.CALLING
    campaign_lead.attempts += 1
    campaign_lead.last_attempt_at = datetime.now(UTC)
    await db.flush()

    telephony = get_telephony()

    call = Call(
        user_id=user_id,
        campaign_id=campaign.id,
        campaign_lead_id=campaign_lead.id,
        lead_id=lead.id,
        agent_id=campaign.agent_id,
        phone_number=lead.phone_number,
        state=CallState.INITIALIZING,
        status="INITIALIZING",
        direction="outbound",
        started_at=datetime.now(UTC),
    )
    db.add(call)
    await db.flush()

    # The call UUID in the path is the stream's capability token (see api/routes/ws.py).
    stream_url = (
        f"{settings.twilio_webhook_base_url}{settings.api_v1_prefix}/ws/calls/{call.id}/live"
    )

    try:
        provider_call_id = await telephony.initiate_call(
            to_phone=lead.phone_number,
            from_phone=settings.twilio_phone_number,
            webhook_url=settings.twilio_webhook_base_url,
            stream_url=stream_url,
        )
    except Exception as exc:
        call.state = CallState.FAILED
        call.status = "FAILED"
        call.error_message = str(exc)
        lead.status = LeadStatus.FAILED
        campaign_lead.status = LeadStatus.FAILED
        await db.commit()
        logger.warning("call_init_failed", lead_id=str(lead.id), error=str(exc))
        return call

    call.provider_call_id = provider_call_id
    await db.commit()
    await db.refresh(call)
    logger.info(
        "call_initiated",
        call_id=str(call.id),
        provider_call_id=provider_call_id,
        lead_id=str(lead.id),
    )
    return call


async def mark_lead_dialed(db: AsyncSession, *, call: Call, provider_status: str) -> None:
    """Apply a status-webhook style update (idempotent)."""
    updated = await get_by_provider_id(db, call.provider_call_id or "")
    if updated is None:
        return
