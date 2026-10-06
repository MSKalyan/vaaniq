"""Lead CRUD + CSV import endpoints."""

import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.enums import LeadStatus
from app.models.lead import Lead
from app.models.user import User
from app.schemas.lead import ImportResult, LeadCreate, LeadOut, LeadUpdate
from app.services import leads as service
from app.services.csv_import import import_csv

router = APIRouter()


@router.get("", response_model=list[LeadOut])
async def list_leads(
    status: LeadStatus | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Lead]:
    # response_model serializes the ORM rows into LeadOut.
    return await service.list_leads(db, user_id=user.id, status=status, limit=limit, offset=offset)


@router.post("", response_model=LeadOut, status_code=status.HTTP_201_CREATED)
async def create_lead(
    data: LeadCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Lead:
    try:
        return await service.create_lead(db, user_id=user.id, data=data)
    except service.DuplicateLeadError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from None


@router.post("/import", response_model=ImportResult)
async def import_leads(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ImportResult:
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Only CSV files are supported"
        )

    from app.repositories import leads as repo

    job = await repo.create_import_job(db, user.id, file.filename)
    content = await file.read()
    summary = await import_csv(db, user_id=user.id, filename=file.filename, content=content)

    await repo.update_import_job(
        db,
        job,
        {
            "total_rows": summary.total_rows,
            "imported": summary.imported,
            "duplicates": summary.duplicates,
            "invalid": summary.invalid,
            "status": "COMPLETED",
            "errors": summary.errors,
        },
    )
    return ImportResult(
        job_id=job.id,
        filename=file.filename,
        total_rows=summary.total_rows,
        imported=summary.imported,
        duplicates=summary.duplicates,
        invalid=summary.invalid,
        status=job.status,
        errors=summary.errors,
    )


@router.get("/{lead_id}", response_model=LeadOut)
async def get_lead(
    lead_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Lead:
    try:
        return await service.get_lead(db, lead_id=lead_id, user_id=user.id)
    except service.LeadNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from None


@router.patch("/{lead_id}", response_model=LeadOut)
async def update_lead(
    lead_id: uuid.UUID,
    data: LeadUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Lead:
    try:
        return await service.update_lead(db, lead_id=lead_id, user_id=user.id, data=data)
    except service.LeadNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from None


@router.delete("/{lead_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_lead(
    lead_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    try:
        await service.delete_lead(db, lead_id=lead_id, user_id=user.id)
    except service.LeadNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from None
