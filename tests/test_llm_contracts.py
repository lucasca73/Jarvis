"""Check the STT-to-LLM boundary and content-safe value representations."""

import unittest

from jarvis.llm import LanguageModel, LanguageModelError, TextRequest, TextResponse
from jarvis.stt import TranscriptionResult


class StubLanguageModel(LanguageModel):
    def __init__(self):
        self.closed = False

    def respond(self, request):
        return TextResponse('An answer.')

    def reset(self):
        pass

    def close(self):
        self.closed = True


class LlmContractTests(unittest.TestCase):
    def test_transcription_becomes_request_without_losing_content(self):
        transcript = TranscriptionResult('  Explain café culture.\n', 'en')
        request = TextRequest(transcript.text)
        self.assertEqual(request.text, 'Explain café culture.')
        self.assertNotIn('café', repr(request))
        response = TextResponse('  A private answer.\n')
        self.assertEqual(response.text, 'A private answer.')
        self.assertNotIn('private', repr(response))

    def test_empty_transcription_cannot_be_sent_to_model(self):
        with self.assertRaises(ValueError):
            TextRequest(TranscriptionResult(' ').text)

    def test_invalid_values_are_rejected_without_echoing_content(self):
        for contract in (TextRequest, TextResponse):
            for value in ('', ' \n\t'):
                with self.assertRaises(ValueError):
                    contract(value)
            for value in (None, 1, b'private content'):
                with self.assertRaises(TypeError) as raised:
                    contract(value)
                self.assertNotIn('private content', str(raised.exception))

    def test_cleanup_on_success_and_failure(self):
        backend = StubLanguageModel()
        with backend as entered:
            self.assertIs(entered, backend)
        self.assertTrue(backend.closed)
        backend = StubLanguageModel()
        with self.assertRaises(LanguageModelError):
            with backend:
                raise LanguageModelError('Local inference failed')
        self.assertTrue(backend.closed)

    def test_interface_requires_implementation(self):
        with self.assertRaises(TypeError):
            LanguageModel()
