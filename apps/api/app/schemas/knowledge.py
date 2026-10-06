"""Knowledge base request/response schemas."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class KnowledgeBaseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = None


class KnowledgeBaseOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class KnowledgeDocumentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    content: str = Field(min_length=1)
    source_type: str = Field(default="text", max_length=32)
    metadata: dict[str, Any] = Field(default_factory=dict)


class KnowledgeDocumentOut(BaseModel):
    id: uuid.UUID
    knowledge_base_id: uuid.UUID
    title: str
    source_type: str
    doc_metadata: dict[str, Any]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class KnowledgeSearchHit(BaseModel):
    chunk_id: uuid.UUID
    content: str
    chunk_index: int
    title: str | None
    score: float


class KnowledgeSearchResponse(BaseModel):
    query: str
    hits: list[KnowledgeSearchHit]
