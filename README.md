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
├── capture/           # spoken-request contracts and pre-roll buffer
└── vad/               # local voice activity detection
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

Use `--device 2` to select a microphone or `--threshold 0.35` to adjust the
trigger threshold. The default is 0.35; higher thresholds make activation harder
and lower thresholds increase recall while allowing more false activations. For example,
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

`PreRollBuffer` retains the newest audio in memory for up to 0.5 seconds by
default (configurable). `append(chunk)` evicts the oldest PCM frames when the
limit is reached; `snapshot()` returns an immutable sequence without consuming
the buffer, and `clear()` releases retained chunks and resets format tracking.
The limit measures stored samples, not elapsed time across capture gaps.
Snapshots retain their audio until their consumers release them.

Chunks must share a PCM format and arrive in capture order. Partial trimming
preserves complete PCM frames and the original chunk capture timestamp. The
buffer performs no disk writes and does not open the microphone.

Local VAD is implemented as described below. State transitions,
microphone-to-buffer integration, and end-of-request handling will be
implemented in subsequent micro steps. The existing wake-word
diagnostic still only reports activation events.


## Local voice activity detection (VAD)

`SileroVoiceActivityDetector` uses Silero through sherpa-onnx on CPU. It
identifies speech activity without transcribing words. The runtime reads
local model files and keeps audio in memory; it does not download models,
send audio to a service, or save speech segments.

Install the optional dependencies (shared with the wakeword extra):

```bash
.venv/bin/python -m pip install -e ".[vad]"
```

Download the model once during setup:

```bash
mkdir -p models/vad
curl -fL https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/silero_vad.onnx -o models/vad/silero_vad.onnx
```

The default path is `models/vad/silero_vad.onnx`, relative to the working
directory; the constructor accepts a different `model_path`. The validated
model SHA-256 is
`9e2449e1087496d8d4caba907f23e0bd3f78d91fa552479bb9c23ac09cbb1fd6`.
See the [official Silero model documentation](https://k2-fsa.github.io/sherpa/onnx/vad/silero-vad.html).

The adapter consumes the same 16 kHz mono 16-bit PCM as the microphone. It
buffers incomplete windows and returns ordered `VoiceActivity` decisions for
all complete 512-sample windows (32 ms each). Short input may return no
results. `reset()` discards partial input and speech state; `close()` releases
resources. The detector supports use as a context manager.

`VadConfig` defaults to a threshold of 0.5, 0.25 seconds of minimum speech,
and 0.5 seconds of minimum silence. Decisions reflect the backend's debounced
speech state, so the capture controller must account for this delay when
implementing end-of-request handling. These settings are separate from the
0.5-second pre-roll buffer. Incomplete final windows are discarded on reset;
stream-end handling belongs to the future controller.

Native completed segments are discarded after every window. The native
segment buffer is limited to 30 seconds and internally splits speech at
20 seconds; this is not the application's request timeout.

Validation on macOS ARM64 / Python 3.9 with sherpa-onnx 1.13.7: silence
produced no speech, the downloaded wake-word model's `test_wavs/0.wav`
produced speech, and a two-second silence tail returned the detector to
silence. All 51 unit tests passed. Live microphone VAD and full request
capture are not yet validated or connected to the wake-word diagnostic.

### Request capture controller

`jarvis.capture.CaptureController` connects an injected wake-word detector and
VAD to the in-memory pre-roll buffer. Feed ordered 16 kHz mono 16-bit PCM chunks
through `process(chunk)`. It returns an `AudioRequest` on completion, or `None`
while waiting, capturing, or cancelling an activation without speech. The
`state` property exposes `WAITING` and `CAPTURING`.

`CaptureConfig` defaults:

- `pre_roll_seconds=0.5`: retained audio up to and including activation.
- `no_speech_timeout_seconds=3.0`: cancel if no speech is detected after activation.
- `max_duration_seconds=15.0`: stop collecting post-activation audio at this limit.
- `silence_hold_seconds=0.5`: require sustained non-speech decisions after speech.
  This is additional to Silero's 0.5-second silence debounce, so the default
  endpoint delay is approximately one second, plus window/chunk rounding.

Timeouts measure audio samples, not wall-clock time. Silence and no-speech
completion are checked at chunk boundaries; use the existing 100 ms input
chunks. Maximum duration trims on a PCM frame boundary and excludes pre-roll.
A request includes its pre-roll and trailing silence. Audio beyond completion
in the final input chunk is discarded. An interrupted audio source must call
`reset()` to discard the unfinished request; sample-based timeouts cannot
advance while no audio arrives.

Activation/pre-roll audio is not fed to VAD, preventing the activation alone
from qualifying as a request. Speech entirely inside that audio cannot qualify
either; this boundary needs live testing with “Jarvis” followed immediately by
short commands. The additional silence hold tolerates brief VAD state changes;
custom hold/debounce settings and requests longer than Silero's internal
20-second segment limit require validation together.

The controller resets detector state after completion or cancellation. It does
not open or close the caller-owned detectors or microphone, transcribe speech,
or persist audio. Automated controller tests pass; a live microphone capture
diagnostic is available below; the user confirmed live capture works on 2026-09-09.

### Live request capture test

With the wake-word and VAD models installed, run from the repository root:

```bash
.venv/bin/python -m jarvis.capture.diagnostics --duration 90
```

Use `--device ID` or `--device "device name"` to select a microphone. List
devices with `.venv/bin/python -m jarvis.audio.diagnostics --list-devices`.
The diagnostic prints activation, request completion (stored duration and
frame count), and cancellation without saving audio. It also loads the local
Whisper model and transcribes each completed request in memory. STT timing and
empty status are always reported; add `--show-text` to print each transcript.

1. Say “Jarvis” followed by a sentence, then stop speaking. Expect activation,
   completion after silence, and a return to waiting.
2. Say only “Jarvis”. Expect cancellation after three seconds without speech.
3. Speak a request with a brief pause, then continue. Check that it stays in
   one request. Repeat with a longer pause to observe the endpoint.
4. Repeat several requests to check that each activation starts fresh.
5. Test a shorter maximum with `--max-duration 4 --no-speech-timeout 2`.
   Keep speaking after activation: capture should finish after four seconds
   of post-activation audio, with up to 0.5 seconds of pre-roll added.
6. Test “Jarvis” immediately followed by a short command, and compare with
   waiting for the activation message before speaking. Report missed commands.

`--silence-hold`, `--pre-roll`, and `--no-speech-timeout` configure the controller
in seconds. `--threshold` configures wake-word sensitivity; `--model-dir`,
`--keywords-file`, and `--vad-model` override model paths. `--duration` limits
the whole session; expiry or Ctrl+C discards any unfinished request.

Automated verification: all 63 tests pass, including diagnostic completion,
reactivation, cancellation, interruption, source failure, and invalid session
duration. The user confirmed live request capture works on 2026-09-09; detailed observations for every edge case have not been reported. Console events establish
capture boundaries; they do not establish transcription accuracy or whether
every spoken word was retained.


### Speech-to-text contracts

`jarvis.stt.Transcriber` defines synchronous local transcription of an
`AudioRequest`, preserving the capture format and in-memory audio boundary.
Adapters implement `transcribe(request)` and idempotent `close()`; the interface
also supports context-manager cleanup.

`TranscriptionResult` contains trimmed `text` and an optional backend-reported
`language` code. `is_empty` identifies recognition with no usable text. Text is
excluded from the default representation. Unsupported audio raises `ValueError`;
backend failures use `TranscriptionError` with content-free messages. Adapters
must keep audio and text out of logs and files and perform inference locally.
These are contracts, not an implemented recognizer or enforced network sandbox.

The first adapter is `jarvis.stt.SherpaWhisperTranscriber`. It loads the int8
Whisper tiny.en files, converts each request chunk from signed 16-bit PCM to
float samples in memory, and returns English text. It does not write audio or
transcripts. Missing model files and unavailable dependencies fail before
inference; backend failures are reported as `TranscriptionError` without
including content. Exact-zero PCM silence returns an empty result without
invoking the model, preventing a needless inference path. Empty recognizer
output is successful and distinguishable from `TranscriptionError`.

On the Apple M4 development machine, model load took 0.152 seconds and one
6.6-second bundled sample took 0.251 seconds to transcribe with two CPU
threads. These are single-run smoke measurements, not a latency guarantee.

All 68 tests pass. Voice interaction is English-only for now, as confirmed by
the user. The initial backend/model is selected below; latency remains to be measured.

Run `python -m jarvis.stt.diagnostics path/to/request.wav` to benchmark a local
English request without printing its transcript. Add `--show-text` to inspect
the recognized text during validation. The WAV must be 16 kHz mono 16-bit PCM.
The diagnostic reports audio length, model load time, inference time, and empty
status; it keeps normal output free of conversation content.


### Initial STT backend selection

Selected on 2026-09-09: **Whisper tiny.en through sherpa-onnx 1.13.7, CPU**.
The development machine is an Apple M4 Mac mini with 16 GB RAM; the existing
Python environment already runs sherpa-onnx for wake word and VAD. English-only
interaction allows an English-only model. Reusing the installed inference stack
keeps the first adapter small and supports in-memory PCM input.

The model is installed under `models/stt/sherpa-onnx-whisper-tiny.en/`. The
int8 encoder and decoder loaded successfully, and bundled sample 0 produced a
transcription locally.

The [official sherpa-onnx tiny.en documentation](https://k2-fsa.github.io/sherpa/onnx/pretrained_models/whisper/tiny.en.html)
provides an exported ONNX model. The installed Python API was inspected and
exposes `OfflineRecognizer.from_whisper` with encoder, decoder, tokens, language,
task, thread count, and provider arguments. Initial settings will be
`language="en"`, `task="transcribe"`, `provider="cpu"`, `num_threads=2`, and
`debug=False`, loading explicit files under `models/stt/`. Model download is a
setup action; normal transcription must use local files without network access.

Alternatives considered:

- [whisper.cpp](https://github.com/ggml-org/whisper.cpp) supports Apple Silicon
  acceleration through Metal and Core ML. It is a useful candidate if CPU
  latency is inadequate, but requires another runtime and an in-memory binding.
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) provides a Python
  API and CPU int8 inference, but introduces the CTranslate2 inference stack.

Choosing tiny.en is an initial integration decision, not a benchmark result or
an accuracy guarantee. Next, measure model load time and warm transcription latency on
short English requests and the 15-second capture limit; check recognition of
the user's accent, silence, and empty output. A provisional engineering target
is warm transcription faster than audio duration, then assess conversational
latency with the user. If accuracy is inadequate, evaluate a larger English
Whisper model; if latency is inadequate, compare an Apple-accelerated runtime.
Keep measurement logs to timings and counts, without transcript content.


## Local language-model contracts

`jarvis.llm` defines `TextRequest` and `TextResponse` as nonempty, trimmed
text values held in memory, with content excluded from their representations.
Callers must skip empty STT results before constructing a request.

`LanguageModel.respond(request)` returns a response; backend failures, including
empty answers, must raise a content-free `LanguageModelError`. Implementations
must use local inference without remote fallback or conversation logging.
Any history must remain bounded in memory; `reset()` clears it, and `close()`
clears history and releases resources. Context-manager exit calls `close()`.
The first adapter is `jarvis.llm.ollama.OllamaLanguageModel`, configured through
`OllamaConfig`. The pipeline can depend on `LanguageModel` while backend-specific
configuration stays at construction time.

The user validated live capture and transcription on 2026-09-09 and accepted
current recognition limitations to prioritize completing the full voice pipeline.


### Local Ollama adapter

The initial model is `llama3.2:3b`, served at `http://127.0.0.1:11434`.
Install it separately with `ollama pull llama3.2:3b`; Jarvis never downloads
models during inference. Defaults are a 2,048-token context, a 100-token answer
limit, a 30-second socket timeout, and a 600-second model keep-alive. The answer
limit may truncate text. The socket timeout bounds individual blocking socket
operations, not an absolute end-to-end deadline.

Run a fixed, nonsensitive English question through the adapter:

```bash
.venv/bin/python -m jarvis.llm.diagnostics --show-text
```

Without `--show-text`, output contains only timing and character count.
`--model` and `--endpoint` override the diagnostic defaults. Programmatic callers
can configure all limits with `OllamaConfig` and call `respond(TextRequest(...))`.
This adapter handles one independent interaction at a time; bounded history and
microphone integration remain later steps.

The HTTP client connects directly to literal loopback IPs, ignores environment
proxies, and rejects redirects. Cloud-named models are rejected. HTTP failures,
connection failures, timeouts, and malformed/empty answers become content-free
`LanguageModelError` values; later requests can retry. Audio, prompts, and answers
are not logged or written by the adapter. Closing it does not unload the shared
Ollama model; the server manages that model according to keep-alive.

A local endpoint and model-name checks cannot enforce the separate server's
behavior (including aliased models). Disable cloud features on the Ollama server
with `OLLAMA_NO_CLOUD=1` and restart it. For the macOS application, set it with
`launchctl setenv OLLAMA_NO_CLOUD 1` before restarting Ollama. Server configuration
and a full offline/privacy audit remain unverified in this step. See the
[official server configuration FAQ](https://docs.ollama.com/faq) and
[chat API](https://docs.ollama.com/api/chat).

Validation: all 89 tests passed. A real adapter call to the installed local
`llama3.2:3b` returned 188 characters in 0.863 seconds (one smoke measurement,
not a latency guarantee).
