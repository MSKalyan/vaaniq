"""Lead + CSV import integration tests using an in-memory async SQLite DB.

Uses only the lead models (no pgvector), so SQLite works. Validates the import
dedup/invalid logic and lead CRUD against real repo/service code.
"""

import uuid

import pytest
from app.schemas.lead import LeadCreate
from app.services import leads as service
from app.services.csv_import import import_csv
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

USER = uuid.uuid4()


@pytest.fixture
async def db():
    import app.models.lead as lead_models

    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(lead_models.Lead.metadata.create_all)
    app_session = async_sessionmaker(engine, expire_on_commit=False)
    async with app_session() as session:
        yield session
    await engine.dispose()


async def test_csv_import_counts_and_dedups(db):
    csv_text = (
        "name,phone_number,email,language,location,budget\n"
        "Ravi,+919876543210,ravi@example.com,te-IN,Visakhapatnam,7000000\n"
        "Suresh,+919876543211,suresh@example.com,hi-IN,Hyderabad,5000000\n"
        "Dup,+919876543210,,,,,\n"  # duplicate within file
        "NoPhone,,a@b.com,en-IN,,,\n"  # invalid: missing phone
        "BadPhone,+12,bad@example.com,,,,\n"  # invalid: too short
    )
    summary = await import_csv(db, user_id=USER, filename="leads.csv", content=csv_text.encode())

    assert summary.total_rows == 5
    assert summary.imported == 2
    assert summary.duplicates == 1
    assert summary.invalid == 2

    leads = await service.list_leads(db, user_id=USER)
    assert len(leads) == 2


async def test_duplicate_lead_creation_rejected(db):
    data = LeadCreate(name="Ravi", phone_number="+919876543210")
    await service.create_lead(db, user_id=USER, data=data)
    with pytest.raises(service.DuplicateLeadError):
        await service.create_lead(db, user_id=USER, data=data)
