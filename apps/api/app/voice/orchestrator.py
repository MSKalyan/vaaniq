"""Conversation orchestrator.

Owns the turn-taking loop between STT, LLM, and TTS for one call, plus barge-in.
Audio-transport agnostic: receives inbound audio as bytes (fed into STT) and emits
outbound audio via a sink callback — so Twilio or a browser test console can be the
transport interchangeably.

Barge-in: when the customer speaks while the AI is talking, STT emits
`vad.speech_start` -> the orchestrator stops TTS playback, notifies the transport to
clear its buffered audio, captures the customer's speech, and answers again.

Only finalized customer utterances are sent to the LLM; partials drive interruption,
never conversational context.
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
# Called with (speaker, text, is_final) so transports can persist the transcript.
TranscriptHook = Callable[[str, str, bool], Awaitable[None]]
# Called when playback must be flushed (barge-in).
InterruptHook = Callable[[], Awaitable[None]]

SYSTEM_PROMPT_TEMPLATE = """You are an AI voice assistant for a business.

Agent instructions:
{system_prompt}

Conversation rules:
- Speak in the customer's preferred language.
- Be polite, concise and conversational. Ask one question at a time.
- Never invent facts, prices, availability or policies. If you do not know,
  say you can arrange a callback.
- If the customer asks not to be contacted again, acknowledge it.
- Keep responses short and speakable (1 to 3 sentences).
{knowledge_block}"""

# Recent turns kept for short-term memory.
SHORT_TERM_MEMORY_TURNS = 8


class ConversationOrchestrator:
    """Runs a single voice conversation for one call/customer.

    Wire-up (Twilio transport):

        orch = ConversationOrchestrator(...)
        stt_task = asyncio.create_task(orch.run_stt())   # pumps stt -> handle_stt_event
        turn_task = asyncio.create_task(orch.run())       # pumps finals -> LLM -> TTS -> sink
        await orch.feed_audio(chunk)                       # from Twilio media stream
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
        max_call_duration_s: float = 600.0,
        sink: AudioSink,
        state: CallStateMachine | None = None,
        greeting: str = "",
        on_transcript: TranscriptHook | None = None,
        on_interrupt: InterruptHook | None = None,
    ) -> None:
        self.llm = llm
        self.stt = stt
        self.tts = tts
        self.language = language
        self.voice = voice
        self.temperature = temperature
        self.max_listen_s = max_listen_s
        self.max_call_duration_s = max_call_duration_s
        self.sink = sink
        self.state = state or CallStateMachine()
        self.greeting = greeting
        self.on_transcript = on_transcript
        self.on_interrupt = on_interrupt
        self._agent_instructions = system_prompt

        # Finalized customer utterances (ASR) waiting to be processed.
        self._utterance_queue: asyncio.Queue[str] = asyncio.Queue()
        self._stop = asyncio.Event()  # set by close(): force termination
        self._stt_ended = asyncio.Event()  # set when the STT stream ends
        self._tts_stop = asyncio.Event()

        self.messages: list[dict[str, str]] = []
        self._conversation_log: list[dict[str, str]] = []
        self._knowledge_block = ""
        self._speaking = False
        self._latency: dict[str, float] = {}
        self.turn_count = 0

    @property
    def system_prompt(self) -> str:
        """Base instructions plus any knowledge-base context injected at runtime."""
        knowledge = (
            f"\nRelevant knowledge:\n{self._knowledge_block}\n" if self._knowledge_block else ""
        )
        return SYSTEM_PROMPT_TEMPLATE.format(
            system_prompt=self._agent_instructions, knowledge_block=knowledge
        )

    @property
    def latency(self) -> dict[str, float]:
        """Per-stage timings in ms: llm_total, tts_first_chunk, turn_total."""
        return dict(self._latency)

    @property
    def transcript(self) -> list[dict[str, str]]:
        """In-memory transcript (also streamed to the persistence hook)."""
        return list(self._conversation_log)

    def set_agent_instructions(self, instructions: str) -> None:
        self._agent_instructions = instructions

    def set_knowledge(self, snippets: list[str]) -> None:
        """Inject retrieved knowledge-base snippets into the next LLM turn."""
        self._knowledge_block = "\n".join(f"- {snippet}" for snippet in snippets)

    def set_greeting(self, greeting: str) -> None:
        self.greeting = greeting

    # ----- inbound audio (from transport) -----
    async def feed_audio(self, chunk: bytes) -> None:
        """Feed inbound customer audio into the STT stream."""
        await self.stt.feed_audio(chunk)

    # ----- STT event ingestion -----
    async def handle_stt_event(self, event: dict[str, Any]) -> None:
        """Process one STT event (from run_stt)."""
        ev = event.get("event")

        # Sarvam realtime STT names this vad.speech_start; older/other providers
        # may use speech_start. Both mean "customer started talking".
        if ev in ("vad.speech_start", "speech_start"):
            if self._speaking:
                await self._barge_in()
            return

        if ev == "transcript.partial":
            text = (event.get("text") or "").strip()
            if text:
                await self._emit_transcript("CUSTOMER", text, is_final=False)
            return

        if ev == "transcript.final":
            text = (event.get("text") or "").strip()
            language = event.get("language_code") or event.get("language")
            if text:
                await self._emit_transcript("CUSTOMER", text, is_final=True, language=language)
                await self._utterance_queue.put(text)
            return

        if ev == "vad.speech_end":
            await self._emit_system_event("customer_speech_end")
            return

        if ev in ("session.end", "error"):
            # End of audio stream: drain queued finals, then let the loop finish.
            await self._emit_system_event(f"stt_{ev}")
            self._stt_ended.set()

    async def _barge_in(self) -> None:
        logger.info("barge_in: customer spoke during TTS; interrupting playback")
        self._tts_stop.set()
        self._speaking = False
        if self.on_interrupt is not None:
            await self.on_interrupt()
        try:
            await self.state.transition(CallState.INTERRUPTED)
        except Exception:  # noqa: BLE001, S110 - interruption is best-effort
            pass

    async def _emit_transcript(
        self,
        speaker: str,
        text: str,
        *,
        is_final: bool,
        language: str | None = None,
    ) -> None:
        if not is_final:
            return
        self._conversation_log.append(
            {"speaker": speaker, "text": text, "language": language or ""}
        )
        if self.on_transcript is None:
            return
        try:
            await self.on_transcript(speaker, text, is_final)
        except Exception as exc:  # noqa: BLE001 - persistence must not break the call
            logger.warning("transcript_hook_error", error=str(exc))

    async def _emit_system_event(self, event: str) -> None:
        await self._emit_transcript("SYSTEM", event, is_final=True)

    # ----- TTS -----
    async def _speak(self, text: str) -> None:
        self._tts_stop = asyncio.Event()
        self._speaking = True
        first_chunk = True
        t0 = time.monotonic()
        try:
            async for chunk in self.tts.synthesize_stream(
                text=text, voice=self.voice, language=self.language
            ):
                if first_chunk:
                    self._latency["tts_first_chunk"] = (time.monotonic() - t0) * 1000.0
                    first_chunk = False
                if self._tts_stop.is_set():
                    break
                await self.sink(chunk)
        except Exception as exc:  # noqa: BLE001 - a TTS failure must not kill the call
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
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.warning("stt_stream_error", error=str(exc))
        finally:
            self._stt_ended.set()

    # ----- main turn loop -----
    async def run(self) -> None:
        """Process finalized utterances until the call ends or `close` is called."""
        await self._ensure_connected()
        deadline = time.monotonic() + self.max_call_duration_s
        await self.state.transition(CallState.GREETING)
        if self.greeting:
            await self._emit_transcript("AI", self.greeting, is_final=True)
            self.messages.append({"role": "assistant", "content": self.greeting})
            await self._speak(self.greeting)

        while not self.state.is_terminal() and not self._stop.is_set():
            if time.monotonic() >= deadline:
                logger.info("voice_call_max_duration_reached", max_s=self.max_call_duration_s)
                break
            await self.state.transition(CallState.LISTENING)
            utterance = await self._wait_for_utterance(
                min(deadline - time.monotonic(), self.max_listen_s)
            )
            if utterance is None:
                break
            await self._process_turn(utterance)

    async def _ensure_connected(self) -> None:
        """Put the state machine at CONNECTED before starting the voice flow.

        Telephony has already connected the call before the orchestrator runs, so an
        untouched (INITIALIZING/RINGING) machine is advanced to CONNECTED; already-
        connected machines are left alone. GREETING/LISTENING must follow CONNECTED.
        """
        for target in (CallState.RINGING, CallState.CONNECTED):
            if await self.state.can_transition_to(target):
                await self.state.transition(target)

    async def _wait_for_utterance(self, timeout_s: float | None = None) -> str | None:
        """Wait for the next finalized utterance, or None on timeout/stream-end.

        Waits on the queue and the stream-ended event together, so a stream that ends
        while the call is idle finishes right away instead of after the timeout.
        """
        timeout_s = self.max_listen_s if timeout_s is None else max(timeout_s, 0.0)
        while True:
            if not self._utterance_queue.empty():
                return self._utterance_queue.get_nowait()
            if self._stt_ended.is_set() or timeout_s <= 0:
                return None

            getter = asyncio.ensure_future(self._utterance_queue.get())
            ended = asyncio.ensure_future(self._stt_ended.wait())
            try:
                done, _ = await asyncio.wait(
                    {getter, ended},
                    timeout=timeout_s,
                    return_when=asyncio.FIRST_COMPLETED,
                )
            except asyncio.CancelledError:
                getter.cancel()
                ended.cancel()
                raise

            ended.cancel()
            if getter in done:
                return getter.result()
            getter.cancel()
            # Stream ended, or the listen window expired with no speech. Loop back:
            # an ended stream returns None, silence alone keeps waiting.
            if self._stt_ended.is_set():
                return None

    async def _process_turn(self, utterance: str) -> None:
        turn_start = time.monotonic()
        await self.state.transition(CallState.PROCESSING)
        self.messages.append({"role": "user", "content": utterance})
        self.turn_count += 1

        t0 = time.monotonic()
        response = await self.llm.generate(
            system_prompt=self.system_prompt,
            messages=self.messages[-SHORT_TERM_MEMORY_TURNS:],
            temperature=self.temperature,
        )
        self._latency["llm_total"] = (time.monotonic() - t0) * 1000.0

        response = response.strip()
        if response:
            self.messages.append({"role": "assistant", "content": response})
            await self._emit_transcript("AI", response, is_final=True)
            await self.state.transition(CallState.SPEAKING)
            await self._speak(response)

        self._latency["turn_total"] = (time.monotonic() - turn_start) * 1000.0

    # ----- teardown -----
    async def close(self) -> None:
        """Stop the loop, stop TTS playback, and release the STT connection."""
        self._stop.set()
        self._tts_stop.set()
        self._stt_ended.set()
        try:
            await self.stt.close()
        except Exception as exc:  # noqa: BLE001 - teardown must not raise
            logger.warning("stt_close_error", error=str(exc))
