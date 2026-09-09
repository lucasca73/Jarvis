"""Contracts for transcribing complete in-memory audio requests locally."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from jarvis.capture import AudioRequest


@dataclass(frozen=True)
class TranscriptionResult:
    """Text held in memory, excluded from the default representation.

    Empty text means no usable transcription, not a backend failure. Language
    is an optional backend-reported language code; None means unknown. The
    contract does not infer language from the wake word or invent confidence.
    """

    text: str = field(repr=False)
    language: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.text, str):
            raise TypeError('text must be a string')
        object.__setattr__(self, 'text', self.text.strip())
        if self.language is not None:
            if not isinstance(self.language, str):
                raise TypeError('language must be a string or None')
            if not self.language.strip():
                raise ValueError('language must be nonempty when supplied')
            object.__setattr__(self, 'language', self.language.strip())

    @property
    def is_empty(self) -> bool:
        return not self.text


class TranscriptionError(RuntimeError):
    """Local backend failure; messages must exclude audio and transcript content."""


class Transcriber(ABC):
    """Synchronous local inference on one complete request at a time.

    AudioRequest is the input contract: ordered, consistently formatted PCM
    chunks, including pre-roll and trailing silence. Adapters validate supported
    formats and convert in memory as needed. They must not persist or log audio
    or text, contact remote inference, or retain requests between calls.
    """

    @abstractmethod
    def transcribe(self, request: AudioRequest) -> TranscriptionResult:
        """Return text (possibly empty); reject unsupported input with ValueError.

        Raise TranscriptionError for inference failure, with content-free error
        details. Empty recognition is a successful result, not an exception.
        """

    @abstractmethod
    def close(self) -> None:
        """Release backend resources; repeated calls must be safe."""

    def __enter__(self) -> Transcriber:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
