"""Domain enumerations shared across models.

Values must stay in sync with `packages/shared/index.ts` on the frontend.
"""

from enum import StrEnum


class LeadStatus(StrEnum):
    NEW = "NEW"
    QUEUED = "QUEUED"
    CALLING = "CALLING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    INTERESTED = "INTERESTED"
    NOT_INTERESTED = "NOT_INTERESTED"
    CALLBACK_REQUESTED = "CALLBACK_REQUESTED"
    DO_NOT_CALL = "DO_NOT_CALL"


class CampaignStatus(StrEnum):
    DRAFT = "DRAFT"
    SCHEDULED = "SCHEDULED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class CallState(StrEnum):
    INITIALIZING = "INITIALIZING"
    RINGING = "RINGING"
    CONNECTED = "CONNECTED"
    GREETING = "GREETING"
    LISTENING = "LISTENING"
    PROCESSING = "PROCESSING"
    SPEAKING = "SPEAKING"
    INTERRUPTED = "INTERRUPTED"
    ENDING = "ENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class CallOutcome(StrEnum):
    """Post-call outcome classification."""

    INTERESTED = "INTERESTED"
    NOT_INTERESTED = "NOT_INTERESTED"
    CALLBACK_REQUESTED = "CALLBACK_REQUESTED"
    NO_ANSWER = "NO_ANSWER"
    BUSY = "BUSY"
    FAILED = "FAILED"
    DO_NOT_CALL = "DO_NOT_CALL"


class Speaker(StrEnum):
    AI = "AI"
    CUSTOMER = "CUSTOMER"
    SYSTEM = "SYSTEM"


class Sentiment(StrEnum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


class InterestLevel(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"


class AgentStatus(StrEnum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


class AgentToolType(StrEnum):
    get_customer_profile = "get_customer_profile"
    update_customer_profile = "update_customer_profile"
    search_knowledge = "search_knowledge"
    schedule_callback = "schedule_callback"
    end_call = "end_call"
    mark_interested = "mark_interested"
    mark_not_interested = "mark_not_interested"
    request_human_transfer = "request_human_transfer"
