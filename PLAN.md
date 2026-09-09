# Jarvis implementation plan

Reconstructed on 2026-09-09 from the repository and user-confirmed decisions; this is not a verbatim recovery of the previous conversation. Later modules are a proposed roadmap. STT starts with Whisper tiny.en through sherpa-onnx on CPU; TTS and the specific LLM model remain to be selected. Local VAD uses Silero through sherpa-onnx.

## Objective and confirmed decisions

Build a privacy-first voice assistant: microphone → wake word → request capture → transcription → local LLM → spoken response.

- Privacy is the primary system requirement.
- Use **sherpa-onnx** for local wake-word detection and **local Ollama** for LLM inference. The specific model is still undecided.
- Select local VAD, STT, and TTS backends so the voice pipeline can operate offline after dependencies and models are installed.
- Keep audio, transcripts, prompts, responses, and conversation history in memory by default. Logs should contain operational metadata, not conversation content.
- Do not introduce cloud inference, remote fallback, telemetry, or content persistence by default. Any future change to these boundaries requires an explicit user decision.
- Use English for project documentation, code, identifiers, comments, and application messages. Collaboration with the user can be in English or Portuguese. Voice interaction is English-only for now, confirmed by the user on 2026-09-09.
- Use Python with module contracts separated from backend implementations.

## Current state

- Audio contracts, device discovery, continuous capture, and diagnostics are implemented. Defaults are in-memory mono PCM, 16-bit samples, 16 kHz, and 100 ms chunks.
- The README records previous validation with a real microphone.
- Wake-word contracts exist; the default activation word is `jarvis`.
- The English model is present at `models/wakeword/sherpa-onnx-kws-zipformer-gigaspeech-3.3M-2024-01-01/`, including encoder, decoder, joiner, tokens, BPE, and samples. Inference has not yet been validated in this reconstruction.
- The supplied `keywords_raw.txt` contains example phrases but does not include Jarvis.
- The sherpa-onnx adapter and microphone/WAV diagnostics are implemented. Offline sample inference passed on macOS ARM64 / Python 3.9 with sherpa-onnx 1.13.7. The user confirmed correct live Jarvis detection and satisfactory sensitivity. Accent-related recognition limitations are accepted for the current stage.
- `jarvis.app` is currently an entry-point placeholder.
- During plan reconstruction, all 29 tests passed with `python3 -m unittest discover -s tests -q`. Neither microphone capture nor sherpa-onnx inference was repeated.

## Working method

Implement one small, verifiable step at a time. Record its outcome and the next step here. Test new behavior and meaningful failure cases; validate hardware separately. Demonstrate wake-word activation before proceeding to STT, LLM, or TTS.

## Module 1 — Audio input (implemented)

- [x] 1.1 Define audio configuration, device, PCM chunk, and input interface.
- [x] 1.2 List input devices and identify the default microphone.
- [x] 1.3 Capture chunks continuously and release the device on shutdown.
- [x] 1.4 Provide an audio-level diagnostic command.
- [x] 1.5 Record real microphone validation, as documented in the README.

Completion criterion: deliver audio chunks in memory and release the microphone on shutdown.

## Module 2 — sherpa-onnx wake word (next)

- [x] 2.1 Define configuration, detection event, and detector contracts.
- [x] 2.2 Download the English model.
- [ ] 2.3 Check official API documentation and compatibility with project Python versions and platforms. Configure the optional dependency and model paths, with clear missing-file errors.
- [x] 2.4 Run offline inference using a supplied sample and keyword to verify the model files work together.
- [x] 2.5 Prepare `Jarvis` using the required keyword format and tokenization. Keep project keyword configuration separate from downloaded examples.
- [x] 2.6 Implement `SherpaOnnxWakeWordDetector`: PCM conversion, incremental processing, detection events, reset, and resource cleanup.
- [x] 2.7 Align threshold and confidence contracts with values actually exposed by the backend; do not invent confidence probabilities.
- [x] 2.8 Test audio conversion and validation, processing across chunks, reset, and configuration errors. Separate model integration tests from tests without external dependencies.
- [x] 2.9 Add a microphone-to-detector diagnostic that prints activation events.
- [x] 2.10 Validate Jarvis with the user's voice and assess sensitivity. The user confirmed correct detection and satisfactory sensitivity on 2026-09-09; accent-related recognition limitations are accepted for now.
- [ ] 2.10a Follow-up: explicitly evaluate silence, unrelated speech, and repeated activations; add suppression if observations justify it. These checks have not been reported as completed.
- [x] 2.11 Document the implemented sherpa-onnx backend and its installation and diagnostic commands in README.

Completion criterion: saying Jarvis produces a local activation event, and the diagnostic shuts down cleanly. Record observed results and limitations.

## Module 3 — Request capture and end-of-speech detection

- [x] 3.1 Define waiting and capturing states and an audio-request contract. Added `CaptureState` and `AudioRequest` in `jarvis.capture`, with format/order validation and in-memory chunks. All 36 tests passed.
- [x] 3.2 Maintain a short in-memory buffer to avoid losing speech at the transition. `PreRollBuffer` retains up to 0.5 seconds by default, trims on PCM frame boundaries, and exposes snapshots and clear. All 43 tests passed; controller integration remains pending.
- [x] 3.3 Select and encapsulate a local voice activity detection (VAD) backend. Added Silero through sherpa-onnx on CPU, configuration and window-result contracts, PCM validation, reset, and cleanup. Downloaded the official model to `models/vad/`. All 51 tests passed; real model checks detected speech in sample 0, rejected silence, and returned to silence after a two-second tail. Live VAD validation remains pending.
- [x] 3.4 End capture on silence, no-speech timeout, or a configurable maximum duration. Added `CaptureController` connecting wake word, pre-roll, and VAD. Defaults: 3 seconds without speech, 15 seconds maximum after activation, and 0.5 seconds of additional silence hold after VAD debounce. Activation/pre-roll audio is retained but excluded from speech qualification. All 58 tests passed, including cancellation, short pauses, exact maximum trimming, reset, and repeated requests. Microphone integration and live validation remain in 3.5.
- [x] 3.5 Test transitions, pauses, and limits; validate Jarvis followed by a spoken request. Added `python -m jarvis.capture.diagnostics` with configurable limits, activation/completion/cancellation reporting, and cleanup on interruption or source failure. All 63 tests passed. User confirmed live Jarvis capture works on 2026-09-09. Detailed edge-case observations remain unreported; automated tests cover transitions, pauses, and limits.

Completion criterion: an activation produces a complete in-memory request or returns to waiting if no speech follows.

## Module 4 — Speech-to-text (STT)

- [x] 4.1 Define transcription input and text-result contracts. Reused `AudioRequest` as input; added `Transcriber`, `TranscriptionResult`, and `TranscriptionError` in `jarvis.stt`. Empty recognition is distinct from backend failure, text is excluded from result repr, and context-manager cleanup is defined. All 68 tests passed; no backend selected or installed.
- [x] 4.2 Select a local backend/model based on hardware, intended spoken languages, and latency. Selected and installed Whisper `tiny.en` through existing sherpa-onnx 1.13.7 on CPU for English-only interaction on Apple M4 / 16 GB. Verified the installed `OfflineRecognizer.from_whisper` API, loaded the int8 model, and transcribed bundled sample 0 successfully. This is an initial baseline, not a measured conversational performance claim; benchmark latency and recognition in 4.3–4.5. See README for alternatives and configuration.
- [x] 4.3 Transcribe a captured request locally. Added `SherpaWhisperTranscriber` using the installed int8 Whisper tiny.en model, in-memory PCM conversion, English transcription, lifecycle cleanup, and content-free backend errors. All 73 tests pass. On Apple M4 / 16 GB, model load took 0.152 s and bundled 6.6 s sample inference took 0.251 s (single warm run; not a conversational benchmark).
- [x] 4.4 Handle silence, empty results, and backend failures. Exact-silence PCM requests return an empty English result without invoking inference; empty recognizer text remains a successful empty result; malformed results and runtime failures raise content-free `TranscriptionError`. All 74 tests pass.
- [x] 4.5 Validate real requests in the selected languages. Added `python -m jarvis.stt.diagnostics` for WAVs and connected `capture.diagnostics` to transcribe completed microphone requests with opt-in text display. Official English sample 0 transcribed successfully (6.625 s audio, 0.315 s inference in this run). User confirmed live transcription works on 2026-09-09. Listening and transcription quality remain limited but are accepted for now; prioritize completing the end-to-end pipeline before improving individual stages.

Completion criterion: a spoken request after Jarvis produces useful text without sending audio to an external service. The English wake-word model does not determine the STT language.

## Module 5 — Local Ollama LLM

- [x] 5.1 Define text-request and response contracts. Added nonempty `TextRequest` and `TextResponse` values with content excluded from repr, plus `LanguageModel` lifecycle/history-reset contracts and content-free `LanguageModelError`. Empty STT results must be skipped; empty backend answers are failures. All 83 tests passed. No LLM backend or model is installed by this step.
- [ ] 5.2 Select a locally runnable model based on available hardware and intended languages; configure the local Ollama endpoint and model name.
- [ ] 5.3 Implement an Ollama adapter for one interaction with concise, speakable responses.
- [ ] 5.4 Add bounded, resettable conversation history in memory.
- [ ] 5.5 Handle timeouts, unavailable Ollama, missing models, and empty responses without remote fallback.
- [ ] 5.6 Verify local-only inference configuration and ensure prompts/responses are excluded from application logs and persisted history by default.

Completion criterion: a transcribed request receives a response from a model running locally through Ollama; a backend failure leaves the assistant usable and does not send content elsewhere.

## Module 6 — Text-to-speech (TTS) and playback

- [ ] 6.1 Define synthesis and playback contracts.
- [ ] 6.2 Select a local backend and voice for the intended languages.
- [ ] 6.3 Synthesize and play a short response locally.
- [ ] 6.4 Prevent self-activation from the assistant's voice; initially suspend detection during playback.
- [ ] 6.5 Handle output failures and release resources on shutdown.

Completion criterion: the user hears the response and the assistant automatically returns to wake-word detection.

## Module 7 — MVP integration

- [ ] 7.1 Connect modules in `jarvis.app` with explicit dependencies.
- [ ] 7.2 Consolidate states: waiting → capturing → transcribing → responding → speaking → waiting.
- [ ] 7.3 Centralize device, model, endpoint, and limit configuration.
- [ ] 7.4 Support Ctrl+C shutdown and recovery from module errors.
- [ ] 7.5 Log stage and timing metadata without recording audio or conversation content by default.
- [ ] 7.6 Validate repeated interactions and document installation and execution in English.
- [ ] 7.7 Validate the complete pipeline without internet access after installation, and check that normal use does not persist conversation content or contact external services.

Completion criterion: “Jarvis, [question]” produces a spoken response and returns to waiting without restarting, while meeting the privacy requirements above.

## After the MVP

Actions and tools, integrations, persistent memory, interruption during playback, and a visual interface require separately scoped work. Review their data access and retention against the privacy requirement before implementation.

## Resume here

**Next micro step: 5.2 — select a locally runnable Ollama model and configure the local endpoint/model name.** User accepted current capture and STT quality on 2026-09-09 to prioritize the complete pipeline. Step 5.1 contracts are implemented; all 83 tests pass. Keep recognition improvements and step 2.10a as follow-ups.

Resume verification on 2026-09-09: all 78 tests passed in `.venv`. The local STT diagnostic processed bundled sample 0 (6.625 seconds) with a nonempty result, 0.150-second model load, and 0.238-second inference. These are single-run measurements. At the time of this automated verification, live voice/accent validation was pending (subsequently accepted by the user): run `.venv/bin/python -m jarvis.capture.diagnostics --duration 90 --show-text`, try several English requests, then test activation without a request and silence. Transcript display is opt-in and audio is not saved by the diagnostic. The user subsequently confirmed it works, with recognition quality improvements deferred until after pipeline integration.

Latest verification: all 30 tests passed in `.venv`. Offline sample 0 detected `light up`; sample 1 detected `lovely child` and `forever`. The Jarvis keyword configuration loaded and produced no activation on sample 0. Subsequently, the user confirmed successful live microphone detection with satisfactory sensitivity. Accent handling remains a known limitation accepted for the current stage; no sensitivity changes are required based on this feedback.
