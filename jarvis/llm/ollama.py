"""Single-turn Ollama inference through a loopback-only HTTP connection."""

from __future__ import annotations

from dataclasses import dataclass
import http.client
import json
import math
from urllib.parse import urlsplit

from jarvis.llm.client import LanguageModel, LanguageModelError, TextRequest, TextResponse

SYSTEM_PROMPT = (
    'You are Jarvis, a voice assistant. Answer in English using one or two '
    'short sentences. Avoid markdown.'
)


@dataclass(frozen=True)
class OllamaConfig:
    model: str = 'llama3.2:3b'
    endpoint: str = 'http://127.0.0.1:11434'
    timeout_seconds: float = 30.0
    context_tokens: int = 2048
    max_response_tokens: int = 100
    keep_alive_seconds: int = 600

    def __post_init__(self) -> None:
        if not isinstance(self.model, str) or not self.model.strip():
            raise ValueError('model must be nonempty')
        model = self.model.strip()
        if 'cloud' in model.lower() or '/' in model:
            raise ValueError('Use a local Ollama model name')
        object.__setattr__(self, 'model', model)
        try:
            url = urlsplit(self.endpoint)
            valid = (url.scheme == 'http' and url.hostname in ('127.0.0.1', '::1')
                     and url.username is None and url.password is None
                     and url.path in ('', '/') and not url.query and not url.fragment
                     and (url.port is None or 1 <= url.port <= 65535))
        except (TypeError, ValueError):
            valid = False
        if not valid:
            raise ValueError('endpoint must be an HTTP loopback IP address without a path')
        if (isinstance(self.timeout_seconds, bool)
                or not isinstance(self.timeout_seconds, (int, float))
                or not math.isfinite(self.timeout_seconds) or self.timeout_seconds <= 0):
            raise ValueError('timeout_seconds must be finite and positive')
        for name in ('context_tokens', 'max_response_tokens', 'keep_alive_seconds'):
            value = getattr(self, name)
            if type(value) is not int or value < (0 if name == 'keep_alive_seconds' else 1):
                raise ValueError(f'{name} has an invalid value')


class OllamaLanguageModel(LanguageModel):
    """No history, downloads, retries, redirects, environment proxies, or logging.

    The local Ollama service must also be configured for local-only operation;
    a loopback connection cannot enforce what a separately managed server does.
    """

    def __init__(self, config: OllamaConfig | None = None) -> None:
        self.config = config if config is not None else OllamaConfig()
        self._closed = False

    def respond(self, request: TextRequest) -> TextResponse:
        if self._closed:
            raise LanguageModelError('Language model is closed')
        if not isinstance(request, TextRequest):
            raise TypeError('request must be a TextRequest')
        url = urlsplit(self.config.endpoint)
        connection = http.client.HTTPConnection(
            url.hostname, url.port or 80, timeout=self.config.timeout_seconds)
        payload = {
            'model': self.config.model,
            'messages': [
                {'role': 'system', 'content': SYSTEM_PROMPT},
                {'role': 'user', 'content': request.text},
            ],
            'stream': False,
            'keep_alive': self.config.keep_alive_seconds,
            'options': {'num_ctx': self.config.context_tokens,
                        'num_predict': self.config.max_response_tokens},
        }
        try:
            connection.request('POST', '/api/chat', json.dumps(payload).encode('utf-8'),
                               {'Content-Type': 'application/json'})
            response = connection.getresponse()
            if response.status == 404:
                raise LanguageModelError('Local Ollama model or endpoint was not found')
            if response.status != 200:
                raise LanguageModelError('Local Ollama request failed')
            # Bound malformed server output without retaining arbitrarily large bodies.
            body = response.read(1024 * 1024 + 1)
            if len(body) > 1024 * 1024:
                raise LanguageModelError('Local Ollama response is too large')
            result = json.loads(body)
            if (not isinstance(result, dict) or result.get('done') is not True
                    or 'error' in result or not isinstance(result.get('message'), dict)):
                raise LanguageModelError('Local Ollama returned an invalid response')
            message = result['message']
            if message.get('role') != 'assistant' or message.get('tool_calls'):
                raise LanguageModelError('Local Ollama returned an unsupported response')
            return TextResponse(message.get('content'))
        except LanguageModelError:
            raise
        except (OSError, http.client.HTTPException):
            raise LanguageModelError('Local Ollama is unavailable or timed out') from None
        except (ValueError, TypeError, RecursionError):
            raise LanguageModelError('Local Ollama returned invalid or empty text') from None
        finally:
            connection.close()

    def reset(self) -> None:
        """No history is retained by this single-turn adapter."""

    def close(self) -> None:
        self._closed = True
