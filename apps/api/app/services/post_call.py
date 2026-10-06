"""Post-call analysis.

After a call completes, the full transcript is sent to the LLM with a JSON schema
constraining the output, and the result is persisted to `call_analysis`. The analysis
outcome is also applied to the call and lead, and the `customer_memory` record is
refreshed so future calls start informed.

Analysis runs out-of-band (Celery task or inline on webhook) and must never break the
status webhook — every provider failure degrades to "no analysis" rather than an error
returned to Twilio.
"""

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.integrations.base import LLMProvider
from app.models.call import Call, CallAnalysis
from app.models.enums import CallOutcome, InterestLevel, LeadStatus, Sentiment
from app.models.lead import Lead
from app.models.misc import CustomerMemory
from app.services import transcripts as transcript_service

logger = get_logger("calls.analysis")

ANALYSIS_SYSTEM_PROMPT = """You are a call-review analyst for a sales team.
Read the call transcript and return structured analysis.

Rules:
- Base every field only on what the transcript supports. Never invent details.
- `summary`: 2-3 sentences describing how the call went.
- `sentiment`: positive | neutral | negative (the customer's overall sentiment).
- `intent`: the customer's main intent, e.g. pricing, availability, demo, complaint.
- `interest_level`: high | medium | low | none.
- `key_points`: short factual bullet strings (max 5).
- `extracted_data`: concrete facts worth keeping (budget, timeline, product, etc.).
- `objections`: objections the customer raised (max 5).
- `next_action`: the single best next step for a human rep.
- `callback_required`: true if a human should call back.
- `outcome`: one of INTERESTED, NOT_INTERESTED, CALLBACK_REQUESTED, DO_NOT_CALL,
  NO_ANSWER, BUSY, FAILED.
"""

_OUTCOME_VALUES = [outcome.value for outcome in CallOutcome]

ANALYSIS_SCHEMA: dict[str, Any] = {
    "name": "call_analysis",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "summary",
            "sentiment",
            "intent",
            "interest_level",
            "key_points",
            "extracted_data",
            "objections",
            "next_action",
            "callback_required",
            "outcome",
        ],
        "properties": {
            "summary": {"type": "string"},
            "sentiment": {"type": "string", "enum": ["positive", "neutral", "negative"]},
            "intent": {"type": "string"},
            "interest_level": {"type": "string", "enum": ["high", "medium", "low", "none"]},
            "key_points": {"type": "array", "items": {"type": "string"}},
            "extracted_data": {"type": "object"},
            "objections": {"type": "array", "items": {"type": "string"}},
            "next_action": {"type": "string"},
            "callback_required": {"type": "boolean"},
            "outcome": {"type": "string", "enum": _OUTCOME_VALUES},
        },
    },
}

# Lead status implied by each outcome.
_OUTCOME_TO_LEAD_STATUS: dict[CallOutcome, LeadStatus] = {
    CallOutcome.INTERESTED: LeadStatus.INTERESTED,
    CallOutcome.NOT_INTERESTED: LeadStatus.NOT_INTERESTED,
    CallOutcome.CALLBACK_REQUESTED: LeadStatus.CALLBACK_REQUESTED,
    CallOutcome.DO_NOT_CALL: LeadStatus.DO_NOT_CALL,
    # Unreachable lead stays queued so the campaign can retry it.
    CallOutcome.NO_ANSWER: LeadStatus.QUEUED,
    CallOutcome.BUSY: LeadStatus.QUEUED,
    CallOutcome.FAILED: LeadStatus.FAILED,
}

_VALID_SENTIMENTS = {s.value for s in Sentiment}
_VALID_INTERESTS = {i.value for i in InterestLevel}


async def analyze_call(
    db: AsyncSession,
    *,
    call: Call,
    llm: LLMProvider | None = None,
) -> CallAnalysis | None:
    """Analyze a completed call and persist the result. None if nothing to analyze."""
    turns = await transcript_service.list_transcript(db, call.id)
    spoken = [t for t in turns if t.text and not t.text.startswith("stt_")]
    if not spoken:
        logger.info("analysis_skipped_no_transcript", call_id=str(call.id))
        return None

    if llm is None:
        from app.integrations.factory import get_llm

        llm = get_llm()

    transcript_text = transcript_service.to_plaintext(spoken)
    try:
        raw = await llm.generate(
            system_prompt=ANALYSIS_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": f"Call transcript:\n{transcript_text}"}],
            temperature=0.0,
            max_tokens=1024,
            response_format={"type": "json_schema", "json_schema": ANALYSIS_SCHEMA},
        )
    except Exception as exc:  # noqa: BLE001 - analysis is best-effort
        logger.warning("analysis_llm_failed", call_id=str(call.id), error=str(exc))
        return None

    parsed = _parse(raw)
    if parsed is None:
        logger.warning("analysis_parse_failed", call_id=str(call.id))
        return None

    analysis = await upsert_analysis(db, call_id=call.id, data=parsed, llm_model=llm.model_name)
    await apply_analysis(
        db, call=call, analysis=analysis, outcome=_as_outcome(parsed.get("outcome"))
    )
    logger.info(
        "analysis_completed",
        call_id=str(call.id),
        outcome=str(call.outcome or ""),
        interest_level=analysis.interest_level,
    )
    return analysis


async def upsert_analysis(
    db: AsyncSession,
    *,
    call_id: uuid.UUID,
    data: dict[str, Any],
    llm_model: str | None = None,
) -> CallAnalysis:
    """Create or replace the analysis row for a call."""
    analysis = await db.scalar(select(CallAnalysis).where(CallAnalysis.call_id == call_id))
    if analysis is None:
        analysis = CallAnalysis(call_id=call_id)
        db.add(analysis)

    analysis.summary = _as_str(data.get("summary"))
    analysis.sentiment = _validated(data.get("sentiment"), _VALID_SENTIMENTS)
    analysis.intent = _as_str(data.get("intent"), limit=64)
    analysis.interest_level = _validated(data.get("interest_level"), _VALID_INTERESTS)
    analysis.key_points = _as_list(data.get("key_points"))
    analysis.extracted_data = _as_dict(data.get("extracted_data"))
    analysis.objections = _as_list(data.get("objections"))
    analysis.next_action = _as_str(data.get("next_action"))
    analysis.callback_required = bool(data.get("callback_required", False))
    analysis.hllm_version = llm_model

    if analysis.callback_required and analysis.callback_time is None:
        analysis.callback_time = datetime.now(UTC)

    await db.commit()
    await db.refresh(analysis)
    return analysis


async def apply_analysis(
    db: AsyncSession,
    *,
    call: Call,
    analysis: CallAnalysis,
    outcome: CallOutcome | None,
) -> None:
    """Apply the analyzed outcome to the call, lead, and customer memory."""
    if outcome is not None:
        call.outcome = outcome

    lead = await db.get(Lead, call.lead_id)
    if lead is not None and outcome is not None:
        lead.status = _OUTCOME_TO_LEAD_STATUS.get(outcome, lead.status)

    memory = await db.scalar(select(CustomerMemory).where(CustomerMemory.lead_id == call.lead_id))
    if memory is None:
        memory = CustomerMemory(lead_id=call.lead_id)
        db.add(memory)
    if analysis.summary:
        memory.previous_call_summary = analysis.summary
    if analysis.interest_level:
        memory.interest_level = analysis.interest_level

    extracted = analysis.extracted_data or {}
    budget = extracted.get("budget")
    if budget is not None:
        memory.budget = budget if isinstance(budget, dict) else {"value": budget}
    location = extracted.get("location")
    if isinstance(location, str) and location:
        memory.location = location
    requirements = extracted.get("requirements")
    if isinstance(requirements, list):
        memory.requirements = requirements

    await db.commit()


def _as_outcome(value: Any) -> CallOutcome | None:
    text = _as_str(value)
    if text is None:
        return None
    try:
        return CallOutcome(text)
    except ValueError:
        return None


def _parse(raw: str) -> dict[str, Any] | None:
    """Parse the LLM JSON response, tolerating markdown code fences."""
    text = raw.strip()
    if text.startswith("```"):
        parts = text.split("```")
        if len(parts) >= 2:
            text = parts[1]
        text = text.removeprefix("json").strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _as_str(value: Any, limit: int | None = None) -> str | None:
    if not isinstance(value, str):
        return None
    trimmed = value.strip()
    if not trimmed:
        return None
    return trimmed[:limit] if limit else trimmed


def _as_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _validated(value: Any, allowed: set[str]) -> str | None:
    text = _as_str(value)
    return text if text in allowed else None
