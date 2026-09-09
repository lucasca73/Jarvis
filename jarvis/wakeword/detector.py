"""Abstract contract for local wake-word detector backends."""

from __future__ import annotations

from abc import ABC, abstractmethod

from jarvis.audio import AudioChunk
from jarvis.wakeword.models import WakeWordDetection


class WakeWordDetector(ABC):
    """Consume PCM audio chunks and report local wake-word detections."""

    @abstractmethod
    def process(self, chunk: AudioChunk) -> WakeWordDetection | None:
        """Process one PCM chunk and return a detection when the wake word is heard."""

    @abstractmethod
    def reset(self) -> None:
        """Discard detector state before processing a new audio stream."""
