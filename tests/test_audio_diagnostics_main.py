"""Tests for the diagnostic command flow."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from jarvis.audio import AudioChunk
from jarvis.audio import diagnostics


class FakeAudioInput:
    """Audio input that times out after the diagnostic deadline."""

    def __init__(self) -> None:
        self.stopped = False

    def list_input_devices(self) -> list[object]:
        return []

    def stop(self) -> None:
        self.stopped = True


class AudioDiagnosticsMainTests(unittest.TestCase):
    def test_exits_cleanly_when_deadline_timeout_occurs(self) -> None:
        input_source = FakeAudioInput()
        time_values = iter([0.0, 0.0, 1.0, 1.0])

        with (
            patch.object(diagnostics, "SoundDeviceAudioInput", return_value=input_source),
            patch.object(diagnostics, "monotonic", side_effect=time_values),
            patch.object(diagnostics, "build_parser") as build_parser,
        ):
            build_parser.return_value.parse_args.return_value = type(
                "Arguments",
                (),
                {"duration": 1.0, "list_devices": False, "device": None},
            )()
            input_source.list_input_devices = lambda: [
                type(
                    "Device",
                    (),
                    {
                        "id": 2,
                        "name": "Test Microphone",
                        "max_input_channels": 1,
                        "default_sample_rate": 16_000,
                    },
                )()
            ]
            input_source.start = lambda config: None
            input_source.read_chunk = lambda timeout: (_ for _ in ()).throw(TimeoutError())

            diagnostics.main()

        self.assertTrue(input_source.stopped)
