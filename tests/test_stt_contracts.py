"""Validate text handling and backend lifecycle without an STT model."""

import unittest

from jarvis.stt import Transcriber, TranscriptionError, TranscriptionResult


class StubTranscriber(Transcriber):
    def __init__(self):
        self.closed = False

    def transcribe(self, request):
        return TranscriptionResult('hello')

    def close(self):
        self.closed = True


class SttContractTests(unittest.TestCase):
    def test_text_preserves_words_and_unicode_but_trims_edges(self):
        result = TranscriptionResult('  Olá, mundo!\n', ' pt ')
        self.assertEqual(result.text, 'Olá, mundo!')
        self.assertEqual(result.language, 'pt')
        self.assertFalse(result.is_empty)
        self.assertNotIn('Olá', repr(result))

    def test_empty_recognition_is_a_result(self):
        for text in ('', ' \n\t'):
            result = TranscriptionResult(text)
            self.assertTrue(result.is_empty)
            self.assertEqual(result.text, '')
            self.assertIsNone(result.language)

    def test_rejects_invalid_result_fields(self):
        for text in (None, 1, b'hello'):
            with self.assertRaises(TypeError):
                TranscriptionResult(text)
        with self.assertRaises(TypeError):
            TranscriptionResult('hello', 1)
        with self.assertRaises(ValueError):
            TranscriptionResult('hello', ' ')

    def test_context_releases_backend_after_success_and_failure(self):
        backend = StubTranscriber()
        with backend as entered:
            self.assertIs(entered, backend)
        self.assertTrue(backend.closed)
        backend = StubTranscriber()
        with self.assertRaises(TranscriptionError):
            with backend:
                raise TranscriptionError('Local inference failed')
        self.assertTrue(backend.closed)

    def test_interface_requires_backend_implementation(self):
        with self.assertRaises(TypeError):
            Transcriber()
