"""Shared HTTP client + auth for Sarvam AI providers.

All Sarvam REST/WebSocket calls go through this module so endpoints and auth are
centralized. The API key is read from settings and never leaves the server.
"""

import logging

import httpx

from app.core.config import settings

logger = logging.getLogger("nenuaikadu.sarvam")


class SarvamError(Exception):
    """Raised for non-2xx Sarvam API responses or transport failures."""


def _headers() -> dict[str, str]:
    if not settings.sarvam_api_key:
        raise SarvamError("SARVAM_API_KEY is not configured")
    return {
        "api-subscription-key": settings.sarvam_api_key,
        "Content-Type": "application/json",
    }


async def post_json(path: str, payload: dict, *, http_timeout: float = 60.0) -> dict:
    url = f"{settings.sarvam_base_url.rstrip('/')}{path}"
    try:
        async with httpx.AsyncClient(timeout=http_timeout) as client:
            resp = await client.post(url, json=payload, headers=_headers())
    except httpx.HTTPError as exc:
        raise SarvamError(f"Sarvam transport error: {exc}") from exc

    if resp.status_code >= 400:
        logger.error("Sarvam error %s -> %s: %s", resp.status_code, url, resp.text[:500])
        raise SarvamError(f"Sarvam API error {resp.status_code}: {resp.text[:300]}")

    return resp.json()


async def get_json(path: str, *, http_timeout: float = 60.0) -> dict:
    url = f"{settings.sarvam_base_url.rstrip('/')}{path}"
    try:
        async with httpx.AsyncClient(timeout=http_timeout) as client:
            resp = await client.get(url, headers=_headers())
    except httpx.HTTPError as exc:
        raise SarvamError(f"Sarvam transport error: {exc}") from exc

    if resp.status_code >= 400:
        logger.error("Sarvam error %s -> %s: %s", resp.status_code, url, resp.text[:500])
        raise SarvamError(f"Sarvam API error {resp.status_code}: {resp.text[:300]}")

    return resp.json()
