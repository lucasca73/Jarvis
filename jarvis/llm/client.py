"""In-memory text contracts for a local conversational backend."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


def _validated_text(text: str) -> str:
    if not isinstance(text, str):
        raise TypeError('text must be a string')
    text = text.strip()
    if not text:
        raise ValueError('text must be nonempty')
    return text


@dataclass(frozen=True)
class TextRequest:
    """A nonempty user request; callers must skip empty STT results."""

    text: str = field(repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, 'text', _validated_text(self.text))


@dataclass(frozen=True)
class TextResponse:
    """A nonempty answer intended for speech synthesis."""

    text: str = field(repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, 'text', _validated_text(self.text))


class LanguageModelError(RuntimeError):
    """Backend failure with messages that exclude conversation content."""


class LanguageModel(ABC):
    """Synchronous local inference, with no remote fallback or content logging.

    Adapters must keep prompts and responses in memory without persisting them.
    Any conversation history must be bounded and cleared by reset() and close().
    These requirements are backend obligations, not a network sandbox.
    """

    @abstractmethod
    def respond(self, request: TextRequest) -> TextResponse:
        """Return an answer or raise a content-free LanguageModelError.

        Timeouts, unavailable backends/models, and empty or malformed backend
        responses are failures. A failure must leave the backend reusable.
        """

    @abstractmethod
    def reset(self) -> None:
        """Discard any retained conversation history."""

    @abstractmethod
    def close(self) -> None:
        """Clear history and release resources; repeated calls must be safe."""

    def __enter__(self) -> LanguageModel:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
