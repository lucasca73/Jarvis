"""Ensure voice output cannot be queued as a later microphone request."""

import unittest
from unittest.mock import Mock

from jarvis.audio import AudioConfig
from jarvis.capture.playback import speak_response
from jarvis.llm import TextResponse
from jarvis.tts import AudioPlayerError, SynthesisError


class CapturePlaybackTests(unittest.TestCase):
    def setUp(self):
        self.events = []
        self.source = Mock()
        self.controller = Mock()
        self.synth = Mock()
        self.player = Mock()
        self.running = True
        self.queued = ['old microphone audio']

        def stop():
            self.events.append('input.stop')
            self.running = False
            self.queued.clear()

        def start(config):
            self.assertFalse(self.running)
            self.assertEqual(self.queued, [])
            self.events.append('input.start')
            self.running = True

        def synthesize(response):
            self.assertFalse(self.running)
            self.events.append('synthesize')
            return b'audio'

        def play(audio):
            self.assertFalse(self.running)
            self.events.append('play')

        self.source.stop.side_effect = stop
        self.source.start.side_effect = start
        self.controller.reset.side_effect = lambda: self.events.append('reset')
        self.synth.synthesize.side_effect = synthesize
        self.player.play.side_effect = play
        self.player.stop.side_effect = lambda: self.events.append('output.stop')

    def speak(self):
        speak_response(self.source, self.controller, AudioConfig(device=4),
                       self.synth, self.player, TextResponse('Jarvis is ready.'))

    def test_order_and_repeated_requests(self):
        for _ in range(2):
            self.events.clear()
            self.speak()
            self.assertEqual(self.events, ['input.stop', 'reset', 'synthesize', 'play',
                                           'output.stop', 'reset', 'input.start'])
        self.source.start.assert_called_with(AudioConfig(device=4))

    def test_expected_failures_restore_listening(self):
        for component, error in ((self.synth.synthesize, SynthesisError),
                                 (self.player.play, AudioPlayerError)):
            old = component.side_effect
            component.side_effect = error('Backend failed')
            with self.assertRaises(error):
                self.speak()
            self.assertTrue(self.running)
            self.assertEqual(self.events[-3:], ['output.stop', 'reset', 'input.start'])
            component.side_effect = old

    def test_interrupt_does_not_restart_microphone(self):
        self.player.play.side_effect = KeyboardInterrupt
        with self.assertRaises(KeyboardInterrupt):
            self.speak()
        self.assertFalse(self.running)
        self.source.start.assert_not_called()
        self.player.stop.assert_called_once()

    def test_output_cleanup_failure_prevents_restart(self):
        self.player.stop.side_effect = AudioPlayerError('Cannot close output')
        with self.assertRaises(AudioPlayerError):
            self.speak()
        self.source.start.assert_not_called()
        self.assertFalse(self.running)
