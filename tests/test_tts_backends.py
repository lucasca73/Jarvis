"""Exercise synthesis conversion and output cleanup without hardware."""

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

import numpy as np

from jarvis.llm import TextResponse
from jarvis.tts import AudioPlayerError, SynthesizedAudio, SynthesisError
from jarvis.tts.piper import SherpaPiperSynthesizer
from jarvis.tts.player import SoundDeviceAudioPlayer


class PiperTests(unittest.TestCase):
    def engine(self, samples, rate=22050):
        synth = SherpaPiperSynthesizer.__new__(SherpaPiperSynthesizer)
        synth._np = np
        synth._engine = MagicMock()
        synth._engine.generate.return_value = SimpleNamespace(samples=samples, sample_rate=rate)
        return synth

    def test_conversion_preserves_rate_and_clips_without_wrapping(self):
        synth = self.engine([-2, -1, -0.5, 0, 0.5, 1, 2])
        audio = synth.synthesize(TextResponse('Hello'))
        self.assertEqual(audio.sample_rate, 22050)
        self.assertEqual(np.frombuffer(audio.data, dtype='<i2').tolist(),
                         [-32768, -32768, -16384, 0, 16384, 32767, 32767])
        synth._engine.generate.assert_called_once_with('Hello', sid=0, speed=1.0)

    def test_bad_output_and_backend_failure_do_not_expose_text(self):
        for samples in ([], [[0]], [float('nan')], [float('inf')]):
            with self.assertRaises(SynthesisError):
                self.engine(samples).synthesize(TextResponse('private text'))
        synth = self.engine([0])
        synth._engine.generate.side_effect = RuntimeError('private text')
        with self.assertRaises(SynthesisError) as raised:
            synth.synthesize(TextResponse('private text'))
        self.assertNotIn('private', str(raised.exception))
        synth._engine.generate.side_effect = None
        self.assertEqual(synth.synthesize(TextResponse('Retry')).frame_count, 1)

    def test_close_and_missing_files(self):
        synth = self.engine([0])
        synth.close()
        synth.close()
        with self.assertRaises(SynthesisError):
            synth.synthesize(TextResponse('Hello'))
        with TemporaryDirectory() as root:
            with self.assertRaises(ValueError):
                SherpaPiperSynthesizer(root)

    def test_constructor_uses_local_files_and_cpu(self):
        with TemporaryDirectory() as root, patch.dict('sys.modules', {'sherpa_onnx': MagicMock()}) as modules:
            root = Path(root)
            for name in ('en_US-lessac-medium.onnx', 'tokens.txt', 'espeak-ng-data/phontab',
                         'espeak-ng-data/phondata', 'espeak-ng-data/phonindex', 'espeak-ng-data/en_dict'):
                path = root / name
                path.parent.mkdir(exist_ok=True)
                path.write_bytes(b'model fixture')
            with SherpaPiperSynthesizer(root):
                kwargs = modules['sherpa_onnx'].OfflineTtsModelConfig.call_args.kwargs
                self.assertEqual(kwargs['provider'], 'cpu')
                self.assertFalse(kwargs['debug'])


class PlayerTests(unittest.TestCase):
    def setUp(self):
        self.backend = MagicMock()
        self.stream = self.backend.RawOutputStream.return_value
        self.stream.write.return_value = False
        self.player = SoundDeviceAudioPlayer(device=4, backend=self.backend)
        self.audio = SynthesizedAudio(b'\x01\x00' * 3000, 22050)

    def test_blocks_drains_and_closes_with_exact_pcm(self):
        def write(data):
            self.assertTrue(self.player.is_playing)
            return False
        self.stream.write.side_effect = write
        self.player.play(self.audio)
        self.assertEqual(b''.join(call.args[0] for call in self.stream.write.call_args_list), self.audio.data)
        self.stream.stop.assert_called_once()
        self.stream.close.assert_called_once()
        self.assertFalse(self.player.is_playing)
        self.backend.RawOutputStream.assert_called_once_with(
            samplerate=22050, channels=1, dtype='int16', device=4)
        self.player.stop()
        self.stream.close.assert_called_once()

    def test_start_write_and_drain_failures_release_output_and_allow_retry(self):
        for operation in ('start', 'write', 'stop'):
            with self.subTest(operation=operation):
                getattr(self.stream, operation).side_effect = RuntimeError('private audio')
                with self.assertRaises(AudioPlayerError) as raised:
                    self.player.play(self.audio)
                self.assertNotIn('private', str(raised.exception))
                self.assertFalse(self.player.is_playing)
                self.assertIsNone(self.player._stream)
                getattr(self.stream, operation).side_effect = None
                self.player.play(self.audio)

    def test_interrupt_and_close_failure_preserve_interrupt(self):
        self.stream.write.side_effect = KeyboardInterrupt()
        self.stream.close.side_effect = RuntimeError('private audio')
        with self.assertRaises(KeyboardInterrupt):
            self.player.play(self.audio)
        self.stream.close.assert_called_once()
        self.assertFalse(self.player.is_playing)

    def test_underflow_and_unsupported_format(self):
        self.stream.write.return_value = True
        with self.assertRaises(AudioPlayerError):
            self.player.play(self.audio)
        self.stream.close.assert_called_once()
        with self.assertRaises(ValueError):
            self.player.play(SynthesizedAudio(b'\x00' * 4, sample_width_bytes=4))
