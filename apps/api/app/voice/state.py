"""Explicit call state machine.

Transitions are validated; invalid transitions raise `InvalidStateTransitionError`.
States: INITIALIZING, RINGING, CONNECTED, GREETING, LISTENING, PROCESSING,
SPEAKING, INTERRUPTED, ENDING, COMPLETED, FAILED.

A per-instance lock guards transitions against concurrent STT/TTS/worker coroutines.
"""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field

from app.models.enums import CallState


class InvalidStateTransitionError(Exception):
    pass


# Allowed transitions. Completing/failing is allowed from most states.
TRANSITIONS: dict[CallState, set[CallState]] = {
    CallState.INITIALIZING: {CallState.RINGING, CallState.FAILED},
    CallState.RINGING: {CallState.CONNECTED, CallState.COMPLETED, CallState.FAILED},
    CallState.CONNECTED: {CallState.GREETING, CallState.LISTENING, CallState.FAILED},
    CallState.GREETING: {CallState.LISTENING, CallState.SPEAKING, CallState.FAILED},
    CallState.LISTENING: {
        CallState.PROCESSING,
        CallState.ENDING,
        CallState.INTERRUPTED,
        CallState.FAILED,
    },
    CallState.PROCESSING: {
        CallState.SPEAKING,
        CallState.ENDING,
        CallState.FAILED,
    },
    CallState.SPEAKING: {
        CallState.LISTENING,
        CallState.INTERRUPTED,
        CallState.ENDING,
        CallState.FAILED,
    },
    CallState.INTERRUPTED: {CallState.LISTENING, CallState.FAILED},
    CallState.ENDING: {CallState.COMPLETED, CallState.FAILED},
    CallState.COMPLETED: set(),
    CallState.FAILED: set(),
}


@dataclass
class CallStateMachine:
    """Tracks the current call state with validated transitions and a lock."""

    _state: CallState = field(default=CallState.INITIALIZING, init=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)
    on_change: Callable[[CallState], None] | None = None

    @property
    def state(self) -> CallState:
        return self._state

    async def transition(self, new_state: CallState) -> None:
        async with self._lock:
            allowed = TRANSITIONS.get(self._state, set())
            if new_state not in allowed:
                raise InvalidStateTransitionError(
                    f"Cannot transition {self._state.value} -> {new_state.value}"
                )
            self._state = new_state
            if self.on_change is not None:
                self.on_change(new_state)

    def is_terminal(self) -> bool:
        return self._state in (CallState.COMPLETED, CallState.FAILED)

    async def can_transition_to(self, target: CallState) -> bool:
        return target in TRANSITIONS.get(self._state, set())
