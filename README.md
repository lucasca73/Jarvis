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

Hardware capture has not yet been validated in the development environment,
which currently exposes no input device to PortAudio. The audio backend is
covered by simulated tests; validation with a permitted physical or virtual
microphone remains pending.

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
