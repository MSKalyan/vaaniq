"""Agent CRUD + voices endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.repositories import agents as repo
from app.schemas.agent import AgentCreate, AgentOut, AgentUpdate, AgentVoiceOut
from app.services import agents as service

router = APIRouter()


@router.get("", response_model=list[AgentOut])
async def list_agents(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[AgentOut]:
    return await service.list_agents(db, user_id=user.id)


@router.post("", response_model=AgentOut, status_code=status.HTTP_201_CREATED)
async def create_agent(
    data: AgentCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AgentOut:
    return await service.create_agent(db, user_id=user.id, data=data)


@router.get("/voices", response_model=list[AgentVoiceOut])
async def list_voices(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list[AgentVoiceOut]:
    return await repo.list_voices(db)


@router.get("/{agent_id}", response_model=AgentOut)
async def get_agent(
    agent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AgentOut:
    try:
        return await service.get_agent(db, agent_id=agent_id, user_id=user.id)
    except service.AgentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from None


@router.patch("/{agent_id}", response_model=AgentOut)
async def update_agent(
    agent_id: uuid.UUID,
    data: AgentUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AgentOut:
    try:
        return await service.update_agent(db, agent_id=agent_id, user_id=user.id, data=data)
    except service.AgentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from None


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(
    agent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    try:
        await service.delete_agent(db, agent_id=agent_id, user_id=user.id)
    except service.AgentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from None
