"""Backend-independent local speech-to-text contracts."""

from jarvis.stt.transcriber import Transcriber, TranscriptionError, TranscriptionResult

__all__ = ['Transcriber', 'TranscriptionError', 'TranscriptionResult']
