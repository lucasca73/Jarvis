"""Behavior tests for the optional local wake-word adapter."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock

from jarvis.audio import AudioChunk
from jarvis.wakeword import SherpaOnnxWakeWordDetector, WakeWordDetection

try:
    import numpy as np
except ImportError:
    np = None


class SherpaConfigurationTests(unittest.TestCase):
    def test_missing_model_reports_path(self):
        with TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, 'tokens.txt'):
                SherpaOnnxWakeWordDetector(Path(directory))

    def test_detection_can_have_unknown_confidence(self):
        event = WakeWordDetection.create('jarvis', None)
        self.assertIsNone(event.confidence)


@unittest.skipIf(np is None, 'Install the wakeword extra to test PCM conversion')
class SherpaProcessingTests(unittest.TestCase):
    def setUp(self):
        self.detector = SherpaOnnxWakeWordDetector.__new__(SherpaOnnxWakeWordDetector)
        self.detector._np = np
        self.engine = Mock()
        self.detector._engine = self.engine
        self.stream = Mock()
        self.detector._stream = self.stream

    def test_normalizes_pcm_and_preserves_stream_between_chunks(self):
        self.engine.is_ready.return_value = False
        pcm = np.array([-32768, 0, 32767], dtype=np.int16).tobytes()
        for _ in range(2):
            self.assertIsNone(self.detector.process(AudioChunk(pcm, 16000)))
        rate, samples = self.stream.accept_waveform.call_args.args
        self.assertEqual(rate, 16000)
        np.testing.assert_allclose(samples, [-1, 0, 32767 / 32768])
        self.engine.create_stream.assert_not_called()

    def test_detection_resets_decoder_and_drains_ready_frames(self):
        self.engine.is_ready.side_effect = [True, True, False]
        self.engine.get_result.side_effect = ['Jarvis', '']
        result = self.detector.process(AudioChunk(bytes(3200), 16000))
        self.assertEqual(result.wake_word, 'jarvis')
        self.assertIsNone(result.confidence)
        self.engine.reset_stream.assert_called_once_with(self.stream)
        self.assertEqual(self.engine.decode_stream.call_count, 2)

    def test_reset_replaces_buffered_stream(self):
        self.detector.reset()
        self.assertIs(self.detector._stream, self.engine.create_stream.return_value)
        self.assertIsNot(self.detector._stream, self.stream)

    def test_invalid_audio_is_rejected_before_consumption(self):
        for kwargs in ({'sample_rate': 8000}, {'sample_rate': 16000, 'channels': 2},
                       {'sample_rate': 16000, 'sample_width_bytes': 1}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.detector.process(AudioChunk(bytes(4), **kwargs))
        self.stream.accept_waveform.assert_not_called()

    def test_close_is_idempotent_and_prevents_processing(self):
        self.detector.close()
        self.detector.close()
        with self.assertRaises(RuntimeError):
            self.detector.process(AudioChunk(bytes(3200), 16000))
        with self.assertRaises(RuntimeError):
            self.detector.reset()
