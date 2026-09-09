# JARVIS

A local-first voice-activated personal assistant.

```text
Audio → wake-word detection → transcription → LLM → voice response
```

## Current structure

```text
jarvis/
├── __init__.py
├── app.py             # application entry point
└── audio/             # audio-capture contracts and future implementation
    ├── input.py
    └── models.py
```

The project uses Python 3.9 or later. There are no external dependencies yet:
audio capture will be implemented in the next step.

The audio module currently exposes these contracts:

- `AudioConfig`: PCM input settings, with 16 kHz mono audio as the default.
- `AudioDevice`: an available input device.
- `AudioChunk`: a timestamped in-memory PCM segment.
- `AudioInput`: the abstract interface that an audio backend must implement.

It also provides `SoundDeviceDeviceCatalog` to list input devices and identify
the operating system's default microphone. The `sounddevice` dependency is
installed with the project dependencies:

```bash
python3 -m pip install -e .
```

`SoundDeviceAudioInput` captures signed 16-bit PCM in memory and returns
100-millisecond `AudioChunk` values by default. It does not write raw audio to
disk.

Hardware capture was validated with a real input device. The audio backend
correctly listed the device, opened a 16 kHz mono stream, received a
100-millisecond PCM chunk, and released the stream without persisting audio.

### Audio diagnostics

List available input devices without opening the microphone:

```bash
python3 -m jarvis.audio.diagnostics --list-devices
```

Open the default microphone for five seconds and show its live signal level.
Audio remains in memory and is discarded after each chunk:

```bash
python3 -m jarvis.audio.diagnostics
```

To select a device and change the duration:

```bash
python3 -m jarvis.audio.diagnostics --device 2 --duration 10
```

To verify the entry point:

```bash
python -m jarvis.app
```

## Tests

Run the complete test suite from the project root:

```bash
python3 -m unittest discover -s tests -v
```

Run a specific test file:

```bash
python3 -m unittest tests/test_audio_models.py -v
```
