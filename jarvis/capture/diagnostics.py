"""Observe local wake-word activation and request capture on a microphone."""

from __future__ import annotations

import argparse
import math
from time import monotonic

from jarvis.audio import AudioConfig, SoundDeviceAudioInput
from jarvis.audio.diagnostics import parse_device
from jarvis.capture import CaptureConfig, CaptureController, CaptureState
from jarvis.vad import SileroVoiceActivityDetector
from jarvis.vad.silero import DEFAULT_MODEL_PATH
from jarvis.wakeword import SherpaOnnxWakeWordDetector, WakeWordConfig
from jarvis.wakeword.sherpa import DEFAULT_KEYWORDS, DEFAULT_MODEL_DIR


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--device', type=parse_device)
    parser.add_argument('--duration', type=float, default=60)
    parser.add_argument('--model-dir', default=str(DEFAULT_MODEL_DIR))
    parser.add_argument('--keywords-file', default=str(DEFAULT_KEYWORDS))
    parser.add_argument('--vad-model', default=str(DEFAULT_MODEL_PATH))
    parser.add_argument('--threshold', type=float, default=0.5)
    parser.add_argument('--pre-roll', type=float, default=0.5)
    parser.add_argument('--no-speech-timeout', type=float, default=3)
    parser.add_argument('--max-duration', type=float, default=15)
    parser.add_argument('--silence-hold', type=float, default=0.5)
    return parser


def run_capture(source, controller: CaptureController, duration: float) -> None:
    """Report transitions and release request audio immediately after reporting."""
    deadline = monotonic() + duration
    print('Waiting for Jarvis. Audio stays in memory. Press Ctrl+C to stop.', flush=True)
    try:
        while True:
            remaining = deadline - monotonic()
            if remaining <= 0:
                break
            try:
                chunk = source.read_chunk(timeout=remaining)
            except TimeoutError:
                if monotonic() < deadline:
                    raise
                break
            previous = controller.state
            request = controller.process(chunk)
            if previous == CaptureState.WAITING and controller.state == CaptureState.CAPTURING:
                print('Activated. Capturing request...', flush=True)
            elif previous == CaptureState.CAPTURING and controller.state == CaptureState.WAITING:
                if request is None:
                    print('Cancelled: no speech detected. Waiting for Jarvis.', flush=True)
                else:
                    print(f'Request complete: {request.duration_seconds:.2f}s '
                          f'({request.frame_count} frames, including pre-roll and silence). '
                          'Waiting for Jarvis.', flush=True)
            del request
    finally:
        if controller.state == CaptureState.CAPTURING:
            print('Unfinished request discarded.', flush=True)
        controller.reset()


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if not math.isfinite(args.duration) or args.duration <= 0:
        parser.error('--duration must be finite and greater than zero')
    try:
        config = CaptureConfig(args.pre_roll, args.no_speech_timeout,
                               args.max_duration, args.silence_hold)
        wakeword_config = WakeWordConfig(threshold=args.threshold)
        with SherpaOnnxWakeWordDetector(
            args.model_dir, keywords_file=args.keywords_file, config=wakeword_config,
        ) as wakeword, SileroVoiceActivityDetector(args.vad_model) as vad:
            controller = CaptureController(wakeword, vad, config)
            with SoundDeviceAudioInput() as source:
                source.start(AudioConfig(device=args.device))
                run_capture(source, controller, args.duration)
        print('Capture diagnostic complete.')
    except KeyboardInterrupt:
        print('\nCapture diagnostic stopped.')
    except (ValueError, RuntimeError, OSError, TimeoutError) as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == '__main__':
    main()
