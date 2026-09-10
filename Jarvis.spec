"""PyInstaller spec for the macOS directory-based Jarvis.app bundle."""

from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules


ROOT = Path(SPECPATH).resolve()
WAKE = ROOT / "models/wakeword/sherpa-onnx-kws-zipformer-gigaspeech-3.3M-2024-01-01"
STT = ROOT / "models/stt/sherpa-onnx-whisper-tiny.en"
TTS = ROOT / "models/tts/vits-piper-en_US-lessac-medium"


def data_file(path: Path, destination: str):
    return (str(path), destination)


datas = [
    data_file(WAKE / name, "models/wakeword/sherpa-onnx-kws-zipformer-gigaspeech-3.3M-2024-01-01")
    for name in (
        "encoder-epoch-12-avg-2-chunk-16-left-64.int8.onnx",
        "decoder-epoch-12-avg-2-chunk-16-left-64.onnx",
        "joiner-epoch-12-avg-2-chunk-16-left-64.int8.onnx",
        "tokens.txt",
    )
]
datas += [
    data_file(STT / name, "models/stt/sherpa-onnx-whisper-tiny.en")
    for name in ("tiny.en-encoder.int8.onnx", "tiny.en-decoder.int8.onnx", "tiny.en-tokens.txt")
]
datas += [data_file(ROOT / "models/vad/silero_vad.onnx", "models/vad")]
datas += [data_file(TTS / "en_US-lessac-medium.onnx", "models/tts/vits-piper-en_US-lessac-medium")]
datas += [data_file(TTS / "tokens.txt", "models/tts/vits-piper-en_US-lessac-medium")]
for path in (TTS / "espeak-ng-data").rglob("*"):
    if path.is_file():
        datas.append(data_file(path, str(Path("models/tts/vits-piper-en_US-lessac-medium/espeak-ng-data") / path.relative_to(TTS / "espeak-ng-data").parent)))
datas.append(data_file(ROOT / "jarvis/wakeword/keywords.txt", "jarvis/wakeword"))


a = Analysis(
    [str(ROOT / "jarvis/ui/main.py")],
    pathex=[str(ROOT)],
    binaries=[], datas=datas,
    hiddenimports=collect_submodules("sherpa_onnx"),
    excludes=["tkinter"],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="Jarvis", debug=False,
          bootloader_ignore_signals=False, strip=False, upx=False, console=False)
coll = COLLECT(exe, a.binaries, a.datas, a.zipfiles,
               name="Jarvis", strip=False, upx=False)
app = BUNDLE(
    coll,
    name="Jarvis.app",
    bundle_identifier="com.jarvis.local",
    info_plist={
        "CFBundleDisplayName": "Jarvis",
        "NSMicrophoneUsageDescription": (
            "Jarvis needs microphone access to detect the wake word and hear requests."
        ),
    },
)
