"""Knowledge base service: CRUD, chunking + embedding, and similarity retrieval.

Documents are split into overlapping chunks, embedded once at ingest, and stored with
their vector. Retrieval embeds the query and returns the nearest chunks, so a voice
agent's answer is grounded in the tenant's own material.
"""

import re
import uuid
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.integrations.base import EmbeddingProvider
from app.models.misc import KnowledgeBase, KnowledgeChunk, KnowledgeDocument

logger = get_logger("knowledge")

# Chunking tuned for spoken Q&A: ~800 chars with 100 overlap keeps each chunk inside
# one answer without splitting mid-thought.
CHUNK_SIZE = 800
CHUNK_OVERLAP = 100


class KnowledgeBaseNotFoundError(Exception):
    pass


class DocumentNotFoundError(Exception):
    pass


def chunk_text(text: str, *, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping chunks, preferring sentence/word boundaries."""
    cleaned = re.sub(r"[ \t]+", " ", text).strip()
    if not cleaned:
        return []
    if len(cleaned) <= size:
        return [cleaned]

    chunks: list[str] = []
    start = 0
    while start < len(cleaned):
        end = min(start + size, len(cleaned))
        if end < len(cleaned):
            # Prefer to break at the last sentence end, else the last space.
            window = cleaned[start:end]
            boundary = max(window.rfind(". "), window.rfind("! "), window.rfind("? "))
            if boundary > size // 2:
                end = start + boundary + 1
            else:
                space = window.rfind(" ")
                if space > size // 2:
                    end = start + space + 1
        chunk = cleaned[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(cleaned):
            break
        start = max(end - overlap, start + 1)
    return chunks


async def get_knowledge_base(
    db: AsyncSession, *, kb_id: uuid.UUID, user_id: uuid.UUID
) -> KnowledgeBase:
    kb = await db.scalar(
        select(KnowledgeBase).where(KnowledgeBase.id == kb_id, KnowledgeBase.user_id == user_id)
    )
    if kb is None:
        raise KnowledgeBaseNotFoundError("Knowledge base not found")
    return kb


async def list_knowledge_bases(db: AsyncSession, user_id: uuid.UUID) -> list[KnowledgeBase]:
    result = await db.scalars(
        select(KnowledgeBase)
        .where(KnowledgeBase.user_id == user_id)
        .order_by(KnowledgeBase.created_at.desc())
    )
    return list(result)


async def create_knowledge_base(
    db: AsyncSession, *, user_id: uuid.UUID, name: str, description: str | None
) -> KnowledgeBase:
    kb = KnowledgeBase(user_id=user_id, name=name, description=description)
    db.add(kb)
    await db.commit()
    await db.refresh(kb)
    return kb


async def delete_knowledge_base(db: AsyncSession, *, kb_id: uuid.UUID, user_id: uuid.UUID) -> None:
    kb = await get_knowledge_base(db, kb_id=kb_id, user_id=user_id)
    await db.delete(kb)
    await db.commit()


async def list_documents(db: AsyncSession, kb_id: uuid.UUID) -> list[KnowledgeDocument]:
    result = await db.scalars(
        select(KnowledgeDocument)
        .where(KnowledgeDocument.knowledge_base_id == kb_id)
        .order_by(KnowledgeDocument.created_at.desc())
    )
    return list(result)


async def create_document(
    db: AsyncSession,
    *,
    kb_id: uuid.UUID,
    user_id: uuid.UUID,
    title: str,
    content: str,
    source_type: str = "text",
    metadata: dict[str, Any] | None = None,
    embedder: EmbeddingProvider | None = None,
) -> KnowledgeDocument:
    """Create a document, chunk it, and embed every chunk."""
    await get_knowledge_base(db, kb_id=kb_id, user_id=user_id)

    doc = KnowledgeDocument(
        knowledge_base_id=kb_id,
        title=title,
        source_type=source_type,
        doc_metadata=metadata or {},
    )
    db.add(doc)
    await db.flush()

    chunks = chunk_text(content)
    if chunks:
        vectors = await _embed(embedder, chunks)
        for index, (text, vector) in enumerate(zip(chunks, vectors, strict=True)):
            db.add(
                KnowledgeChunk(
                    document_id=doc.id,
                    content=text,
                    chunk_index=index,
                    embedding=vector,
                    chunk_metadata={"title": title},
                )
            )
    await db.commit()
    await db.refresh(doc)
    logger.info("knowledge_document_indexed", document_id=str(doc.id), chunks=len(chunks))
    return doc


async def delete_document(
    db: AsyncSession, *, document_id: uuid.UUID, kb_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    await get_knowledge_base(db, kb_id=kb_id, user_id=user_id)
    document = await db.scalar(
        select(KnowledgeDocument).where(
            KnowledgeDocument.id == document_id,
            KnowledgeDocument.knowledge_base_id == kb_id,
        )
    )
    if document is None:
        raise DocumentNotFoundError("Document not found")
    await db.execute(delete(KnowledgeChunk).where(KnowledgeChunk.document_id == document_id))
    await db.delete(document)
    await db.commit()


async def search(
    db: AsyncSession,
    *,
    kb_ids: list[uuid.UUID],
    query: str,
    embedder: EmbeddingProvider | None = None,
    limit: int = 4,
    min_score: float = 0.0,
) -> list[dict[str, Any]]:
    """Return the chunks closest to `query`, best first.

    Scoring is cosine similarity (both vectors are unit length, so the dot product is
    the cosine). Chunks without an embedding are ignored.
    """
    if not kb_ids or not query.strip():
        return []
    if embedder is None:
        from app.integrations.factory import get_embedding_model

        embedder = get_embedding_model()

    query_vector = await embedder.embed_query(query)
    distance = KnowledgeChunk.embedding.cosine_distance(query_vector)
    rows = (
        await db.execute(
            select(
                KnowledgeChunk.id,
                KnowledgeChunk.content,
                KnowledgeChunk.chunk_index,
                KnowledgeDocument.title,
                distance.label("distance"),
            )
            .join(KnowledgeDocument, KnowledgeDocument.id == KnowledgeChunk.document_id)
            .where(
                KnowledgeDocument.knowledge_base_id.in_(kb_ids),
                KnowledgeChunk.embedding.is_not(None),
            )
            .order_by(distance)
            .limit(limit)
        )
    ).all()

    results: list[dict[str, Any]] = []
    for row in rows:
        score = 1.0 - float(row.distance if row.distance is not None else 1.0)
        if score < min_score:
            continue
        results.append(
            {
                "chunk_id": row.id,
                "content": row.content,
                "chunk_index": int(row.chunk_index or 0),
                "title": row.title,
                "score": round(score, 4),
            }
        )
    return results


async def document_count(db: AsyncSession, kb_id: uuid.UUID) -> int:
    value = await db.scalar(
        select(func.count(KnowledgeDocument.id)).where(KnowledgeDocument.knowledge_base_id == kb_id)
    )
    return int(value or 0)


async def _embed(embedder: EmbeddingProvider | None, texts: list[str]) -> list[list[float]]:
    if embedder is None:
        from app.integrations.factory import get_embedding_model

        embedder = get_embedding_model()
    return await embedder.embed_texts(texts)
