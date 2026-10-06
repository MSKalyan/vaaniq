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
    do_not_call: int
    in_progress_calls: int
    connection_rate: float
    interest_rate: float
    callback_rate: float


class CallOutcomeCount(BaseModel):
    outcome: str
    count: int


class LanguageCount(BaseModel):
    language: str
    count: int


class DailyVolume(BaseModel):
    day: str | None = None
    total: int
    connected: int


class CampaignMetric(BaseModel):
    campaign_id: str
    name: str
    status: str
    total_leads: int
    calls_attempted: int
    calls_connected: int
    completed: int
    interested: int
    callback_requested: int
    connection_rate: float
    completion_rate: float


class AnalyticsDashboard(BaseModel):
    """Single payload backing the whole analytics screen."""

    overview: OverviewMetrics
    campaigns: list[CampaignMetric]
    outcomes: list[CallOutcomeCount]
    languages: list[LanguageCount]
    daily_volume: list[DailyVolume]
