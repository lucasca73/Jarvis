"""In-memory contracts for local speech synthesis and audio playback."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from jarvis.llm import TextResponse


@dataclass(frozen=True)
class SynthesizedAudio:
    """PCM audio produced in memory for a response."""

    data: bytes = field(repr=False)
    sample_rate: int = 16_000
    channels: int = 1
    sample_width_bytes: int = 2

    def __post_init__(self) -> None:
        if not isinstance(self.data, bytes) or not self.data:
            raise ValueError('data must be nonempty PCM bytes')
        if self.sample_rate <= 0 or self.channels <= 0 or self.sample_width_bytes <= 0:
            raise ValueError('audio format values must be positive')
        if len(self.data) % (self.channels * self.sample_width_bytes):
            raise ValueError('data must align with complete PCM frames')

    @property
    def frame_count(self) -> int:
        return len(self.data) // (self.channels * self.sample_width_bytes)

    @property
    def duration_seconds(self) -> float:
        return self.frame_count / self.sample_rate


class SynthesisError(RuntimeError):
    """Local synthesis failure without speech text in the message."""


class AudioPlayerError(RuntimeError):
    """Playback failure without audio contents in the message."""


class Synthesizer(ABC):
    """Convert one text response into in-memory PCM audio."""

    @abstractmethod
    def synthesize(self, response: TextResponse) -> SynthesizedAudio:
        """Return audio or raise a content-free SynthesisError."""

    @abstractmethod
    def close(self) -> None:
        """Release backend resources; repeated calls must be safe."""

    def __enter__(self) -> Synthesizer:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


class AudioPlayer(ABC):
    """Play synthesized PCM and expose lifecycle state."""

    @property
    @abstractmethod
    def is_playing(self) -> bool:
        """Whether playback is currently active."""

    @abstractmethod
    def play(self, audio: SynthesizedAudio) -> None:
        """Play audio in memory or raise AudioPlayerError."""

    @abstractmethod
    def stop(self) -> None:
        """Stop playback and release active output resources."""

    def __enter__(self) -> AudioPlayer:
        return self

    def __exit__(self, *_: object) -> None:
        self.stop()
