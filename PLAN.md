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
- `jarvis.app` now connects capture, STT, local Ollama, TTS, and playback with injected dependencies. Startup with the real microphone passed; the user confirmed the integrated voice pipeline works on 2026-09-10.
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
- [x] 5.2 Selected `llama3.2:3b` at `http://127.0.0.1:11434` through `OllamaConfig`: 2,048 context tokens, 100 response tokens, 30-second socket timeout, and 600-second keep-alive. Backend-specific configuration remains outside the pipeline contracts.
- [x] 5.3 Added `OllamaLanguageModel` for single-turn English responses, direct loopback HTTP, and a fixed-prompt diagnostic with opt-in text display. All 89 tests passed; a real local call returned 188 characters in 0.863 seconds.
- [x] 5.4 Add bounded, resettable conversation history in memory. `OllamaLanguageModel` retains four user/assistant turns by default, configurable through `max_history_turns`; `reset()` and `close()` clear it. Failed turns are not retained. All 90 tests pass.
- [x] 5.5 Adapter translates socket timeouts, unavailable Ollama, missing models/endpoints, HTTP errors, and malformed/empty responses into content-free errors. Connections close on success and failure; recovery tests pass. No redirects, proxies, downloads, or remote fallback.
- [x] 5.6 Add a client-side local-only privacy audit. `jarvis.llm.privacy` verifies loopback endpoint/model naming and requires `OLLAMA_NO_CLOUD=1`; the adapter never logs or persists prompts/responses. Server-side behavior remains an external configuration responsibility. All 93 tests pass.

Completion criterion: a transcribed request receives a response from a model running locally through Ollama; a backend failure leaves the assistant usable and does not send content elsewhere.

## Module 6 — Text-to-speech (TTS) and playback

- [x] 6.1 Define synthesis and playback contracts. Added in-memory `SynthesizedAudio`, `Synthesizer`, and `AudioPlayer` contracts with format validation, lifecycle cleanup, and content-free backend errors. All 97 tests pass; no TTS backend selected yet.
- [x] 6.2 Selected Piper/VITS through sherpa-onnx 1.13.7 on CPU with `en_US-lessac-medium` (English, one speaker, 22,050 Hz). Reuses the installed runtime; native TTS configuration classes are available. Added the `tts` dependency extra and documented setup, planned model location, and initial parameters. Model download, inference/latency, and listening validation remain in 6.3.
- [x] 6.3 Implemented `SherpaPiperSynthesizer`, `SoundDeviceAudioPlayer`, and `python -m jarvis.tts.diagnostics --play`. On 2026-09-10 the native voice generated 2.958 seconds of in-memory PCM in 0.104 seconds (load 0.265 seconds), and the default Mac output stream completed playback. All 105 tests passed. User confirmation of audibility and voice quality remains pending.
- [x] 6.4 Added `speak_response` to stop the microphone, discard its queue, reset detection, synthesize/play, and restart with clean state. Capture diagnostic `--speak-confirmation` exercises the boundary with a fixed phrase containing Jarvis. Expected backend failures restore listening; interruption or cleanup failure prevents restart. All 109 tests pass. The user confirmed hearing the spoken confirmation on 2026-09-10. Detailed live self-activation/room echo observations remain unreported.
- [x] 6.5 Verified output failure/shutdown handling. Output close failures retain the stream for cleanup retry and block new playback. Response cleanup attempts both output release and detector reset, preserves the original failure/Ctrl+C, and prevents input restart if cleanup fails. Failed microphone restart triggers input cleanup. All 113 tests pass, including injected close/reset/restart failures. Real hardware disconnect behavior remains untested.

Completion criterion: the user hears the response and the assistant automatically returns to wake-word detection.

## Module 7 — MVP integration

- [x] 7.1 Connected modules in `jarvis.app` with explicit dependencies. The runner stops input for the complete response cycle, skips empty recognition, recovers expected backend errors, and clears content/history on shutdown. All 118 tests pass. Real startup, microphone opening, and timed shutdown passed; the user confirmed the integrated voice pipeline works on 2026-09-10. Extended stability and offline/privacy checks remain separate work.
- [x] 7.2 Added explicit waiting → capturing → transcribing → responding → synthesizing → speaking → waiting states with content-free reporting.
- [x] 7.3 Centralize device, model, endpoint, and limit configuration. Added `AppConfig` and CLI overrides for devices, all model paths, wake-word/VAD settings, capture limits, and Ollama limits/history. Existing defaults and local-only endpoint restrictions are preserved. Invalid settings fail before backend startup. All 121 tests pass, including configuration propagation; hardware was not revalidated for this step.
- [ ] 7.4 Support Ctrl+C shutdown and recovery from module errors.
- [ ] 7.5 Log stage and timing metadata without recording audio or conversation content by default.
- [ ] 7.6 Validate repeated interactions and document installation and execution in English.
- [ ] 7.7 Validate the complete pipeline without internet access after installation, and check that normal use does not persist conversation content or contact external services.

Completion criterion: “Jarvis, [question]” produces a spoken response and returns to waiting without restarting, while meeting the privacy requirements above.

## After the MVP

Actions and tools, integrations, persistent memory, interruption during playback, and a visual interface require separately scoped work. Review their data access and retention against the privacy requirement before implementation.

## Resume here

**Next micro step: 7.4 — review shutdown and module-error recovery.** The user confirmed the integrated voice pipeline works on 2026-09-10. Configuration consolidation is complete; all 121 tests pass. Existing shutdown/recovery behavior is implemented and covered in part; review remaining gaps before marking 7.4 complete. Extended stability validation and the final offline/privacy checks remain pending. Recognition improvements follow MVP consolidation.

Resume verification on 2026-09-09: all 78 tests passed in `.venv`. The local STT diagnostic processed bundled sample 0 (6.625 seconds) with a nonempty result, 0.150-second model load, and 0.238-second inference. These are single-run measurements. At the time of this automated verification, live voice/accent validation was pending (subsequently accepted by the user): run `.venv/bin/python -m jarvis.capture.diagnostics --duration 90 --show-text`, try several English requests, then test activation without a request and silence. Transcript display is opt-in and audio is not saved by the diagnostic. The user subsequently confirmed it works, with recognition quality improvements deferred until after pipeline integration.

Latest verification: all 30 tests passed in `.venv`. Offline sample 0 detected `light up`; sample 1 detected `lovely child` and `forever`. The Jarvis keyword configuration loaded and produced no activation on sample 0. Subsequently, the user confirmed successful live microphone detection with satisfactory sensitivity. Accent handling remains a known limitation accepted for the current stage; no sensitivity changes are required based on this feedback.
