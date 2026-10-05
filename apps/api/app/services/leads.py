"""Lead business logic."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import LeadStatus
from app.models.lead import Lead
from app.repositories import leads as repo
from app.schemas.lead import LeadCreate, LeadUpdate


class LeadNotFoundError(Exception):
    pass


class DuplicateLeadError(Exception):
    pass


async def get_lead(db: AsyncSession, *, lead_id: uuid.UUID, user_id: uuid.UUID) -> Lead:
    lead = await repo.get(db, lead_id, user_id)
    if lead is None:
        raise LeadNotFoundError("Lead not found")
    return lead


async def create_lead(db: AsyncSession, *, user_id: uuid.UUID, data: LeadCreate) -> Lead:
    exists = await repo.get_by_phone(db, user_id, data.phone_number)
    if exists is not None:
        raise DuplicateLeadError("A lead with this phone number already exists")
    return await repo.create(db, user_id, data.model_dump())


async def update_lead(
    db: AsyncSession, *, lead_id: uuid.UUID, user_id: uuid.UUID, data: LeadUpdate
) -> Lead:
    lead = await get_lead(db, lead_id=lead_id, user_id=user_id)
    updates = {k: v for k, v in data.model_dump(exclude_unset=True).items() if v is not None}
    return await repo.update(db, lead, updates)


async def delete_lead(db: AsyncSession, *, lead_id: uuid.UUID, user_id: uuid.UUID) -> None:
    lead = await get_lead(db, lead_id=lead_id, user_id=user_id)
    await repo.delete(db, lead)


async def set_status(
    db: AsyncSession, *, lead_id: uuid.UUID, user_id: uuid.UUID, status: LeadStatus
) -> Lead:
    lead = await get_lead(db, lead_id=lead_id, user_id=user_id)
    return await repo.update(db, lead, {"status": status})


async def list_leads(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    status: LeadStatus | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[Lead]:
    return await repo.list_for_user(db, user_id, status=status, limit=limit, offset=offset)
