"""Lead data-access operations."""

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import LeadStatus
from app.models.lead import Lead, LeadImportJob


async def get(db: AsyncSession, lead_id: uuid.UUID, user_id: uuid.UUID) -> Lead | None:
    return await db.scalar(select(Lead).where(Lead.id == lead_id, Lead.user_id == user_id))


async def get_by_phone(db: AsyncSession, user_id: uuid.UUID, phone: str) -> Lead | None:
    return await db.scalar(select(Lead).where(Lead.user_id == user_id, Lead.phone_number == phone))


async def list_for_user(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    status: LeadStatus | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[Lead]:
    query = select(Lead).where(Lead.user_id == user_id)
    if status is not None:
        query = query.where(Lead.status == status)
    query = query.order_by(Lead.created_at.desc()).limit(limit).offset(offset)
    result = await db.scalars(query)
    return list(result)


async def create(db: AsyncSession, user_id: uuid.UUID, data: dict[str, Any]) -> Lead:
    lead = Lead(user_id=user_id, **data)
    db.add(lead)
    await db.commit()
    await db.refresh(lead)
    return lead


async def update(db: AsyncSession, lead: Lead, data: dict[str, Any]) -> Lead:
    for key, value in data.items():
        setattr(lead, key, value)
    await db.commit()
    await db.refresh(lead)
    return lead


async def delete(db: AsyncSession, lead: Lead) -> None:
    await db.delete(lead)
    await db.commit()


async def create_import_job(db: AsyncSession, user_id: uuid.UUID, filename: str) -> LeadImportJob:
    job = LeadImportJob(user_id=user_id, filename=filename)
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


async def update_import_job(
    db: AsyncSession, job: LeadImportJob, data: dict[str, Any]
) -> LeadImportJob:
    for key, value in data.items():
        setattr(job, key, value)
    await db.commit()
    return job
