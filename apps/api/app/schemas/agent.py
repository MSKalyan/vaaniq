"""Agent request/response schemas."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import AgentStatus


class AgentBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = None
    system_prompt: str = ""
    language: str = "auto"
    voice: str | None = None
    greeting: str | None = None
    objectives: list[Any] = Field(default_factory=list)
    max_call_duration: int = Field(default=600, ge=30, le=7200)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    status: AgentStatus = AgentStatus.DRAFT


class AgentCreate(AgentBase):
    pass


class AgentUpdate(BaseModel):
    """All fields optional for partial update."""

    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = None
    system_prompt: str | None = None
    language: str | None = None
    voice: str | None = None
    greeting: str | None = None
    objectives: list[Any] | None = None
    max_call_duration: int | None = Field(default=None, ge=30, le=7200)
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    status: AgentStatus | None = None


class AgentOut(AgentBase):
    id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AgentVoiceOut(BaseModel):
    id: uuid.UUID
    provider: str
    voice_name: str
    language: str
    voice_metadata: dict[str, Any]

    model_config = ConfigDict(from_attributes=True)
