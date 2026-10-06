"""Smoke test for the conversation orchestrator using fake providers.

Verifies the full loop STT(finals) -> LLM -> TTS -> sink without external APIs.
"""

import asyncio

import pytest
from app.models.enums import CallState, Speaker
from app.voice.orchestrator import ConversationOrchestrator
from app.voice.state import CallStateMachine

from tests.fakes import FakeLLM, FakeTTS, FinalsSTT


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
        stt=FinalsSTT(finals=["hello", "i want a 3bhk"]),
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


@pytest.mark.asyncio
async def test_orchestrator_reports_transcript_and_closes_stt():
    """Finalized turns reach the transcript hook, and close() releases the STT."""
    turns: list[tuple[str, str, bool]] = []

    async def on_transcript(speaker: str, text: str, is_final: bool) -> None:
        turns.append((speaker, text, is_final))

    stt = FinalsSTT(finals=["what is the price"])

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
        on_transcript=on_transcript,
        greeting="Hello, how can I help?",
    )

    await asyncio.gather(
        asyncio.create_task(orch.run_stt()),
        asyncio.create_task(orch.run()),
        return_exceptions=True,
    )
    await orch.close()

    spoken = [(speaker, text) for speaker, text, final in turns if final]
    assert (Speaker.AI.value, "Hello, how can I help?") in spoken
    assert any(
        speaker == Speaker.CUSTOMER.value and text == "what is the price"
        for speaker, text in spoken
    )
    assert stt.closed is True


@pytest.mark.asyncio
async def test_partial_transcripts_do_not_enter_context():
    """Only finalized utterances reach the LLM — partials must not."""
    llm = FakeLLM()
    stt = FinalsSTT(finals=["complete sentence"])

    async def sink(chunk: bytes) -> None:
        return None

    state = CallStateMachine()
    await state.transition(CallState.RINGING)
    await state.transition(CallState.CONNECTED)
    orch = ConversationOrchestrator(
        llm=llm, stt=stt, tts=FakeTTS(), system_prompt="sys", sink=sink, state=state
    )

    await orch.handle_stt_event({"event": "transcript.partial", "text": "complete sen"})
    await asyncio.gather(
        asyncio.create_task(orch.run_stt()),
        asyncio.create_task(orch.run()),
        return_exceptions=True,
    )

    user_turns = [m["content"] for m in orch.messages if m["role"] == "user"]
    assert user_turns == ["complete sentence"]


@pytest.mark.asyncio
async def test_knowledge_context_is_injected_into_prompt():
    llm = FakeLLM()
    stt = FinalsSTT(finals=["what are your opening hours?"])

    async def sink(chunk: bytes) -> None:
        return None

    state = CallStateMachine()
    await state.transition(CallState.RINGING)
    await state.transition(CallState.CONNECTED)
    orch = ConversationOrchestrator(
        llm=llm, stt=stt, tts=FakeTTS(), system_prompt="You sell homes.", sink=sink, state=state
    )
    orch.set_knowledge(["We are open 9am to 7pm daily."])

    await asyncio.gather(
        asyncio.create_task(orch.run_stt()),
        asyncio.create_task(orch.run()),
        return_exceptions=True,
    )

    assert "9am to 7pm" in llm.calls[0]["system_prompt"]


@pytest.mark.asyncio
async def test_latency_metrics_are_reported():
    async def sink(chunk: bytes) -> None:
        return None

    state = CallStateMachine()
    await state.transition(CallState.RINGING)
    await state.transition(CallState.CONNECTED)
    orch = ConversationOrchestrator(
        llm=FakeLLM(),
        stt=FinalsSTT(finals=["hi"]),
        tts=FakeTTS(),
        system_prompt="sys",
        sink=sink,
        state=state,
    )

    await asyncio.gather(
        asyncio.create_task(orch.run_stt()),
        asyncio.create_task(orch.run()),
        return_exceptions=True,
    )

    latency = orch.latency
    assert latency["llm_total"] >= 0
    assert latency["tts_first_chunk"] >= 0
    assert latency["turn_total"] >= latency["llm_total"]
