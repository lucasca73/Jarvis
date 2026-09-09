"""Data models shared by audio inputs and consumers."""

from __future__ import annotations

from dataclasses import dataclass
from time import monotonic


@dataclass(frozen=True)
class AudioConfig:
    """Configuration for a mono PCM audio input stream."""

    sample_rate: int = 16_000
    channels: int = 1
    sample_width_bytes: int = 2
    device: int | str | None = None

    def __post_init__(self) -> None:
        if self.sample_rate <= 0:
            raise ValueError("sample_rate must be greater than zero")
        if self.channels <= 0:
            raise ValueError("channels must be greater than zero")
        if self.sample_width_bytes <= 0:
            raise ValueError("sample_width_bytes must be greater than zero")

    @property
    def bytes_per_frame(self) -> int:
        """Return the number of bytes in one audio frame."""
        return self.channels * self.sample_width_bytes


@dataclass(frozen=True)
class AudioDevice:
    """An input device available to an audio backend."""

    id: int | str
    name: str
    max_input_channels: int
    default_sample_rate: float | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("name must not be blank")
        if self.max_input_channels < 1:
            raise ValueError("max_input_channels must be at least one")


@dataclass(frozen=True)
class AudioChunk:
    """A timestamped PCM audio segment kept entirely in memory."""

    data: bytes
    sample_rate: int
    channels: int = 1
    sample_width_bytes: int = 2
    captured_at: float = 0.0

    def __post_init__(self) -> None:
        if not self.data:
            raise ValueError("data must not be empty")
        if self.sample_rate <= 0:
            raise ValueError("sample_rate must be greater than zero")
        if self.channels <= 0:
            raise ValueError("channels must be greater than zero")
        if self.sample_width_bytes <= 0:
            raise ValueError("sample_width_bytes must be greater than zero")
        if len(self.data) % self.bytes_per_frame:
            raise ValueError("data length must align with the PCM frame size")

    @classmethod
    def from_pcm(
        cls,
        data: bytes,
        config: AudioConfig,
        *,
        captured_at: float | None = None,
    ) -> AudioChunk:
        """Create a chunk using an input stream configuration."""
        return cls(
            data=data,
            sample_rate=config.sample_rate,
            channels=config.channels,
            sample_width_bytes=config.sample_width_bytes,
            captured_at=monotonic() if captured_at is None else captured_at,
        )

    @property
    def bytes_per_frame(self) -> int:
        """Return the number of bytes in one audio frame."""
        return self.channels * self.sample_width_bytes

    @property
    def frame_count(self) -> int:
        """Return the number of PCM frames in the chunk."""
        return len(self.data) // self.bytes_per_frame

    @property
    def duration_seconds(self) -> float:
        """Return the duration represented by this chunk."""
        return self.frame_count / self.sample_rate
