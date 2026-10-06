"""Sarvam conversational LLM provider.

Endpoint: POST {base}/v1/chat/completions  (V1 — sarvam-105b, sarvam-105b-conversations)
Models:   `sarvam-105b-conversations` is post-trained for realtime dialogue and is the
          default for the voice-agent workload.
Structured output via `response_format: {"type": "json_schema", "json_schema": {...}}`.
Reference: https://docs.sarvam.ai/api/api-guides-tutorials/chat-completion/overview
"""

from typing import Any

from app.core.config import settings
from app.integrations.base import LLMProvider
from app.integrations.sarvam.client import SarvamError, headers, post_json


class SarvamLLM(LLMProvider):
    def __init__(
        self,
        *,
        model: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
    ) -> None:
        self.model = model or settings.sarvam_llm_model
        self._base_url = base_url
        self._api_key = api_key

    @property
    def model_name(self) -> str:
        return self.model

    def _request_headers(self) -> dict[str, str]:
        if self._api_key:
            return {
                "api-subscription-key": self._api_key,
                "Content-Type": "application/json",
            }
        return headers()

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

        body = await post_json(
            "/v1/chat/completions",
            payload,
            request_headers=self._request_headers(),
            base_url_override=self._base_url,
        )

        try:
            content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise SarvamError("Sarvam LLM response missing choices[0].message.content") from exc
        if not isinstance(content, str):
            raise SarvamError("Sarvam LLM response content was not a string")
        return content
