"""Qt entry point for the optional Jarvis desktop application."""

from __future__ import annotations

from contextlib import ExitStack

from jarvis.audio import SoundDeviceAudioInput
from jarvis.capture import CaptureController
from jarvis.llm import OllamaLanguageModel
from jarvis.service import AssistantEvent, AssistantEventKind, AssistantService
from jarvis.stt import SherpaWhisperTranscriber
from jarvis.tts import SherpaPiperSynthesizer, SoundDeviceAudioPlayer
from jarvis.vad import SileroVoiceActivityDetector
from jarvis.wakeword import SherpaOnnxWakeWordDetector
from jarvis.ui.status import snapshot_for
from jarvis.ui.window import create_window


def _runner_for(config):
    """Return a worker function that constructs and owns local backends."""
    from jarvis.app import run_assistant

    def run(*, on_state, stop_requested, report):
        with ExitStack() as stack:
            wakeword = stack.enter_context(SherpaOnnxWakeWordDetector(
                config.wakeword_model_dir, config=config.wakeword,
                keywords_file=config.keywords_file))
            vad = stack.enter_context(SileroVoiceActivityDetector(
                config.vad_model, config=config.vad))
            controller = CaptureController(wakeword, vad, config.capture)
            transcriber = stack.enter_context(SherpaWhisperTranscriber(config.stt_model_dir))
            model = stack.enter_context(OllamaLanguageModel(config.ollama))
            synthesizer = stack.enter_context(SherpaPiperSynthesizer(config.tts_model_dir))
            player = stack.enter_context(SoundDeviceAudioPlayer(config.output_device))
            source = stack.enter_context(SoundDeviceAudioInput())
            run_assistant(source, controller, transcriber, model, synthesizer, player,
                          config.audio, duration=config.duration, on_state=on_state,
                          stop_requested=stop_requested, report=report)

    return run


def main(argv=None) -> int:
    try:
        from PySide6.QtCore import QObject, Signal, Slot
        from PySide6.QtWidgets import QApplication
    except ImportError:
        raise SystemExit("Install the optional GUI dependency with: pip install -e '.[gui]'") from None

    from jarvis.config import parse_config
    config = parse_config(argv)
    app = QApplication([])
    app.setApplicationName("Jarvis")

    class Bridge(QObject):
        event = Signal(object)

        def publish(self, value):
            self.event.emit(value)

    bridge = Bridge()
    service = AssistantService(runner=_runner_for(config), event_sink=bridge.publish)

    def quit_requested():
        service.request_stop()
        if not service.is_running:
            app.quit()

    window = create_window(snapshot_for("starting"), on_quit=quit_requested)

    @Slot(object)
    def handle(event: AssistantEvent):
        if event.kind == AssistantEventKind.STATE:
            window.set_snapshot(snapshot_for(event.state))
        elif event.kind == AssistantEventKind.ERROR:
            window.set_snapshot(snapshot_for("unavailable", detail=event.detail))
        elif event.kind == AssistantEventKind.STOPPED:
            app.quit()

    bridge.event.connect(handle)
    window.show()
    service.start()
    result = app.exec()
    service.request_stop()
    service.wait(2)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
