"""Lead request/response schemas."""

import re
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.config import settings
from app.models.enums import LeadStatus

_E164 = re.compile(r"^\+\d{10,15}$")


def _normalize_phone(v: str) -> str:
    """Normalize a phone number to E.164.

    Bare national numbers (``9381331609``, ``09381331609``) get
    ``settings.default_country_code`` prefixed; without this Twilio maps the
    number to the account's home country (e.g. +1 on a US trial account).
    """
    raw = "".join(ch for ch in v.strip() if ch.isdigit() or ch == "+")
    if raw.startswith("00"):
        return "+" + raw[2:]
    if raw.startswith("+"):
        return raw
    national = raw.lstrip("0")
    if len(national) <= 10:
        return f"+{settings.default_country_code}{national}"
    # Longer than a national number: assume the country code is already present.
    return f"+{national}"


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
        normalized = _normalize_phone(v)
        if not _E164.match(normalized):
            raise ValueError(f"Invalid phone number: {normalized}")
        return normalized


class LeadCreate(LeadBase):
    status: LeadStatus = LeadStatus.NEW


class LeadUpdate(BaseModel):
    name: str | None = None
    phone_number: str | None = None
    email: EmailStr | None = None
    language: str | None = Field(default=None, max_length=16)
    location: str | None = Field(default=None, max_length=120)
    status: LeadStatus | None = None
    custom_fields: dict[str, Any] | None = None

    @field_validator("phone_number")
    @classmethod
    def validate_phone(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        if not v:
            raise ValueError("Phone number is required")
        normalized = _normalize_phone(v)
        if not _E164.match(normalized):
            raise ValueError(f"Invalid phone number: {normalized}")
        return normalized


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
