"""Exercise Ollama transport boundaries without a running model."""

import json
import unittest
from unittest.mock import patch

from jarvis.llm import LanguageModelError, TextRequest
from jarvis.llm.ollama import OllamaConfig, OllamaLanguageModel


def response_body(text='A short answer.'):
    return json.dumps({'done': True, 'message': {'role': 'assistant', 'content': text}}).encode()


class OllamaTests(unittest.TestCase):
    def test_rejects_remote_endpoints_and_cloud_models(self):
        for endpoint in ('https://example.com', 'http://localhost:11434',
                         'http://127.0.0.1.evil.test', 'http://user@127.0.0.1',
                         'http://127.0.0.1/path', 'http://127.0.0.1?x=1',
                         'http://127.0.0.1:0', 'http://127.0.0.1:99999'):
            with self.subTest(endpoint=endpoint), self.assertRaises(ValueError):
                OllamaConfig(endpoint=endpoint)
        for model in ('', 'model:cloud', 'model-cloud', 'https://host/model'):
            with self.assertRaises(ValueError):
                OllamaConfig(model=model)
        self.assertEqual(OllamaConfig(endpoint='http://[::1]:11434').context_tokens, 2048)

    def test_invalid_limits(self):
        for kwargs in ({'timeout_seconds': float('nan')}, {'timeout_seconds': 0},
                       {'context_tokens': True}, {'max_response_tokens': 0},
                       {'keep_alive_seconds': -1}):
            with self.assertRaises(ValueError):
                OllamaConfig(**kwargs)

    @patch('jarvis.llm.ollama.http.client.HTTPConnection')
    def test_serializes_special_text_and_does_not_retain_history(self, factory):
        connection = factory.return_value
        connection.getresponse.return_value.status = 200
        connection.getresponse.return_value.read.return_value = response_body()
        model = OllamaLanguageModel()
        secret = 'A "quoted" question\nwith café.'
        self.assertEqual(model.respond(TextRequest(secret)).text, 'A short answer.')
        args = connection.request.call_args.args
        payload = json.loads(args[2])
        self.assertEqual(payload['messages'][1]['content'], secret)
        self.assertFalse(payload['stream'])
        self.assertEqual(payload['options'], {'num_ctx': 2048, 'num_predict': 100})
        factory.assert_called_with('127.0.0.1', 11434, timeout=30.0)
        model.respond(TextRequest('Another question'))
        self.assertEqual(len(json.loads(connection.request.call_args.args[2])['messages']), 2)
        self.assertEqual(connection.close.call_count, 2)

    @patch('jarvis.llm.ollama.http.client.HTTPConnection')
    def test_bad_responses_are_content_free_and_backend_recovers(self, factory):
        connection = factory.return_value
        response = connection.getresponse.return_value
        model = OllamaLanguageModel()
        cases = [(404, b'private server error'), (500, b'private error'),
                 (302, b'redirect'), (200, b'private invalid JSON'),
                 (200, response_body(' ')), (200, response_body(None)),
                 (200, b'[]'), (200, b'{"done": false}'),
                 (200, b'x' * (1024 * 1024 + 1))]
        for status, body in cases:
            response.status = status
            response.read.return_value = body
            with self.subTest(status=status, size=len(body)):
                with self.assertRaises(LanguageModelError) as raised:
                    model.respond(TextRequest('private prompt'))
                self.assertNotIn('private', str(raised.exception))
        response.status = 200
        response.read.return_value = response_body()
        self.assertEqual(model.respond(TextRequest('Retry')).text, 'A short answer.')
        self.assertEqual(connection.close.call_count, len(cases) + 1)

    @patch('jarvis.llm.ollama.http.client.HTTPConnection')
    def test_timeout_closes_connection_and_can_retry(self, factory):
        connection = factory.return_value
        connection.request.side_effect = TimeoutError('private content')
        model = OllamaLanguageModel()
        with self.assertRaises(LanguageModelError) as raised:
            model.respond(TextRequest('private prompt'))
        self.assertNotIn('private', str(raised.exception))
        connection.close.assert_called_once()
        connection.request.side_effect = None
        connection.getresponse.return_value.status = 200
        connection.getresponse.return_value.read.return_value = response_body()
        model.respond(TextRequest('Retry'))

    def test_close_is_idempotent_and_prevents_requests(self):
        model = OllamaLanguageModel()
        model.reset()
        model.close()
        model.close()
        with self.assertRaises(LanguageModelError):
            model.respond(TextRequest('Hello'))
