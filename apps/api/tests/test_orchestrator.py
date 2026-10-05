"""Smoke test for the conversation orchestrator using fake providers.

Verifies the full loop STT(finals) -> LLM -> TTS -> sink without external APIs.
"""

import asyncio

import pytest
from app.integrations.base import LLMProvider, STTProvider, TTSProvider
from app.models.enums import CallState
from app.voice.orchestrator import ConversationOrchestrator
from app.voice.state import CallStateMachine


class FakeLLM(LLMProvider):
    async def generate(
        self, *, system_prompt, messages, temperature=None, max_tokens=None, response_format=None
    ) -> str:
        last_user = messages[-1]["content"] if messages else ""
        return f"echo:{last_user}"


class FakeTTS(TTSProvider):
    async def synthesize_stream(self, *, text, voice=None, language=None):
        # Yield two chunks per caller turn so generation is "streaming".
        for part in text.split(" "):
            yield part.encode()


class FakeSTT(STTProvider):
    """Preloaded STT: yields configured finalized utterances then ends."""

    def __init__(self, finals: list[str]) -> None:
        self._finals = finals
        self._fed = []

    async def transcribe_stream(self, *, language=None, key_terms=None):
        for t in self._finals:
            yield {"event": "transcript.final", "text": t}
        yield {"event": "session.end"}

    async def feed_audio(self, chunk: bytes) -> None:
        self._fed.append(chunk)


@pytest.mark.asyncio
async def test_orchestrator_full_loop():
    sink_chunks: list[bytes] = []

    async def sink(chunk: bytes) -> None:
        sink_chunks.append(chunk)

    state = CallStateMachine()
    # Telephony has already connected the call before the orchestrator runs.
    await state.transition(CallState.RINGING)
    await state.transition(CallState.CONNECTED)

    orch = ConversationOrchestrator(
        llm=FakeLLM(),
        stt=FakeSTT(finals=["hello", "i want a 3bhk"]),
        tts=FakeTTS(),
        system_prompt="You are XYZ Properties assistant.",
        language="te-IN",
        sink=sink,
        state=state,
    )

    stt_task = asyncio.create_task(orch.run_stt())
    run_task = asyncio.create_task(orch.run())
    await asyncio.gather(stt_task, run_task, return_exceptions=True)

    # Both turns processed: model echoed the customer utterances into speech.
    all_out = b"".join(sink_chunks)
    assert b"hello" in all_out
    assert b"3bhk" in all_out
    assert any(m["role"] == "assistant" for m in orch.messages)
    assert any(m["role"] == "user" for m in orch.messages)
    print("transcript:", orch.messages)
