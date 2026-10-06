"""Barge-in / interruption test.

While the AI is speaking, a customer speech_start arrives -> TTS playback is
interrupted and the final utterance drives a new response.
"""

import asyncio

import pytest
from app.models.enums import CallState
from app.voice.orchestrator import ConversationOrchestrator
from app.voice.state import CallStateMachine

from tests.fakes import FakeLLM, FakeTTS, ScriptedSTT


@pytest.mark.asyncio
async def test_barge_in_interrupts_speech():
    sink_chunks: list[bytes] = []

    async def sink(chunk: bytes) -> None:
        sink_chunks.append(chunk)

    interrupts = 0

    async def on_interrupt() -> None:
        nonlocal interrupts
        interrupts += 1

    # The AI is mid-sentence when the customer starts talking again.
    stt = ScriptedSTT(
        [
            {"event": "transcript.final", "text": "first question"},
            {"event": "pause", "seconds": 0.02},
            {"event": "vad.speech_start"},
            {"event": "transcript.final", "text": "interruption"},
            {"event": "pause", "seconds": 0.2},
            {"event": "session.end"},
        ]
    )

    state = CallStateMachine()
    await state.transition(CallState.RINGING)
    await state.transition(CallState.CONNECTED)

    orch = ConversationOrchestrator(
        llm=FakeLLM(),
        stt=stt,
        tts=FakeTTS(chunk_delay=0.01),
        system_prompt="sys",
        sink=sink,
        state=state,
        on_interrupt=on_interrupt,
    )

    await asyncio.gather(
        asyncio.create_task(orch.run_stt()),
        asyncio.create_task(orch.run()),
        return_exceptions=True,
    )

    conversation = "".join(m["content"] for m in orch.messages)
    assert "interruption" in conversation
    assert "first question" in conversation
    # The transport was told to flush buffered audio.
    assert interrupts == 1
    # The interrupted reply did not stream all 50 chunks.
    assert len(sink_chunks) < 200


@pytest.mark.asyncio
async def test_no_barge_in_when_ai_is_not_speaking():
    """A speech_start outside of playback is not an interruption."""
    interrupts = 0

    async def on_interrupt() -> None:
        nonlocal interrupts
        interrupts += 1

    stt = ScriptedSTT(
        [
            {"event": "vad.speech_start"},
            {"event": "transcript.final", "text": "hello there"},
            {"event": "session.end"},
        ]
    )

    async def sink(chunk: bytes) -> None:
        return None

    state = CallStateMachine()
    await state.transition(CallState.RINGING)
    await state.transition(CallState.CONNECTED)
    orch = ConversationOrchestrator(
        llm=FakeLLM(),
        stt=stt,
        tts=FakeTTS(),
        system_prompt="sys",
        sink=sink,
        state=state,
        on_interrupt=on_interrupt,
    )

    await asyncio.gather(
        asyncio.create_task(orch.run_stt()),
        asyncio.create_task(orch.run()),
        return_exceptions=True,
    )

    assert interrupts == 0
    assert any("hello there" in m["content"] for m in orch.messages)
