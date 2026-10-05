"""Shared SQLAlchemy column type helpers."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Uuid
from sqlalchemy.orm import Mapped, mapped_column


def pk_uuid() -> Mapped[uuid.UUID]:
    """Primary-key UUID column with a server default."""
    return mapped_column(Uuid, primary_key=True, default=uuid.uuid4)


def utc_now() -> datetime:
    return datetime.now(UTC)


def created_at_col() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


def updated_at_col() -> Mapped[datetime]:
    return mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )
