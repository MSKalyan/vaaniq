"""CSV lead import: validate, deduplicate, and persist in one batch.

Expected columns (spec example):
    name, phone_number, email, language, location, budget (custom)

Returns import summary: total/imported/duplicates/invalid + per-row errors.
"""

import csv
import io
import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.enums import LeadStatus
from app.models.lead import Lead
from app.repositories import leads as repo
from app.schemas.lead import _normalize_phone

logger = get_logger("leads.csv")

REQUIRED_COLUMNS = ["phone_number"]
KNOWN_COLUMNS = {"name", "phone_number", "email", "language", "location"}


@dataclass
class ImportSummary:
    total_rows: int = 0
    imported: int = 0
    duplicates: int = 0
    invalid: int = 0
    errors: list[dict[str, Any]] = field(default_factory=list)


def _validate_row(
    row: dict[str, Any], row_number: int, errors: list[dict[str, Any]]
) -> dict[str, Any] | None:
    phone = (row.get("phone_number") or "").strip()
    if not phone:
        errors.append({"row": row_number, "reason": "missing phone_number", "raw": row})
        return None

    phone = _normalize_phone(phone)
    if len(phone) < 8 or len(phone) > 16:
        errors.append({"row": row_number, "reason": f"invalid phone_number '{phone}'", "raw": row})
        return None

    name = (row.get("name") or "").strip() or None
    email = (row.get("email") or "").strip() or None
    output = {
        "phone_number": phone,
        "name": name,
        "email": email,
        "language": row.get("language") or None,
        "location": row.get("location") or None,
    }
    return output


async def import_csv(
    db: AsyncSession, *, user_id: uuid.UUID, filename: str, content: bytes
) -> ImportSummary:
    summary = ImportSummary()

    try:
        text = content.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))
        columns = {c.strip().lower() for c in (reader.fieldnames or [])}
    except Exception as exc:
        summary.invalid += 1
        summary.errors.append({"row": 0, "reason": f"unparseable CSV: {exc}", "raw": {}})
        return summary

    if REQUIRED_COLUMNS[0] not in columns:
        summary.invalid += 1
        summary.errors.append(
            {"row": 0, "reason": "missing required column 'phone_number'", "raw": {}}
        )
        return summary

    # Existing phones in this user's account to detect duplicates within/beyond file.
    existing_phones: set[str] = set()
    rows = list(reader)
    summary.total_rows = len(rows)

    for idx, raw_row in enumerate(rows, start=2):  # row 1 is the header
        row = {(k.strip().lower() if k else ""): v for k, v in raw_row.items() if k is not None}
        parsed = _validate_row(row, idx, summary.errors)
        if parsed is None:
            summary.invalid += 1
            continue

        phone = parsed["phone_number"]
        if phone in existing_phones:
            summary.duplicates += 1
            continue
        # Duplicate against the whole account too.
        if await repo.get_by_phone(db, user_id, phone) is not None:
            summary.duplicates += 1
            continue

        existing_phones.add(phone)
        lead = Lead(
            user_id=user_id,
            name=parsed["name"],
            phone_number=parsed["phone_number"],
            email=parsed["email"],
            language=parsed["language"],
            location=parsed["location"],
            status=LeadStatus.NEW,
            custom_fields={
                k: v for k, v in raw_row.items() if k.lower() not in KNOWN_COLUMNS and v
            },
        )
        db.add(lead)
        summary.imported += 1

    await db.commit()
    logger.info(
        "csv_import_complete",
        filename=filename,
        imported=summary.imported,
        duplicates=summary.duplicates,
        invalid=summary.invalid,
    )
    return summary
