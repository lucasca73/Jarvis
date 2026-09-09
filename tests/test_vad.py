"""VAD configuration and streaming adapter behavior tests."""

from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock

from jarvis.audio import AudioChunk
from jarvis.vad import SileroVoiceActivityDetector, VadConfig

try:
    import numpy as np
except ImportError:
    np = None


class VadConfigTests(unittest.TestCase):
    def test_invalid_config(self):
        for kwargs in ({'threshold': float('nan')}, {'threshold': 1}, {'threshold': 0},
                       {'min_speech_duration': 0}, {'min_silence_duration': -1},
                       {'min_silence_duration': float('inf')}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                VadConfig(**kwargs)

    def test_missing_model(self):
        with TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, 'missing or empty'):
                SileroVoiceActivityDetector(directory + '/missing.onnx')


@unittest.skipIf(np is None, 'Install the vad extra to test the adapter')
class SileroTests(unittest.TestCase):
    def setUp(self):
        self.vad = SileroVoiceActivityDetector.__new__(SileroVoiceActivityDetector)
        self.vad._np = np
        self.engine = Mock()
        self.engine.empty.return_value = True
        self.engine.is_speech_detected.return_value = False
        self.vad._engine = self.engine
        self.vad._pending = b''

    def test_partial_window_is_preserved_and_pcm_normalized(self):
        pcm = np.array([-32768, 32767] * 256, dtype=np.int16).tobytes()
        self.assertEqual(self.vad.process(AudioChunk(pcm[:400], 16000)), ())
        self.engine.accept_waveform.assert_not_called()
        result = self.vad.process(AudioChunk(pcm[400:], 16000))
        self.assertEqual(len(result), 1)
        self.assertAlmostEqual(result[0].duration_seconds, 0.032)
        samples = self.engine.accept_waveform.call_args.args[0]
        np.testing.assert_allclose(samples[:2], [-1, 32767 / 32768])

    def test_100ms_chunks_preserve_all_samples(self):
        results = []
        for _ in range(8):
            results.extend(self.vad.process(AudioChunk(bytes(3200), 16000)))
        self.assertEqual(len(results), 25)
        self.assertEqual(self.vad._pending, b'')
        self.assertAlmostEqual(sum(r.duration_seconds for r in results), 0.8)

    def test_returns_all_state_changes_and_discards_completed_segments(self):
        self.engine.is_speech_detected.side_effect = [False, True, False]
        self.engine.empty.side_effect = [True, True, False, False, True]
        results = self.vad.process(AudioChunk(bytes(3072), 16000))
        self.assertEqual([r.is_speech for r in results], [False, True, False])
        self.assertEqual(self.engine.pop.call_count, 2)

    def test_reset_discards_pending_window_and_backend_state(self):
        self.vad.process(AudioChunk(bytes(1000), 16000))
        self.vad.reset()
        self.engine.reset.assert_called_once()
        self.assertEqual(self.vad.process(AudioChunk(bytes(24), 16000)), ())
        self.engine.accept_waveform.assert_not_called()

    def test_invalid_pcm_does_not_change_pending_data(self):
        self.vad.process(AudioChunk(bytes(100), 16000))
        for kwargs in ({'sample_rate': 8000}, {'sample_rate': 16000, 'channels': 2},
                       {'sample_rate': 16000, 'sample_width_bytes': 1}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.vad.process(AudioChunk(bytes(4), **kwargs))
        self.assertEqual(self.vad._pending, bytes(100))

    def test_closed_detector_rejects_calls(self):
        self.vad.close()
        self.vad.close()
        with self.assertRaises(RuntimeError):
            self.vad.process(AudioChunk(bytes(1024), 16000))
        with self.assertRaises(RuntimeError):
            self.vad.reset()
