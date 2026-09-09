import unittest
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np

from jarvis.audio import AudioChunk
from jarvis.capture import AudioRequest
from jarvis.stt import SherpaWhisperTranscriber, TranscriptionError
from jarvis.wakeword.models import WakeWordDetection


def request(data=b'\x01\x00' * 1600):
    return AudioRequest(WakeWordDetection.create('jarvis', None),
                        (AudioChunk(data, 16000, captured_at=0),))


class WhisperTests(unittest.TestCase):
    def setUp(self):
        self.stream = Mock()
        self.stream.result = SimpleNamespace(text=' hello world ')
        self.recognizer = Mock()
        self.recognizer.create_stream.return_value = self.stream
        self.transcriber = SherpaWhisperTranscriber(recognizer=self.recognizer, numpy=np)

    def test_transcribes_all_chunks_and_returns_english(self):
        result = self.transcriber.transcribe(request())
        self.assertEqual(result.text, 'hello world')
        self.assertEqual(result.language, 'en')
        self.recognizer.decode_stream.assert_called_once_with(self.stream)
        self.stream.accept_waveform.assert_called_once()

    def test_empty_recognition_is_returned_for_silence(self):
        self.stream.result = SimpleNamespace(text='')
        result = self.transcriber.transcribe(request(bytes(3200)))
        self.assertTrue(result.is_empty)
        self.recognizer.create_stream.assert_not_called()

    def test_invalid_backend_result_is_a_transcription_error(self):
        self.stream.result = SimpleNamespace(text=None)
        with self.assertRaisesRegex(TranscriptionError, 'invalid result'):
            self.transcriber.transcribe(request())

    def test_backend_failure_is_content_free(self):
        self.recognizer.decode_stream.side_effect = RuntimeError('secret transcript')
        with self.assertRaisesRegex(TranscriptionError, 'Local STT inference failed') as error:
            self.transcriber.transcribe(request())
        self.assertNotIn('secret transcript', str(error.exception))

    def test_close_is_idempotent_and_blocks_use(self):
        self.transcriber.close()
        self.transcriber.close()
        with self.assertRaises(RuntimeError):
            self.transcriber.transcribe(request())

    def test_missing_model_file_is_rejected(self):
        with self.assertRaises(ValueError):
            SherpaWhisperTranscriber('/tmp/no-such-jarvis-stt-model')
