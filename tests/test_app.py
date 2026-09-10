"""Verify complete orchestration with injected backends and no microphone."""

import unittest
from unittest.mock import Mock

from jarvis.app import AssistantState, run_assistant
from jarvis.audio import AudioConfig
from jarvis.capture import CaptureState
from jarvis.llm import LanguageModelError, TextResponse
from jarvis.stt import TranscriptionResult
from jarvis.tts import AudioPlayerError, SynthesisError


class AppTests(unittest.TestCase):
    def setUp(self):
        self.source = Mock(is_running=False)
        self.source.start.side_effect = lambda config: setattr(self.source, 'is_running', True)
        self.source.stop.side_effect = lambda: setattr(self.source, 'is_running', False)
        self.source.read_chunk.side_effect = [object(), object(), KeyboardInterrupt()]
        self.controller = Mock(state=CaptureState.WAITING)
        self.controller.process.side_effect = [object(), object()]
        self.transcriber, self.model, self.synth, self.player = [Mock() for _ in range(4)]
        self.events = []

        def transcribe(request):
            self.assertFalse(self.source.is_running)
            return TranscriptionResult('private request')

        def respond(request):
            self.assertFalse(self.source.is_running)
            self.assertEqual(request.text, 'private request')
            return TextResponse('private response')

        def synthesize(response):
            self.assertFalse(self.source.is_running)
            self.assertEqual(response.text, 'private response')
            return b'PCM'

        def play(audio):
            self.assertFalse(self.source.is_running)
            self.assertEqual(audio, b'PCM')

        self.transcriber.transcribe.side_effect = transcribe
        self.model.respond.side_effect = respond
        self.synth.synthesize.side_effect = synthesize
        self.player.play.side_effect = play

    def run_until_interrupt(self):
        with self.assertRaises(KeyboardInterrupt):
            run_assistant(self.source, self.controller, self.transcriber, self.model,
                          self.synth, self.player, AudioConfig(), report=self.events.append)
        self.assertFalse(self.source.is_running)
        self.assertNotIn('private', ' '.join(self.events))

    def test_repeated_full_pipeline_and_shutdown(self):
        self.run_until_interrupt()
        self.assertEqual(self.model.respond.call_count, 2)
        self.assertEqual(self.player.play.call_count, 2)
        self.assertEqual(self.events.count('state=waiting'), 3)
        self.model.reset.assert_called_once()

    def test_empty_transcription_skips_response_and_playback(self):
        self.transcriber.transcribe.side_effect = None
        self.transcriber.transcribe.return_value = TranscriptionResult(' ')
        self.run_until_interrupt()
        self.model.respond.assert_not_called()
        self.player.play.assert_not_called()

    def test_failed_request_returns_to_listening_and_next_request_succeeds(self):
        self.model.respond.side_effect = [LanguageModelError('private error'), TextResponse('private response')]
        self.run_until_interrupt()
        self.assertIn('stage_failed=responding', self.events)
        self.player.play.assert_called_once()
        self.assertEqual(self.model.reset.call_count, 2)

    def test_tts_failure_returns_to_listening(self):
        self.synth.synthesize.side_effect = [SynthesisError('private failure'), b'PCM']
        self.run_until_interrupt()
        self.assertIn('stage_failed=synthesizing', self.events)
        self.player.play.assert_called_once()

    def test_cleanup_failure_stops_session_without_restart(self):
        self.player.stop.side_effect = AudioPlayerError('Cannot release output')
        with self.assertRaises(AudioPlayerError):
            run_assistant(self.source, self.controller, self.transcriber, self.model,
                          self.synth, self.player, AudioConfig(), report=self.events.append)
        self.assertFalse(self.source.is_running)
        self.assertEqual(self.source.start.call_count, 1)
        self.assertNotIn('stage_failed=speaking', self.events)

    def test_state_callback_and_cooperative_stop(self):
        states = []
        stop = {'value': False}

        def read_chunk(*, timeout):
            stop['value'] = True
            return object()

        self.source.read_chunk.side_effect = read_chunk
        self.controller.process.return_value = None
        run_assistant(self.source, self.controller, self.transcriber, self.model,
                      self.synth, self.player, AudioConfig(),
                      on_state=states.append, stop_requested=lambda: stop['value'])
        self.assertEqual(states, [AssistantState.WAITING])
        self.transcriber.transcribe.assert_not_called()
