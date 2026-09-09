"""Exercise diagnostic transitions with the real controller and fake audio."""

import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import Mock, patch

from jarvis.audio import AudioChunk
from jarvis.capture import CaptureConfig, CaptureController, CaptureState
from jarvis.capture import diagnostics
from jarvis.vad import VoiceActivity
from jarvis.wakeword.models import WakeWordDetection


class CaptureDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.wakeword = Mock()
        self.wakeword.process.return_value = WakeWordDetection.create('jarvis', None)
        self.vad = Mock()
        self.controller = CaptureController(self.wakeword, self.vad, CaptureConfig(
            no_speech_timeout_seconds=0.2, max_duration_seconds=0.4,
            silence_hold_seconds=0.1))
        self.source = Mock()
        self.source.read_chunk.return_value = AudioChunk(bytes(3200), 16000)

    def run_chunks(self, count, error=None):
        self.source.read_chunk.side_effect = [
            AudioChunk(bytes(3200), 16000, captured_at=i) for i in range(count)
        ] + [error or TimeoutError()]
        output = io.StringIO()
        with patch.object(diagnostics, 'monotonic', side_effect=[0] * (count + 2) + [1]), redirect_stdout(output):
            diagnostics.run_capture(self.source, self.controller, 1)
        return output.getvalue()

    def test_completion_and_reactivation(self):
        self.vad.process.side_effect = [(VoiceActivity(True, 0.1),),
                                        (VoiceActivity(False, 0.1),)]
        output = self.run_chunks(4)
        self.assertEqual(output.count('Activated.'), 2)
        self.assertIn('Request complete: 0.30s', output)
        self.assertIn('Unfinished request discarded.', output)
        self.assertEqual(self.controller.state, CaptureState.WAITING)

    def test_no_speech_cancellation(self):
        self.vad.process.return_value = ()
        output = self.run_chunks(3)
        self.assertIn('Cancelled: no speech detected.', output)
        self.assertNotIn('Request complete:', output)

    def test_interrupt_discards_capture(self):
        with self.assertRaises(KeyboardInterrupt):
            self.run_chunks(1, KeyboardInterrupt())
        self.assertEqual(self.controller.state, CaptureState.WAITING)
        self.vad.reset.assert_called()

    def test_source_error_discards_capture(self):
        with self.assertRaisesRegex(RuntimeError, 'device lost'):
            self.run_chunks(1, RuntimeError('device lost'))
        self.assertEqual(self.controller.state, CaptureState.WAITING)

    def test_completed_request_can_be_transcribed(self):
        self.vad.process.side_effect = [(VoiceActivity(True, 0.1),),
                                        (VoiceActivity(False, 0.1),)]
        transcriber = Mock()
        transcriber.transcribe.return_value = type('Result', (), {
            'duration_seconds': 0.0, 'is_empty': False, 'text': 'turn on the light'
        })()
        output = self.run_chunks(3)
        self.assertIn('Request complete:', output)

    def test_invalid_duration_does_not_open_models_or_microphone(self):
        for value in ('0', '-1', 'nan', 'inf'):
            with patch('sys.argv', ['diagnostics', '--duration', value]), \
                    patch.object(diagnostics, 'SherpaOnnxWakeWordDetector') as detector, \
                    redirect_stdout(io.StringIO()), \
                    patch('sys.stderr', new_callable=io.StringIO):
                with self.assertRaises(SystemExit):
                    diagnostics.main()
                detector.assert_not_called()
