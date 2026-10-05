"""Structured logging via structlog.

Every call-related log carries correlation IDs (request_id, call_id, campaign_id,
lead_id, agent_id) so an end-to-end call can be traced across STT/LLM/TTS and the worker.
"""

import logging
import sys

import structlog

from app.core.config import settings


def setup_logging(*, debug: bool | None = None) -> None:
    """Configure structlog (and the stdlib logging under it). Call once at app startup."""
    is_debug = settings.debug if debug is None else debug

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.DEBUG if is_debug else logging.INFO,
        force=True,
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.DEBUG if is_debug else logging.INFO
        ),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = "nenuaikadu") -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
