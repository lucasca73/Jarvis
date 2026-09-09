"""Abstract contract for microphone and test audio sources."""

from __future__ import annotations

from abc import ABC, abstractmethod

from jarvis.audio.models import AudioChunk, AudioConfig, AudioDevice


class AudioInput(ABC):
    """A source that provides in-memory PCM audio chunks."""

    @abstractmethod
    def list_input_devices(self) -> list[AudioDevice]:
        """Return the input devices available to this source."""

    @property
    @abstractmethod
    def is_running(self) -> bool:
        """Whether the source is currently capturing audio."""

    @abstractmethod
    def start(self, config: AudioConfig) -> None:
        """Start capturing audio with the supplied configuration."""

    @abstractmethod
    def read_chunk(self, timeout: float | None = None) -> AudioChunk:
        """Return the next captured chunk or raise TimeoutError after timeout."""

    @abstractmethod
    def stop(self) -> None:
        """Stop capture and release the underlying audio resource."""

    def __enter__(self) -> AudioInput:
        return self

    def __exit__(self, *_: object) -> None:
        self.stop()
