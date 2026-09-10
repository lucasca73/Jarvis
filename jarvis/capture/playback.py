"""Suspend microphone capture around a spoken response on the consumer thread."""

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
        # A cleanup failure prevents restart: playback may still be active.
        player.stop()
        controller.reset()
        if resume:
            source.start(audio_config)
