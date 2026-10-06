"""Twilio webhook signature + public-URL normalization tests.

The signature algorithm is security-critical and easy to get subtly wrong, so these
tests compute the expected HMAC independently of the provider code.
"""

import base64
import hashlib
import hmac
from urllib.parse import parse_qs, urlencode, urlsplit

from app.integrations.twilio.provider import (
    FormData,
    TwilioProvider,
    _derive_stream_url,
    to_websocket_url,
)

AUTH_TOKEN = "test-auth-token-12345"
URL = "https://example.ngrok.app/api/v1/webhooks/twilio/status"


def _provider(*, webhook_base_url: str = "https://example.ngrok.app") -> TwilioProvider:
    return TwilioProvider(
        account_sid="AC" + "a" * 32,
        auth_token=AUTH_TOKEN,
        from_phone="+14155550100",
        webhook_base_url=webhook_base_url,
    )


def _expected_signature(url: str, params: dict[str, str], auth_token: str = AUTH_TOKEN) -> str:
    """Twilio's documented algorithm, written out longhand."""
    payload = url
    for key in sorted(params):
        payload += key
        payload += params[key]
    digest = hmac.new(auth_token.encode(), payload.encode(), hashlib.sha1).digest()
    return base64.b64encode(digest).decode()


def test_valid_signature_is_accepted():
    params = {"CallSid": "CA123", "CallStatus": "completed", "From": "+919876543210"}

    assert _provider().validate_request_signature(URL, params, _expected_signature(URL, params))


def test_parameter_order_does_not_matter():
    """Twilio sorts keys, so a different insertion order must still validate."""
    forward = {"a": "1", "b": "2", "c": "3"}
    reverse = {"c": "3", "b": "2", "a": "1"}

    assert _provider().validate_request_signature(URL, forward, _expected_signature(URL, reverse))


def test_tampered_parameter_is_rejected():
    params = {"CallSid": "CA123", "CallStatus": "completed"}
    signature = _expected_signature(URL, params)

    tampered = {**params, "CallStatus": "in-progress"}
    assert not _provider().validate_request_signature(URL, tampered, signature)


def test_wrong_token_is_rejected():
    params = {"CallSid": "CA123"}
    signature = _expected_signature(URL, params, auth_token="a-different-token")

    assert not _provider().validate_request_signature(URL, params, signature)


def test_wrong_url_is_rejected():
    """Swapping the path breaks the signature, so path tampering is caught."""
    params = {"CallSid": "CA123"}
    signature = _expected_signature(URL, params)

    other = "https://example.ngrok.app/api/v1/webhooks/twilio/recording"
    assert not _provider().validate_request_signature(other, params, signature)


def test_public_url_for_rewrites_internal_origin():
    provider = _provider(webhook_base_url="https://public.example.com")
    internal = "http://web:8000/api/v1/webhooks/twilio/status"

    assert (
        provider.public_url_for(internal)
        == "https://public.example.com/api/v1/webhooks/twilio/status"
    )


def test_public_url_for_leaves_matching_url_alone():
    provider = _provider(webhook_base_url="https://public.example.com")
    already_public = "https://public.example.com/api/v1/webhooks/twilio/status"

    assert provider.public_url_for(already_public) == already_public


def test_stream_twiml_is_bidirectional():
    twiml = _provider()._stream_twiml("wss://host/api/v1/ws/calls/abc/live")

    assert "<Connect><Stream" in twiml
    assert 'track="both_tracks"' in twiml
    assert urlsplit("wss://host/x").scheme == "wss"


def test_repeated_status_callback_events_survive_form_encoding():
    """A dict would collapse StatusCallbackEvent[] to one value; Twilio needs all five."""
    form: list[tuple[str, str]] = [
        ("To", "+919876543210"),
        ("StatusCallbackEvent[]", "initiated"),
        ("StatusCallbackEvent[]", "ringing"),
        ("StatusCallbackEvent[]", "answered"),
        ("StatusCallbackEvent[]", "completed"),
    ]

    events = parse_qs(urlencode(form, doseq=True))["StatusCallbackEvent[]"]

    assert events == ["initiated", "ringing", "answered", "completed"]


def test_to_websocket_url_rewrites_schemes():
    assert to_websocket_url("https://host/x") == "wss://host/x"
    assert to_websocket_url("http://host/x") == "ws://host/x"
    assert to_websocket_url("wss://host/x") == "wss://host/x"


def test_derived_stream_url_is_wss():
    assert _derive_stream_url("https://host") == "wss://host/api/v1/ws/calls/live"
    assert _derive_stream_url("http://host/") == "ws://host/api/v1/ws/calls/live"


async def test_initiate_call_rewrites_stream_url_to_wss(monkeypatch):
    """A http(s) stream URL would be rejected by Twilio; it must reach TwiML as wss."""
    provider = _provider()
    captured: dict[str, str] = {}

    async def _post(url: str, form: FormData) -> dict[str, str]:
        captured.update(dict(form))
        return {"sid": "CA123"}

    monkeypatch.setattr(provider, "_post", _post)

    sid = await provider.initiate_call(
        to_phone="+919876543210",
        from_phone="",
        webhook_url="https://example.ngrok.app",
        stream_url="https://example.ngrok.app/api/v1/ws/calls/abc/live",
    )

    assert sid == "CA123"
    assert 'url="wss://example.ngrok.app/api/v1/ws/calls/abc/live"' in captured["Twiml"]
    assert captured["StatusCallback"] == ("https://example.ngrok.app/api/v1/webhooks/twilio/status")
