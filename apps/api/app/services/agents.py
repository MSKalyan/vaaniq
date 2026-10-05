"""Agent business logic."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Agent
from app.repositories import agents as repo
from app.schemas.agent import AgentCreate, AgentUpdate


class AgentNotFoundError(Exception):
    pass


async def get_agent(db: AsyncSession, *, agent_id: uuid.UUID, user_id: uuid.UUID) -> Agent:
    agent = await repo.get(db, agent_id, user_id)
    if agent is None:
        raise AgentNotFoundError("Agent not found")
    return agent


async def create_agent(db: AsyncSession, *, user_id: uuid.UUID, data: AgentCreate) -> Agent:
    return await repo.create(db, user_id, data.model_dump())


async def update_agent(
    db: AsyncSession, *, agent_id: uuid.UUID, user_id: uuid.UUID, data: AgentUpdate
) -> Agent:
    agent = await get_agent(db, agent_id=agent_id, user_id=user_id)
    updates = {k: v for k, v in data.model_dump(exclude_unset=True).items() if v is not None}
    return await repo.update(db, agent, updates)


async def delete_agent(db: AsyncSession, *, agent_id: uuid.UUID, user_id: uuid.UUID) -> None:
    agent = await get_agent(db, agent_id=agent_id, user_id=user_id)
    await repo.delete(db, agent)


async def list_agents(db: AsyncSession, *, user_id: uuid.UUID) -> list[Agent]:
    return await repo.list_for_user(db, user_id)
