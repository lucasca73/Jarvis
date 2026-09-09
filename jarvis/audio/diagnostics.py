"""Command-line diagnostics for Jarvis audio input."""

from __future__ import annotations

import argparse
import math
from time import monotonic

from jarvis.audio import AudioChunk, AudioConfig, SoundDeviceAudioInput


def rms_level(chunk: AudioChunk) -> float:
    """Return the root mean square of a signed 16-bit PCM chunk."""
    if chunk.sample_width_bytes != 2:
        raise ValueError("rms_level only supports 16-bit PCM audio")

    samples = memoryview(chunk.data).cast("h")
    return math.sqrt(sum(sample * sample for sample in samples) / len(samples))


def dbfs_level(chunk: AudioChunk) -> float:
    """Return the chunk volume in decibels relative to full scale."""
    rms = rms_level(chunk)
    return float("-inf") if rms == 0 else 20 * math.log10(rms / 32_767)


def parse_device(value: str) -> int | str:
    """Parse numeric device IDs while preserving device names."""
    return int(value) if value.isdigit() else value


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(description="Diagnose Jarvis audio input.")
    parser.add_argument(
        "--list-devices",
        action="store_true",
        help="list input devices and exit without opening the microphone",
    )
    parser.add_argument(
        "--device",
        type=parse_device,
        help="input device ID or name; defaults to the operating system default",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=5.0,
        help="capture duration in seconds (default: 5)",
    )
    return parser


def main() -> None:
    """List input devices or display their live signal level briefly."""
    arguments = build_parser().parse_args()
    if arguments.duration <= 0:
        raise SystemExit("--duration must be greater than zero")

    source = SoundDeviceAudioInput()
    devices = source.list_input_devices()
    if not devices:
        raise SystemExit("No input devices are available.")

    print("Input devices:")
    for device in devices:
        print(
            f"  {device.id}: {device.name} "
            f"({device.max_input_channels} input channel(s), "
            f"default rate {device.default_sample_rate} Hz)"
        )

    if arguments.list_devices:
        return

    config = AudioConfig(device=arguments.device)
    print("\nOpening input stream. Audio is kept in memory and discarded.")
    source.start(config)
    deadline = monotonic() + arguments.duration

    try:
        while monotonic() < deadline:
            remaining = max(0, deadline - monotonic())
            try:
                chunk = source.read_chunk(timeout=remaining)
            except TimeoutError:
                if monotonic() >= deadline:
                    break
                raise
            level = dbfs_level(chunk)
            level_text = "-∞ dBFS" if math.isinf(level) else f"{level:.1f} dBFS"
            print(f"\rSignal level: {level_text:>10}", end="", flush=True)
    finally:
        source.stop()

    print("\nCapture diagnostic complete.")


if __name__ == "__main__":
    main()
