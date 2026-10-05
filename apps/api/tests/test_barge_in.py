"""Barge-in / interruption test.

While the AI is speaking, a customer speech_start arrives -> TTS playback is
interrupted and the final utterance drives a new response.
"""

import asyncio

import pytest
from app.integrations.base import LLMProvider, STTProvider, TTSProvider
from app.models.enums import CallState
from app.voice.orchestrator import ConversationOrchestrator
from app.voice.state import CallStateMachine


class SlowTTS(TTSProvider):
    """Yields many chunks slowly to give time for an interrupt."""

    async def synthesize_stream(self, *, text, voice=None, language=None):
        for i in range(50):
            yield f"{text}#{i}".encode()
            await asyncio.sleep(0.01)


class RecordingSink:
    def __init__(self) -> None:
        self.chunks: list[bytes] = []

    async def __call__(self, chunk: bytes) -> None:
        self.chunks.append(chunk)


class SilentLLM(LLMProvider):
    async def generate(
        self, *, system_prompt, messages, temperature=None, max_tokens=None, response_format=None
    ) -> str:
        last = messages[-1]["content"]
        return f"reply-to:{last}"


class InterruptSTT(STTProvider):
    """Emit one final, then a speech_start (barge-in) while AI speaks."""

    async def transcribe_stream(self, *, language=None, key_terms=None):
        yield {"event": "transcript.final", "text": "first question"}
        await asyncio.sleep(0.05)  # let the AI start replying
        yield {"event": "speech_start"}  # barge-in
        yield {"event": "transcript.final", "text": "interruption"}
        await asyncio.sleep(0.3)
        yield {"event": "session.end"}

    async def feed_audio(self, chunk: bytes) -> None:
        pass


@pytest.mark.asyncio
async def test_barge_in_interrupts_speech():
    sink = RecordingSink()
    state = CallStateMachine()
    await state.transition(CallState.RINGING)
    await state.transition(CallState.CONNECTED)

    orch = ConversationOrchestrator(
        llm=SilentLLM(),
        stt=InterruptSTT(),
        tts=SlowTTS(),
        system_prompt="sys",
        sink=sink,
        state=state,
    )

    stt_task = asyncio.create_task(orch.run_stt())
    run_task = asyncio.create_task(orch.run())
    await asyncio.gather(stt_task, run_task, return_exceptions=True)

    transcript_text = "".join(m["content"] for m in orch.messages)
    # The interruption utterance was processed as a user turn.
    assert "interruption" in transcript_text
    # The first question was answered before barge-in occurred.
    assert "first question" in transcript_text
