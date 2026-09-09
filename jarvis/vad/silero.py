"""Local CPU Silero VAD through sherpa-onnx."""

from __future__ import annotations

from pathlib import Path

from jarvis.audio import AudioChunk
from jarvis.vad.detector import VadConfig, VoiceActivity, VoiceActivityDetector

DEFAULT_MODEL_PATH = Path('models/vad/silero_vad.onnx')


class SileroVoiceActivityDetector(VoiceActivityDetector):
    """Process mono 16 kHz native-endian PCM in 512-sample (32 ms) windows.

    The backend debounces speech using VadConfig. Its completed audio segments
    are discarded immediately: capture owns the request audio. The native
    segment buffer is bounded to 30 seconds and segments split at 20 seconds;
    that internal split does not define the future controller's request limit.
    """

    def __init__(self, model_path: str | Path = DEFAULT_MODEL_PATH, *,
                 config: VadConfig | None = None) -> None:
        path = Path(model_path)
        if not path.is_file() or path.stat().st_size == 0:
            raise ValueError(f'VAD model file is missing or empty: {path}')
        config = config or VadConfig()
        try:
            import numpy as np
            import sherpa_onnx
        except ImportError as exc:
            raise RuntimeError('Install VAD dependencies with: python -m pip install -e ".[vad]"') from exc
        native = sherpa_onnx.VadModelConfig()
        native.sample_rate = 16000
        native.num_threads = 1
        native.provider = 'cpu'
        native.silero_vad.model = str(path)
        native.silero_vad.window_size = 512
        native.silero_vad.threshold = config.threshold
        native.silero_vad.min_speech_duration = config.min_speech_duration
        native.silero_vad.min_silence_duration = config.min_silence_duration
        native.silero_vad.max_speech_duration = 20
        self._np = np
        self._engine = sherpa_onnx.VoiceActivityDetector(native, buffer_size_in_seconds=30)
        self._pending = b''

    def process(self, chunk: AudioChunk) -> tuple[VoiceActivity, ...]:
        if self._engine is None:
            raise RuntimeError('The VAD detector is closed')
        if (chunk.sample_rate, chunk.channels, chunk.sample_width_bytes) != (16000, 1, 2):
            raise ValueError('VAD requires 16 kHz mono 16-bit PCM')
        data = self._pending + chunk.data
        complete = len(data) // 1024 * 1024
        self._pending = data[complete:]
        results = []
        for offset in range(0, complete, 1024):
            samples = self._np.frombuffer(data[offset:offset + 1024], dtype=self._np.int16)
            self._engine.accept_waveform(samples.astype(self._np.float32) / 32768.0)
            results.append(VoiceActivity(self._engine.is_speech_detected(), 512 / 16000))
            while not self._engine.empty():
                self._engine.pop()
        return tuple(results)

    def reset(self) -> None:
        if self._engine is None:
            raise RuntimeError('The VAD detector is closed')
        self._engine.reset()
        self._pending = b''

    def close(self) -> None:
        self._pending = b''
        self._engine = None

    def __enter__(self) -> SileroVoiceActivityDetector:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
