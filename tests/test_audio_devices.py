"""Tests for audio input-device discovery."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from jarvis.audio import NoInputDeviceError, SoundDeviceDeviceCatalog


class FakeSoundDeviceBackend:
    """In-memory sounddevice replacement for deterministic tests."""

    def __init__(self, devices: list[dict], default_input_device: int | None) -> None:
        self._devices = devices
        self.default = SimpleNamespace(device=[default_input_device, -1])

    def query_devices(self) -> list[dict]:
        return self._devices


class SoundDeviceDeviceCatalogTests(unittest.TestCase):
    def setUp(self) -> None:
        self.devices = [
            {
                "name": "Built-in Output",
                "max_input_channels": 0,
                "default_samplerate": 48_000,
            },
            {
                "name": "Built-in Microphone",
                "max_input_channels": 2,
                "default_samplerate": 44_100,
            },
        ]

    def test_lists_only_input_devices(self) -> None:
        catalog = SoundDeviceDeviceCatalog(FakeSoundDeviceBackend(self.devices, 1))

        devices = catalog.list_input_devices()

        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0].id, 1)
        self.assertEqual(devices[0].name, "Built-in Microphone")
        self.assertEqual(devices[0].default_sample_rate, 44_100.0)

    def test_returns_the_default_input_device(self) -> None:
        catalog = SoundDeviceDeviceCatalog(FakeSoundDeviceBackend(self.devices, 1))

        device = catalog.get_default_input_device()

        self.assertEqual(device.name, "Built-in Microphone")

    def test_rejects_missing_default_input_device(self) -> None:
        catalog = SoundDeviceDeviceCatalog(FakeSoundDeviceBackend(self.devices, None))

        with self.assertRaises(NoInputDeviceError):
            catalog.get_default_input_device()
