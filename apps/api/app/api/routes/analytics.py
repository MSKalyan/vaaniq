"""Analytics endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.repositories import analytics as analytics_repo
from app.schemas.analytics import (
    AnalyticsDashboard,
    CallOutcomeCount,
    CampaignMetric,
    DailyVolume,
    LanguageCount,
    OverviewMetrics,
)

router = APIRouter()


@router.get("/overview", response_model=OverviewMetrics)
async def overview(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> OverviewMetrics:
    return await analytics_repo.get_overview(db, user.id)


@router.get("/campaigns", response_model=list[CampaignMetric])
async def campaign_metrics(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[CampaignMetric]:
    return await analytics_repo.list_campaign_metrics(db, user.id)


@router.get("/outcomes", response_model=list[CallOutcomeCount])
async def outcome_breakdown(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[CallOutcomeCount]:
    rows = await analytics_repo.list_outcome_breakdown(db, user.id)
    return [CallOutcomeCount(**row) for row in rows]


@router.get("/languages", response_model=list[LanguageCount])
async def language_breakdown(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[LanguageCount]:
    return await analytics_repo.list_language_breakdown(db, user.id)


@router.get("/daily-volume", response_model=list[DailyVolume])
async def daily_volume(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[DailyVolume]:
    rows = await analytics_repo.get_daily_volume(db, user.id, days=days)
    return [DailyVolume(**row) for row in rows]


@router.get("/dashboard", response_model=AnalyticsDashboard)
async def dashboard(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AnalyticsDashboard:
    """Everything the analytics screen needs in a single round trip."""
    return AnalyticsDashboard(
        overview=await analytics_repo.get_overview(db, user.id),
        campaigns=await analytics_repo.list_campaign_metrics(db, user.id),
        outcomes=[
            CallOutcomeCount(**row)
            for row in await analytics_repo.list_outcome_breakdown(db, user.id)
        ],
        languages=await analytics_repo.list_language_breakdown(db, user.id),
        daily_volume=[
            DailyVolume(**row)
            for row in await analytics_repo.get_daily_volume(db, user.id, days=days)
        ],
    )
