"""Call, transcript, recording, and analysis request/response schemas."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import CallOutcome, CallState


class CallOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    lead_id: uuid.UUID
    agent_id: uuid.UUID | None
    campaign_id: uuid.UUID | None
    provider_call_id: str | None
    state: CallState
    outcome: CallOutcome | None
    status: str
    direction: str
    phone_number: str | None
    started_at: datetime | None
    ended_at: datetime | None
    duration_seconds: int | None
    latency_ms: dict[str, Any]
    error_message: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CallSummary(CallOut):
    """Call plus denormalized lead details for list views."""

    lead_name: str | None = None
    agent_name: str | None = None


class TranscriptTurnOut(BaseModel):
    id: uuid.UUID
    speaker: str
    text: str
    language: str | None
    timestamp: datetime
    sequence_number: int

    model_config = ConfigDict(from_attributes=True)


class TranscriptOut(BaseModel):
    call_id: uuid.UUID
    duration_seconds: int | None
    turns: list[TranscriptTurnOut]
    text: str = ""


class RecordingOut(BaseModel):
    id: uuid.UUID
    call_id: uuid.UUID
    recording_url: str | None
    storage_key: str | None
    duration: int | None
    status: str
    started_at: datetime | None
    ended_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class AnalysisOut(BaseModel):
    id: uuid.UUID
    call_id: uuid.UUID
    summary: str | None
    sentiment: str | None
    intent: str | None
    interest_level: str | None
    key_points: list[Any]
    extracted_data: dict[str, Any]
    objections: list[Any]
    next_action: str | None
    callback_required: bool
    callback_time: datetime | None
    hllm_version: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CallDetailOut(CallOut):
    """Everything the call-detail screen renders."""

    lead_name: str | None = None
    agent_name: str | None = None
    transcript: list[TranscriptTurnOut] = Field(default_factory=list)
    recording: RecordingOut | None = None
    analysis: AnalysisOut | None = None


class InitiateCallRequest(BaseModel):
    """Ad-hoc outbound call to a single lead (no campaign required)."""

    lead_id: uuid.UUID
    agent_id: uuid.UUID


class CallsPage(BaseModel):
    items: list[CallSummary]
    total: int
    limit: int
    offset: int
