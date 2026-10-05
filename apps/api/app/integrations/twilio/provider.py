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

import httpx

from app.integrations.base import TelephonyProvider


class TwilioError(Exception):
    pass


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

    # ----- stream TwiML -----
    def _stream_twiml(self, stream_url: str) -> str:
        """Bidirectional <Connect><Stream> — Twilio will send audio to us and
        accept audio we send back (drives the voice pipeline)."""
        return f'<Response><Connect><Stream url="{stream_url}" /></Connect></Response>'

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

        `stream_url` is the bidirectional media-stream WebSocket URL (defaults to
        `<webhook_base>/api/v1/ws/calls/live/stream`). `status_callback_url` defaults
        to the status webhook.
        """
        from_phone = from_phone or self.from_phone
        stream = stream_url or f"{self.webhook_base_url}/api/v1/ws/calls/live"
        twiml = self._stream_twiml(stream)
        status_callback = (
            status_callback_url or f"{self.webhook_base_url}/api/v1/webhooks/twilio/status"
        )

        form = {
            "To": to_phone,
            "From": from_phone,
            "Twiml": twiml,
            "StatusCallback": status_callback,
            "StatusCallbackEvent[]": "answered",
        }
        if timeout_seconds is not None:
            form["Timeout"] = str(timeout_seconds)

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    self._calls_url(), data=form, auth=self._auth(), timeout=30.0
                )
        except httpx.HTTPError as exc:
            raise TwilioError(f"Twilio transport error: {exc}") from exc

        if resp.status_code >= 400:
            raise TwilioError(f"Twilio error {resp.status_code}: {resp.text[:400]}")

        body = resp.json()
        sid = body.get("sid")
        if not sid:
            raise TwilioError("Twilio response missing Call SID")
        return sid

    async def end_call(self, *, call_id: str) -> None:
        url = f"{self.api_base}/2010-04-01/Accounts/{self.account_sid}/Calls/{call_id}.json"
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    url,
                    data={"Status": "completed"},
                    auth=self._auth(),
                    timeout=30.0,
                )
        except httpx.HTTPError as exc:
            raise TwilioError(f"Twilio transport error: {exc}") from exc
        if resp.status_code >= 400:
            raise TwilioError(f"Twilio error {resp.status_code}: {resp.text[:300]}")

    async def transfer_call(self, *, call_id: str, to_phone: str) -> None:
        url = f"{self.api_base}/2010-04-01/Accounts/{self.account_sid}/Calls/{call_id}.json"
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    url,
                    data={"Twiml": f"<Response><Dial>{to_phone}</Dial></Response>"},
                    auth=self._auth(),
                    timeout=30.0,
                )
        except httpx.HTTPError as exc:
            raise TwilioError(f"Twilio transport error: {exc}") from exc
        if resp.status_code >= 400:
            raise TwilioError(f"Twilio error {resp.status_code}: {resp.text[:300]}")

    async def get_call_status(self, *, call_id: str) -> dict:
        url = f"{self.api_base}/2010-04-01/Accounts/{self.account_sid}/Calls/{call_id}.json"
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, auth=self._auth(), timeout=30.0)
        except httpx.HTTPError as exc:
            raise TwilioError(f"Twilio transport error: {exc}") from exc
        if resp.status_code >= 400:
            raise TwilioError(f"Twilio error {resp.status_code}: {resp.text[:300]}")
        return resp.json()

    # ----- webhook signature validation -----
    from urllib.parse import urlencode as _urlencode

    def validate_request_signature(self, url: str, params: dict[str, str], signature: str) -> bool:
        """Validate the X-Twilio-Signature header.

        Docs algorithm: HMAC-SHA1 over (canonical URL + form-encoded params sorted by
        key, each key/val URL-encoded then joined keyvalue), keyed by Auth Token,
        base64-encoded. Constant-time compare.
        https://www.twilio.com/docs/usage/webhooks/webhooks-security
        """
        sig_data = url
        for key in sorted(params):
            sig_data += key + params[key]
        expected = base64.b64encode(
            hmac.new(self.auth_token.encode(), sig_data.encode(), hashlib.sha1).digest()
        ).decode()
        return hmac.compare_digest(expected, signature)
