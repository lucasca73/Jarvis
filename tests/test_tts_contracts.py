import unittest

from jarvis.llm import TextResponse
from jarvis.tts import AudioPlayer, AudioPlayerError, SynthesizedAudio, Synthesizer, SynthesisError


class StubSynthesizer(Synthesizer):
    def __init__(self): self.closed = False
    def synthesize(self, response): return SynthesizedAudio(b'\x00\x00' * 1600)
    def close(self): self.closed = True


class StubPlayer(AudioPlayer):
    def __init__(self): self.playing = False
    @property
    def is_playing(self): return self.playing
    def play(self, audio): self.playing = True
    def stop(self): self.playing = False


class TtsContractTests(unittest.TestCase):
    def test_audio_format_and_duration_are_validated(self):
        audio = SynthesizedAudio(b'\x00\x00' * 1600)
        self.assertEqual(audio.frame_count, 1600)
        self.assertEqual(audio.duration_seconds, 0.1)
        self.assertNotIn('\\x00', repr(audio))
        for kwargs in ({'data': b''}, {'data': b'\x00'}, {'data': b'\x00\x00', 'sample_rate': 0}, {'data': b'\x00\x00', 'channels': 0}):
            with self.assertRaises(ValueError): SynthesizedAudio(**kwargs)

    def test_text_response_is_synthesis_input(self):
        result = StubSynthesizer().synthesize(TextResponse('hello'))
        self.assertEqual(result.duration_seconds, 0.1)

    def test_context_cleanup_and_player_state(self):
        synth = StubSynthesizer()
        with synth: pass
        self.assertTrue(synth.closed)
        player = StubPlayer()
        with player:
            player.play(SynthesizedAudio(b'\x00\x00'))
            self.assertTrue(player.is_playing)
        self.assertFalse(player.is_playing)

    def test_interfaces_are_abstract(self):
        with self.assertRaises(TypeError): Synthesizer()
        with self.assertRaises(TypeError): AudioPlayer()
