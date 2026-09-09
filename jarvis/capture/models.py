"""Contracts for capturing an in-memory spoken request after activation."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from jarvis.audio import AudioChunk
from jarvis.wakeword.models import WakeWordDetection


class CaptureState(str, Enum):
    """Capture lifecycle managed by the controller.

    WAITING listens for activation. CAPTURING collects the spoken request.
    Completion or cancellation returns the controller to WAITING.
    """

    WAITING = "waiting"
    CAPTURING = "capturing"


@dataclass(frozen=True)
class AudioRequest:
    """Ordered PCM chunks associated with one wake-word activation.

    Chunks share one format and remain in memory. Their timestamps use the
    audio source's monotonic clock; pre-roll may precede the activation.
    Duration measures stored samples, not elapsed wall time or detected speech.
    An empty/cancelled capture produces no AudioRequest. This contract does
    not establish whether speech is present; the controller uses VAD for that.
    """

    activation: WakeWordDetection
    chunks: tuple[AudioChunk, ...] = field(repr=False)

    def __post_init__(self) -> None:
        # Snapshot the sequence so a caller's list cannot change the request.
        object.__setattr__(self, "chunks", tuple(self.chunks))
        if not self.chunks:
            raise ValueError("An audio request must contain at least one chunk")
        first = self.chunks[0]
        audio_format = (first.sample_rate, first.channels, first.sample_width_bytes)
        previous_time = first.captured_at
        for chunk in self.chunks:
            if (chunk.sample_rate, chunk.channels, chunk.sample_width_bytes) != audio_format:
                raise ValueError("All request chunks must use the same PCM format")
            if chunk.captured_at < previous_time:
                raise ValueError("Request chunks must be in capture order")
            previous_time = chunk.captured_at

    @property
    def sample_rate(self) -> int:
        return self.chunks[0].sample_rate

    @property
    def channels(self) -> int:
        return self.chunks[0].channels

    @property
    def sample_width_bytes(self) -> int:
        return self.chunks[0].sample_width_bytes

    @property
    def frame_count(self) -> int:
        return sum(chunk.frame_count for chunk in self.chunks)

    @property
    def duration_seconds(self) -> float:
        return self.frame_count / self.sample_rate
