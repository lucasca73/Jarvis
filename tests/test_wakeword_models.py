"""Tests for wake-word module data contracts."""

from __future__ import annotations

import unittest

from jarvis.wakeword import WakeWordConfig, WakeWordDetection


class WakeWordConfigTests(unittest.TestCase):
    def test_normalizes_the_wake_word(self) -> None:
        config = WakeWordConfig(wake_word="  JARVIS  ")

        self.assertEqual(config.wake_word, "jarvis")

    def test_rejects_blank_wake_word(self) -> None:
        with self.assertRaises(ValueError):
            WakeWordConfig(wake_word="  ")

    def test_rejects_invalid_threshold(self) -> None:
        with self.assertRaises(ValueError):
            WakeWordConfig(threshold=1.1)

    def test_default_threshold_favors_recall(self) -> None:
        self.assertEqual(WakeWordConfig().threshold, 0.35)


class WakeWordDetectionTests(unittest.TestCase):
    def test_rejects_invalid_confidence(self) -> None:
        with self.assertRaises(ValueError):
            WakeWordDetection(wake_word="jarvis", confidence=-0.1, detected_at=1.0)

    def test_accepts_valid_detection(self) -> None:
        detection = WakeWordDetection(
            wake_word="jarvis", confidence=0.9, detected_at=1.0
        )

        self.assertEqual(detection.confidence, 0.9)
