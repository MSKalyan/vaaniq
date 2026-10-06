"""Twilio telephony provider.

Implements `TelephonyProvider` for outbound calls with bidirectional media streams.

Initiate: POST https://api.twilio.com/2010-04-01/Accounts/{sid}/Calls.json
          with inline TwiML <Connect><Stream url=... /></Connect> for bidirectional audio.
Media stream messages documented at:
  https://www.twilio.com/docs/voice/media-streams/websocket-messages
Reference: https://www.twilio.com/docs/voice/twiml/stream
"""

import base64
import hashlib
import hmac
from collections.abc import Mapping, Sequence
from typing import Any, cast
from urllib.parse import urlencode

import httpx

from app.core.logging import get_logger
from app.integrations.base import ProviderError, TelephonyProvider

logger = get_logger("twilio")

_DEFAULT_TIMEOUT = 30.0

# Twilio takes application/x-www-form-urlencoded bodies, including repeated keys.
FormData = Mapping[str, str] | Sequence[tuple[str, str]]


class TwilioError(ProviderError):
    """Raised for transport failures or non-2xx Twilio responses."""


class TwilioProvider(TelephonyProvider):
    def __init__(
        self,
        *,
        account_sid: str,
        auth_token: str,
        from_phone: str,
        webhook_base_url: str,
        api_base: str = "https://api.twilio.com",
    ) -> None:
        self.account_sid = account_sid
        self.auth_token = auth_token
        self.from_phone = from_phone
        self.webhook_base_url = webhook_base_url.rstrip("/")
        self.api_base = api_base.rstrip("/")

    # ----- auth -----
    def _auth(self) -> tuple[str, str]:
        return (self.account_sid, self.auth_token)

    def _calls_url(self) -> str:
        return f"{self.api_base}/2010-04-01/Accounts/{self.account_sid}/Calls.json"

    def _call_url(self, call_id: str) -> str:
        return f"{self.api_base}/2010-04-01/Accounts/{self.account_sid}/Calls/{call_id}.json"

    # ----- TwiML -----
    def _stream_twiml(self, stream_url: str, *, track: str = "both_tracks") -> str:
        """Bidirectional <Connect><Stream> — Twilio sends audio to us and accepts
        audio we send back, which is what drives the voice pipeline."""
        return (
            f'<Response><Connect><Stream url="{stream_url}" track="{track}" /></Connect></Response>'
        )

    async def _post(self, url: str, form: FormData) -> dict[str, Any]:
        # Encode the body ourselves so repeated keys (StatusCallbackEvent[]) survive —
        # a dict would collapse them and Twilio would miss the events.
        body = urlencode(form, doseq=True).encode()
        try:
            async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) as client:
                resp = await client.post(
                    url,
                    content=body,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    auth=self._auth(),
                )
        except httpx.HTTPError as exc:
            raise TwilioError(f"Twilio transport error: {exc}") from exc
        return _handle(resp, "POST")

    async def _get(self, url: str) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) as client:
                resp = await client.get(url, auth=self._auth())
        except httpx.HTTPError as exc:
            raise TwilioError(f"Twilio transport error: {exc}") from exc
        return _handle(resp, "GET")

    async def initiate_call(
        self,
        *,
        to_phone: str,
        from_phone: str,
        webhook_url: str,
        timeout_seconds: int | None = None,
        stream_url: str | None = None,
        status_callback_url: str | None = None,
    ) -> str:
        """Start an outbound call; returns the Twilio Call SID.

        `stream_url` is the bidirectional media-stream WebSocket URL. Callers should
        pass the per-call URL (it embeds the call id); if omitted, it is derived from
        `webhook_url` and must be corrected by the caller before use. Twilio requires a
        ws(s):// scheme, so an http(s):// value is rewritten here.
        `status_callback_url` receives call lifecycle updates.
        """
        caller = from_phone or self.from_phone
        if not caller:
            raise TwilioError("No caller phone number configured")

        if stream_url:
            resolved_stream_url = to_websocket_url(stream_url)
        else:
            logger.warning(
                "twilio_stream_url_derived",
                detail="stream_url not supplied; derived URL has no call id and will not match",
            )
            resolved_stream_url = _derive_stream_url(webhook_url)
        status_callback = status_callback_url or (
            f"{self.webhook_base_url}/api/v1/webhooks/twilio/status"
        )

        # StatusCallbackEvent[] is a repeated form field, so the body is a list of
        # pairs rather than a dict (a dict would collapse them to the last value).
        form: list[tuple[str, str]] = [
            ("To", to_phone),
            ("From", caller),
            ("Twiml", self._stream_twiml(resolved_stream_url)),
            ("StatusCallback", status_callback),
            ("StatusCallbackMethod", "POST"),
            ("StatusCallbackEvent[]", "initiated"),
            ("StatusCallbackEvent[]", "ringing"),
            ("StatusCallbackEvent[]", "answered"),
            ("StatusCallbackEvent[]", "completed"),
        ]
        if timeout_seconds is not None:
            form.append(("Timeout", str(timeout_seconds)))

        body = await self._post(self._calls_url(), form)
        sid = body.get("sid")
        if not isinstance(sid, str) or not sid:
            raise TwilioError("Twilio response missing Call SID")
        return sid

    async def end_call(self, *, call_id: str) -> None:
        await self._post(self._call_url(call_id), {"Status": "completed"})

    async def transfer_call(self, *, call_id: str, to_phone: str) -> None:
        await self._post(
            self._call_url(call_id), {"Twiml": f"<Response><Dial>{to_phone}</Dial></Response>"}
        )

    async def get_call_status(self, *, call_id: str) -> dict[str, Any]:
        return await self._get(self._call_url(call_id))

    # ----- webhook signature validation -----
    def validate_request_signature(self, url: str, params: dict[str, str], signature: str) -> bool:
        """Validate the X-Twilio-Signature header.

        Twilio builds the signed string as the request URL followed by, for every POST
        parameter in sorted-key order, the parameter's *name* and then its *value*.
        HMAC-SHA1 keyed by the auth token, base64 encoded. Compared in constant time.

        Note: when running behind a proxy the URL Twilio signed is the public URL, so
        the caller must pass the externally-visible URL (see `public_url_for`).
        https://www.twilio.com/docs/usage/webhooks/webhooks-security
        """
        payload = url
        for key in sorted(params):
            payload += key + params[key]
        expected = base64.b64encode(
            hmac.new(self.auth_token.encode(), payload.encode(), hashlib.sha1).digest()
        ).decode()
        return hmac.compare_digest(expected, signature)

    def public_url_for(self, request_url: str) -> str:
        """Rewrite an inbound request URL to the one Twilio actually called.

        Twilio signs the public URL. Behind ngrok/render/nginx the framework may see
        an internal host, so swap the origin for the configured webhook base URL when
        they disagree.
        """
        if not self.webhook_base_url:
            return request_url
        if request_url.startswith(self.webhook_base_url):
            return request_url
        _, _, remainder = request_url.partition("://")
        _, _slash, path = remainder.partition("/")
        return f"{self.webhook_base_url}/{path}"


def to_websocket_url(url: str) -> str:
    """Rewrite http(s):// to ws(s):// — Twilio's <Stream url=> needs a WebSocket URL."""
    if url.startswith("https://"):
        return "wss://" + url[len("https://") :]
    if url.startswith("http://"):
        return "ws://" + url[len("http://") :]
    return url


def _derive_stream_url(webhook_url: str) -> str:
    """Build a media-stream WS URL from a public base URL (http(s) -> ws(s))."""
    return to_websocket_url(webhook_url.rstrip("/")) + "/api/v1/ws/calls/live"


def _handle(resp: httpx.Response, method: str) -> dict[str, Any]:
    if resp.status_code >= 400:
        raise TwilioError(f"Twilio error {resp.status_code} ({method}): {resp.text[:400]}")
    try:
        body = resp.json()
    except ValueError as exc:
        raise TwilioError("Twilio returned a non-JSON response") from exc
    if not isinstance(body, dict):
        raise TwilioError("Twilio returned an unexpected JSON payload")
    return cast(dict[str, Any], body)
