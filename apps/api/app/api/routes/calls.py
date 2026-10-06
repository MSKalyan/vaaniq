"""Call listing, detail, transcript, recording, and analysis endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.agent import Agent
from app.models.call import Call
from app.models.enums import CallOutcome, CallState
from app.models.lead import Lead
from app.models.user import User
from app.schemas.call import (
    AnalysisOut,
    CallDetailOut,
    CallsPage,
    CallSummary,
    InitiateCallRequest,
    RecordingOut,
    TranscriptOut,
    TranscriptTurnOut,
)
from app.services import calls as call_service
from app.services import post_call
from app.services import transcripts as transcript_service

router = APIRouter()


async def _load_call(db: AsyncSession, call_id: uuid.UUID, user_id: uuid.UUID) -> Call:
    call = await db.scalar(
        select(Call)
        .options(
            selectinload(Call.lead),
            selectinload(Call.agent),
            selectinload(Call.recording),
            selectinload(Call.analysis),
        )
        .where(Call.id == call_id, Call.user_id == user_id)
    )
    if call is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Call not found")
    return call


def _to_summary(call: Call) -> CallSummary:
    summary = CallSummary.model_validate(call)
    summary.lead_name = call.lead.name if call.lead else None
    summary.agent_name = call.agent.name if call.agent else None
    return summary


@router.get("", response_model=CallsPage)
async def list_calls(
    state: CallState | None = Query(default=None),
    outcome: CallOutcome | None = Query(default=None),
    campaign_id: uuid.UUID | None = Query(default=None),
    agent_id: uuid.UUID | None = Query(default=None),
    lead_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CallsPage:
    filters = [Call.user_id == user.id]
    if state is not None:
        filters.append(Call.state == state)
    if outcome is not None:
        filters.append(Call.outcome == outcome)
    if campaign_id is not None:
        filters.append(Call.campaign_id == campaign_id)
    if agent_id is not None:
        filters.append(Call.agent_id == agent_id)
    if lead_id is not None:
        filters.append(Call.lead_id == lead_id)

    total = int(await db.scalar(select(func.count(Call.id)).where(*filters)) or 0)
    rows = (
        await db.scalars(
            select(Call)
            .options(selectinload(Call.lead), selectinload(Call.agent))
            .where(*filters)
            .order_by(Call.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
    ).all()
    return CallsPage(
        items=[_to_summary(call) for call in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=CallDetailOut, status_code=status.HTTP_201_CREATED)
async def initiate_call(
    data: InitiateCallRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CallDetailOut:
    """Place a single ad-hoc outbound call, bypassing campaigns."""
    lead = await db.scalar(select(Lead).where(Lead.id == data.lead_id, Lead.user_id == user.id))
    if lead is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
    agent = await db.scalar(
        select(Agent).where(Agent.id == data.agent_id, Agent.user_id == user.id)
    )
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    from app.models.campaign import Campaign, CampaignLead
    from app.services.call_init import initiate_call as dial

    # Ad-hoc calls still flow through the same initiation path, so the call is wrapped
    # in a one-off campaign and call_init's joins and analytics stay uniform.
    campaign = Campaign(user_id=user.id, agent_id=agent.id, name="Ad-hoc call")
    db.add(campaign)
    await db.flush()
    campaign_lead = CampaignLead(campaign_id=campaign.id, lead_id=lead.id)
    db.add(campaign_lead)
    await db.flush()

    call = await dial(db, campaign=campaign, campaign_lead=campaign_lead, user_id=user.id)
    if call is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Lead is not callable right now"
        )
    return await _load_detail(db, call.id, user.id)


async def _load_detail(db: AsyncSession, call_id: uuid.UUID, user_id: uuid.UUID) -> CallDetailOut:
    call = await _load_call(db, call_id, user_id)
    detail = CallDetailOut.model_validate(call)
    detail.lead_name = call.lead.name if call.lead else None
    detail.agent_name = call.agent.name if call.agent else None
    detail.transcript = [
        TranscriptTurnOut.model_validate(turn)
        for turn in await transcript_service.list_transcript(db, call.id)
    ]
    return detail


@router.get("/{call_id}", response_model=CallDetailOut)
async def get_call(
    call_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CallDetailOut:
    return await _load_detail(db, call_id, user.id)


@router.get("/{call_id}/transcript", response_model=TranscriptOut)
async def get_transcript(
    call_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TranscriptOut:
    call = await _load_call(db, call_id, user.id)
    turns = await transcript_service.list_transcript(db, call.id)
    return TranscriptOut(
        call_id=call.id,
        duration_seconds=call.duration_seconds,
        turns=[TranscriptTurnOut.model_validate(turn) for turn in turns],
        text=transcript_service.to_plaintext(turns),
    )


@router.get("/{call_id}/recording", response_model=RecordingOut)
async def get_recording(
    call_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> RecordingOut:
    call = await _load_call(db, call_id, user.id)
    if call.recording is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No recording for this call"
        )
    return RecordingOut.model_validate(call.recording)


@router.get("/{call_id}/analysis", response_model=AnalysisOut)
async def get_analysis(
    call_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AnalysisOut:
    call = await _load_call(db, call_id, user.id)
    if call.analysis is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No analysis for this call"
        )
    return AnalysisOut.model_validate(call.analysis)


@router.post("/{call_id}/analyze", response_model=AnalysisOut)
async def analyze_call(
    call_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AnalysisOut:
    """Run (or re-run) post-call analysis on demand."""
    call = await _load_call(db, call_id, user.id)
    analysis = await post_call.analyze_call(db, call=call)
    if analysis is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Call could not be analyzed (no transcript, or the LLM failed)",
        )
    return AnalysisOut.model_validate(analysis)


@router.post("/{call_id}/end", response_model=CallDetailOut)
async def end_call(
    call_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CallDetailOut:
    """Hang up a live call through the telephony provider."""
    call = await _load_call(db, call_id, user.id)
    if not call.provider_call_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Call was never dialed")

    from app.integrations.factory import ProviderNotConfiguredError, get_telephony

    try:
        await get_telephony().end_call(call_id=call.provider_call_id)
    except ProviderNotConfiguredError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from None

    await call_service.update_from_status_webhook(
        db, provider_call_id=call.provider_call_id, status="completed"
    )
    return await _load_detail(db, call_id, user.id)
