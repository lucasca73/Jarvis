"""Tests for audio diagnostic helpers."""

from __future__ import annotations

import math
import unittest

from jarvis.audio import AudioChunk
from jarvis.audio.diagnostics import dbfs_level, parse_device, rms_level


class AudioDiagnosticsTests(unittest.TestCase):
    def test_calculates_rms_for_16_bit_pcm(self) -> None:
        chunk = AudioChunk(data=b"\xff\x7f\x01\x80", sample_rate=16_000)

        self.assertAlmostEqual(rms_level(chunk), 32_767, places=0)

    def test_calculates_silence_as_negative_infinity_dbfs(self) -> None:
        chunk = AudioChunk(data=b"\x00\x00" * 10, sample_rate=16_000)

        self.assertTrue(math.isinf(dbfs_level(chunk)))
        self.assertLess(dbfs_level(chunk), 0)

    def test_parses_numeric_device_identifier(self) -> None:
        self.assertEqual(parse_device("2"), 2)

    def test_preserves_device_name(self) -> None:
        self.assertEqual(parse_device("Test Microphone"), "Test Microphone")
