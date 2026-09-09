"""Data models for local wake-word detection."""

from __future__ import annotations

from dataclasses import dataclass
from time import monotonic


@dataclass(frozen=True)
class WakeWordConfig:
    """Configuration shared by wake-word detector implementations."""

    wake_word: str = "jarvis"
    # Lower values improve recall at the cost of more false activations.
    threshold: float = 0.25

    def __post_init__(self) -> None:
        normalized_wake_word = self.wake_word.strip().casefold()
        if not normalized_wake_word:
            raise ValueError("wake_word must not be blank")
        if not 0 <= self.threshold <= 1:
            raise ValueError("threshold must be between zero and one")

        object.__setattr__(self, "wake_word", normalized_wake_word)


@dataclass(frozen=True)
class WakeWordDetection:
    """A local wake-word detection produced from an audio stream."""

    wake_word: str
    confidence: float | None
    detected_at: float

    def __post_init__(self) -> None:
        if not self.wake_word.strip():
            raise ValueError("wake_word must not be blank")
        if self.confidence is not None and not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between zero and one")

    @classmethod
    def create(cls, wake_word: str, confidence: float | None) -> WakeWordDetection:
        """Create a detection timestamped with the local monotonic clock."""
        return cls(
            wake_word=wake_word,
            confidence=confidence,
            detected_at=monotonic(),
        )
