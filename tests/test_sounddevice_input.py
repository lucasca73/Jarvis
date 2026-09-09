"""Tests for continuous sounddevice audio capture."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from typing import Any, Callable

from jarvis.audio import AudioConfig, SoundDeviceAudioInput


class FakeRawInputStream:
    """Minimal raw stream that lets tests trigger the audio callback."""

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs
        self.callback: Callable[..., None] = kwargs["callback"]
        self.started = False
        self.stopped = False
        self.closed = False

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.stopped = True

    def close(self) -> None:
        self.closed = True

    def emit(self, pcm_data: bytes) -> None:
        self.callback(pcm_data, 0, None, None)


class FakeSoundDeviceBackend:
    """In-memory replacement for the subset of sounddevice under test."""

    def __init__(self) -> None:
        self.default = SimpleNamespace(device=[0, -1])
        self.stream: FakeRawInputStream | None = None

    def query_devices(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "Test Microphone",
                "max_input_channels": 1,
                "default_samplerate": 16_000,
            }
        ]

    def RawInputStream(self, **kwargs: Any) -> FakeRawInputStream:
        self.stream = FakeRawInputStream(**kwargs)
        return self.stream


class SoundDeviceAudioInputTests(unittest.TestCase):
    def setUp(self) -> None:
        self.backend = FakeSoundDeviceBackend()
        self.audio_input = SoundDeviceAudioInput(backend=self.backend)

    def test_starts_and_delivers_pcm_chunk(self) -> None:
        self.audio_input.start(AudioConfig())

        assert self.backend.stream is not None
        self.backend.stream.emit(b"\x00\x00" * 1_600)
        chunk = self.audio_input.read_chunk(timeout=0)

        self.assertTrue(self.audio_input.is_running)
        self.assertTrue(self.backend.stream.started)
        self.assertEqual(self.backend.stream.kwargs["dtype"], "int16")
        self.assertEqual(self.backend.stream.kwargs["blocksize"], 1_600)
        self.assertEqual(chunk.frame_count, 1_600)
        self.assertEqual(chunk.duration_seconds, 0.1)

    def test_stop_releases_stream_and_discards_audio(self) -> None:
        self.audio_input.start(AudioConfig())

        assert self.backend.stream is not None
        stream = self.backend.stream
        stream.emit(b"\x00\x00")
        self.audio_input.stop()

        self.assertFalse(self.audio_input.is_running)
        self.assertTrue(stream.stopped)
        self.assertTrue(stream.closed)
        with self.assertRaises(RuntimeError):
            self.audio_input.read_chunk(timeout=0)

    def test_rejects_non_16_bit_pcm(self) -> None:
        with self.assertRaises(ValueError):
            self.audio_input.start(AudioConfig(sample_width_bytes=4))

    def test_rejects_a_second_start(self) -> None:
        self.audio_input.start(AudioConfig())

        with self.assertRaises(RuntimeError):
            self.audio_input.start(AudioConfig())

    def test_raises_timeout_without_audio(self) -> None:
        self.audio_input.start(AudioConfig())

        with self.assertRaises(TimeoutError):
            self.audio_input.read_chunk(timeout=0)
