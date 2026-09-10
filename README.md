# JARVIS

A privacy-first voice assistant with an implemented local voice pipeline:

```text
Microphone → Jarvis wake word → request capture / VAD → Whisper → Ollama → Piper → speakers
```

The user confirmed the integrated pipeline works on 2026-09-10. MVP consolidation
is in progress: configuration is centralized; shutdown/recovery review, stage
latency reporting, extended stability, and complete offline/privacy validation
remain pending. See [PLAN.md](PLAN.md) for implementation milestones and next work.

Voice interaction is English-only. Code, documentation, and application messages
are in English. Recognition quality and accent handling are accepted limitations
for this stage; improvements follow MVP consolidation.

## Requirements and installation

The package declares Python 3.9 or later. The development environment validated
so far is macOS ARM64, Python 3.9, Apple M4 with 16 GB RAM. Other Python versions
and platforms have not been validated. Microphone access and an output device
are needed for live use.

From the repository root:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[wakeword,vad,tts]"
```

`sounddevice>=0.5,<1` is the base dependency. The three extras currently share
`sherpa-onnx==1.13.7` and `numpy>=1.23,<3`; they cover the complete local audio
inference pipeline, including STT. There is no separate `stt` extra.
Ollama is a separately installed and managed service.

### Local models

Download models during setup, then run with local files. Model assets are
ignored by Git and are not included in the Python package. Run these commands
from the repository root if the bundles are not already installed:

```bash
mkdir -p models/wakeword models/vad models/stt models/tts
curl -fL https://github.com/k2-fsa/sherpa-onnx/releases/download/kws-models/sherpa-onnx-kws-zipformer-gigaspeech-3.3M-2024-01-01.tar.bz2 -o models/wakeword/model.tar.bz2
tar -xjf models/wakeword/model.tar.bz2 -C models/wakeword
curl -fL https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/silero_vad.onnx -o models/vad/silero_vad.onnx
curl -fL https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-whisper-tiny.en.tar.bz2 -o models/stt/model.tar.bz2
tar -xjf models/stt/model.tar.bz2 -C models/stt
curl -fL https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/vits-piper-en_US-lessac-medium.tar.bz2 -o models/tts/model.tar.bz2
tar -xjf models/tts/model.tar.bz2 -C models/tts
```

Model sources: [sherpa-onnx keyword models](https://k2-fsa.github.io/sherpa/onnx/kws/pretrained_models/index.html),
[Silero VAD](https://k2-fsa.github.io/sherpa/onnx/vad/silero-vad.html),
[Whisper tiny.en](https://k2-fsa.github.io/sherpa/onnx/pretrained_models/whisper/tiny.en.html),
and [Piper Lessac](https://k2-fsa.github.io/sherpa/onnx/tts/all/English/vits-piper-en_US-lessac-medium.html).

| Stage | Default path | Required assets |
| --- | --- | --- |
| Wake word | `models/wakeword/sherpa-onnx-kws-zipformer-gigaspeech-3.3M-2024-01-01/` | `encoder-epoch-12-avg-2-chunk-16-left-64.int8.onnx`, `decoder-epoch-12-avg-2-chunk-16-left-64.onnx`, `joiner-epoch-12-avg-2-chunk-16-left-64.int8.onnx`, `tokens.txt` |
| VAD | `models/vad/silero_vad.onnx` | Silero ONNX file |
| STT | `models/stt/sherpa-onnx-whisper-tiny.en/` | `tiny.en-encoder.int8.onnx`, `tiny.en-decoder.int8.onnx`, `tiny.en-tokens.txt` |
| TTS | `models/tts/vits-piper-en_US-lessac-medium/` | `en_US-lessac-medium.onnx`, `tokens.txt`, complete `espeak-ng-data/` |

Jarvis uses its packaged `jarvis/wakeword/keywords.txt`, containing
`▁JA R VI S @jarvis`, rather than the downloaded example keywords. A custom
keyword file must use the model's token syntax. SentencePiece is needed only
when preparing new BPE keywords, not for normal inference.

Recorded local SHA-256 values (not publisher-authenticated checksums):

- Silero model: `9e2449e1087496d8d4caba907f23e0bd3f78d91fa552479bb9c23ac09cbb1fd6`.
- Piper archive: `9e3febfacf0abf4270172d2958bcec246032b7e88efc2720840cc80c93de334e`.

### Ollama setup and privacy boundary

Install Ollama separately and download the selected model during setup:

```bash
ollama pull llama3.2:3b
```

Configure the Ollama server with `OLLAMA_NO_CLOUD=1` and restart it. For the
macOS application, run `launchctl setenv OLLAMA_NO_CLOUD 1` before restarting
Ollama. For a manually managed server, start it with
`OLLAMA_NO_CLOUD=1 ollama serve`. See the [official Ollama FAQ](https://docs.ollama.com/faq)
for service-specific environment configuration.

Jarvis connects directly to `http://127.0.0.1:11434` by default. Its client
accepts only HTTP literal loopback addresses (`127.0.0.1` or `::1`), ignores
proxy environment variables, rejects redirects, and rejects model names
containing `cloud` or `/`. It does not download models or provide remote fallback.
These checks cannot establish the behavior of a separately managed server or
an aliased model.

Audio, transcripts, prompts, responses, and bounded conversation history remain
in application memory by default. Normal application output contains operational
metadata, not conversation content. Selected diagnostics expose text only with
`--show-text`. Jarvis does not implement a network sandbox, and the complete
pipeline has not yet undergone the offline/network/persistence audit in step 7.7.

Run the standalone client configuration check:

```bash
OLLAMA_NO_CLOUD=1 .venv/bin/python -m jarvis.llm.privacy_diagnostics
```

This command checks default client settings and the diagnostic process's own
environment. It makes no server request, does not inspect the Ollama process,
and does not read the app's CLI overrides. A passing result does not establish
that cloud features are disabled in the running server. The app does not
automatically run this diagnostic or require this environment variable itself.

## Run the assistant

With the models installed and the configured Ollama service running:

```bash
.venv/bin/python -m jarvis.app
```

After `state=waiting`, say “Jarvis, why is the sky blue?” The application captures
the request, transcribes it, generates and speaks an answer, and returns to
waiting. Its states are waiting → capturing → transcribing → responding →
synthesizing → speaking → waiting; empty recognition skips the response stages.

Input is stopped and queued audio discarded during the entire response cycle.
Speech during transcription, LLM inference, synthesis, or playback is ignored.
There is no interruption during playback, echo cancellation, or post-playback
delay. Ctrl+C initiates cleanup, discards unfinished capture, and clears history.

Expected STT, LLM, synthesis, and playback errors restore listening when cleanup
and microphone restart succeed. A failed response clears history so subsequent
turns do not assume the answer was heard. Device, unexpected backend, and cleanup
failures terminate the session. These paths have automated coverage; additional
shutdown/recovery review and real hardware disconnect tests remain pending.

### Configuration

`jarvis.config.AppConfig` groups the existing backend configuration contracts.
`parse_config` applies CLI overrides and validates settings before backend
startup. Adapters check model files when loading. Relative paths resolve from
the working directory; path overrides do not change expected bundle filenames.
The app does not read a configuration file or environment overrides for these
settings. Backend defaults remain the source of default values.

```bash
.venv/bin/python -m jarvis.app --help
.venv/bin/python -m jarvis.app --device 2 --max-duration 10 --no-speech-timeout 2 --max-history-turns 2
```

| Options | Defaults / meaning |
| --- | --- |
| `--device`, `--output-device` | System defaults; accept device IDs or names |
| `--duration` | Unlimited session; positive seconds, checked between requests; an in-flight response can finish after the deadline |
| `--wakeword-model-dir`, `--keywords-file`, `--vad-model`, `--stt-model-dir`, `--tts-model-dir` | Paths listed above; packaged Jarvis keywords |
| `--threshold` | Wake-word trigger 0.35; lower values increase recall and potential false activations; not a confidence probability |
| `--pre-roll`, `--no-speech-timeout`, `--max-duration`, `--silence-hold` | 0.5, 3, 15, 0.5 seconds respectively; positive; no-speech timeout cannot exceed maximum duration |
| `--vad-threshold`, `--vad-min-speech-duration`, `--vad-min-silence-duration` | 0.5, 0.25 s, 0.5 s |
| `--model`, `--endpoint` | `llama3.2:3b`, `http://127.0.0.1:11434` |
| `--timeout-seconds`, `--context-tokens`, `--max-response-tokens` | 30, 2048, 100 |
| `--keep-alive-seconds`, `--max-history-turns` | 600, 4; zero history turns selects independent requests |

The Ollama timeout bounds individual blocking socket operations, not total
response time. The response token limit may truncate answers. Closing Jarvis
clears its history but does not explicitly unload the shared Ollama model.

## Components and contracts

```text
jarvis/
├── app.py       # orchestration, states, resource ownership
├── config.py    # application configuration and CLI
├── audio/       # devices, PCM contracts, microphone input
├── wakeword/    # sherpa-onnx keyword spotting and packaged keywords
├── vad/         # Silero speech activity decisions
├── capture/     # pre-roll, request controller, microphone suspension
├── stt/         # Whisper transcription
├── llm/         # Ollama client, bounded history, configuration audit
└── tts/         # Piper synthesis and sounddevice playback
```

`run_assistant` accepts injected backend dependencies; `main()` constructs the
concrete components and manages their lifetimes. Contracts remain separate
from backend implementations.

- **Audio:** `AudioConfig`, `AudioDevice`, `AudioChunk`, and `AudioInput` describe
  input. `SoundDeviceDeviceCatalog` discovers microphones. `SoundDeviceAudioInput`
  captures 100 ms chunks by default, with a bounded queue. The integrated pipeline
  requires 16 kHz mono signed 16-bit PCM.
- **Wake word:** `WakeWordConfig`, `WakeWordDetection`, and `WakeWordDetector`
  define activation. `SherpaOnnxWakeWordDetector` processes incremental audio on
  CPU and emits events with `confidence=None`; reset discards decoder state.
- **VAD:** `SileroVoiceActivityDetector` consumes complete 512-sample windows
  (32 ms), buffers partial windows, and returns debounced `VoiceActivity` values.
  Reset discards partial audio and speech state. Native completed segments are
  discarded; its 30-second buffer and 20-second segment splitting are internal.
- **Capture:** `PreRollBuffer` retains recent PCM on frame boundaries.
  `CaptureController.process` returns an `AudioRequest` on completion or `None`
  while waiting, capturing, or cancelling. Requests include pre-roll and trailing
  silence. Timeouts measure audio samples; maximum duration excludes pre-roll
  and trims precisely to a PCM frame. Silence/no-speech checks use chunk boundaries.
- **STT:** `SherpaWhisperTranscriber` implements `Transcriber` with English int8
  Whisper tiny.en on CPU and two threads. `TranscriptionResult.is_empty` distinguishes
  empty recognition from failure; exact-zero PCM skips inference.
- **LLM:** `OllamaLanguageModel` implements `LanguageModel` with nonempty
  `TextRequest` and `TextResponse` values. History retains up to four successful
  user/assistant turns; `reset()` and `close()` clear it. Failed turns are not retained.
- **TTS:** `SherpaPiperSynthesizer` implements `Synthesizer` with the English
  Lessac voice, CPU, two threads, speaker 0, and speed 1.0. It produces in-memory
  mono signed 16-bit little-endian PCM at 22,050 Hz. `SoundDeviceAudioPlayer`
  implements blocking playback and releases the output stream afterward.

Activation/pre-roll audio is retained for STT but excluded from VAD speech
qualification. A short command entirely within that audio can be missed.
The default silence hold adds 0.5 seconds after VAD's 0.5-second debounce,
so endpoint delay is approximately one second plus window/chunk rounding.
Requests longer than the native VAD segment limit need joint validation with
custom capture settings. Sample-based timeouts cannot advance without audio.

## Diagnostics

Run commands from the repository root with their required local models installed.
Each diagnostic has its own CLI; application options are not shared automatically.

| Purpose | Command |
| --- | --- |
| List microphones | `.venv/bin/python -m jarvis.audio.diagnostics --list-devices` |
| Audio levels for five seconds | `.venv/bin/python -m jarvis.audio.diagnostics` |
| Wake-word events only | `.venv/bin/python -m jarvis.wakeword.diagnostics --duration 30` |
| Capture and transcribe requests | `.venv/bin/python -m jarvis.capture.diagnostics --duration 90` |
| Capture with transcript display | `.venv/bin/python -m jarvis.capture.diagnostics --duration 90 --show-text` |
| Test microphone suspension with a fixed spoken confirmation | `.venv/bin/python -m jarvis.capture.diagnostics --duration 90 --speak-confirmation` |
| Transcribe a local WAV | `.venv/bin/python -m jarvis.stt.diagnostics path/to/request.wav` |
| Fixed LLM prompt | `.venv/bin/python -m jarvis.llm.diagnostics` |
| Generate and play a fixed sentence | `.venv/bin/python -m jarvis.tts.diagnostics --play` |

Capture diagnostics require wake-word, VAD, and Whisper models; spoken confirmation
also requires Piper. They do not call Ollama. Use the app for complete responses.
STT and LLM diagnostics support `--show-text`. TTS without `--play` synthesizes
without opening an output device. These commands do not save audio.

Use each inference/audio diagnostic's `--help` for options. Capture uses `--model-dir`
for wake word and `--stt-model` for Whisper, while the app uses
`--wakeword-model-dir` and `--stt-model-dir`. TTS uses `--device` for output;
capture and the app use `--output-device`.

Offline wake-word sample inference (16 kHz mono 16-bit PCM WAV):

```bash
.venv/bin/python -m jarvis.wakeword.diagnostics \
  --wav models/wakeword/sherpa-onnx-kws-zipformer-gigaspeech-3.3M-2024-01-01/test_wavs/0.wav \
  --keywords-file models/wakeword/sherpa-onnx-kws-zipformer-gigaspeech-3.3M-2024-01-01/test_wavs/test_keywords.txt
```

The diagnostic adds a silence tail to flush features. Sample 0 previously produced
`light up`; sample 1 produced `lovely child` and `forever`. These check the sample
keywords, not Jarvis recognition. STT WAV input also requires 16 kHz mono 16-bit PCM.

### Manual validation still needed

1. Observe silence and unrelated speech for false activations; repeat Jarvis requests.
2. Say only “Jarvis” and verify no-speech cancellation. Compare immediate short
   commands with commands spoken after the activation event.
3. Try brief and long pauses, then a shorter maximum using `--max-duration 4
   --no-speech-timeout 2` in the app or capture diagnostic.
4. Remain silent during playback and confirm room echo does not reactivate Jarvis;
   then issue another request.
5. Review Ctrl+C and backend/device failure behavior, run longer sessions, and
   validate operation with internet unavailable while preserving local Ollama access.
6. Audit network activity and content persistence separately; successful interaction
   and a passing configuration diagnostic do not complete this audit.

## Verification

Latest automated verification on 2026-09-10: **121 tests passed**. Tests cover
contracts, conversion, capture transitions, failure handling, playback cleanup,
injected full-pipeline interactions, and configuration propagation/validation.
They do not establish hardware compatibility or complete offline operation.

```bash
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m unittest discover -s tests -p 'test_audio_models.py' -v
```

Previously recorded live validation: microphone capture; Jarvis activation with
satisfactory sensitivity; capture and English transcription (2026-09-09);
audible spoken confirmation and integrated voice responses (2026-09-10).
Real app startup reached waiting and exited after a two-second session.
Detailed voice-quality, echo, false-activation, and long-session results remain
unreported. Documentation/configuration checks did not repeat hardware validation.

Recorded single-run measurements on the development machine, not latency guarantees:

| Stage | Observation |
| --- | --- |
| Whisper | 0.152 s load; 0.251 s inference for approximately 6.6 s of sample audio |
| Ollama | 0.863 s for a response of 188 characters |
| Piper | 0.265 s load; 0.104 s synthesis for 2.958 s of audio |

Actions/tools, integrations, persistent memory, playback interruption, and a
visual interface are outside the current MVP scope and require separate work.
