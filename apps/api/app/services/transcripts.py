"""Transcript persistence.

Finalized turns are appended to `call_transcripts` as the call progresses so a
crashed call still leaves a usable transcript. Writes are batched by the caller
(one short transaction per finalized turn) — cheap relative to audio, and it keeps
ordering deterministic via `sequence_number`.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.call import Call, CallTranscript
from app.models.enums import Speaker

logger = get_logger("calls.transcript")


@dataclass(slots=True)
class TranscriptTurn:
    speaker: Speaker
    text: str
    language: str | None = None


async def next_sequence_number(db: AsyncSession, call_id: uuid.UUID) -> int:
    current = await db.scalar(
        select(func.max(CallTranscript.sequence_number)).where(CallTranscript.call_id == call_id)
    )
    return int(current or 0) + 1


async def append_turn(
    db: AsyncSession, *, call_id: uuid.UUID, turn: TranscriptTurn
) -> CallTranscript:
    """Persist one finalized turn and return the row."""
    sequence = await next_sequence_number(db, call_id)
    row = CallTranscript(
        call_id=call_id,
        speaker=turn.speaker,
        text=turn.text,
        language=turn.language,
        sequence_number=sequence,
    )
    db.add(row)
    await db.commit()
    return row


async def append_many(db: AsyncSession, *, call_id: uuid.UUID, turns: list[TranscriptTurn]) -> int:
    """Persist several turns in one transaction. Returns the count written."""
    if not turns:
        return 0
    sequence = await next_sequence_number(db, call_id)
    for offset, turn in enumerate(turns):
        db.add(
            CallTranscript(
                call_id=call_id,
                speaker=turn.speaker,
                text=turn.text,
                language=turn.language,
                sequence_number=sequence + offset,
            )
        )
    await db.commit()
    return len(turns)


async def list_transcript(db: AsyncSession, call_id: uuid.UUID) -> list[CallTranscript]:
    result = await db.scalars(
        select(CallTranscript)
        .where(CallTranscript.call_id == call_id)
        .order_by(CallTranscript.sequence_number)
    )
    return list(result)


def to_plaintext(turns: list[CallTranscript]) -> str:
    """Render a transcript for the post-call analysis prompt."""
    label = {Speaker.AI: "Agent", Speaker.CUSTOMER: "Customer", Speaker.SYSTEM: "System"}
    lines: list[str] = []
    for turn in turns:
        speaker = turn.speaker
        name = label.get(speaker) if isinstance(speaker, Speaker) else str(speaker or "Unknown")
        lines.append(f"{name}: {turn.text}")
    return "\n".join(lines)


async def get_call_or_404(db: AsyncSession, call_id: uuid.UUID, user_id: uuid.UUID) -> Call | None:
    """Fetch a call scoped to its owner (None when missing or not theirs)."""
    return await db.scalar(select(Call).where(Call.id == call_id, Call.user_id == user_id))
