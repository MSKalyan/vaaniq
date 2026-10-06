"""Aggregation queries for the analytics dashboard.

All queries are scoped to the authenticated user so one tenant can never see
another tenant's numbers. Rates are returned as fractions (0.0-1.0).
"""

import uuid
from typing import Any

from sqlalchemy import Float, case, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.call import Call
from app.models.campaign import Campaign, CampaignLead
from app.models.enums import CallOutcome, CallState, LeadStatus
from app.models.lead import Lead
from app.schemas.analytics import (
    CampaignMetric,
    LanguageCount,
    OverviewMetrics,
)

# Outcomes that represent a real conversation with the customer.
CONNECTED_OUTCOMES = (
    CallOutcome.INTERESTED,
    CallOutcome.NOT_INTERESTED,
    CallOutcome.CALLBACK_REQUESTED,
)
# Outcomes that count as "we finished handling the lead".
TERMINAL_OUTCOMES = CONNECTED_OUTCOMES + (
    CallOutcome.DO_NOT_CALL,
    CallOutcome.NO_ANSWER,
    CallOutcome.BUSY,
    CallOutcome.FAILED,
)


async def get_overview(db: AsyncSession, user_id: uuid.UUID) -> OverviewMetrics:
    total_leads = await _scalar_count(db, Lead.id, Lead.user_id == user_id)
    total_calls = await _scalar_count(db, Call.id, Call.user_id == user_id)

    connected = await _scalar_count(
        db, Call.id, Call.user_id == user_id, Call.outcome.in_(CONNECTED_OUTCOMES)
    )
    failed = await _scalar_count(
        db,
        Call.id,
        Call.user_id == user_id,
        Call.outcome.in_((CallOutcome.FAILED, CallOutcome.NO_ANSWER, CallOutcome.BUSY)),
    )
    do_not_call = await _scalar_count(
        db, Call.id, Call.user_id == user_id, Call.outcome == CallOutcome.DO_NOT_CALL
    )
    in_progress = await _scalar_count(
        db,
        Call.id,
        Call.user_id == user_id,
        Call.outcome.is_(None),
        Call.state != CallState.COMPLETED,
    )

    interested = await _scalar_count(
        db, Lead.id, Lead.user_id == user_id, Lead.status == LeadStatus.INTERESTED
    )
    not_interested = await _scalar_count(
        db, Lead.id, Lead.user_id == user_id, Lead.status == LeadStatus.NOT_INTERESTED
    )
    callback_requested = await _scalar_count(
        db, Lead.id, Lead.user_id == user_id, Lead.status == LeadStatus.CALLBACK_REQUESTED
    )

    avg_duration = await db.scalar(
        select(func.avg(Call.duration_seconds)).where(
            Call.user_id == user_id,
            Call.duration_seconds.is_not(None),
        )
    )
    total_latency = Call.latency_ms["total"].as_string()
    avg_latency = await db.scalar(
        select(func.avg(cast(total_latency, Float))).where(
            Call.user_id == user_id,
            total_latency.is_not(None),
        )
    )

    return OverviewMetrics(
        total_leads=total_leads,
        total_calls=total_calls,
        completed_calls=connected,
        failed_calls=failed,
        interested=interested,
        not_interested=not_interested,
        callback_requested=callback_requested,
        average_call_duration_seconds=float(avg_duration or 0.0),
        average_call_latency_ms=float(avg_latency or 0.0),
        do_not_call=do_not_call,
        in_progress_calls=in_progress,
        connection_rate=_ratio(connected, total_calls),
        interest_rate=_ratio(interested, total_leads),
        callback_rate=_ratio(callback_requested, total_leads),
    )


async def list_campaign_metrics(db: AsyncSession, user_id: uuid.UUID) -> list[CampaignMetric]:
    """Per-campaign rollup used by the campaigns table and dashboard."""
    rows = (
        await db.execute(
            select(
                Campaign.id,
                Campaign.name,
                Campaign.status,
                func.count(func.distinct(CampaignLead.id)).label("total_leads"),
                func.count(Call.id).label("calls_attempted"),
                func.count(case((Call.outcome.in_(CONNECTED_OUTCOMES), 1))).label(
                    "calls_connected"
                ),
                func.count(case((Call.outcome.in_(TERMINAL_OUTCOMES), 1))).label("completed"),
                func.count(case((Call.outcome == CallOutcome.INTERESTED, 1))).label("interested"),
                func.count(case((Call.outcome == CallOutcome.CALLBACK_REQUESTED, 1))).label(
                    "callback_requested"
                ),
            )
            .outerjoin(CampaignLead, CampaignLead.campaign_id == Campaign.id)
            .outerjoin(
                Call,
                (Call.campaign_id == Campaign.id) | (Call.campaign_lead_id == CampaignLead.id),
            )
            .where(Campaign.user_id == user_id)
            .group_by(Campaign.id, Campaign.name, Campaign.status)
            .order_by(Campaign.created_at.desc())
        )
    ).all()

    metrics: list[CampaignMetric] = []
    for row in rows:
        attempted = int(row.calls_attempted or 0)
        connected = int(row.calls_connected or 0)
        completed = int(row.completed or 0)
        metrics.append(
            CampaignMetric(
                campaign_id=str(row.id),
                name=row.name,
                status=str(row.status),
                total_leads=int(row.total_leads or 0),
                calls_attempted=attempted,
                calls_connected=connected,
                completed=completed,
                interested=int(row.interested or 0),
                callback_requested=int(row.callback_requested or 0),
                connection_rate=_ratio(connected, attempted),
                completion_rate=_ratio(completed, attempted),
            )
        )
    return metrics


async def list_outcome_breakdown(db: AsyncSession, user_id: uuid.UUID) -> list[dict[str, Any]]:
    """Call counts grouped by outcome (used for the donut chart)."""
    rows = (
        await db.execute(
            select(Call.outcome, func.count(Call.id))
            .where(Call.user_id == user_id, Call.outcome.is_not(None))
            .group_by(Call.outcome)
            .order_by(func.count(Call.id).desc())
        )
    ).all()
    return [{"outcome": str(row[0]), "count": int(row[1])} for row in rows]


async def list_language_breakdown(db: AsyncSession, user_id: uuid.UUID) -> list[LanguageCount]:
    """Call counts grouped by lead language (used for the language bar chart)."""
    rows = (
        await db.execute(
            select(Lead.language, func.count(Call.id))
            .join(Lead, Lead.id == Call.lead_id)
            .where(Call.user_id == user_id)
            .group_by(Lead.language)
            .order_by(func.count(Call.id).desc())
        )
    ).all()
    return [LanguageCount(language=str(row[0] or "unknown"), count=int(row[1])) for row in rows]


async def get_daily_volume(
    db: AsyncSession, user_id: uuid.UUID, *, days: int = 30
) -> list[dict[str, Any]]:
    """Calls per day for the trend chart."""
    rows = (
        await db.execute(
            select(
                func.date_trunc("day", Call.created_at).label("day"),
                func.count(Call.id).label("total"),
                func.count(case((Call.outcome.in_(CONNECTED_OUTCOMES), 1))).label("connected"),
            )
            .where(Call.user_id == user_id)
            .group_by("day")
            .order_by("day")
            .limit(days)
        )
    ).all()
    return [
        {
            "day": row.day.isoformat() if row.day else None,
            "total": int(row.total or 0),
            "connected": int(row.connected or 0),
        }
        for row in rows
    ]


async def _scalar_count(db: AsyncSession, column: Any, *conditions: Any) -> int:
    value = await db.scalar(select(func.count(column)).where(*conditions))
    return int(value or 0)


def _ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 4)
