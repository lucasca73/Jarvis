"""Capture lifecycle tests without a microphone or inference models."""

import unittest
from unittest.mock import Mock

from jarvis.audio import AudioChunk
from jarvis.capture import CaptureConfig, CaptureController, CaptureState
from jarvis.vad import VoiceActivity
from jarvis.wakeword.models import WakeWordDetection


class CaptureControllerTests(unittest.TestCase):
    def setUp(self):
        self.wakeword = Mock()
        self.wakeword.process.return_value = None
        self.vad = Mock()
        self.vad.process.return_value = ()
        self.controller = CaptureController(self.wakeword, self.vad, CaptureConfig(
            no_speech_timeout_seconds=0.3, max_duration_seconds=0.6,
            silence_hold_seconds=0.2))
        self.timestamp = 0

    def feed(self, speech=None, frames=1600):
        self.timestamp += 1
        self.vad.process.return_value = (() if speech is None else
                                        (VoiceActivity(speech, frames / 16000),))
        return self.controller.process(AudioChunk(b'\x01\x00' * frames, 16000,
                                                 captured_at=self.timestamp))

    def activate(self):
        self.wakeword.process.return_value = WakeWordDetection.create('jarvis', None)
        self.feed()
        self.assertEqual(self.controller.state, CaptureState.CAPTURING)

    def test_activation_retains_bounded_pre_roll_without_feeding_vad(self):
        for _ in range(8):
            self.feed()
        self.activate()
        self.vad.process.assert_not_called()
        self.feed(True)
        self.feed(False)
        request = self.feed(False)
        self.assertAlmostEqual(request.duration_seconds, 0.8)
        self.assertEqual(self.controller.state, CaptureState.WAITING)
        self.assertEqual(self.wakeword.process.call_count, 9)

    def test_no_speech_cancels_even_without_complete_vad_windows(self):
        self.activate()
        for _ in range(3):
            self.assertIsNone(self.feed())
        self.assertEqual(self.controller.state, CaptureState.WAITING)

    def test_short_pause_recovers_before_later_completion(self):
        self.activate()
        self.feed(True)
        self.assertIsNone(self.feed(False))
        self.assertIsNone(self.feed(True))
        self.assertIsNone(self.feed(False))
        self.assertIsNotNone(self.feed(False))

    def test_maximum_trims_chunk_on_frame_boundary(self):
        self.activate()
        self.feed(True, frames=4000)
        request = self.feed(True, frames=8000)
        self.assertEqual(request.frame_count, 1600 + 9600)
        self.assertEqual(request.chunks[-1].frame_count, 5600)
        self.assertEqual(self.controller.state, CaptureState.WAITING)

    def test_reset_and_repeated_requests_do_not_reuse_audio(self):
        self.activate()
        self.feed(True)
        self.controller.reset()
        self.assertEqual(self.controller.state, CaptureState.WAITING)
        for _ in range(2):
            self.activate()
            self.feed(True)
            self.feed(False)
            request = self.feed(False)
            self.assertEqual(request.frame_count, 6400)

    def test_invalid_audio_leaves_capture_usable(self):
        self.activate()
        for chunk in (AudioChunk(b'\0\0', 8000),
                      AudioChunk(b'\0\0', 16000, captured_at=float('nan')),
                      AudioChunk(b'\0\0', 16000, captured_at=0)):
            with self.assertRaises(ValueError):
                self.controller.process(chunk)
        self.feed(True)
        self.feed(False)
        self.assertIsNotNone(self.feed(False))

    def test_invalid_configuration(self):
        for field in ('pre_roll_seconds', 'no_speech_timeout_seconds',
                      'max_duration_seconds', 'silence_hold_seconds'):
            for value in (0, -1, float('inf'), float('nan')):
                with self.assertRaises(ValueError):
                    CaptureConfig(**{field: value})
        with self.assertRaises(ValueError):
            CaptureConfig(no_speech_timeout_seconds=16)
