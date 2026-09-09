"""Tests for audio module data contracts."""

import unittest

from jarvis.audio import AudioChunk, AudioConfig, AudioDevice


class AudioConfigTests(unittest.TestCase):
    def test_default_config_is_mono_16khz_pcm(self) -> None:
        config = AudioConfig()

        self.assertEqual(config.sample_rate, 16_000)
        self.assertEqual(config.channels, 1)
        self.assertEqual(config.sample_width_bytes, 2)
        self.assertEqual(config.bytes_per_frame, 2)

    def test_rejects_invalid_sample_rate(self) -> None:
        with self.assertRaises(ValueError):
            AudioConfig(sample_rate=0)


class AudioChunkTests(unittest.TestCase):
    def test_calculates_chunk_duration(self) -> None:
        config = AudioConfig(sample_rate=16_000)
        chunk = AudioChunk.from_pcm(b"\x00\x00" * 1_600, config, captured_at=10.0)

        self.assertEqual(chunk.frame_count, 1_600)
        self.assertEqual(chunk.duration_seconds, 0.1)
        self.assertEqual(chunk.captured_at, 10.0)

    def test_rejects_unaligned_pcm_data(self) -> None:
        with self.assertRaises(ValueError):
            AudioChunk(data=b"\x00", sample_rate=16_000)


class AudioDeviceTests(unittest.TestCase):
    def test_rejects_device_without_input_channels(self) -> None:
        with self.assertRaises(ValueError):
            AudioDevice(id=1, name="Microphone", max_input_channels=0)
