"""Campaign CRUD + status transition endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.campaign import Campaign
from app.models.enums import CampaignStatus
from app.models.user import User
from app.schemas.campaign import CampaignCreate, CampaignOut, CampaignUpdate
from app.services import campaigns as service

router = APIRouter()

ACTION_STATUS: dict[str, CampaignStatus] = {
    "start": CampaignStatus.RUNNING,
    "pause": CampaignStatus.PAUSED,
    "complete": CampaignStatus.COMPLETED,
    "cancel": CampaignStatus.CANCELLED,
    "schedule": CampaignStatus.SCHEDULED,
}


def _to_out(campaign: Campaign, lead_count: int) -> CampaignOut:
    out = CampaignOut.model_validate(campaign)
    out.lead_count = lead_count
    return out


@router.get("", response_model=list[CampaignOut])
async def list_campaigns(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[CampaignOut]:
    campaigns = await service.list_campaigns(db, user_id=user.id)
    counts = await service.lead_counts(db, [c.id for c in campaigns])
    return [_to_out(c, counts.get(c.id, 0)) for c in campaigns]


@router.post("", response_model=CampaignOut, status_code=status.HTTP_201_CREATED)
async def create_campaign(
    data: CampaignCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CampaignOut:
    campaign = await service.create_campaign(db, user_id=user.id, data=data)
    return _to_out(campaign, await service.count_leads(db, campaign.id))


@router.get("/{campaign_id}", response_model=CampaignOut)
async def get_campaign(
    campaign_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CampaignOut:
    try:
        campaign = await service.get_campaign(db, campaign_id=campaign_id, user_id=user.id)
    except service.CampaignNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from None
    return _to_out(campaign, await service.count_leads(db, campaign.id))


@router.patch("/{campaign_id}", response_model=CampaignOut)
async def update_campaign(
    campaign_id: uuid.UUID,
    data: CampaignUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CampaignOut:
    try:
        campaign = await service.update_campaign(
            db, campaign_id=campaign_id, user_id=user.id, data=data
        )
    except service.CampaignNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from None
    return _to_out(campaign, await service.count_leads(db, campaign.id))


@router.post("/{campaign_id}/{action}", response_model=CampaignOut)
async def campaign_action(
    campaign_id: uuid.UUID,
    action: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CampaignOut:
    target = ACTION_STATUS.get(action)
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown action '{action}'. Valid: {', '.join(ACTION_STATUS)}",
        )
    try:
        campaign = await service.transition_status(
            db, campaign_id=campaign_id, user_id=user.id, status=target
        )
    except service.CampaignNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from None
    except service.InvalidCampaignStateError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from None
    return _to_out(campaign, await service.count_leads(db, campaign.id))
