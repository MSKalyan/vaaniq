"""Campaign business logic."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.campaign import Campaign, CampaignLead
from app.models.enums import CampaignStatus, LeadStatus
from app.models.lead import Lead
from app.schemas.campaign import CampaignCreate, CampaignUpdate

logger = get_logger("campaigns")


class CampaignNotFoundError(Exception):
    pass


class InvalidCampaignStateError(Exception):
    pass


async def get_campaign(db: AsyncSession, *, campaign_id: uuid.UUID, user_id: uuid.UUID) -> Campaign:
    campaign = await db.scalar(
        select(Campaign).where(Campaign.id == campaign_id, Campaign.user_id == user_id)
    )
    if campaign is None:
        raise CampaignNotFoundError("Campaign not found")
    return campaign


async def create_campaign(
    db: AsyncSession, *, user_id: uuid.UUID, data: CampaignCreate
) -> Campaign:
    campaign = Campaign(
        user_id=user_id,
        name=data.name,
        agent_id=data.agent_id,
        status=CampaignStatus.DRAFT,
        start_time=data.start_time,
        end_time=data.end_time,
        max_concurrent_calls=data.max_concurrent_calls,
        retry_attempts=data.retry_attempts,
        retry_delay_minutes=data.retry_delay_minutes,
    )
    db.add(campaign)
    await db.flush()

    # Enroll leads.
    for lead_id in data.lead_ids:
        db.add(CampaignLead(campaign_id=campaign.id, lead_id=lead_id))
        # Mark enrolled leads as QUEUED (if not already in a retryable state).
        lead = await db.get(Lead, lead_id)
        if lead is not None and lead.status in (LeadStatus.NEW, LeadStatus.QUEUED):
            lead.status = LeadStatus.QUEUED

    await db.commit()
    await db.refresh(campaign)
    return campaign


async def update_campaign(
    db: AsyncSession, *, campaign_id: uuid.UUID, user_id: uuid.UUID, data: CampaignUpdate
) -> Campaign:
    campaign = await get_campaign(db, campaign_id=campaign_id, user_id=user_id)
    updates = data.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(campaign, key, value)
    await db.commit()
    await db.refresh(campaign)
    return campaign


async def transition_status(
    db: AsyncSession, *, campaign_id: uuid.UUID, user_id: uuid.UUID, status: CampaignStatus
) -> Campaign:
    campaign = await get_campaign(db, campaign_id=campaign_id, user_id=user_id)
    # Normalize stored string -> enum (SQLite returns str; Postgres native enum).
    current = (
        campaign.status
        if isinstance(campaign.status, CampaignStatus)
        else CampaignStatus(campaign.status)
    )

    allowed: dict[CampaignStatus, set[CampaignStatus]] = {
        CampaignStatus.DRAFT: {
            CampaignStatus.SCHEDULED,
            CampaignStatus.RUNNING,
            CampaignStatus.CANCELLED,
        },
        CampaignStatus.SCHEDULED: {CampaignStatus.RUNNING, CampaignStatus.CANCELLED},
        CampaignStatus.RUNNING: {
            CampaignStatus.PAUSED,
            CampaignStatus.COMPLETED,
            CampaignStatus.CANCELLED,
        },
        CampaignStatus.PAUSED: {CampaignStatus.RUNNING, CampaignStatus.CANCELLED},
        CampaignStatus.COMPLETED: set(),
        CampaignStatus.CANCELLED: set(),
    }
    if status not in allowed.get(current, set()):
        raise InvalidCampaignStateError(
            f"Cannot transition campaign from {current.value} to {status.value}"
        )

    campaign.status = status
    await db.commit()
    await db.refresh(campaign)
    logger.info("campaign_status_changed", campaign_id=str(campaign.id), status=status.value)
    return campaign


async def list_campaigns(db: AsyncSession, *, user_id: uuid.UUID) -> list[Campaign]:
    result = await db.scalars(
        select(Campaign).where(Campaign.user_id == user_id).order_by(Campaign.created_at.desc())
    )
    campaigns = list(result)
    # Attach lead counts in one query per campaign set.
    counts = await db.execute(
        select(CampaignLead.campaign_id, func.count(CampaignLead.id))
        .where(CampaignLead.campaign_id.in_([c.id for c in campaigns]))
        .group_by(CampaignLead.campaign_id)
    )
    count_map = {str(cid): n for cid, n in counts.all()}
    for c in campaigns:
        c._lead_count = count_map.get(str(c.id), 0)
    return campaigns
