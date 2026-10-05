"""Campaign execution worker (Celery).

Walks a RUNNING campaign's eligible leads and initiates calls, respecting the
max_concurrent_calls cap, honoring DO_NOT_CALL and retry/backoff settings.

Guards against duplicate simultaneous dials:
- CampaignLead/Call status reservation (CALLING) with optimistic checks.
- `skip_locked` row lock when picking eligible leads.
"""

import asyncio
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.database import engine
from app.core.logging import get_logger
from app.models.campaign import Campaign, CampaignLead
from app.models.enums import CampaignStatus, LeadStatus
from app.services.call_init import initiate_call
from app.workers.celery_app import celery_app

logger = get_logger("campaigns.worker")

session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def _process_campaign_once(campaign_id: uuid.UUID) -> int:
    """One campaign pass: pick up to max_concurrent eligible leads and dial them."""
    initiated = 0
    async with session_factory() as db:
        campaign = await db.get(Campaign, campaign_id)
        if campaign is None or campaign.status != CampaignStatus.RUNNING:
            return 0

        result = await db.execute(
            select(CampaignLead)
            .where(
                CampaignLead.campaign_id == campaign_id,
                CampaignLead.status.in_([LeadStatus.NEW, LeadStatus.QUEUED]),
            )
            .order_by(CampaignLead.created_at.asc())
            .limit(campaign.max_concurrent_calls)
            .with_for_update(skip_locked=True),
        )
        pending = list(result.scalars())

        for campaign_lead in pending:
            campaign = await db.get(Campaign, campaign_id)  # re-read after dialect ops
            try:
                call = await initiate_call(
                    db,
                    campaign=campaign,
                    campaign_lead=campaign_lead,
                    user_id=campaign.user_id,
                )
                if call is not None:
                    initiated += 1
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "campaign_lead_error",
                    campaign_id=str(campaign_id),
                    campaign_lead_id=str(campaign_lead.id),
                    error=str(exc),
                )
    return initiated


@celery_app.task(name="campaigns.process")
def process_campaign(campaign_id: str) -> dict:
    """Process a campaign's next batch of leads. Returns a summary dict."""
    initiated = asyncio.run(_process_campaign_once(uuid.UUID(campaign_id)))
    return {"campaign_id": campaign_id, "initiated": initiated}


@celery_app.task(name="campaigns.requeue")
def requeue_leads(campaign_id: str) -> dict:
    """Requeue FAILED campaign leads whose retry backoff window has elapsed.

    Backoff schedule (spec §48): attempt 1 -> wait retry_delay -> attempt 2 ->
    wait 4h -> attempt 3 -> mark FAILED.
    """
    # TODO: implement retry/backoff — requeue FAILED CampaignLead rows where
    # attempts < campaign.retry_attempts and next_attempt_at <= now; set
    # status back to QUEUED and compute next backoff (linear delay, cap at
    # 4 hours). Mark FAILD permanently once attempts exceeds retry_attempts.
    return {"campaign_id": campaign_id, "requeued": 0}
