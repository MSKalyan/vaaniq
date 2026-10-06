"""Calls, transcripts, recordings, and post-call analysis."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.types import created_at_col, pk_uuid, updated_at_col
from app.models.enums import CallOutcome, CallState, Speaker


class Call(Base):
    __tablename__ = "calls"

    id: Mapped[uuid.UUID] = pk_uuid()
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    campaign_lead_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("campaign_leads.id", ondelete="SET NULL"), index=True, nullable=True
    )
    lead_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("leads.id", ondelete="CASCADE"), index=True, nullable=False
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agents.id", ondelete="SET NULL"), index=True, nullable=True
    )
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("campaigns.id", ondelete="SET NULL"), index=True, nullable=True
    )
    # External provider call id (Twilio Call SID)
    provider_call_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    state: Mapped[CallState] = mapped_column(
        String(24), default=CallState.INITIALIZING, index=True, nullable=False
    )
    outcome: Mapped[CallOutcome | None] = mapped_column(
        Enum(CallOutcome, native_enum=False, length=24), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(String(24), default="INITIALIZING", nullable=False)
    direction: Mapped[str] = mapped_column(String(12), default="outbound", nullable=False)
    phone_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(nullable=True)
    # Latency metrics: STT/LLM/TTS/total per the observability requirements
    latency_ms: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()

    campaign_lead = relationship("CampaignLead", back_populates="calls")
    lead = relationship("Lead", back_populates="calls")
    campaign = relationship("Campaign", back_populates="calls")
    agent = relationship("Agent")
    transcript = relationship("CallTranscript", back_populates="call")
    recording = relationship("CallRecording", back_populates="call", uselist=False)
    analysis = relationship("CallAnalysis", back_populates="call", uselist=False)


class CallTranscript(Base):
    __tablename__ = "call_transcripts"

    id: Mapped[uuid.UUID] = pk_uuid()
    call_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("calls.id", ondelete="CASCADE"), index=True, nullable=False
    )
    speaker: Mapped[Speaker] = mapped_column(String(12), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str | None] = mapped_column(String(16), nullable=True)
    timestamp: Mapped[datetime] = created_at_col()
    sequence_number: Mapped[int] = mapped_column(default=0, nullable=False)

    call = relationship("Call", back_populates="transcript")


class CallRecording(Base):
    __tablename__ = "call_recordings"

    id: Mapped[uuid.UUID] = pk_uuid()
    call_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("calls.id", ondelete="CASCADE"), index=True, nullable=False
    )
    storage_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    recording_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration: Mapped[int | None] = mapped_column(nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="PENDING", nullable=False)
    created_at: Mapped[datetime] = created_at_col()

    call = relationship("Call", back_populates="recording")


class CallAnalysis(Base):
    __tablename__ = "call_analysis"

    id: Mapped[uuid.UUID] = pk_uuid()
    call_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("calls.id", ondelete="CASCADE"), index=True, nullable=False
    )
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    sentiment: Mapped[str | None] = mapped_column(String(16), nullable=True)
    intent: Mapped[str | None] = mapped_column(String(64), nullable=True)
    interest_level: Mapped[str | None] = mapped_column(String(16), nullable=True)
    key_points: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    extracted_data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    objections: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    next_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    callback_required: Mapped[bool] = mapped_column(default=False, nullable=False)
    callback_time: Mapped[datetime | None] = mapped_column(nullable=True)
    hllm_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = created_at_col()

    call = relationship("Call", back_populates="analysis")
