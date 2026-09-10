"""Local Piper/VITS speech synthesis through sherpa-onnx."""

from pathlib import Path

from jarvis.llm import TextResponse
from jarvis.resources import runtime_path
from jarvis.tts.contracts import SynthesizedAudio, Synthesizer, SynthesisError

DEFAULT_MODEL_DIR = runtime_path('models/tts/vits-piper-en_US-lessac-medium')


class SherpaPiperSynthesizer(Synthesizer):
    """Load the Lessac voice locally and synthesize mono signed 16-bit PCM."""

    def __init__(self, model_dir=DEFAULT_MODEL_DIR, *, num_threads=2):
        if type(num_threads) is not int or num_threads <= 0:
            raise ValueError('num_threads must be a positive integer')
        root = Path(model_dir)
        model = root / 'en_US-lessac-medium.onnx'
        tokens = root / 'tokens.txt'
        data = root / 'espeak-ng-data'
        for path in (model, tokens, data / 'phontab', data / 'phondata',
                     data / 'phonindex', data / 'en_dict'):
            if not path.is_file() or not path.stat().st_size:
                raise ValueError(f'Required TTS file is missing or empty: {path}')
        try:
            import numpy as np
            import sherpa_onnx as sherpa
        except ImportError:
            raise SynthesisError('Install TTS dependencies with: pip install -e ".[tts]"') from None
        self._np = np
        try:
            config = sherpa.OfflineTtsConfig(model=sherpa.OfflineTtsModelConfig(
                vits=sherpa.OfflineTtsVitsModelConfig(
                    model=str(model), tokens=str(tokens), data_dir=str(data)),
                num_threads=num_threads, debug=False, provider='cpu'))
            self._engine = sherpa.OfflineTts(config)
        except Exception:
            raise SynthesisError('Unable to load the local TTS voice') from None

    def synthesize(self, response: TextResponse) -> SynthesizedAudio:
        if self._engine is None:
            raise SynthesisError('The TTS synthesizer is closed')
        if not isinstance(response, TextResponse):
            raise TypeError('response must be a TextResponse')
        try:
            generated = self._engine.generate(response.text, sid=0, speed=1.0)
            samples = self._np.asarray(generated.samples, dtype=self._np.float32)
            if samples.ndim != 1 or not samples.size or not self._np.isfinite(samples).all():
                raise ValueError('Invalid samples')
            pcm = self._np.clip(self._np.rint(samples * 32768.0), -32768, 32767)
            return SynthesizedAudio(pcm.astype('<i2').tobytes(), generated.sample_rate)
        except Exception:
            raise SynthesisError('Local TTS synthesis failed or returned invalid audio') from None

    def close(self) -> None:
        self._engine = None
        self._np = None
