"""Application settings and CLI parsing; no backend resources are opened here."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import math
from pathlib import Path

from jarvis.audio import AudioConfig
from jarvis.audio.diagnostics import parse_device
from jarvis.capture.controller import CaptureConfig
from jarvis.llm import OllamaConfig
from jarvis.vad.detector import VadConfig
from jarvis.wakeword.models import WakeWordConfig
from jarvis.wakeword.sherpa import DEFAULT_MODEL_DIR as WAKEWORD_MODEL, DEFAULT_KEYWORDS
from jarvis.vad.silero import DEFAULT_MODEL_PATH as VAD_MODEL
from jarvis.stt.whisper import DEFAULT_MODEL_DIR as STT_MODEL
from jarvis.tts.piper import DEFAULT_MODEL_DIR as TTS_MODEL


@dataclass(frozen=True)
class AppConfig:
    audio: AudioConfig = field(default_factory=AudioConfig)
    output_device: int | str | None = None
    wakeword: WakeWordConfig = field(default_factory=WakeWordConfig)
    vad: VadConfig = field(default_factory=VadConfig)
    capture: CaptureConfig = field(default_factory=CaptureConfig)
    ollama: OllamaConfig = field(default_factory=OllamaConfig)
    wakeword_model_dir: Path = WAKEWORD_MODEL
    keywords_file: Path = DEFAULT_KEYWORDS
    vad_model: Path = VAD_MODEL
    stt_model_dir: Path = STT_MODEL
    tts_model_dir: Path = TTS_MODEL
    duration: float | None = None

    def __post_init__(self):
        if (self.audio.sample_rate, self.audio.channels, self.audio.sample_width_bytes) != (16000, 1, 2):
            raise ValueError('The voice pipeline requires 16 kHz mono 16-bit PCM')
        if self.duration is not None and (not math.isfinite(self.duration) or self.duration <= 0):
            raise ValueError('duration must be finite and positive')


def parse_config(argv=None) -> AppConfig:
    """Resolve CLI overrides over backend defaults, validating before startup.

    Relative model paths are relative to the working directory. No environment
    overrides, configuration writes, or model downloads are performed.
    """
    defaults = AppConfig()
    parser = argparse.ArgumentParser(description='Run the local Jarvis voice assistant.')
    parser.add_argument('--device', type=parse_device, help='microphone ID or name')
    parser.add_argument('--output-device', type=parse_device)
    parser.add_argument('--duration', type=float, help='session seconds; finish an in-flight response')
    for option in ('wakeword-model-dir', 'keywords-file', 'vad-model', 'stt-model-dir', 'tts-model-dir'):
        parser.add_argument('--' + option, type=Path, default=getattr(defaults, option.replace('-', '_')))
    parser.add_argument('--threshold', type=float, default=defaults.wakeword.threshold,
                        help='wake-word threshold (0 to 1)')
    for option, attribute in (('pre-roll', 'pre_roll_seconds'),
                              ('no-speech-timeout', 'no_speech_timeout_seconds'),
                              ('max-duration', 'max_duration_seconds'),
                              ('silence-hold', 'silence_hold_seconds')):
        parser.add_argument('--' + option, type=float, default=getattr(defaults.capture, attribute))
    for attribute in ('threshold', 'min_speech_duration', 'min_silence_duration'):
        parser.add_argument('--vad-' + attribute.replace('_', '-'), type=float,
                            default=getattr(defaults.vad, attribute))
    for attribute in ('model', 'endpoint', 'timeout_seconds', 'context_tokens',
                      'max_response_tokens', 'keep_alive_seconds', 'max_history_turns'):
        value = getattr(defaults.ollama, attribute)
        parser.add_argument('--' + attribute.replace('_', '-'), type=type(value), default=value)
    args = parser.parse_args(argv)
    try:
        return AppConfig(
            audio=AudioConfig(device=args.device), output_device=args.output_device,
            wakeword=WakeWordConfig(threshold=args.threshold),
            vad=VadConfig(args.vad_threshold, args.vad_min_speech_duration, args.vad_min_silence_duration),
            capture=CaptureConfig(args.pre_roll, args.no_speech_timeout, args.max_duration, args.silence_hold),
            ollama=OllamaConfig(**{key: getattr(args, key) for key in (
                'model', 'endpoint', 'timeout_seconds', 'context_tokens',
                'max_response_tokens', 'keep_alive_seconds', 'max_history_turns')}),
            **{key: getattr(args, key) for key in ('wakeword_model_dir', 'keywords_file',
                'vad_model', 'stt_model_dir', 'tts_model_dir', 'duration')})
    except ValueError as exc:
        parser.error(str(exc))
