"""Sarvam conversational LLM provider.

Endpoint: POST {base}/v1/chat/completions  (V1, Sarvam models)
Models:   sarvam-105b, sarvam-105b-conversations (voice-agent workload)
Structured output via response_format: {"type":"json_schema","json_schema":{...}}
Reference: https://docs.sarvam.ai/api-reference/chat/chat-completions-v1
"""

from typing import Any

import httpx

from app.core.config import settings
from app.integrations.base import LLMProvider
from app.integrations.sarvam.client import SarvamError


class SarvamLLM(LLMProvider):
    def __init__(
        self,
        *,
        model: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
    ) -> None:
        self.model = model or settings.sarvam_llm_model
        self.base_url = (base_url or settings.sarvam_base_url).rstrip("/")
        self._api_key = api_key or settings.sarvam_api_key

    def _headers(self) -> dict[str, str]:
        if not self._api_key:
            raise SarvamError("SARVAM_API_KEY is not configured")
        return {
            "api-subscription-key": self._api_key,
            "Content-Type": "application/json",
        }

    async def generate(
        self,
        *,
        system_prompt: str,
        messages: list[dict[str, str]],
        temperature: float | None = None,
        max_tokens: int | None = None,
        response_format: dict[str, Any] | None = None,
    ) -> str:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "system", "content": system_prompt}, *messages],
        }
        if temperature is not None:
            payload["temperature"] = temperature
        payload["max_tokens"] = max_tokens or settings.sarvam_llm_max_tokens
        if response_format is not None:
            payload["response_format"] = response_format

        url = f"{self.base_url}/v1/chat/completions"
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(url, json=payload, headers=self._headers())
        except httpx.HTTPError as exc:
            raise SarvamError(f"Sarvam LLM transport error: {exc}") from exc

        if resp.status_code >= 400:
            raise SarvamError(f"Sarvam LLM error {resp.status_code}: {resp.text[:300]}")

        body = resp.json()
        try:
            content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:
            raise SarvamError("Sarvam LLM response missing choices[0].message.content") from exc
        return content
