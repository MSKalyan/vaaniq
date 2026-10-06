"""Campaign execution worker (Celery).

Walks a RUNNING campaign's eligible leads and initiates calls, respecting the
max_concurrent_calls cap, honoring DO_NOT_CALL and retry/backoff settings.

Guards against duplicate simultaneous dials:
- CampaignLead/Call status reservation (CALLING) with optimistic checks.
- `skip_locked` row lock when picking eligible leads.

Retry/backoff: a lead that could not be reached is rescheduled `retry_delay_minutes`
after the attempt, and the delay grows by `BACKOFF_FACTOR` per attempt up to
`MAX_BACKOFF_MINUTES`. Once attempts exceed `campaign.retry_attempts`, the lead is
marked FAILED permanently and stops being eligible.
"""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.database import engine
from app.core.logging import get_logger
from app.models.call import Call
from app.models.campaign import Campaign, CampaignLead
from app.models.enums import CallState, CampaignStatus, LeadStatus
from app.services.call_init import initiate_call
from app.workers.celery_app import celery_app

logger = get_logger("campaigns.worker")

session_factory = async_sessionmaker(engine, expire_on_commit=False)

# Backoff progression for retried leads: 30m, 120m, 480m, capped at 8h.
BACKOFF_FACTOR = 4
MAX_BACKOFF_MINUTES = 480
# How often a running campaign re-checks for dialable leads.
CAMPAIGN_TICK_SECONDS = 30


def backoff_minutes(base_delay_minutes: int, attempt: int) -> int:
    """Delay before attempt `attempt + 1`, growing geometrically from the base."""
    delay = base_delay_minutes * (BACKOFF_FACTOR ** max(0, attempt - 1))
    return int(min(delay, MAX_BACKOFF_MINUTES))


async def _active_call_count(db: AsyncSession, campaign_id: uuid.UUID) -> int:
    """Calls for this campaign that are still live (not terminal)."""
    value = await db.scalar(
        select(func.count(Call.id)).where(
            Call.campaign_id == campaign_id,
            Call.state.notin_([CallState.COMPLETED, CallState.FAILED]),
        )
    )
    return int(value or 0)


async def _process_campaign_once(campaign_id: uuid.UUID) -> int:
    """One campaign pass: fill available concurrency slots with eligible leads."""
    initiated = 0
    async with session_factory() as db:
        campaign = await db.get(Campaign, campaign_id)
        if campaign is None or campaign.status != CampaignStatus.RUNNING:
            return 0

        in_flight = await _active_call_count(db, campaign_id)
        capacity = max(0, campaign.max_concurrent_calls - in_flight)
        if capacity == 0:
            logger.info("campaign_at_capacity", campaign_id=str(campaign_id))
            return 0

        now = datetime.now(UTC)
        result = await db.execute(
            select(CampaignLead)
            .where(
                CampaignLead.campaign_id == campaign_id,
                CampaignLead.status.in_([LeadStatus.NEW, LeadStatus.QUEUED]),
                # Respect the per-lead backoff window.
                (CampaignLead.next_attempt_at.is_(None)) | (CampaignLead.next_attempt_at <= now),
            )
            .order_by(CampaignLead.created_at.asc())
            .limit(capacity)
            .with_for_update(skip_locked=True),
        )
        pending = list(result.scalars())
        if not pending:
            await _maybe_complete_campaign(db, campaign)
            return 0

        for campaign_lead in pending:
            try:
                call = await initiate_call(
                    db,
                    campaign=campaign,
                    campaign_lead=campaign_lead,
                    user_id=campaign.user_id,
                )
                if call is not None and call.state.name != "FAILED":
                    initiated += 1
            except Exception as exc:  # noqa: BLE001 - one bad lead must not stop the batch
                logger.error(
                    "campaign_lead_error",
                    campaign_id=str(campaign_id),
                    campaign_lead_id=str(campaign_lead.id),
                    error=str(exc),
                )
                await _schedule_retry(db, campaign=campaign, campaign_lead=campaign_lead)
    return initiated


async def _maybe_complete_campaign(db: AsyncSession, campaign: Campaign) -> None:
    """Mark the campaign COMPLETED once no lead is eligible to dial."""
    remaining = int(
        await db.scalar(
            select(func.count(CampaignLead.id)).where(
                CampaignLead.campaign_id == campaign.id,
                CampaignLead.status.in_([LeadStatus.NEW, LeadStatus.QUEUED, LeadStatus.CALLING]),
            )
        )
        or 0
    )
    if remaining == 0:
        campaign.status = CampaignStatus.COMPLETED
        await db.commit()
        logger.info("campaign_completed", campaign_id=str(campaign.id))


async def _schedule_retry(
    db: AsyncSession, *, campaign: Campaign, campaign_lead: CampaignLead
) -> None:
    """Queue a lead for another attempt, or fail it permanently."""
    if campaign_lead.attempts >= campaign.retry_attempts:
        campaign_lead.status = LeadStatus.FAILED
        campaign_lead.next_attempt_at = None
        logger.info(
            "campaign_lead_exhausted",
            campaign_lead_id=str(campaign_lead.id),
            attempts=campaign_lead.attempts,
        )
    else:
        delay = backoff_minutes(campaign.retry_delay_minutes, campaign_lead.attempts)
        campaign_lead.status = LeadStatus.QUEUED
        campaign_lead.next_attempt_at = datetime.now(UTC) + timedelta(minutes=delay)
        logger.info(
            "campaign_lead_retry_scheduled",
            campaign_lead_id=str(campaign_lead.id),
            attempt=campaign_lead.attempts + 1,
            retry_in_minutes=delay,
        )
    await db.commit()


def process_campaign(campaign_id: str) -> dict[str, Any]:
    """Process a campaign's next batch of leads. Returns a summary dict."""
    initiated, reschedule = asyncio.run(_process_and_report(campaign_id))
    # Keep ticking while the campaign still has work, at a cadence that respects the
    # concurrency cap without hot-looping.
    if reschedule:
        process_campaign_task.apply_async(args=[campaign_id], countdown=CAMPAIGN_TICK_SECONDS)
    return {"campaign_id": campaign_id, "initiated": initiated, "rescheduled": reschedule}


async def _process_and_report(campaign_id: str) -> tuple[int, bool]:
    """One pass plus a follow-up check, sharing a single event loop."""
    uuid_value = uuid.UUID(campaign_id)
    initiated = await _process_campaign_once(uuid_value)
    return initiated, await _has_pending_work(uuid_value)


async def _has_pending_work(campaign_id: uuid.UUID) -> bool:
    async with session_factory() as db:
        campaign = await db.get(Campaign, campaign_id)
        if campaign is None or campaign.status != CampaignStatus.RUNNING:
            return False
        value = await db.scalar(
            select(func.count(CampaignLead.id)).where(
                CampaignLead.campaign_id == campaign_id,
                CampaignLead.status.in_([LeadStatus.NEW, LeadStatus.QUEUED]),
            )
        )
        return int(value or 0) > 0


def requeue_leads(campaign_id: str) -> dict[str, Any]:
    """Reschedule FAILED campaign leads whose backoff window has elapsed.

    Backoff schedule: attempt 1 waits `retry_delay_minutes`, attempt 2 waits
    `retry_delay_minutes * 4`, and so on up to MAX_BACKOFF_MINUTES. Leads past
    `campaign.retry_attempts` stay FAILED permanently.
    """
    requeued = asyncio.run(_requeue_once(uuid.UUID(campaign_id)))
    return {"campaign_id": campaign_id, "requeued": requeued}


def sweep_active_campaigns() -> dict[str, Any]:
    """Fan out a process task for every RUNNING campaign.

    This is what makes campaigns survive a worker restart: beat re-enqueues them.
    """
    campaign_ids = asyncio.run(_list_running_campaigns())
    for campaign_id in campaign_ids:
        process_campaign_task.apply_async(args=[campaign_id], countdown=0)
    return {"swept": len(campaign_ids)}


async def _list_running_campaigns() -> list[str]:
    async with session_factory() as db:
        rows = await db.execute(
            select(Campaign.id).where(Campaign.status == CampaignStatus.RUNNING)
        )
        return [str(row) for row in rows.scalars()]


async def _requeue_once(campaign_id: uuid.UUID) -> int:
    requeued = 0
    async with session_factory() as db:
        campaign = await db.get(Campaign, campaign_id)
        if campaign is None or campaign.status in (
            CampaignStatus.CANCELLED,
            CampaignStatus.COMPLETED,
        ):
            return 0

        now = datetime.now(UTC)
        result = await db.execute(
            select(CampaignLead)
            .where(
                CampaignLead.campaign_id == campaign_id,
                CampaignLead.status == LeadStatus.FAILED,
                CampaignLead.attempts < campaign.retry_attempts,
                (CampaignLead.next_attempt_at.is_(None)) | (CampaignLead.next_attempt_at <= now),
            )
            .with_for_update(skip_locked=True)
        )
        for campaign_lead in result.scalars():
            delay = backoff_minutes(campaign.retry_delay_minutes, campaign_lead.attempts)
            campaign_lead.status = LeadStatus.QUEUED
            campaign_lead.next_attempt_at = now + timedelta(minutes=delay)
            requeued += 1

        if requeued:
            await db.commit()
            logger.info("campaign_leads_requeued", campaign_id=str(campaign_id), count=requeued)
    return requeued


# Task registration is kept separate from the definitions above so the functions stay
# ordinary typed callables — celery_app.task is untyped, and decorating in place would
# make mypy treat every worker function as untyped. The `*_task` names are what
# Celery and `apply_async` use.
process_campaign_task = celery_app.task(name="campaigns.process")(process_campaign)
requeue_leads_task = celery_app.task(name="campaigns.requeue")(requeue_leads)
sweep_active_campaigns_task = celery_app.task(name="campaigns.sweep_active")(sweep_active_campaigns)
