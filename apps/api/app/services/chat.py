"""Agent test-chat business logic.

Lets a user converse with an agent before launching it in a campaign. Uses the
configured LLM provider; system prompt comes from the agent's configuration.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.factory import get_llm
from app.models.agent import Agent
from app.repositories import agents as repo
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.agents import AgentNotFoundError


async def chat(
    db: AsyncSession, *, agent_id: str, user_id: uuid.UUID, data: ChatRequest
) -> ChatResponse:
    agent_uuid = uuid.UUID(agent_id)
    agent: Agent | None = await repo.get(db, agent_uuid, user_id)
    if agent is None:
        raise AgentNotFoundError("Agent not found")

    llm = get_llm()
    messages = [{"role": m.role, "content": m.content} for m in data.messages]
    reply = await llm.generate(
        system_prompt=agent.system_prompt,
        messages=messages,
        temperature=agent.temperature,
    )
    return ChatResponse(reply=reply)
