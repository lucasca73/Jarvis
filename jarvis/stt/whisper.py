"""Local English Whisper transcription through sherpa-onnx."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jarvis.capture import AudioRequest
from jarvis.resources import runtime_path
from jarvis.stt.transcriber import Transcriber, TranscriptionError, TranscriptionResult

DEFAULT_MODEL_DIR = runtime_path("models/stt/sherpa-onnx-whisper-tiny.en")


class SherpaWhisperTranscriber(Transcriber):
    """Transcribe complete 16 kHz mono 16-bit requests on the local CPU."""

    def __init__(self, model_dir: str | Path = DEFAULT_MODEL_DIR, *,
                 num_threads: int = 2, provider: str = "cpu",
                 recognizer: Any | None = None, numpy: Any | None = None) -> None:
        if num_threads <= 0:
            raise ValueError("num_threads must be greater than zero")
        self._recognizer = recognizer
        self._np = numpy
        self._closed = False
        if recognizer is not None:
            return
        root = Path(model_dir)
        files = {
            "encoder": root / "tiny.en-encoder.int8.onnx",
            "decoder": root / "tiny.en-decoder.int8.onnx",
            "tokens": root / "tiny.en-tokens.txt",
        }
        for path in files.values():
            if not path.is_file() or path.stat().st_size == 0:
                raise ValueError(f"Required STT model file is missing or empty: {path}")
        try:
            import numpy as np
            import sherpa_onnx
            self._np = np
            self._recognizer = sherpa_onnx.OfflineRecognizer.from_whisper(
                **{name: str(path) for name, path in files.items()},
                language="en", task="transcribe", num_threads=num_threads,
                decoding_method="greedy_search", provider=provider,
            )
        except ImportError as exc:
            raise RuntimeError('Install STT dependencies with: python -m pip install -e ".[vad]"') from exc
        except Exception as exc:
            raise TranscriptionError("Unable to load the local STT model") from exc

    def transcribe(self, request: AudioRequest) -> TranscriptionResult:
        if self._closed or self._recognizer is None:
            raise RuntimeError("The STT transcriber is closed")
        if (request.sample_rate, request.channels, request.sample_width_bytes) != (16000, 1, 2):
            raise ValueError("Whisper STT requires 16 kHz mono 16-bit PCM")
        if self._np is None:
            raise RuntimeError("The STT numeric backend is unavailable")
        try:
            if all(not chunk.data.strip(b"\x00") for chunk in request.chunks):
                return TranscriptionResult("", "en")
            stream = self._recognizer.create_stream()
            for chunk in request.chunks:
                samples = self._np.frombuffer(chunk.data, dtype=self._np.int16).astype(self._np.float32) / 32768.0
                if len(samples):
                    stream.accept_waveform(request.sample_rate, samples)
            self._recognizer.decode_stream(stream)
            result = stream.result
            text = getattr(result, "text", "")
            if not isinstance(text, str):
                raise TranscriptionError("Local STT returned an invalid result")
            return TranscriptionResult(text, "en")
        except (ValueError, TranscriptionError):
            raise
        except Exception as exc:
            raise TranscriptionError("Local STT inference failed") from exc

    def close(self) -> None:
        self._recognizer = None
        self._np = None
        self._closed = True
