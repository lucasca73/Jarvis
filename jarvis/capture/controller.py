"""Streaming request capture without audio persistence or device ownership."""

from __future__ import annotations

from dataclasses import dataclass, replace
import math

from jarvis.audio import AudioChunk
from jarvis.capture.buffer import PreRollBuffer
from jarvis.capture.models import AudioRequest, CaptureState
from jarvis.vad import VoiceActivityDetector
from jarvis.wakeword.detector import WakeWordDetector


@dataclass(frozen=True)
class CaptureConfig:
    pre_roll_seconds: float = 0.5
    no_speech_timeout_seconds: float = 3.0
    max_duration_seconds: float = 15.0
    silence_hold_seconds: float = 0.5

    def __post_init__(self) -> None:
        for value in (self.pre_roll_seconds, self.no_speech_timeout_seconds,
                      self.max_duration_seconds, self.silence_hold_seconds):
            if not math.isfinite(value) or value <= 0:
                raise ValueError("Capture durations must be finite and positive")
        if self.no_speech_timeout_seconds > self.max_duration_seconds:
            raise ValueError("No-speech timeout must not exceed maximum duration")


class CaptureController:
    """Consume ordered 16 kHz mono PCM on a single consumer thread.

    Activation audio is retained but excluded from VAD, so the wake word alone
    does not qualify as a request. Limits count samples after activation and
    exclude pre-roll. Silence hold is additional to the backend's debounce;
    brief false decisions (including native segment splits) can recover.
    Completion occurs at an input chunk boundary; the maximum is frame-exact.
    Call reset when restarting an interrupted audio stream. Detectors are
    supplied and owned by the caller.
    """

    def __init__(self, wakeword: WakeWordDetector, vad: VoiceActivityDetector,
                 config: CaptureConfig | None = None) -> None:
        self.config = config or CaptureConfig()
        self._wakeword = wakeword
        self._vad = vad
        self._pre_roll = PreRollBuffer(self.config.pre_roll_seconds)
        self.reset()

    @property
    def state(self) -> CaptureState:
        return self._state

    def reset(self) -> None:
        """Cancel any request and discard all buffered audio and detector state."""
        self._wakeword.reset()
        self._vad.reset()
        self._pre_roll.clear()
        self._state = CaptureState.WAITING
        self._activation = None
        self._chunks: list[AudioChunk] = []
        self._frames = 0
        self._speech_seen = False
        self._silence = 0.0
        self._last_captured_at = None

    def process(self, chunk: AudioChunk) -> AudioRequest | None:
        """Return a completed request, or None while waiting/capturing/cancelling."""
        if (chunk.sample_rate, chunk.channels, chunk.sample_width_bytes) != (16000, 1, 2):
            raise ValueError("Capture requires 16 kHz mono 16-bit PCM")
        if not math.isfinite(chunk.captured_at):
            raise ValueError("captured_at must be finite")
        if self._last_captured_at is not None and chunk.captured_at < self._last_captured_at:
            raise ValueError("Capture chunks must be in capture order")
        self._last_captured_at = chunk.captured_at
        if self.state == CaptureState.WAITING:
            self._pre_roll.append(chunk)
            activation = self._wakeword.process(chunk)
            if activation is not None:
                self._vad.reset()
                self._activation = activation
                self._chunks = list(self._pre_roll.snapshot())
                self._pre_roll.clear()
                self._state = CaptureState.CAPTURING
            return None

        limit = max(1, int(self.config.max_duration_seconds * chunk.sample_rate))
        remaining = limit - self._frames
        if chunk.frame_count > remaining:
            chunk = replace(chunk, data=chunk.data[:remaining * chunk.bytes_per_frame])
        self._chunks.append(chunk)
        self._frames += chunk.frame_count
        ended = False
        for activity in self._vad.process(chunk):
            if activity.is_speech:
                self._speech_seen = True
                self._silence = 0.0
            elif self._speech_seen:
                self._silence += activity.duration_seconds
                if self._silence + 1e-9 >= self.config.silence_hold_seconds:
                    ended = True
                    break
        elapsed = self._frames / chunk.sample_rate
        if (ended or elapsed >= self.config.max_duration_seconds or
                (not self._speech_seen and elapsed >= self.config.no_speech_timeout_seconds)):
            request = AudioRequest(self._activation, tuple(self._chunks)) if self._speech_seen else None
            self.reset()
            return request
        return None
