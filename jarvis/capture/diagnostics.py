"""Observe local wake-word activation and request capture on a microphone."""

from __future__ import annotations

import argparse
import math
from contextlib import ExitStack
from time import monotonic

from jarvis.audio import AudioConfig, SoundDeviceAudioInput
from jarvis.audio.diagnostics import parse_device
from jarvis.capture import CaptureConfig, CaptureController, CaptureState
from jarvis.vad import SileroVoiceActivityDetector
from jarvis.vad.silero import DEFAULT_MODEL_PATH
from jarvis.wakeword import SherpaOnnxWakeWordDetector, WakeWordConfig
from jarvis.wakeword.sherpa import DEFAULT_KEYWORDS, DEFAULT_MODEL_DIR
from jarvis.stt import SherpaWhisperTranscriber
from jarvis.stt.whisper import DEFAULT_MODEL_DIR as DEFAULT_STT_MODEL_DIR
from jarvis.capture.playback import speak_response
from jarvis.llm import TextResponse
from jarvis.tts import SherpaPiperSynthesizer, SoundDeviceAudioPlayer, SynthesisError, AudioPlayerError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--device', type=parse_device)
    parser.add_argument('--duration', type=float, default=60)
    parser.add_argument('--model-dir', default=str(DEFAULT_MODEL_DIR))
    parser.add_argument('--keywords-file', default=str(DEFAULT_KEYWORDS))
    parser.add_argument('--vad-model', default=str(DEFAULT_MODEL_PATH))
    parser.add_argument('--threshold', type=float, default=0.35)
    parser.add_argument('--pre-roll', type=float, default=0.5)
    parser.add_argument('--no-speech-timeout', type=float, default=3)
    parser.add_argument('--max-duration', type=float, default=15)
    parser.add_argument('--silence-hold', type=float, default=0.5)
    parser.add_argument('--stt-model', default=str(DEFAULT_STT_MODEL_DIR))
    parser.add_argument('--show-text', action='store_true', help='print each transcript')
    parser.add_argument('--speak-confirmation', action='store_true',
                        help='test microphone suspension with a fixed spoken confirmation')
    parser.add_argument('--output-device', type=parse_device)
    return parser


def run_capture(source, controller: CaptureController, duration: float, *,
                transcriber=None, show_text: bool = False, confirmation=None) -> None:
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
                    message = (f'Request complete: {request.duration_seconds:.2f}s '
                               f'({request.frame_count} frames, including pre-roll and silence). '
                               'Waiting for Jarvis.')
                    print(message, flush=True)
                    if transcriber is not None:
                        started = monotonic()
                        result = transcriber.transcribe(request)
                        elapsed = monotonic() - started
                        print(f'STT complete: {elapsed:.3f}s empty={result.is_empty}', flush=True)
                        if show_text:
                            print(f'Transcript: {result.text}', flush=True)
                    if confirmation is not None:
                        try:
                            confirmation()
                        except (SynthesisError, AudioPlayerError):
                            if not source.is_running:
                                raise
                            print('Spoken confirmation failed. Listening restored.', flush=True)
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
        ) as wakeword, SileroVoiceActivityDetector(args.vad_model) as vad, \
                SherpaWhisperTranscriber(args.stt_model) as transcriber:
            controller = CaptureController(wakeword, vad, config)
            with ExitStack() as stack:
                confirmation = None
                source = stack.enter_context(SoundDeviceAudioInput())
                audio_config = AudioConfig(device=args.device)
                if args.speak_confirmation:
                    synth = stack.enter_context(SherpaPiperSynthesizer())
                    player = stack.enter_context(SoundDeviceAudioPlayer(args.output_device))

                    def confirmation():
                        print('Speaking confirmation with microphone suspended.', flush=True)
                        speak_response(source, controller, audio_config, synth, player,
                                       TextResponse('Jarvis is ready for your next request.'))
                        print('Waiting for Jarvis.', flush=True)

                source.start(audio_config)
                run_capture(source, controller, args.duration,
                            transcriber=transcriber, show_text=args.show_text,
                            confirmation=confirmation)
        print('Capture diagnostic complete.')
    except KeyboardInterrupt:
        print('\nCapture diagnostic stopped.')
    except (ValueError, RuntimeError, OSError, TimeoutError) as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == '__main__':
    main()
