"""Synchronous output of in-memory PCM using sounddevice."""

import sys

from jarvis.tts.contracts import AudioPlayer, AudioPlayerError, SynthesizedAudio


class SoundDeviceAudioPlayer(AudioPlayer):
    """One caller at a time; always close the stream after a playback attempt."""

    def __init__(self, device=None, *, backend=None):
        if backend is None:
            import sounddevice as backend
        self._backend = backend
        self._device = device
        self._stream = None
        self._playing = False

    @property
    def is_playing(self):
        return self._playing

    def play(self, audio: SynthesizedAudio) -> None:
        if not isinstance(audio, SynthesizedAudio):
            raise TypeError('audio must be SynthesizedAudio')
        if audio.sample_width_bytes != 2:
            raise ValueError('Playback requires signed 16-bit PCM')
        if self._stream is not None:
            raise AudioPlayerError('Playback is already active')
        data = audio.data
        if sys.byteorder != 'little':
            from array import array
            samples = array('h', data)
            samples.byteswap()
            data = samples.tobytes()
        try:
            self._stream = self._backend.RawOutputStream(
                samplerate=audio.sample_rate, channels=audio.channels,
                dtype='int16', device=self._device)
            self._stream.start()
            self._playing = True
            chunk_size = max(1, audio.sample_rate // 10) * audio.channels * 2
            for offset in range(0, len(data), chunk_size):
                if self._stream.write(data[offset:offset + chunk_size]):
                    raise AudioPlayerError('Audio output underflowed')
            self._stream.stop()  # Drain queued output before releasing the device.
        except Exception:
            raise AudioPlayerError('Local audio playback failed') from None
        finally:
            # Cleanup must preserve an existing failure or Ctrl+C.
            failed = sys.exc_info()[0] is not None
            try:
                self.stop()
            except AudioPlayerError:
                if not failed:
                    raise

    def stop(self) -> None:
        stream = self._stream
        if stream is not None:
            try:
                stream.close()  # PortAudio discards pending audio on close.
            except Exception:
                # Retain ownership so a later cleanup can retry. The output
                # must not be treated as released until close succeeds.
                raise AudioPlayerError('Unable to release audio output') from None
        self._stream = None
        self._playing = False
