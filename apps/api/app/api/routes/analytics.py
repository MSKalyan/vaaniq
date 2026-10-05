"""Analytics endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.repositories import analytics as analytics_repo
from app.schemas.analytics import OverviewMetrics

router = APIRouter()


@router.get("/overview", response_model=OverviewMetrics)
async def overview(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> OverviewMetrics:
    return await analytics_repo.get_overview(db, user.id)


@router.get("/campaigns")
async def campaign_metrics(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict]:
    return await analytics_repo.list_campaign_metrics(db, user.id)
