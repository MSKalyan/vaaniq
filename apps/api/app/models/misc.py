"""Customer memory, callbacks, knowledge base, and audit log."""

import uuid
from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import settings
from app.core.database import Base
from app.core.types import created_at_col, pk_uuid, updated_at_col

# The vector width is fixed at DDL time (the column type is not dynamic), so read
# the configured embedding dimension once at import. EMBEDDING_DIMENSION must be
# changed before the first migration to alter the schema.
_EMBEDDING_DIM = settings.embedding_dimension


class CustomerMemory(Base):
    """Persisted insight about a lead across calls (budget, location, interest, ...)."""

    __tablename__ = "customer_memory"

    id: Mapped[uuid.UUID] = pk_uuid()
    lead_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("leads.id", ondelete="CASCADE"), index=True, unique=True, nullable=False
    )
    preferred_language: Mapped[str | None] = mapped_column(String(16), nullable=True)
    budget: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    location: Mapped[str | None] = mapped_column(String(120), nullable=True)
    requirements: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    interest_level: Mapped[str | None] = mapped_column(String(16), nullable=True)
    preferred_callback_time: Mapped[datetime | None] = mapped_column(nullable=True)
    previous_call_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = updated_at_col()

    lead = relationship("Lead", back_populates="customer_memory")


class Callback(Base):
    """Scheduled callbacks requested during conversations."""

    __tablename__ = "callbacks"

    id: Mapped[uuid.UUID] = pk_uuid()
    lead_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("leads.id", ondelete="CASCADE"), index=True, nullable=False
    )
    call_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("calls.id", ondelete="SET NULL"), nullable=True
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agents.id", ondelete="CASCADE"), index=True, nullable=False
    )
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="SCHEDULED", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = created_at_col()

    lead = relationship("Lead")
    agent = relationship("Agent")


class KnowledgeBase(Base):
    __tablename__ = "knowledge_bases"

    id: Mapped[uuid.UUID] = pk_uuid()
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()

    documents = relationship("KnowledgeDocument", back_populates="knowledge_base")
    agents = relationship(
        "Agent",
        secondary="agent_knowledge",
        back_populates="knowledge_bases",
        overlaps="knowledge_bases",
    )


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"

    id: Mapped[uuid.UUID] = pk_uuid()
    knowledge_base_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_bases.id", ondelete="CASCADE"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), default="text", nullable=False)
    storage_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    doc_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = created_at_col()

    knowledge_base = relationship("KnowledgeBase", back_populates="documents")
    chunks = relationship("KnowledgeChunk", back_populates="document")


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"

    id: Mapped[uuid.UUID] = pk_uuid()
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_documents.id", ondelete="CASCADE"), index=True, nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_index: Mapped[int] = mapped_column(default=0, nullable=False)
    # pgvector embedding; width fixed at migration time by EMBEDDING_DIMENSION
    embedding = mapped_column(Vector(_EMBEDDING_DIM), nullable=True)
    chunk_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = created_at_col()

    document = relationship("KnowledgeDocument", back_populates="chunks")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = pk_uuid()
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
    action: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    resource_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    resource_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = created_at_col()
