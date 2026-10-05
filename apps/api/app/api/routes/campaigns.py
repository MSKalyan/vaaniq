"""Campaign CRUD + status transition endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.enums import CampaignStatus
from app.models.user import User
from app.schemas.campaign import CampaignCreate, CampaignOut, CampaignUpdate
from app.services import campaigns as service

router = APIRouter()


@router.get("", response_model=list[CampaignOut])
async def list_campaigns(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[CampaignOut]:
    campaigns = await service.list_campaigns(db, user_id=user.id)
    out: list[CampaignOut] = []
    for c in campaigns:
        item = CampaignOut.model_validate(c)
        item.lead_count = getattr(c, "_lead_count", 0)
        out.append(item)
    return out


@router.post("", response_model=CampaignOut, status_code=status.HTTP_201_CREATED)
async def create_campaign(
    data: CampaignCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CampaignOut:
    campaign = await service.create_campaign(db, user_id=user.id, data=data)
    out = CampaignOut.model_validate(campaign)
    out.lead_count = len(data.lead_ids)
    return out


@router.get("/{campaign_id}", response_model=CampaignOut)
async def get_campaign(
    campaign_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CampaignOut:
    try:
        return await service.get_campaign(db, campaign_id=campaign_id, user_id=user.id)
    except service.CampaignNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from None


@router.patch("/{campaign_id}", response_model=CampaignOut)
async def update_campaign(
    campaign_id: uuid.UUID,
    data: CampaignUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CampaignOut:
    try:
        return await service.update_campaign(
            db, campaign_id=campaign_id, user_id=user.id, data=data
        )
    except service.CampaignNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from None


@router.post("/{campaign_id}/{action}")
async def campaign_action(
    campaign_id: uuid.UUID,
    action: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CampaignOut:
    status_map = {
        "start": CampaignStatus.RUNNING,
        "pause": CampaignStatus.PAUSED,
        "complete": CampaignStatus.COMPLETED,
        "cancel": CampaignStatus.CANCELLED,
        "schedule": CampaignStatus.SCHEDULED,
    }
    target = status_map.get(action)
    if target is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown action")
    try:
        return await service.transition_status(
            db, campaign_id=campaign_id, user_id=user.id, status=target
        )
    except service.CampaignNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from None
    except service.InvalidCampaignStateError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from None
