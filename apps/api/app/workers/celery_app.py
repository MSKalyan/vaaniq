"""Celery application + configuration.

The worker is intentionally minimal: campaigns and retry sweeps. Beat schedules the
per-minute sweep for every active campaign, so a restarted worker resumes automatically.
"""

from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "VoiceAI",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.workers.campaign_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    # A campaign task reschedules itself, so prefetching more than one queued task
    # per worker just ties up slots waiting for the countdown.
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_time_limit=15 * 60,
    task_soft_time_limit=13 * 60,
    broker_connection_retry_on_startup=True,
    beat_schedule={
        # Sweep every running campaign for dialable leads and retry windows.
        "sweep-active-campaigns": {
            "task": "campaigns.sweep_active",
            "schedule": 30.0,
        },
    },
)
