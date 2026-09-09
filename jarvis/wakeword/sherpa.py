"""Offline keyword spotting with the English GigaSpeech Zipformer model."""

from __future__ import annotations

from pathlib import Path

from jarvis.audio import AudioChunk
from jarvis.wakeword.detector import WakeWordDetector
from jarvis.wakeword.models import WakeWordConfig, WakeWordDetection

DEFAULT_MODEL_DIR = Path("models/wakeword/sherpa-onnx-kws-zipformer-gigaspeech-3.3M-2024-01-01")
DEFAULT_KEYWORDS = Path(__file__).with_name("keywords.txt")


class SherpaOnnxWakeWordDetector(WakeWordDetector):
    """Consume native-endian signed PCM; all inference runs locally on CPU.

    Custom keyword files use sherpa-onnx token syntax. The bundled keywords
    target the downloaded English model. Results have no confidence score.
    """

    def __init__(self, model_dir: str | Path = DEFAULT_MODEL_DIR, *,
                 config: WakeWordConfig | None = None,
                 keywords_file: str | Path = DEFAULT_KEYWORDS) -> None:
        config = config or WakeWordConfig()
        if Path(keywords_file) == DEFAULT_KEYWORDS and config.wake_word != "jarvis":
            raise ValueError("A custom wake word requires a tokenized keywords_file")
        root = Path(model_dir)
        paths = {
            "tokens": root / "tokens.txt",
            "encoder": root / "encoder-epoch-12-avg-2-chunk-16-left-64.int8.onnx",
            "decoder": root / "decoder-epoch-12-avg-2-chunk-16-left-64.onnx",
            "joiner": root / "joiner-epoch-12-avg-2-chunk-16-left-64.int8.onnx",
            "keywords_file": Path(keywords_file),
        }
        for path in paths.values():
            if not path.is_file() or path.stat().st_size == 0:
                raise ValueError(f"Required model or keyword file is missing or empty: {path}")
        # Validate token spelling before entering the native backend.
        vocabulary = {line.rsplit(maxsplit=1)[0] for line in paths["tokens"].read_text().splitlines() if line.strip()}
        lines = paths["keywords_file"].read_text().splitlines()
        if not any(line.strip() for line in lines):
            raise ValueError("The keywords file must contain at least one keyword")
        for line in lines:
            pieces = line.split()
            tokens = [piece for piece in pieces if not piece.startswith(("@", ":", "#"))]
            if pieces and (not tokens or any(token not in vocabulary for token in tokens)):
                raise ValueError("The keywords file contains missing or unknown model tokens")
        try:
            import numpy as np
            import sherpa_onnx
        except ImportError as exc:
            raise RuntimeError('Install the wake-word backend with: python -m pip install -e ".[wakeword]"') from exc
        self._np = np
        self._engine = sherpa_onnx.KeywordSpotter(
            **{name: str(path) for name, path in paths.items()},
            provider="cpu", num_threads=2, sample_rate=16000,
            keywords_threshold=config.threshold,
        )
        self._stream = self._engine.create_stream()

    def process(self, chunk: AudioChunk) -> WakeWordDetection | None:
        if self._engine is None:
            raise RuntimeError("The wake-word detector is closed")
        if (chunk.sample_rate, chunk.channels, chunk.sample_width_bytes) != (16000, 1, 2):
            raise ValueError("Wake-word detection requires 16 kHz mono 16-bit PCM")
        samples = self._np.frombuffer(chunk.data, dtype=self._np.int16).astype(self._np.float32) / 32768.0
        self._stream.accept_waveform(16000, samples)
        detection = None
        while self._engine.is_ready(self._stream):
            self._engine.decode_stream(self._stream)
            keyword = self._engine.get_result(self._stream)
            if keyword:
                self._engine.reset_stream(self._stream)
                if detection is None:
                    detection = WakeWordDetection.create(keyword.strip().casefold(), confidence=None)
        return detection

    def reset(self) -> None:
        """Discard buffered audio as well as decoder state."""
        if self._engine is None:
            raise RuntimeError("The wake-word detector is closed")
        self._stream = self._engine.create_stream()

    def close(self) -> None:
        """Release references to native inference resources."""
        self._stream = None
        self._engine = None

    def __enter__(self) -> SherpaOnnxWakeWordDetector:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
