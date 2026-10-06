"""Twilio webhooks: call status, answer, and recording callbacks.

All endpoints verify the X-Twilio-Signature before mutating state.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.integrations.factory import get_telephony
from app.services import calls as call_service

router = APIRouter()


def _verify_twilio_signature(request: Request, params: dict[str, str]) -> None:
    signature = request.headers.get("X-Twilio-Signature")
    if not signature:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing signature")
    telephony = get_telephony()
    # Twilio signs the URL it called. Behind a proxy that differs from what the ASGI
    # server saw, so normalize it against the configured public base URL.
    signed_url = str(request.url)
    public_url = getattr(telephony, "public_url_for", None)
    if callable(public_url):
        signed_url = public_url(signed_url)
    if not telephony.validate_request_signature(signed_url, params, signature):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid signature")


@router.post("/twilio/status")
async def twilio_status(request: Request, db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    form = await request.form()
    params = {k: str(v) for k, v in form.items()}
    _verify_twilio_signature(request, params)

    provider_call_id = params.get("CallSid")
    call_status = params.get("CallStatus")

    if provider_call_id:
        await call_service.update_from_status_webhook(
            db,
            provider_call_id=provider_call_id,
            status=call_status,
        )
    return {"status": "ok"}


@router.post("/twilio/recording")
async def twilio_recording(request: Request, db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    form = await request.form()
    params = {k: str(v) for k, v in form.items()}
    _verify_twilio_signature(request, params)

    provider_call_id = params.get("CallSid")
    recording_url = params.get("RecordingUrl")
    duration = params.get("RecordingDuration")

    if provider_call_id:
        await call_service.update_recording_from_webhook(
            db,
            provider_call_id=provider_call_id,
            recording_url=recording_url,
            duration=int(duration) if duration else None,
        )
    return {"status": "ok"}
