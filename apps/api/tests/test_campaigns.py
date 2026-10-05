"""Campaign service tests using an async in-memory SQLite DB.

Validates campaign creation, lead enrollment, and status transitions
(GOOD state machine + invalid-transition rejection) against real service code.
"""

import uuid

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.models.enums import CampaignStatus, LeadStatus
from app.repositories import leads as lead_repo
from app.schemas.campaign import CampaignCreate
from app.schemas.lead import LeadCreate
from app.services import campaigns as service
from app.services import leads as lead_service

USER = uuid.uuid4()


@pytest.fixture
async def db():
    # Importing all models registers every table on Base.metadata.
    # knowledge_chunks uses pgvector Vector — exclude it from the SQLite fixture.
    from sqlalchemy import MetaData

    import app.models  # noqa: F401  (registers all tables)
    from app.core.database import Base

    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # Build a filtered metadata without the pgvector table (knowledge_chunks).
    filtered = MetaData()
    for table in Base.metadata.sorted_tables:
        if table.name == "knowledge_chunks":
            continue
        table.to_metadata(filtered)

    async with engine.begin() as conn:
        await conn.run_sync(filtered.create_all)

    app_session = async_sessionmaker(engine, expire_on_commit=False)
    async with app_session() as session:
        yield session
    await engine.dispose()


async def _make_agent(db, uid: uuid.UUID):
    from app.models.agent import Agent

    agent = Agent(user_id=uid, name="Test Agent", system_prompt="sys")
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    return agent


async def test_campaign_create_and_enroll_leads(db):
    agent = await _make_agent(db, USER)
    lead = await lead_service.create_lead(
        db, user_id=USER, data=LeadCreate(name="Ravi", phone_number="+919876543210")
    )

    campaign = await service.create_campaign(
        db,
        user_id=USER,
        data=CampaignCreate(
            name="Test Campaign",
            agent_id=agent.id,
            lead_ids=[lead.id],
        ),
    )
    assert campaign.status == CampaignStatus.DRAFT
    assert campaign.max_concurrent_calls == 5
    # Lead enrolled + marked QUEUED.
    updated_lead = await lead_repo.get(db, lead.id, USER)
    assert updated_lead.status == LeadStatus.QUEUED


async def test_campaign_valid_and_invalid_transitions(db):
    agent = await _make_agent(db, USER)
    campaign = await service.create_campaign(
        db, user_id=USER, data=CampaignCreate(name="C", agent_id=agent.id)
    )

    # DRAFT -> RUNNING is valid.
    campaign = await service.transition_status(
        db, campaign_id=campaign.id, user_id=USER, status=CampaignStatus.RUNNING
    )
    assert campaign.status == CampaignStatus.RUNNING

    # RUNNING -> DRAFT is invalid.
    with pytest.raises(service.InvalidCampaignStateError):
        await service.transition_status(
            db, campaign_id=campaign.id, user_id=USER, status=CampaignStatus.DRAFT
        )

    # RUNNING -> PAUSED -> RUNNING is valid.
    await service.transition_status(
        db, campaign_id=campaign.id, user_id=USER, status=CampaignStatus.PAUSED
    )
    campaign = await service.transition_status(
        db, campaign_id=campaign.id, user_id=USER, status=CampaignStatus.RUNNING
    )
    assert campaign.status == CampaignStatus.RUNNING


async def test_campaign_not_found(db):
    with pytest.raises(service.CampaignNotFoundError):
        await service.get_campaign(db, campaign_id=uuid.uuid4(), user_id=USER)