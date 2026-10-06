"""Calling campaigns."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.types import created_at_col, pk_uuid, updated_at_col
from app.models.enums import CampaignStatus, LeadStatus


class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[uuid.UUID] = pk_uuid()
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agents.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[CampaignStatus] = mapped_column(
        String(24), default=CampaignStatus.DRAFT, index=True, nullable=False
    )
    start_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    max_concurrent_calls: Mapped[int] = mapped_column(default=5, nullable=False)
    retry_attempts: Mapped[int] = mapped_column(default=2, nullable=False)
    retry_delay_minutes: Mapped[int] = mapped_column(default=30, nullable=False)
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()

    user = relationship("User", back_populates="campaigns")
    agent = relationship("Agent", back_populates="campaigns")
    campaign_leads = relationship(
        "CampaignLead", back_populates="campaign", cascade="all, delete-orphan"
    )
    calls = relationship("Call", back_populates="campaign")


class CampaignLead(Base):
    """A lead enrolled in a campaign, with per-lead call state."""

    __tablename__ = "campaign_leads"

    id: Mapped[uuid.UUID] = pk_uuid()
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), index=True, nullable=False
    )
    lead_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("leads.id", ondelete="CASCADE"), index=True, nullable=False
    )
    status: Mapped[LeadStatus] = mapped_column(String(24), default=LeadStatus.NEW, nullable=False)
    attempts: Mapped[int] = mapped_column(default=0, nullable=False)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = created_at_col()

    campaign = relationship("Campaign", back_populates="campaign_leads")
    lead = relationship("Lead", back_populates="campaign_leads")
    calls = relationship("Call", back_populates="campaign_lead")
