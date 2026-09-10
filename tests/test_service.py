"""Test the toolkit-independent threaded service boundary."""

import threading
import time
import unittest

from jarvis.app import AssistantState
from jarvis.service import AssistantEvent, AssistantEventKind, AssistantService


class ServiceTests(unittest.TestCase):
    def test_worker_publishes_states_and_stops_cooperatively(self):
        events = []
        stopped = threading.Event()

        def runner(*, on_state, stop_requested, report):
            on_state(AssistantState.WAITING)
            while not stop_requested():
                time.sleep(0.001)
            stopped.set()

        service = AssistantService(runner=runner, event_sink=events.append)
        service.start()
        self.assertTrue(service.is_running)
        service.request_stop()
        self.assertTrue(service.wait(1))
        self.assertTrue(stopped.is_set())
        self.assertEqual([event.kind for event in events],
                         [AssistantEventKind.STATE, AssistantEventKind.STOPPED])
        self.assertEqual(events[0].state, AssistantState.WAITING)

    def test_worker_converts_failures_to_content_free_event(self):
        events = []

        def runner(**_kwargs):
            raise RuntimeError("private prompt leaked")

        service = AssistantService(runner=runner, event_sink=events.append)
        service.start()
        self.assertTrue(service.wait(1))
        self.assertIsNotNone(service.failure)
        self.assertEqual(events[0], AssistantEvent(AssistantEventKind.ERROR,
                                                   detail="A local component failed"))
        self.assertEqual(events[1], AssistantEvent(AssistantEventKind.STOPPED))

    def test_event_contract_rejects_invalid_state_and_detail(self):
        with self.assertRaises(ValueError):
            AssistantEvent(AssistantEventKind.STATE)
        with self.assertRaises(ValueError):
            AssistantEvent(AssistantEventKind.ERROR, state=AssistantState.WAITING)
        with self.assertRaises(ValueError):
            AssistantEvent(AssistantEventKind.ERROR, detail="x\nprivate")
