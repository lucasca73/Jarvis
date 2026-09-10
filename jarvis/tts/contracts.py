"""In-memory contracts for local speech synthesis and audio playback."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from jarvis.llm import TextResponse


@dataclass(frozen=True)
class SynthesizedAudio:
    """Signed little-endian integer PCM kept in memory for a response."""

    data: bytes = field(repr=False)
    sample_rate: int = 16_000
    channels: int = 1
    sample_width_bytes: int = 2

    def __post_init__(self) -> None:
        if not isinstance(self.data, bytes) or not self.data:
            raise ValueError('data must be nonempty PCM bytes')
        for value in (self.sample_rate, self.channels, self.sample_width_bytes):
            if type(value) is not int or value <= 0:
                raise ValueError('audio format values must be positive integers')
        if self.sample_width_bytes not in (2, 3, 4):
            raise ValueError('signed PCM requires a supported sample width')
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
        """Block until playback finishes; raise AudioPlayerError on failure.

        Release the output stream before returning, including on interruption.
        Detection suspension is the caller's responsibility during playback.
        """

    @abstractmethod
    def stop(self) -> None:
        """Stop playback and release active output resources."""

    def __enter__(self) -> AudioPlayer:
        return self

    def __exit__(self, *_: object) -> None:
        self.stop()
