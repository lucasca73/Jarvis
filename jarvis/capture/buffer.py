"""Bounded in-memory PCM pre-roll for the transition into request capture."""

from __future__ import annotations

from collections import deque
import math

from jarvis.audio import AudioChunk


class PreRollBuffer:
    """Retain the newest PCM frames up to a sample-based duration limit.

    This buffer neither opens a microphone nor detects speech. The capture
    controller appends incoming chunks while waiting and takes a snapshot
    on activation. It is intended for use by a single consumer thread.
    """

    def __init__(self, max_duration_seconds: float = 0.5) -> None:
        if not math.isfinite(max_duration_seconds) or max_duration_seconds <= 0:
            raise ValueError("max_duration_seconds must be finite and positive")
        self._max_duration_seconds = max_duration_seconds
        self._chunks: deque[AudioChunk] = deque()
        self._frame_count = 0
        self._format: tuple[int, int, int] | None = None
        self._last_captured_at: float | None = None

    @property
    def frame_count(self) -> int:
        return self._frame_count

    @property
    def duration_seconds(self) -> float:
        return self._frame_count / self._format[0] if self._format else 0.0

    def append(self, chunk: AudioChunk) -> None:
        """Append audio, evicting oldest frames without splitting PCM frames.

        Partial eviction preserves captured_at, which records when the original
        chunk was captured, not an inferred timestamp of its first sample.
        Invalid input leaves the existing buffer unchanged.
        """
        audio_format = (chunk.sample_rate, chunk.channels, chunk.sample_width_bytes)
        if self._format is not None and audio_format != self._format:
            raise ValueError("Buffer chunks must use the same PCM format; clear before changing it")
        if not math.isfinite(chunk.captured_at):
            raise ValueError("captured_at must be finite")
        if self._last_captured_at is not None and chunk.captured_at < self._last_captured_at:
            raise ValueError("Buffer chunks must be in capture order")
        limit = int(self._max_duration_seconds * chunk.sample_rate)
        if limit < 1:
            raise ValueError("Buffer duration must hold at least one audio frame")
        self._format = audio_format
        self._last_captured_at = chunk.captured_at
        self._chunks.append(chunk)
        self._frame_count += chunk.frame_count
        excess = self._frame_count - limit
        while excess > 0:
            oldest = self._chunks.popleft()
            removed = min(excess, oldest.frame_count)
            if removed < oldest.frame_count:
                self._chunks.appendleft(AudioChunk(
                    data=oldest.data[removed * oldest.bytes_per_frame:],
                    sample_rate=oldest.sample_rate,
                    channels=oldest.channels,
                    sample_width_bytes=oldest.sample_width_bytes,
                    captured_at=oldest.captured_at,
                ))
            self._frame_count -= removed
            excess -= removed

    def snapshot(self) -> tuple[AudioChunk, ...]:
        """Return retained chunks without consuming or copying their PCM bytes."""
        return tuple(self._chunks)

    def clear(self) -> None:
        """Release retained chunks and reset format and timestamp tracking."""
        self._chunks.clear()
        self._frame_count = 0
        self._format = None
        self._last_captured_at = None
