"""Shared HTTP helpers for Sarvam AI REST providers.

Centralizes the base URL, auth header, timeout, and error translation so every Sarvam
REST call fails the same way. The API key is read from settings and never leaves the
server.
"""

import json
from typing import Any, cast

import httpx

from app.core.config import settings
from app.integrations.base import ProviderError

DEFAULT_TIMEOUT_SECONDS = 60.0


class SarvamError(ProviderError):
    """Raised for non-2xx Sarvam API responses or transport failures."""


def base_url() -> str:
    return settings.sarvam_base_url.rstrip("/")


def api_key() -> str:
    key = settings.sarvam_api_key
    if not key:
        raise SarvamError("SARVAM_API_KEY is not configured")
    return key


def headers() -> dict[str, str]:
    return {
        "api-subscription-key": api_key(),
        "Content-Type": "application/json",
    }


async def post_json(
    path: str,
    payload: dict[str, Any],
    *,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    request_headers: dict[str, str] | None = None,
    base_url_override: str | None = None,
) -> dict[str, Any]:
    """POST JSON to a Sarvam path and return the decoded object."""
    root = (base_url_override or base_url()).rstrip("/")
    url = f"{root}{path}"
    send_headers = request_headers if request_headers is not None else headers()
    try:
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            resp = await client.post(url, json=payload, headers=send_headers)
    except httpx.HTTPError as exc:
        raise SarvamError(f"Sarvam transport error: {exc}") from exc
    return _check(resp, url)


def _check(resp: httpx.Response, url: str) -> dict[str, Any]:
    if resp.status_code >= 400:
        body = _safe_json(resp)
        raise SarvamError(
            extract_error_message(body, f"Sarvam error {resp.status_code}: {resp.text[:300]}")
        )
    return _as_dict(resp)


def _as_dict(resp: httpx.Response) -> dict[str, Any]:
    try:
        body = resp.json()
    except (json.JSONDecodeError, ValueError) as exc:
        raise SarvamError("Sarvam returned a non-JSON response") from exc
    if not isinstance(body, dict):
        raise SarvamError("Sarvam returned an unexpected JSON payload")
    return cast(dict[str, Any], body)


def _safe_json(resp: httpx.Response) -> dict[str, Any]:
    try:
        data = resp.json()
    except ValueError:
        return {}
    return cast(dict[str, Any], data) if isinstance(data, dict) else {}


def extract_error_message(payload: dict[str, Any], fallback: str) -> str:
    """Sarvam errors use `{"error": {"message": ...}}`; fall back to raw text."""
    error = payload.get("error")
    if isinstance(error, dict):
        message = error.get("message")
        if isinstance(message, str) and message:
            return message
    return fallback
