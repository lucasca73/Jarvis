"""Test the GUI-independent status presentation model."""

import unittest

from jarvis.app import AssistantState
from jarvis.ui import DisplayState, StatusSnapshot, snapshot_for
from jarvis.ui.window import qt_available


class UiStatusTests(unittest.TestCase):
    def test_pipeline_states_map_to_minimal_labels(self):
        self.assertEqual(snapshot_for(AssistantState.WAITING).state, DisplayState.READY)
        self.assertEqual(snapshot_for(AssistantState.CAPTURING).label, "Listening")
        self.assertEqual(snapshot_for(AssistantState.RESPONDING).label, "Thinking")
        self.assertEqual(snapshot_for(AssistantState.SPEAKING).state, DisplayState.SPEAKING)

    def test_detail_is_optional_and_does_not_change_main_label(self):
        snapshot = snapshot_for("unavailable", detail="Start Ollama and reopen Jarvis")
        self.assertEqual(snapshot, StatusSnapshot(DisplayState.UNAVAILABLE, "Unavailable", "Start Ollama and reopen Jarvis"))

    def test_unknown_state_and_multiline_content_are_rejected(self):
        with self.assertRaises(ValueError):
            snapshot_for("translating")
        with self.assertRaises(ValueError):
            StatusSnapshot(DisplayState.READY, "Ready\nnow")

    def test_qt_is_optional_at_import_time(self):
        self.assertIsInstance(qt_available(), bool)
