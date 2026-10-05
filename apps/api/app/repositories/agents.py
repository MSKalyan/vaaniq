"""Agent data-access operations."""

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Agent, AgentVoice


async def get(db: AsyncSession, agent_id: uuid.UUID, user_id: uuid.UUID) -> Agent | None:
    return await db.scalar(select(Agent).where(Agent.id == agent_id, Agent.user_id == user_id))


async def list_for_user(db: AsyncSession, user_id: uuid.UUID) -> list[Agent]:
    result = await db.scalars(
        select(Agent).where(Agent.user_id == user_id).order_by(Agent.created_at.desc())
    )
    return list(result)


async def create(db: AsyncSession, user_id: uuid.UUID, data: dict[str, Any]) -> Agent:
    agent = Agent(user_id=user_id, **data)
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    return agent


async def update(db: AsyncSession, agent: Agent, data: dict[str, Any]) -> Agent:
    for key, value in data.items():
        setattr(agent, key, value)
    await db.commit()
    await db.refresh(agent)
    return agent


async def delete(db: AsyncSession, agent: Agent) -> None:
    await db.delete(agent)
    await db.commit()


async def list_voices(db: AsyncSession) -> list[AgentVoice]:
    result = await db.scalars(select(AgentVoice).order_by(AgentVoice.voice_name))
    return list(result)
