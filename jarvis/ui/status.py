"""Pure status mapping shared by GUI, diagnostics, and future integrations."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class DisplayState(str, Enum):
    STARTING = "starting"
    READY = "ready"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"
    STOPPING = "stopping"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class StatusSnapshot:
    """Content-free information suitable for display by any UI toolkit."""

    state: DisplayState
    label: str
    detail: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.state, DisplayState):
            raise TypeError("state must be a DisplayState")
        if not self.label.strip():
            raise ValueError("label must not be blank")
        if "\n" in self.label or "\n" in self.detail:
            raise ValueError("status text must be a single line")


_SNAPSHOTS = {
    DisplayState.STARTING: StatusSnapshot(DisplayState.STARTING, "Starting"),
    DisplayState.READY: StatusSnapshot(DisplayState.READY, "Ready"),
    DisplayState.LISTENING: StatusSnapshot(DisplayState.LISTENING, "Listening"),
    DisplayState.THINKING: StatusSnapshot(DisplayState.THINKING, "Thinking"),
    DisplayState.SPEAKING: StatusSnapshot(DisplayState.SPEAKING, "Speaking"),
    DisplayState.STOPPING: StatusSnapshot(DisplayState.STOPPING, "Stopping"),
    DisplayState.UNAVAILABLE: StatusSnapshot(DisplayState.UNAVAILABLE, "Unavailable"),
}


def snapshot_for(state: object, *, detail: str = "") -> StatusSnapshot:
    """Map an assistant state name to a display snapshot without exposing content."""
    name = getattr(state, "value", state)
    if not isinstance(name, str):
        raise TypeError("state must be a string or enum with a string value")
    mapping = {
        "waiting": DisplayState.READY,
        "capturing": DisplayState.LISTENING,
        "transcribing": DisplayState.THINKING,
        "responding": DisplayState.THINKING,
        "synthesizing": DisplayState.THINKING,
        "speaking": DisplayState.SPEAKING,
        "starting": DisplayState.STARTING,
        "stopping": DisplayState.STOPPING,
        "unavailable": DisplayState.UNAVAILABLE,
    }
    try:
        target = mapping[name.casefold()]
    except KeyError as exc:
        raise ValueError(f"unknown assistant state: {name}") from exc
    return StatusSnapshot(target, _SNAPSHOTS[target].label, detail=detail)
