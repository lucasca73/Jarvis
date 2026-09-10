"""Backend-independent speech synthesis and playback contracts."""

from jarvis.tts.contracts import (
    AudioPlayer,
    AudioPlayerError,
    SynthesizedAudio,
    Synthesizer,
    SynthesisError,
)
from jarvis.tts.piper import SherpaPiperSynthesizer
from jarvis.tts.player import SoundDeviceAudioPlayer

__all__ = [
    'AudioPlayer', 'AudioPlayerError', 'SynthesizedAudio', 'Synthesizer',
    'SynthesisError',
    'SherpaPiperSynthesizer', 'SoundDeviceAudioPlayer',
]
