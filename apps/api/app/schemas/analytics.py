"""Analytics response schemas."""

from pydantic import BaseModel


class OverviewMetrics(BaseModel):
    total_leads: int
    total_calls: int
    completed_calls: int
    failed_calls: int
    interested: int
    not_interested: int
    callback_requested: int
    average_call_duration_seconds: float
    average_call_latency_ms: float


class CallOutcomeCount(BaseModel):
    outcome: str
    count: int


class LanguageCount(BaseModel):
    language: str
    count: int


class CampaignMetric(BaseModel):
    campaign_id: str
    name: str
    total_leads: int
    calls_attempted: int
    calls_connected: int
    completed: int
    interested: int
    callback_requested: int
    connection_rate: float
    completion_rate: float
