"""Knowledge base endpoints: bases, documents, and retrieval."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.misc import KnowledgeBase, KnowledgeDocument
from app.models.user import User
from app.schemas.knowledge import (
    KnowledgeBaseCreate,
    KnowledgeBaseOut,
    KnowledgeDocumentCreate,
    KnowledgeDocumentOut,
    KnowledgeSearchHit,
    KnowledgeSearchResponse,
)
from app.services import knowledge as service

router = APIRouter()


@router.get("/bases", response_model=list[KnowledgeBaseOut])
async def list_bases(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[KnowledgeBase]:
    return await service.list_knowledge_bases(db, user.id)


@router.post("/bases", response_model=KnowledgeBaseOut, status_code=status.HTTP_201_CREATED)
async def create_base(
    data: KnowledgeBaseCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> KnowledgeBase:
    return await service.create_knowledge_base(
        db, user_id=user.id, name=data.name, description=data.description
    )


@router.get("/bases/{kb_id}/documents", response_model=list[KnowledgeDocumentOut])
async def list_documents(
    kb_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[KnowledgeDocument]:
    try:
        await service.get_knowledge_base(db, kb_id=kb_id, user_id=user.id)
    except service.KnowledgeBaseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from None
    return await service.list_documents(db, kb_id)


@router.post(
    "/bases/{kb_id}/documents",
    response_model=KnowledgeDocumentOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_document(
    kb_id: uuid.UUID,
    data: KnowledgeDocumentCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> KnowledgeDocument:
    try:
        return await service.create_document(
            db,
            kb_id=kb_id,
            user_id=user.id,
            title=data.title,
            content=data.content,
            source_type=data.source_type,
            metadata=data.metadata,
        )
    except service.KnowledgeBaseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from None


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: uuid.UUID,
    kb_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    try:
        await service.delete_document(db, document_id=document_id, kb_id=kb_id, user_id=user.id)
    except service.KnowledgeBaseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from None
    except service.DocumentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from None


@router.delete("/bases/{kb_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_base(
    kb_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    try:
        await service.delete_knowledge_base(db, kb_id=kb_id, user_id=user.id)
    except service.KnowledgeBaseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from None


@router.get("/search", response_model=KnowledgeSearchResponse)
async def search(
    q: str = Query(min_length=1),
    kb_id: list[uuid.UUID] = Query(default_factory=list),
    limit: int = Query(default=4, ge=1, le=20),
    min_score: float = Query(default=0.0, ge=-1.0, le=1.0),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> KnowledgeSearchResponse:
    """Similarity search across knowledge bases the caller owns."""
    owned = [
        kb.id
        for kb in await service.list_knowledge_bases(db, user.id)
        if not kb_id or kb.id in kb_id
    ]
    hits = await service.search(db, kb_ids=owned, query=q, limit=limit, min_score=min_score)
    return KnowledgeSearchResponse(query=q, hits=[KnowledgeSearchHit(**hit) for hit in hits])
