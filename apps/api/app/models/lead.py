"""Lead definitions and CSV-import models."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.types import created_at_col, pk_uuid, updated_at_col
from app.models.enums import LeadStatus


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[uuid.UUID] = pk_uuid()
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    phone_number: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    language: Mapped[str | None] = mapped_column(String(16), nullable=True)
    location: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[LeadStatus] = mapped_column(
        String(24), default=LeadStatus.NEW, index=True, nullable=False
    )
    custom_fields: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()

    user = relationship("User", back_populates="leads")
    campaign_leads = relationship("CampaignLead", back_populates="lead")
    calls = relationship("Call", back_populates="lead")
    customer_memory = relationship("CustomerMemory", back_populates="lead", uselist=False)


class LeadImportJob(Base):
    """Tracks a CSV import batch and its validation results."""

    __tablename__ = "lead_import_jobs"

    id: Mapped[uuid.UUID] = pk_uuid()
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    total_rows: Mapped[int] = mapped_column(default=0, nullable=False)
    imported: Mapped[int] = mapped_column(default=0, nullable=False)
    duplicates: Mapped[int] = mapped_column(default=0, nullable=False)
    invalid: Mapped[int] = mapped_column(default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="PENDING", nullable=False)
    errors: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = created_at_col()


class ImportError(Base):
    """Per-row CSV import errors (filename stored on LeadImportJob)."""

    __tablename__ = "import_errors"

    id: Mapped[uuid.UUID] = pk_uuid()
    job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("lead_import_jobs.id", ondelete="CASCADE"), index=True, nullable=False
    )
    row_number: Mapped[int] = mapped_column(nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    raw_data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
