"""Backend-independent local speech-to-text contracts."""

from jarvis.stt.transcriber import Transcriber, TranscriptionError, TranscriptionResult
from jarvis.stt.whisper import SherpaWhisperTranscriber

__all__ = ['Transcriber', 'TranscriptionError', 'TranscriptionResult', 'SherpaWhisperTranscriber']
