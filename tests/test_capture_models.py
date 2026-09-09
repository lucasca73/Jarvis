"""Tests for spoken-request capture contracts."""

import unittest

from jarvis.audio import AudioChunk
from jarvis.capture import AudioRequest, CaptureState
from jarvis.wakeword import WakeWordDetection


class AudioRequestTests(unittest.TestCase):
    def setUp(self):
        self.activation = WakeWordDetection("jarvis", None, 10.0)

    def test_preserves_activation_and_counts_samples_including_pre_roll(self):
        chunks = (
            AudioChunk(bytes(3200), 16000, captured_at=9.9),
            AudioChunk(bytes(1600), 16000, captured_at=10.0),
        )
        request = AudioRequest(self.activation, chunks)
        self.assertIs(request.activation, self.activation)
        self.assertEqual(request.frame_count, 2400)
        self.assertAlmostEqual(request.duration_seconds, 0.15)
        self.assertEqual((request.sample_rate, request.channels, request.sample_width_bytes),
                         (16000, 1, 2))
        self.assertIs(request.chunks[0], chunks[0])

    def test_rejects_empty_capture(self):
        with self.assertRaises(ValueError):
            AudioRequest(self.activation, ())

    def test_rejects_mixed_pcm_formats(self):
        first = AudioChunk(bytes(4), 16000)
        for chunk in (AudioChunk(bytes(4), 8000),
                      AudioChunk(bytes(4), 16000, channels=2),
                      AudioChunk(bytes(4), 16000, sample_width_bytes=1)):
            with self.subTest(chunk=chunk), self.assertRaises(ValueError):
                AudioRequest(self.activation, (first, chunk))

    def test_rejects_reversed_capture_order(self):
        with self.assertRaises(ValueError):
            AudioRequest(self.activation, (
                AudioChunk(bytes(4), 16000, captured_at=11),
                AudioChunk(bytes(4), 16000, captured_at=10),
            ))

    def test_snapshots_mutable_sequence_and_omits_audio_from_repr(self):
        chunks = [AudioChunk(b'\x01\x02', 16000)]
        request = AudioRequest(self.activation, chunks)
        chunks.clear()
        self.assertEqual(len(request.chunks), 1)
        self.assertNotIn('chunks=', repr(request))
        self.assertNotIn('data=', repr(request))


class CaptureStateTests(unittest.TestCase):
    def test_states_have_stable_external_values(self):
        self.assertEqual(CaptureState('waiting'), CaptureState.WAITING)
        self.assertEqual(CaptureState('capturing'), CaptureState.CAPTURING)
