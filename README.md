# JARVIS

A privacy-first voice-activated personal assistant.

The planned voice pipeline runs locally, using sherpa-onnx for wake-word
detection and local Ollama for LLM inference. Privacy is the primary
requirement: audio and conversation content stay in memory by default, with
no cloud fallback. Project code and documentation are written in English.

See [the implementation plan](PLAN.md) for confirmed decisions, current
progress, and the next micro step.

```text
Audio → wake-word detection → transcription → LLM → voice response
```

## Current structure

```text
jarvis/
├── __init__.py
├── app.py             # application entry point
├── audio/             # cross-platform microphone capture
├── wakeword/          # local wake-word detection
└── capture/           # spoken-request capture contracts
```

The project uses Python 3.9 or later. Its current dependency is `sounddevice`
for cross-platform microphone access.

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

## Wake-word detection

The wake-word module currently defines local detection contracts only:

- `WakeWordConfig`: the activation phrase and confidence threshold.
- `WakeWordDetection`: a timestamped activation event.
- `WakeWordDetector`: the interface for a future local detector backend.

The first backend will detect `jarvis` locally from the in-memory PCM chunks
produced by the audio module.

### sherpa-onnx backend

`SherpaOnnxWakeWordDetector` runs keyword spotting locally on CPU using the
English GigaSpeech Zipformer model. It consumes 16 kHz mono 16-bit PCM and
reports activation events with `confidence=None`, since this backend does
not expose a confidence score. The threshold controls the backend trigger.

Install in a project virtual environment:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[wakeword]"
```

The model directory defaults to
`models/wakeword/sherpa-onnx-kws-zipformer-gigaspeech-3.3M-2024-01-01/`
relative to the working directory. Use `--model-dir` to override it. The
adapter uses the int8 encoder and joiner, the float decoder, and `tokens.txt`.
The bundled `jarvis/wakeword/keywords.txt` was generated from `JARVIS` with
this model's SentencePiece BPE model (`▁JA R VI S @jarvis`). SentencePiece is
only needed to prepare new keywords, not during normal operation.

#### Live Jarvis voice test

After installing the wakeword extra and downloading the model, run this
command from the project root to listen through the default microphone for
30 seconds:

```bash
.venv/bin/python -m jarvis.wakeword.diagnostics --duration 30
```

When `Listening locally` appears, say **“Jarvis”** clearly. A successful
activation prints:

```text
Wake word detected: jarvis
```

Pause briefly and say “Jarvis” again to check another activation. The command
exits after 30 seconds; press Ctrl+C to stop early. This diagnostic only
reports wake-word events; it does not transcribe a request or speak a reply.
Audio is processed locally in memory and is not saved.

To find the microphone device ID:

```bash
.venv/bin/python -m jarvis.audio.diagnostics --list-devices
```

Use `--device 2` to select a microphone or `--threshold 0.25` to adjust the
trigger threshold. Higher thresholds make activation harder. For example,
replace `2` with an input device ID from the list:

```bash
.venv/bin/python -m jarvis.wakeword.diagnostics --device 2 --duration 30
```

The user validated live Jarvis detection and reported satisfactory
sensitivity on 2026-09-09. Accent-related recognition limitations are accepted
for the current stage. Explicit checks for silence, unrelated speech, and
repeated activations remain follow-up work.

#### Offline sample test

Run offline inference against the supplied sample keywords:

```bash
.venv/bin/python -m jarvis.wakeword.diagnostics \
  --wav models/wakeword/sherpa-onnx-kws-zipformer-gigaspeech-3.3M-2024-01-01/test_wavs/0.wav \
  --keywords-file models/wakeword/sherpa-onnx-kws-zipformer-gigaspeech-3.3M-2024-01-01/test_wavs/test_keywords.txt
```

Sample `0.wav` produced `light up`; sample `1.wav` produced `lovely child`
and `forever`. These validate model inference, not recognition of Jarvis.
The WAV diagnostic adds a short silence tail to flush buffered features.

Integration follows the [official Python example](https://github.com/k2-fsa/sherpa-onnx/blob/master/python-api-examples/keyword-spotter.py)
and [keyword spotter API](https://github.com/k2-fsa/sherpa-onnx/blob/master/sherpa-onnx/python/sherpa_onnx/keyword_spotter.py).
Validated with sherpa-onnx 1.13.7 on macOS ARM64 / Python 3.9; other platforms
have not yet been exercised.

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

## Request capture contracts

`jarvis.capture` defines the contracts for the next stage after activation:

- `CaptureState.WAITING`: listen for the wake word.
- `CaptureState.CAPTURING`: collect the spoken request after activation.
- `AudioRequest`: associate an activation event with an immutable sequence of
  in-memory PCM chunks. Chunks must share a format and remain in capture order.
  The request exposes audio format, frame count, and sample-based duration.

A request may include pre-roll from before activation. Empty captures do not
produce a request. Audio chunks are omitted from the request's representation
so routine object logging does not include PCM content.

These are data contracts only. State transitions, a bounded pre-roll buffer,
VAD, and end-of-request handling will be implemented in subsequent micro steps.
