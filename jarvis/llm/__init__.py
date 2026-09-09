"""Backend-independent contracts for local language-model inference."""

from jarvis.llm.client import LanguageModel, LanguageModelError, TextRequest, TextResponse

__all__ = ['LanguageModel', 'LanguageModelError', 'TextRequest', 'TextResponse']
