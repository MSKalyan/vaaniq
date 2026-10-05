"""Aggregation queries for the analytics dashboard."""

import uuid

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.call import Call
from app.models.campaign import Campaign
from app.models.enums import CallOutcome, LeadStatus
from app.models.lead import Lead
from app.schemas.analytics import OverviewMetrics


async def get_overview(db: AsyncSession, user_id: uuid.UUID) -> OverviewMetrics:
    total_leads = await db.scalar(select(func.count(Lead.id)).where(Lead.user_id == user_id))

    total_calls = await db.scalar(select(func.count(Call.id)).where(Call.user_id == user_id))

    completed = (
        await db.scalar(
            select(func.count(Call.id)).where(
                Call.user_id == user_id,
                Call.outcome.in_(
                    [
                        CallOutcome.INTERESTED,
                        CallOutcome.NOT_INTERESTED,
                        CallOutcome.CALLBACK_REQUESTED,
                    ]
                ),
            )
        )
        or 0
    )

    failed = (
        await db.scalar(
            select(func.count(Call.id)).where(
                Call.user_id == user_id,
                Call.outcome.in_([CallOutcome.FAILED, CallOutcome.NO_ANSWER, CallOutcome.BUSY]),
            )
        )
        or 0
    )

    async def _count(status: LeadStatus) -> int:
        val = await db.scalar(
            select(func.count(Lead.id)).where(Lead.user_id == user_id, Lead.status == status)
        )
        return val or 0

    interested = await _count(LeadStatus.INTERESTED)
    not_interested = await _count(LeadStatus.NOT_INTERESTED)
    callback_requested = await _count(LeadStatus.CALLBACK_REQUESTED)

    avg_duration = (
        db.scalar(
            select(func.avg(Call.duration_seconds)).where(
                Call.user_id == user_id,
                Call.duration_seconds.is_not(None),
            )
        )
        or 0
    )

    avg_latency = (
        db.scalar(
            select(func.avg(text("(latency_ms->>'total')::float"))).where(Call.user_id == user_id)
        )
        or 0
    )

    return OverviewMetrics(
        total_leads=total_leads or 0,
        total_calls=total_calls or 0,
        completed_calls=completed,
        failed_calls=failed,
        interested=interested,
        not_interested=not_interested,
        callback_requested=callback_requested,
        average_call_duration_seconds=float(avg_duration or 0),
        average_call_latency_ms=float(avg_latency or 0),
    )


async def list_campaign_metrics(db: AsyncSession, user_id: uuid.UUID) -> list[dict]:
    """Per-campaign aggregate metrics for the campaigns list/dashboard."""
    rows = await db.execute(
        select(
            Campaign.id,
            Campaign.name,
            Campaign.status,
        )
        .where(Campaign.user_id == user_id)
        .order_by(Campaign.created_at.desc())
    )
    out = []
    for row in rows:
        out.append(
            {
                "campaign_id": str(row.id),
                "name": row.name,
                "status": row.status,
            }
        )
    return out
