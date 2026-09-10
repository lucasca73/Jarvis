"""Backend-independent speech synthesis and playback contracts."""

from jarvis.tts.contracts import (
    AudioPlayer,
    AudioPlayerError,
    SynthesizedAudio,
    Synthesizer,
    SynthesisError,
)

__all__ = [
    'AudioPlayer', 'AudioPlayerError', 'SynthesizedAudio', 'Synthesizer',
    'SynthesisError',
]
