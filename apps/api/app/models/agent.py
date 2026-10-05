"""AI agent definitions."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Column, ForeignKey, String, Table, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.types import created_at_col, pk_uuid, updated_at_col
from app.models.enums import AgentStatus


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[uuid.UUID] = pk_uuid()
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    language: Mapped[str] = mapped_column(String(16), nullable=False, default="auto")
    voice: Mapped[str | None] = mapped_column(String(64), nullable=True)
    greeting: Mapped[str | None] = mapped_column(Text, nullable=True)
    objectives: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    max_call_duration: Mapped[int] = mapped_column(nullable=False, default=600)
    temperature: Mapped[float] = mapped_column(nullable=False, default=0.7)
    status: Mapped[AgentStatus] = mapped_column(
        String(16), default=AgentStatus.DRAFT, nullable=False
    )
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()

    user = relationship("User", back_populates="agents")
    campaigns = relationship("Campaign", back_populates="agent")
    knowledge_bases = relationship(
        "KnowledgeBase",
        secondary="agent_knowledge",
        back_populates="agents",
        overlaps="agents",
    )


class AgentVoice(Base):
    """Catalog of voices visible to the agent builder."""

    __tablename__ = "agent_voices"

    id: Mapped[uuid.UUID] = pk_uuid()
    provider: Mapped[str] = mapped_column(String(32), nullable=False, default="sarvam")
    voice_name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    language: Mapped[str] = mapped_column(String(16), nullable=False, default="auto")
    voice_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = created_at_col()


# Association table agent ↔ knowledge_base
agent_knowledge = Table(
    "agent_knowledge",
    Base.metadata,
    Column("agent_id", ForeignKey("agents.id", ondelete="CASCADE"), primary_key=True),
    Column(
        "knowledge_base_id",
        ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)
