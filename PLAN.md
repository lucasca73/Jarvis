# Jarvis implementation plan

Updated on 2026-09-10 against the implemented pipeline and configuration. Originally
reconstructed on 2026-09-09 from the repository and user-confirmed decisions.
Checked items record completed implementation milestones; test counts within
those items are historical results at that step, not the current suite size.
The current suite has 121 passing tests. Hardware observations below are prior
validation, not new validation performed during this documentation review.

## Objective and confirmed decisions

Build a privacy-first voice assistant: microphone → wake word → request capture → transcription → local LLM → spoken response.

- Privacy is the primary system requirement.
- Use **sherpa-onnx** for local wake-word detection and **local Ollama** for LLM inference. The selected model is `llama3.2:3b`.
- Use Silero VAD, int8 Whisper tiny.en STT, and Piper/VITS Lessac TTS through sherpa-onnx on CPU. Complete offline operation after setup remains to be audited.
- Keep audio, transcripts, prompts, responses, and conversation history in memory by default. Logs should contain operational metadata, not conversation content.
- Do not introduce cloud inference, remote fallback, telemetry, or content persistence by default. Any future change to these boundaries requires an explicit user decision.
- Use English for project documentation, code, identifiers, comments, and application messages. Collaboration with the user can be in English or Portuguese. Voice interaction is English-only for now, confirmed by the user on 2026-09-09.
- Use Python with module contracts separated from backend implementations.

## Current state

- `jarvis.app` connects microphone capture, Jarvis activation, Silero VAD, Whisper STT, local Ollama, Piper TTS, and playback through injected dependencies.
- Input is 16 kHz mono 16-bit PCM in 100 ms chunks. Audio and conversation content are retained in memory by default; history is bounded and resettable.
- Local model bundles are installed in the development workspace. Packaged `jarvis/wakeword/keywords.txt` supplies Jarvis separately from downloaded examples.
- Offline sample inference and live wake-word/capture/STT validation passed. The user confirmed audible confirmation and the integrated pipeline on 2026-09-10. Recognition quality and accent limitations are accepted until after MVP consolidation.
- Step 7.3 is complete: `AppConfig` and CLI overrides centralize devices, paths, thresholds, capture limits, and Ollama settings. All 121 tests pass.
- Ctrl+C cleanup, expected response-error recovery, states, and total request timing are implemented. Remaining review, stage timings, extended live stability, and offline/privacy validation are tracked in 7.4–7.7.
- Client loopback/model checks and an environment diagnostic are implemented. The diagnostic does not inspect the Ollama server process or enforce server behavior; server configuration and complete privacy validation remain unverified.

## Working method

Implement one small, verifiable step at a time. Record its outcome and the next step here. Test new behavior and meaningful failure cases; validate hardware separately. The initial wake-word demonstration prerequisite was met before subsequent pipeline integration.

Priority change on 2026-09-10: the user deferred the validation work and requested
planning for a minimal status interface and executable. Steps 2.3a, 2.10a, and
7.4–7.7 remain open and are temporarily outside the active sequence, including
the unfinished stage-timing work. Narrow checks needed to implement the new
interface/package remain part of that work. See [UI_PLAN.md](UI_PLAN.md) for the
proposal; the GUI and executable have not been implemented.

## Module 1 — Audio input (implemented)

- [x] 1.1 Define audio configuration, device, PCM chunk, and input interface.
- [x] 1.2 List input devices and identify the default microphone.
- [x] 1.3 Capture chunks continuously and release the device on shutdown.
- [x] 1.4 Provide an audio-level diagnostic command.
- [x] 1.5 Record real microphone validation, as documented in the README.

Completion criterion: deliver audio chunks in memory and release the microphone on shutdown.

## Module 2 — sherpa-onnx wake word (implemented; validation follow-ups open)

- [x] 2.1 Define configuration, detection event, and detector contracts.
- [x] 2.2 Download the English model.
- [x] 2.3 Configure the optional sherpa-onnx dependency, explicit model paths, and missing-file errors. The adapter and native inference were validated on macOS ARM64 / Python 3.9 with sherpa-onnx 1.13.7; the original implementation referenced official Python examples/API.
- [ ] 2.3a Validate additional supported Python versions and platforms. The package declares Python >=3.9; broader compatibility has not been exercised.
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
- [x] 3.2 Maintain a short in-memory buffer to avoid losing speech at the transition. `PreRollBuffer` retains up to 0.5 seconds by default, trims on PCM frame boundaries, and exposes snapshots and clear. All 43 tests passed at this step; controller integration was completed in 3.4.
- [x] 3.3 Select and encapsulate a local voice activity detection (VAD) backend. Added Silero through sherpa-onnx on CPU, configuration and window-result contracts, PCM validation, reset, and cleanup. Downloaded the official model to `models/vad/`. All 51 tests passed; real model checks detected speech in sample 0, rejected silence, and returned to silence after a two-second tail. Live capture using this VAD was confirmed in 3.5; detailed isolated VAD edge-case observations remain unreported.
- [x] 3.4 End capture on silence, no-speech timeout, or a configurable maximum duration. Added `CaptureController` connecting wake word, pre-roll, and VAD. Defaults: 3 seconds without speech, 15 seconds maximum after activation, and 0.5 seconds of additional silence hold after VAD debounce. Activation/pre-roll audio is retained but excluded from speech qualification. All 58 tests passed, including cancellation, short pauses, exact maximum trimming, reset, and repeated requests. Microphone integration and live confirmation were completed in 3.5.
- [x] 3.5 Test transitions, pauses, and limits; validate Jarvis followed by a spoken request. Added `python -m jarvis.capture.diagnostics` with configurable limits, activation/completion/cancellation reporting, and cleanup on interruption or source failure. All 63 tests passed. User confirmed live Jarvis capture works on 2026-09-09. Detailed edge-case observations remain unreported; automated tests cover transitions, pauses, and limits.

Completion criterion: an activation produces a complete in-memory request or returns to waiting if no speech follows.

## Module 4 — Speech-to-text (STT)

- [x] 4.1 Define transcription input and text-result contracts. Reused `AudioRequest` as input; added `Transcriber`, `TranscriptionResult`, and `TranscriptionError` in `jarvis.stt`. Empty recognition is distinct from backend failure, text is excluded from result repr, and context-manager cleanup is defined. All 68 tests passed at the contract milestone; backend selection followed in 4.2.
- [x] 4.2 Select a local backend/model based on hardware, intended spoken languages, and latency. Selected and installed Whisper `tiny.en` through existing sherpa-onnx 1.13.7 on CPU for English-only interaction on Apple M4 / 16 GB. Verified the installed `OfflineRecognizer.from_whisper` API, loaded the int8 model, and transcribed bundled sample 0 successfully. This is an initial baseline, not a measured conversational performance claim; initial measurements and live confirmation followed in 4.3–4.5. See README for current configuration; broader recognition/latency benchmarking remains future work.
- [x] 4.3 Transcribe a captured request locally. Added `SherpaWhisperTranscriber` using the installed int8 Whisper tiny.en model, in-memory PCM conversion, English transcription, lifecycle cleanup, and content-free backend errors. All 73 tests pass. On Apple M4 / 16 GB, model load took 0.152 s and bundled 6.6 s sample inference took 0.251 s (single warm run; not a conversational benchmark).
- [x] 4.4 Handle silence, empty results, and backend failures. Exact-silence PCM requests return an empty English result without invoking inference; empty recognizer text remains a successful empty result; malformed results and runtime failures raise content-free `TranscriptionError`. All 74 tests pass.
- [x] 4.5 Validate real requests in the selected languages. Added `python -m jarvis.stt.diagnostics` for WAVs and connected `capture.diagnostics` to transcribe completed microphone requests with opt-in text display. Official English sample 0 transcribed successfully (6.625 s audio, 0.315 s inference in this run). User confirmed live transcription works on 2026-09-09. Listening and transcription quality remain limited but are accepted for now; prioritize completing the end-to-end pipeline before improving individual stages.

Completion criterion: a spoken request after Jarvis produces useful text without sending audio to an external service. The English wake-word model does not determine the STT language.

## Module 5 — Local Ollama LLM

- [x] 5.1 Define text-request and response contracts. Added nonempty `TextRequest` and `TextResponse` values with content excluded from repr, plus `LanguageModel` lifecycle/history-reset contracts and content-free `LanguageModelError`. Empty STT results must be skipped; empty backend answers are failures. All 83 tests passed. Backend implementation followed in 5.2–5.3.
- [x] 5.2 Selected `llama3.2:3b` at `http://127.0.0.1:11434` through `OllamaConfig`: 2,048 context tokens, 100 response tokens, 30-second socket timeout, and 600-second keep-alive. Backend-specific configuration remains outside the pipeline contracts.
- [x] 5.3 Added `OllamaLanguageModel` for single-turn English responses, direct loopback HTTP, and a fixed-prompt diagnostic with opt-in text display. All 89 tests passed; a real local call returned 188 characters in 0.863 seconds.
- [x] 5.4 Add bounded, resettable conversation history in memory. `OllamaLanguageModel` retains four user/assistant turns by default, configurable through `max_history_turns`; `reset()` and `close()` clear it. Failed turns are not retained. All 90 tests pass.
- [x] 5.5 Adapter translates socket timeouts, unavailable Ollama, missing models/endpoints, HTTP errors, and malformed/empty responses into content-free errors. Connections close on success and failure; recovery tests pass. No redirects, proxies, downloads, or remote fallback.
- [x] 5.6 Add a client-side local-only privacy audit. `jarvis.llm.privacy` checks validated client configuration and whether its own process environment contains `OLLAMA_NO_CLOUD=1`; the standalone diagnostic fails without it, but the app does not invoke this audit or require that environment variable. The audit does not inspect the running server; the adapter never logs or persists prompts/responses. Server-side behavior remains an external configuration responsibility. All 93 tests pass.

Completion criterion: a transcribed request receives a response from a model running locally through Ollama; a backend failure leaves the assistant usable and does not send content elsewhere.

## Module 6 — Text-to-speech (TTS) and playback

- [x] 6.1 Define synthesis and playback contracts. Added in-memory `SynthesizedAudio`, `Synthesizer`, and `AudioPlayer` contracts with format validation, lifecycle cleanup, and content-free backend errors. All 97 tests passed at the contract milestone; backend selection followed in 6.2.
- [x] 6.2 Selected Piper/VITS through sherpa-onnx 1.13.7 on CPU with `en_US-lessac-medium` (English, one speaker, 22,050 Hz). Reuses the installed runtime; native TTS configuration classes are available. Added the `tts` dependency extra and documented setup, model location, and initial parameters. Model loading and inference followed in 6.3; audible output was confirmed in 6.4.
- [x] 6.3 Implemented `SherpaPiperSynthesizer`, `SoundDeviceAudioPlayer`, and `python -m jarvis.tts.diagnostics --play`. On 2026-09-10 the native voice generated 2.958 seconds of in-memory PCM in 0.104 seconds (load 0.265 seconds), and the default Mac output stream completed playback. All 105 tests passed. The user subsequently confirmed audible output in 6.4 and integrated responses in 7.1; detailed subjective voice-quality assessment remains unreported.
- [x] 6.4 Added `speak_response` to stop the microphone, discard its queue, reset detection, synthesize/play, and restart with clean state. Capture diagnostic `--speak-confirmation` exercises the boundary with a fixed phrase containing Jarvis. Expected backend failures restore listening; interruption or cleanup failure prevents restart. All 109 tests pass. The user confirmed hearing the spoken confirmation on 2026-09-10. Detailed live self-activation/room echo observations remain unreported.
- [x] 6.5 Verified output failure/shutdown handling. Output close failures retain the stream for cleanup retry and block new playback. Response cleanup attempts both output release and detector reset, preserves the original failure/Ctrl+C, and prevents input restart if cleanup fails. Failed microphone restart triggers input cleanup. All 113 tests pass, including injected close/reset/restart failures. Real hardware disconnect behavior remains untested.

Completion criterion: the user hears the response and the assistant automatically returns to wake-word detection.

## Module 7 — MVP integration

- [x] 7.1 Connected modules in `jarvis.app` with explicit dependencies. The runner stops input for the complete response cycle, skips empty recognition, recovers expected backend errors, and clears content/history on shutdown. All 118 tests pass. Real startup, microphone opening, and timed shutdown passed; the user confirmed the integrated voice pipeline works on 2026-09-10. Extended stability and offline/privacy checks remain separate work.
- [x] 7.2 Added explicit waiting → capturing → transcribing → responding → synthesizing → speaking → waiting states with content-free reporting.
- [x] 7.3 Centralize device, model, endpoint, and limit configuration. Added `AppConfig` and CLI overrides for devices, all model paths, wake-word/VAD settings, capture limits, and Ollama limits/history. Existing defaults and local-only endpoint restrictions are preserved. Invalid settings fail before backend startup. All 121 tests pass, including configuration propagation; hardware was not revalidated for this step.
- [ ] 7.4 Complete the shutdown and module-error recovery review. Ctrl+C cleanup and expected STT/LLM/TTS/output-error recovery already exist with automated coverage; identify remaining gaps, including device failure behavior, before closing this step.
- [ ] 7.5 Complete stage timing metadata. States, failed-stage identifiers, and total request duration are already reported without conversation content; individual stage timings remain to be added/reviewed.
- [ ] 7.6 Complete extended repeated-interaction validation. Injected repeated interactions pass and the user confirmed the integrated pipeline. README installation, execution, configuration, diagnostics, and limitations were consolidated in English on 2026-09-10; a clean setup replay and extended live stability results remain pending.
- [ ] 7.7 Validate the complete pipeline without internet access after installation, and check that normal use does not persist conversation content or contact external services.

Completion criterion: “Jarvis, [question]” produces a spoken response and returns to waiting without restarting, while meeting the privacy requirements above.

## After the MVP

Actions and tools, integrations, persistent memory, and interruption during playback require separately scoped work. Review their data access and retention against the privacy requirement before implementation. A minimal status interface and desktop packaging are now the active planning scope in [UI_PLAN.md](UI_PLAN.md).

## Resume here

**Next micro step: APP.1 — make packaged model resources independent of the working directory.** UI.1–UI.3 now provide the status model, optional Qt window, typed worker service, and `python -m jarvis.ui.main` entry point. PySide6 6.10.3 and PyInstaller 6.22.2 are installed in `.venv` on macOS ARM64 / Python 3.9. The user manually validated the interface states during operation, including listening and speaking; no packaged executable exists yet. Configuration consolidation is complete; the latest automated verification has 129 passing tests. Broader validation in 2.3a, 2.10a, and 7.4–7.7 is deferred by user request and remains incomplete. Recognition improvements remain future work.


## Historical smoke observations

- Wake-word samples: sample 0 detected `light up`; sample 1 detected `lovely child` and `forever`. Jarvis configuration loaded and did not activate on sample 0. Live Jarvis sensitivity was subsequently accepted by the user.
- STT resume check on 2026-09-09: 6.625 s sample, nonempty result, 0.150 s load, 0.238 s inference. This is a single-run measurement; other step-specific measurements above were separate runs.
- Documentation review on 2026-09-10: README and this plan were aligned with current code, CLI options, and recorded validation. No new hardware, model download, or full offline audit was performed.
