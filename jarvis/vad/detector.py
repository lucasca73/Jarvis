"""Backend-independent streaming voice activity contracts."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
import math

from jarvis.audio import AudioChunk


@dataclass(frozen=True)
class VadConfig:
    """Speech trigger and debounce durations, independent of request timeouts."""

    threshold: float = 0.5
    min_speech_duration: float = 0.25
    min_silence_duration: float = 0.5

    def __post_init__(self) -> None:
        if not 0 < self.threshold < 1:
            raise ValueError("threshold must be between zero and one, exclusive")
        for value in (self.min_speech_duration, self.min_silence_duration):
            if not math.isfinite(value) or value <= 0:
                raise ValueError("VAD durations must be finite and positive")


@dataclass(frozen=True)
class VoiceActivity:
    """Debounced speech state for one processed window, not a transcript.

    duration_seconds counts consumed samples, allowing a controller to track
    audio time without depending on processing speed or wall-clock timestamps.
    """

    is_speech: bool
    duration_seconds: float

    def __post_init__(self) -> None:
        if not math.isfinite(self.duration_seconds) or self.duration_seconds <= 0:
            raise ValueError("duration_seconds must be finite and positive")


class VoiceActivityDetector(ABC):
    @abstractmethod
    def process(self, chunk: AudioChunk) -> tuple[VoiceActivity, ...]:
        """Return ordered window decisions; retain incomplete windows in memory."""

    @abstractmethod
    def reset(self) -> None:
        """Discard pending audio and speech state before a new capture."""
