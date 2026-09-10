"""Suspend microphone capture around a spoken response on the consumer thread."""

import sys

from jarvis.tts import AudioPlayerError, SynthesisError


def speak_response(source, controller, audio_config, synthesizer, player, response):
    """Discard captured audio, speak, then restart with fresh detector state.

    Input must be running. The caller owns all components and must use the same
    audio configuration when restarting. Expected synthesis/output failures
    restore listening before propagating. Interruption or unexpected failures
    leave the microphone stopped for caller shutdown. No capture chunks are
    consumed during synthesis or playback. Acoustic echo after reopening still
    needs live validation; this does not implement echo cancellation.
    """
    source.stop()
    resume = False
    try:
        controller.reset()
        try:
            audio = synthesizer.synthesize(response)
            player.play(audio)
        except (SynthesisError, AudioPlayerError):
            resume = True
            raise
        resume = True
    finally:
        original_error = sys.exc_info()[1]
        cleanup_error = None
        # Attempt both cleanup operations even if one fails. Preserve an
        # existing exception (especially Ctrl+C) and never resume on failure.
        for cleanup in (player.stop, controller.reset):
            try:
                cleanup()
            except Exception as exc:
                if cleanup_error is None:
                    cleanup_error = exc
        if cleanup_error is not None:
            if original_error is None:
                raise cleanup_error
        elif resume:
            try:
                source.start(audio_config)
            except BaseException:
                # Start may have acquired partial resources before failing.
                try:
                    source.stop()
                except Exception:
                    pass
                raise
