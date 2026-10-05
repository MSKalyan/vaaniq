"""Lead request/response schemas."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.enums import LeadStatus


def _normalize_phone(v: str) -> str:
    digits = "".join(ch for ch in v if ch.isdigit() or ch in "+")
    if not digits.startswith("+") and not digits.startswith("00"):
        # Prepend country code placeholder if absent (must be configured per-market).
        return digits
    return digits


class LeadBase(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    phone_number: str
    email: EmailStr | None = None
    language: str | None = Field(default=None, max_length=16)
    location: str | None = Field(default=None, max_length=120)
    custom_fields: dict[str, Any] = Field(default_factory=dict)

    @field_validator("phone_number")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Phone number is required")
        return _normalize_phone(v)


class LeadCreate(LeadBase):
    status: LeadStatus = LeadStatus.NEW


class LeadUpdate(BaseModel):
    name: str | None = None
    phone_number: str | None = None
    email: EmailStr | None = None
    language: str | None = None
    location: str | None = None
    status: LeadStatus | None = None
    custom_fields: dict[str, Any] | None = None


class LeadOut(LeadBase):
    id: uuid.UUID
    user_id: uuid.UUID
    status: LeadStatus
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ImportResult(BaseModel):
    job_id: uuid.UUID
    filename: str
    total_rows: int
    imported: int
    duplicates: int
    invalid: int
    status: str
    errors: list[dict[str, Any]]
