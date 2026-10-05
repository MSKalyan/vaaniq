"""Campaign request/response schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import CampaignStatus


class CampaignBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    agent_id: uuid.UUID
    start_time: datetime | None = None
    end_time: datetime | None = None
    max_concurrent_calls: int = Field(default=5, ge=1, le=100)
    retry_attempts: int = Field(default=2, ge=0, le=10)
    retry_delay_minutes: int = Field(default=30, ge=1, le=10080)


class CampaignCreate(CampaignBase):
    lead_ids: list[uuid.UUID] = Field(default_factory=list)


class CampaignUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    status: CampaignStatus | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    max_concurrent_calls: int | None = Field(default=None, ge=1, le=100)
    retry_attempts: int | None = Field(default=None, ge=0, le=10)
    retry_delay_minutes: int | None = Field(default=None, ge=1, le=10080)


class CampaignOut(CampaignBase):
    id: uuid.UUID
    user_id: uuid.UUID
    status: CampaignStatus
    lead_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
