"""Local voice pipeline with explicit backend dependencies."""

import argparse
from contextlib import ExitStack
from enum import Enum
import math
import sys
from time import monotonic

from jarvis.audio import AudioConfig, SoundDeviceAudioInput
from jarvis.audio.diagnostics import parse_device
from jarvis.capture import CaptureController, CaptureState
from jarvis.capture.playback import suspended_capture
from jarvis.llm import LanguageModelError, OllamaConfig, OllamaLanguageModel, TextRequest
from jarvis.stt import SherpaWhisperTranscriber, TranscriptionError
from jarvis.tts import AudioPlayerError, SynthesisError, SherpaPiperSynthesizer, SoundDeviceAudioPlayer
from jarvis.vad import SileroVoiceActivityDetector
from jarvis.wakeword import SherpaOnnxWakeWordDetector


class AssistantState(str, Enum):
    WAITING = 'waiting'
    CAPTURING = 'capturing'
    TRANSCRIBING = 'transcribing'
    RESPONDING = 'responding'
    SYNTHESIZING = 'synthesizing'
    SPEAKING = 'speaking'


RECOVERABLE_ERRORS = (TranscriptionError, LanguageModelError, SynthesisError, AudioPlayerError)


def run_assistant(source, controller, transcriber, model, synthesizer, player,
                  audio_config, *, duration=None, report=print):
    """Run on a single consumer thread; caller owns backend lifetimes.

    Reports contain only states/timing. Duration is checked between requests;
    an in-flight response is allowed to finish. All audio and text stay in memory.
    """
    if duration is not None and (not math.isfinite(duration) or duration <= 0):
        raise ValueError('duration must be finite and positive')
    deadline = None if duration is None else monotonic() + duration
    state = AssistantState.WAITING

    def transition(next_state):
        nonlocal state
        state = next_state
        report(f'state={state.value}')

    try:
        source.start(audio_config)
        transition(AssistantState.WAITING)
        while deadline is None or monotonic() < deadline:
            try:
                chunk = source.read_chunk(timeout=0.5)
            except TimeoutError:
                continue
            request = controller.process(chunk)
            del chunk
            if request is None:
                capture_state = (AssistantState.CAPTURING if controller.state == CaptureState.CAPTURING
                                 else AssistantState.WAITING)
                if capture_state != state:
                    transition(capture_state)
                continue
            started = monotonic()
            transcript = response = audio = None
            try:
                with suspended_capture(source, controller, audio_config, player,
                                       recoverable_errors=RECOVERABLE_ERRORS):
                    transition(AssistantState.TRANSCRIBING)
                    transcript = transcriber.transcribe(request)
                    if not transcript.is_empty:
                        transition(AssistantState.RESPONDING)
                        response = model.respond(TextRequest(transcript.text))
                        transition(AssistantState.SYNTHESIZING)
                        audio = synthesizer.synthesize(response)
                        transition(AssistantState.SPEAKING)
                        player.play(audio)
            except RECOVERABLE_ERRORS:
                if not source.is_running:
                    raise
                # A generated answer may not have been spoken. Discard history
                # so the next interaction cannot assume the user heard it.
                model.reset()
                report(f'stage_failed={state.value}')
            finally:
                request = transcript = response = audio = None
            report(f'request_seconds={monotonic() - started:.3f}')
            transition(AssistantState.WAITING)
    finally:
        original_error = sys.exc_info()[1]
        cleanup_error = None
        for cleanup in (source.stop, player.stop, controller.reset, model.reset):
            try:
                cleanup()
            except Exception as exc:
                if cleanup_error is None:
                    cleanup_error = exc
        if cleanup_error is not None and original_error is None:
            raise cleanup_error


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--device', type=parse_device, help='microphone ID or name')
    parser.add_argument('--output-device', type=parse_device)
    parser.add_argument('--model', default='llama3.2:3b')
    parser.add_argument('--endpoint', default='http://127.0.0.1:11434')
    parser.add_argument('--duration', type=float, help='session seconds; finish an in-flight response')
    args = parser.parse_args()
    if args.duration is not None and (not math.isfinite(args.duration) or args.duration <= 0):
        parser.error('--duration must be finite and positive')
    try:
        config = OllamaConfig(model=args.model, endpoint=args.endpoint)
        with ExitStack() as stack:
            wakeword = stack.enter_context(SherpaOnnxWakeWordDetector())
            vad = stack.enter_context(SileroVoiceActivityDetector())
            controller = CaptureController(wakeword, vad)
            transcriber = stack.enter_context(SherpaWhisperTranscriber())
            model = stack.enter_context(OllamaLanguageModel(config))
            synth = stack.enter_context(SherpaPiperSynthesizer())
            player = stack.enter_context(SoundDeviceAudioPlayer(args.output_device))
            source = stack.enter_context(SoundDeviceAudioInput())
            run_assistant(source, controller, transcriber, model, synth, player,
                          AudioConfig(device=args.device), duration=args.duration,
                          report=lambda message: print(message, flush=True))
    except KeyboardInterrupt:
        print('Jarvis stopped.')
    except Exception:
        # Backend exception messages/chains may contain conversation content.
        raise SystemExit('Jarvis stopped because a local backend failed. Check devices and models.') from None


if __name__ == "__main__":
    main()
