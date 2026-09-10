# Minimal interface and desktop application plan

Planning draft, 2026-09-10. The user requested a minimal listening/speaking
indicator and an executable, with the existing validation work deferred.
No GUI or packaged executable is implemented yet.

## Scope and proposed experience

Initial target: macOS Apple Silicon, matching the development machine. This is
a planning assumption pending platform preference; Windows builds can follow.

A small, movable window, approximately 240 × 160 logical pixels, shows the Jarvis
name, a circular indicator, and one short English status label. Use a neutral
background, readable text, and restrained animation. State must remain clear
without relying on color or motion. The window does not steal focus on activation.

| Pipeline state | Visible label | Indicator |
| --- | --- | --- |
| Backend initialization | `Starting` | Gentle activity |
| Waiting for the wake word | `Ready` | Steady, subdued circle |
| Capturing the spoken request | `Listening` | Slowly expanding ring |
| Transcribing, responding, synthesizing | `Thinking` | Slow rotating arc |
| Audio playback | `Speaking` | Soft rhythmic pulse |
| Quit requested, cleanup in progress | `Stopping` | Steady subdued circle |
| Startup or terminal failure | `Unavailable` | Static symbol and short actionable message |

`Ready` means the microphone is monitoring for Jarvis; `Listening` means a
request is being captured. `Thinking` makes the microphone-off interval visible.
Animations represent state, not measured audio levels. No transcripts, chat,
history, waveform, dashboard, or settings screen are needed for this version.

Proposed controls: a menu-bar icon with current status, Show/Hide, and Quit.
Closing the small window hides it while the menu-bar indicator stays visible;
Quit stops the assistant. Show the window on launch. Do not enable automatic
login startup in the first version. A second launch should reveal the existing
instance rather than opening another microphone session.

## Technical approach

Propose PySide6 with Qt Widgets for the small window and menu-bar integration,
and PyInstaller for packaging. Qt documents macOS support for its
[system tray/status icon](https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QSystemTrayIcon.html),
and PyInstaller supports [windowed macOS app bundles](https://pyinstaller.org/en/stable/usage.html).
This keeps the interface in Python alongside the existing pipeline. The added
Qt runtime increases package size; measure the resulting artifact during packaging.

Before selecting versions, check a compatible Python/PySide6/PyInstaller/native
dependency combination. The current workspace uses Python 3.9; do not assume
current Qt wheels support it. Use an isolated desktop build environment and
record any required Python-version change explicitly. Consult the
[Qt prerequisites](https://doc.qt.io/qtforpython-6/gettingstarted.html).

Reuse `AppConfig`, `AssistantState`, and the injected pipeline. Extract backend
construction/lifetime management from CLI `main()` into a reusable application
service. Keep the CLI as a supported entry point.

Run the Qt event loop on the main thread and model loading/audio processing on
one worker thread that owns all backend resources. Publish typed state and
content-free error events through queued signals; do not parse console strings
or pass audio/transcripts/responses into the view. Preserve CLI reporting through
its own event adapter. Connect listeners before starting the worker.

Add cooperative stop requests because a graphical app cannot depend on Ctrl+C.
Check for stop while waiting and between response stages; discard unfinished
capture, skip subsequent stages, prevent microphone restart, and release resources
on their owning thread. During a blocking inference or playback call, display
`Stopping` until the call returns and cleanup completes. The current socket
timeout is not a total response deadline; immediate quit during every native
call is not promised by this first design. Do not forcibly terminate a thread.

Keep startup/fatal failures visible with a useful message such as “Start Ollama
and reopen Jarvis” or “Microphone access is required.” Recoverable request failures
may show a brief content-free message before returning to Ready. Never display
raw exception text or claim Ready while capture is stopped.

## Executable and model delivery

First deliverable: `dist/Jarvis.app`, launched through Finder without a terminal,
repository checkout, virtual environment, or separately installed Python.
Build on macOS ARM64. Start with a directory-based app bundle containing Python,
Qt, sherpa-onnx/ONNX dependencies, NumPy, audio libraries, and packaged keywords.
PyInstaller's [spec-file mechanism](https://pyinstaller.org/en/stable/spec-files.html)
supports explicit data files and bundle metadata.

Include only runtime wake-word, VAD, Whisper, and Piper assets from the installed
bundles, including complete phonemizer data and required license notices.
Exclude download archives and sample WAVs. Check redistribution terms before
sharing model/runtime bundles outside personal use. Resolve these resources
relative to the bundle, independently of the process working directory.
Keep source/CLI path overrides usable. Normal startup must not download assets.

Ollama and `llama3.2:3b` remain separately installed and configured for local-only
operation. The executable is therefore self-contained for Python and audio
inference, but still depends on the local Ollama service/model. Add a short,
bounded local startup availability check with an actionable failure state; it
does not constitute the deferred privacy audit or start/download Ollama silently.

Configure a stable bundle identifier, app icon, microphone usage description,
and microphone permission handling. Include any signing entitlements required
by the selected distribution method. First produce a personal local build;
Developer ID signing, notarization, and a distributable DMG are a later delivery
step if sharing the application becomes a requirement.

## Implementation order

- [x] UI.1 Confirm the visual proposal and build-runtime compatibility; create
  a small simulated-state prototype to assess the indicator and labels. Added
  the toolkit-independent `jarvis.ui.status` model and an optional Qt window
  skeleton. PySide6 6.10.3 and PyInstaller 6.22.2 are installed in the current
  `.venv` on macOS ARM64 / Python 3.9. The Qt window has not been launched.
- [ ] UI.2 Expose typed state/error events and cooperative shutdown through a
  shared application service; retain CLI behavior. The current runner now
  accepts `on_state` and `stop_requested` callbacks, checked between stages;
  extracting the reusable worker/service and typed error events remains.
- [ ] UI.3 Connect the window and menu-bar indicator to the worker, including
  initialization, failures, quit behavior, and a single running instance.
- [ ] APP.1 Resolve packaged resources independently of the working directory
  and define exactly which model/runtime assets the bundle contains.
- [ ] APP.2 Create a reproducible PyInstaller specification and build command;
  produce a local `Jarvis.app` with app metadata and microphone permission support.
- [ ] APP.3 Check the artifact's basic usability: open through Finder outside
  the repository, observe real state transitions, hide/show, and quit with cleanup.
  Record prerequisites, build environment, artifact size, and limitations.

These narrow implementation checks accompany the new feature. The broader
existing validation campaign is deferred, not marked complete: platform matrix,
false activations, shutdown/recovery audit, stage timings, extended stability,
clean setup replay, and complete offline/privacy audit remain in PLAN.md.

Completion criterion: open Jarvis.app, see the actual listening/processing/speaking
state without conversation content, and quit through the interface with resource
cleanup. No terminal is required for normal use once local prerequisites are set up.
