"""Input-device discovery backed by the cross-platform sounddevice library."""

from __future__ import annotations

from importlib import import_module
from typing import Any, Protocol, Sequence

from jarvis.audio.models import AudioDevice


class AudioBackendUnavailableError(RuntimeError):
    """Raised when the configured audio backend cannot be loaded."""


class NoInputDeviceError(RuntimeError):
    """Raised when no usable input device is available."""


class SoundDeviceBackend(Protocol):
    """The small subset of sounddevice required for device discovery."""

    default: Any

    def query_devices(self) -> Sequence[Any]:
        """Return audio devices known to the backend."""


class SoundDeviceDeviceCatalog:
    """Discover audio input devices using sounddevice and PortAudio."""

    def __init__(self, backend: SoundDeviceBackend | None = None) -> None:
        self._backend = backend if backend is not None else self._load_backend()

    def list_input_devices(self) -> list[AudioDevice]:
        """Return all devices that expose at least one input channel."""
        devices = [
            self._to_audio_device(index, device)
            for index, device in enumerate(self._backend.query_devices())
            if int(device["max_input_channels"]) > 0
        ]

        return devices

    def get_default_input_device(self) -> AudioDevice:
        """Return the operating system's default input device.

        Raises:
            NoInputDeviceError: If the backend has no usable default input device.
        """
        default_device_ids = self._backend.default.device
        if not default_device_ids:
            raise NoInputDeviceError("No default input device is configured")

        input_device_id = default_device_ids[0]
        if input_device_id is None or input_device_id < 0:
            raise NoInputDeviceError("No default input device is configured")

        for device in self.list_input_devices():
            if device.id == input_device_id:
                return device

        raise NoInputDeviceError("The configured default input device is unavailable")

    @staticmethod
    def _load_backend() -> SoundDeviceBackend:
        try:
            return import_module("sounddevice")  # type: ignore[return-value]
        except ImportError as error:
            raise AudioBackendUnavailableError(
                "sounddevice is required for audio device discovery. "
                "Install the project dependencies before using audio capture."
            ) from error

    @staticmethod
    def _to_audio_device(index: int, device: Any) -> AudioDevice:
        default_sample_rate = device.get("default_samplerate")
        return AudioDevice(
            id=index,
            name=str(device["name"]),
            max_input_channels=int(device["max_input_channels"]),
            default_sample_rate=(
                float(default_sample_rate) if default_sample_rate is not None else None
            ),
        )
