"""Application configuration validation without model or device access."""

from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
import unittest
from unittest.mock import patch, MagicMock

from jarvis.config import AppConfig, parse_config
from jarvis.app import main


class ConfigTests(unittest.TestCase):
    def test_defaults_preserve_existing_pipeline(self):
        self.assertEqual(parse_config([]), AppConfig())

    def test_overrides_reach_backends(self):
        config = parse_config([
            '--device', '2', '--output-device', 'Speakers',
            '--wakeword-model-dir', '/tmp/wake', '--keywords-file', '/tmp/keywords',
            '--vad-model', '/tmp/vad.onnx', '--stt-model-dir', '/tmp/stt',
            '--tts-model-dir', '/tmp/tts', '--threshold', '0.4',
            '--max-duration', '8', '--max-history-turns', '0', '--duration', '10'])
        self.assertEqual(config.audio.device, 2)
        self.assertEqual(config.stt_model_dir, Path('/tmp/stt'))
        self.assertEqual(config.capture.max_duration_seconds, 8)
        self.assertEqual(config.ollama.max_history_turns, 0)
        names = ['SherpaOnnxWakeWordDetector', 'SileroVoiceActivityDetector',
                 'CaptureController', 'SherpaWhisperTranscriber', 'OllamaLanguageModel',
                 'SherpaPiperSynthesizer', 'SoundDeviceAudioPlayer', 'SoundDeviceAudioInput']
        mocks = {name: MagicMock() for name in names}
        with patch('jarvis.app.parse_config', return_value=config), patch.multiple('jarvis.app', **mocks), patch('jarvis.app.run_assistant') as run:
            main()
        mocks['SherpaOnnxWakeWordDetector'].assert_called_once_with(
            config.wakeword_model_dir, config=config.wakeword, keywords_file=config.keywords_file)
        mocks['SileroVoiceActivityDetector'].assert_called_once_with(config.vad_model, config=config.vad)
        mocks['SherpaWhisperTranscriber'].assert_called_once_with(config.stt_model_dir)
        mocks['SherpaPiperSynthesizer'].assert_called_once_with(config.tts_model_dir)
        mocks['OllamaLanguageModel'].assert_called_once_with(config.ollama)
        mocks['SoundDeviceAudioPlayer'].assert_called_once_with('Speakers')
        self.assertEqual(run.call_args.args[-1], config.audio)
        self.assertEqual(run.call_args.kwargs['duration'], 10)

    def test_invalid_settings_fail_before_backend_startup(self):
        for args in (['--duration', 'nan'], ['--threshold', '2'],
                     ['--max-duration', '1'], ['--vad-min-speech-duration', '0'],
                     ['--endpoint', 'http://example.com'], ['--model', 'test-cloud'],
                     ['--max-history-turns', '-1'], ['--timeout-seconds', 'inf']):
            with self.subTest(args=args), redirect_stderr(StringIO()), patch('sys.argv', ['jarvis', *args]), patch('jarvis.app.SherpaOnnxWakeWordDetector') as backend:
                with self.assertRaises(SystemExit) as result:
                    main()
                self.assertEqual(result.exception.code, 2)
                backend.assert_not_called()
