"""Database model aggregation.

Import every model so SQLAlchemy registers it on `Base.metadata` for Alembic
autogeneration and relationship resolution.
"""

from app.models.agent import Agent, AgentVoice, agent_knowledge
from app.models.call import (
    Call,
    CallAnalysis,
    CallRecording,
    CallTranscript,
)
from app.models.campaign import Campaign, CampaignLead
from app.models.enums import (
    AgentStatus,
    AgentToolType,
    CallOutcome,
    CallState,
    CampaignStatus,
    InterestLevel,
    LeadStatus,
    Sentiment,
    Speaker,
)
from app.models.lead import ImportError, Lead, LeadImportJob
from app.models.misc import (
    AuditLog,
    Callback,
    CustomerMemory,
    KnowledgeBase,
    KnowledgeChunk,
    KnowledgeDocument,
)
from app.models.user import RefreshToken, User

__all__ = [
    # user
    "User",
    "RefreshToken",
    # agent
    "Agent",
    "AgentVoice",
    "agent_knowledge",
    # lead
    "Lead",
    "LeadImportJob",
    "ImportError",
    # campaign
    "Campaign",
    "CampaignLead",
    # call
    "Call",
    "CallTranscript",
    "CallRecording",
    "CallAnalysis",
    # misc
    "CustomerMemory",
    "Callback",
    "KnowledgeBase",
    "KnowledgeDocument",
    "KnowledgeChunk",
    "AuditLog",
    # enums
    "AgentStatus",
    "AgentToolType",
    "CallOutcome",
    "CallState",
    "CampaignStatus",
    "InterestLevel",
    "LeadStatus",
    "Sentiment",
    "Speaker",
]
