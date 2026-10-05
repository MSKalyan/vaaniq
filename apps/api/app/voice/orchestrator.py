"""Conversation orchestrator.

Owns the turn-taking loop between STT, LLM, and TTS for one call, plus barge-in.
Audio-transport agnostic: receives inbound audio as bytes (fed into STT) and emits
outbound audio via a sink callback — so Twilio or a browser test console can be the
transport interchangeably.

Barge-in: when the customer speaks while the AI is talking, STT emits a
`speech_start`/early partial -> the orchestrator stops TTS playback, clears queued
audio, captures the customer's speech, and generates a new response.

Only finalized customer utterances are sent to the LLM (per the spec); partials drive
interruption, never context.
"""

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import Any

from app.core.logging import get_logger
from app.integrations.base import LLMProvider, STTProvider, TTSProvider
from app.models.enums import CallState
from app.voice.state import CallStateMachine

logger = get_logger("voice.orchestrator")

AudioSink = Callable[[bytes], Awaitable[None]]

SYSTEM_PROMPT_TEMPLATE = """You are an AI voice assistant.

{system_prompt}

Conversation rules:
- Speak in the customer's preferred language.
- Be polite, concise and conversational. Ask one question at a time.
- Never invent facts, prices, availability or policies. If you do not know,
  say you can arrange a callback.
- If the customer asks not to be contacted again, note it (the platform enforces
  DO_NOT_CALL separately).
- Keep responses short and speakable (1 to 3 sentences).
"""


class ConversationOrchestrator:
    """Runs a single voice conversation for one call/customer.

    Wire-up (Twilio transport):
        orch = ConversationOrchestrator(...)
        stt_task = asyncio.create_task(orch.run_stt())   # pumps stt -> handle_stt_event
        turn_task = asyncio.create_task(orch.run())       # pumps finals -> LLM -> TTS -> sink
        await orch.feed_audio(chunk)  # from Twilio media stream
        ...
        await orch.close()
    """

    def __init__(
        self,
        *,
        llm: LLMProvider,
        stt: STTProvider,
        tts: TTSProvider,
        system_prompt: str,
        language: str = "auto",
        voice: str | None = None,
        temperature: float = 0.7,
        max_listen_s: float = 30.0,
        sink: AudioSink,
        state: CallStateMachine | None = None,
    ) -> None:
        self.llm = llm
        self.stt = stt
        self.tts = tts
        self.system_prompt = SYSTEM_PROMPT_TEMPLATE.format(system_prompt=system_prompt)
        self.language = language
        self.voice = voice
        self.temperature = temperature
        self.max_listen_s = max_listen_s
        self.sink = sink
        self.state = state or CallStateMachine()

        # Finalized customer utterances (ASR) waiting to be processed.
        self._utterance_queue: asyncio.Queue[str] = asyncio.Queue()
        self._stop = asyncio.Event()  # set by close(): force termination
        self._stt_ended = asyncio.Event()  # set when STT stream ends
        self._tts_stop = asyncio.Event()

        self.messages: list[dict[str, str]] = []
        self._greeting: str = ""
        self._speaking = False
        self._latency: dict[str, float] = {}

    @property
    def latency(self) -> dict[str, float]:
        return dict(self._latency)

    # ----- inbound audio (from transport) -----
    async def feed_audio(self, chunk: bytes) -> None:
        """Feed inbound customer audio into the STT stream."""
        await self.stt.feed_audio(chunk)

    def set_greeting(self, greeting: str) -> None:
        self._greeting = greeting

    # ----- STT event ingestion -----
    async def handle_stt_event(self, event: dict[str, Any]) -> None:
        """Process one STT event (from run_stt)."""
        ev = event.get("event")
        if ev == "speech_start":
            if self._speaking:
                await self._barge_in()
        elif ev == "transcript.final":
            text = (event.get("text") or "").strip()
            if text:
                await self._utterance_queue.put(text)
        elif ev in ("session.end", "error"):
            # End of audio stream: drain any queued finals, then let the loop finish.
            self._stt_ended.set()

    async def _barge_in(self) -> None:
        logger.info("barge_in: customer spoke during TTS; interrupting playback")
        self._tts_stop.set()
        self._speaking = False
        try:
            await self.state.transition(CallState.INTERRUPTED)
        except Exception:  # noqa: S110 - interruption already handled
            pass

    # ----- TTS -----
    async def _speak(self, text: str) -> None:
        self._tts_stop = asyncio.Event()
        self._speaking = True
        try:
            async for chunk in self.tts.synthesize_stream(
                text=text, voice=self.voice, language=self.language
            ):
                if self._tts_stop.is_set():
                    break
                await self.sink(chunk)
        except Exception as exc:  # TTS failures must not kill the call
            logger.warning("tts_error", error=str(exc))
        finally:
            self._speaking = False
            self._tts_stop.set()

    # ----- STT pump (run concurrently with run) -----
    async def run_stt(self, *, language: str | None = None) -> None:
        """Consume the STT stream and dispatch events into handle_stt_event."""
        try:
            async for event in self.stt.transcribe_stream(language=language):
                await self.handle_stt_event(event)
        except Exception as exc:
            logger.warning("stt_stream_error", error=str(exc))
        finally:
            # STT stream ended -> allow the turn loop to drain then finish.
            self._stt_ended.set()

    # ----- main turn loop -----
    async def run(self) -> None:
        """Process finalized utterances until the call ends or `close` is called."""
        await self.state.transition(CallState.GREETING)
        if self._greeting:
            await self._speak(self._greeting)

        while not self.state.is_terminal() and not self._stop.is_set():
            await self.state.transition(CallState.LISTENING)
            utterance = await self._wait_for_utterance()
            if utterance is None:
                break
            await self._process_turn(utterance)
            # After answering, loop if the stream is not closed yet.

    async def _wait_for_utterance(self) -> str | None:
        """Wait for the next finalized utterance, or None on timeout/stream-end."""
        while True:
            # Prefer any queued utterance already waiting.
            if not self._utterance_queue.empty():
                return self._utterance_queue.get_nowait()
            if self._stt_ended.is_set():
                return None
            try:
                return await asyncio.wait_for(
                    self._utterance_queue.get(), timeout=self.max_listen_s
                )
            except TimeoutError:
                # No new speech and stream still open -> keep listening a bit.
                # If nothing ever arrives, max_listen_s bounds this turn.
                if self._stt_ended.is_set():
                    return None
                continue
            except asyncio.CancelledError:
                return None

    async def _process_turn(self, utterance: str) -> None:
        await self.state.transition(CallState.PROCESSING)
        self.messages.append({"role": "user", "content": utterance})

        t0 = time.monotonic()
        response = await self.llm.generate(
            system_prompt=self.system_prompt,
            messages=self.messages[-8:],  # short-term memory: last N messages
            temperature=self.temperature,
        )
        self._latency["llm_total"] = (time.monotonic() - t0) * 1000.0

        self.messages.append({"role": "assistant", "content": response})
        await self.state.transition(CallState.SPEAKING)
        await self._speak(response)

    # ----- teardown -----
    async def close(self) -> None:
        self._stop.set()
        self._tts_stop.set()
