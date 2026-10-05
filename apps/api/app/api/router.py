"""Aggregates all versioned API routers under /api/v1."""

from fastapi import APIRouter

from app.api.routes import (
    agents,
    analytics,
    auth,
    campaigns,
    chat,
    health,
    leads,
    webhooks,
)

api_router = APIRouter()

api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
api_router.include_router(agents.router, prefix="/agents", tags=["agents"])
api_router.include_router(chat.router, prefix="/agents", tags=["agents"])
api_router.include_router(leads.router, prefix="/leads", tags=["leads"])
api_router.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])
api_router.include_router(campaigns.router, prefix="/campaigns", tags=["campaigns"])

# Feature routers mount as they are implemented:
# api_router.include_router(calls.router, prefix="/calls", tags=["calls"])
# api_router.include_router(knowledge.router, prefix="/knowledge", tags=["knowledge"])
# api_router.include_router(settings.router, prefix="/settings", tags=["settings"])
