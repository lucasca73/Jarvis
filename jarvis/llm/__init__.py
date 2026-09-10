"""Backend-independent contracts for local language-model inference."""

from jarvis.llm.client import LanguageModel, LanguageModelError, TextRequest, TextResponse
from jarvis.llm.ollama import OllamaConfig, OllamaLanguageModel
from jarvis.llm.privacy import OllamaPrivacyAudit, audit

__all__ = [
    'LanguageModel', 'LanguageModelError', 'TextRequest', 'TextResponse',
    'OllamaConfig', 'OllamaLanguageModel',
    'OllamaPrivacyAudit', 'audit',
]
