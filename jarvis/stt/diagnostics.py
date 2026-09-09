"""Benchmark local English STT on a 16 kHz mono PCM WAV file."""

from __future__ import annotations

import argparse
import time
import wave

from jarvis.audio import AudioChunk
from jarvis.capture import AudioRequest
from jarvis.stt import SherpaWhisperTranscriber
from jarvis.stt.whisper import DEFAULT_MODEL_DIR
from jarvis.wakeword.models import WakeWordDetection


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wav", help="16 kHz mono 16-bit PCM WAV")
    parser.add_argument("--model-dir", default=str(DEFAULT_MODEL_DIR))
    parser.add_argument("--threads", type=int, default=2)
    parser.add_argument("--show-text", action="store_true", help="print the transcript")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    try:
        with wave.open(args.wav, "rb") as source:
            if (source.getframerate(), source.getnchannels(), source.getsampwidth()) != (16000, 1, 2):
                raise ValueError("WAV input must be 16 kHz mono 16-bit PCM")
            data = source.readframes(source.getnframes())
            frames = source.getnframes()
        request = AudioRequest(WakeWordDetection.create("jarvis", None),
                               (AudioChunk(data, 16000, captured_at=0),))
        started = time.monotonic()
        with SherpaWhisperTranscriber(args.model_dir, num_threads=args.threads) as transcriber:
            loaded = time.monotonic() - started
            started = time.monotonic()
            result = transcriber.transcribe(request)
            elapsed = time.monotonic() - started
        print(f"frames={frames} audio_seconds={frames / 16000:.3f} "
              f"load_seconds={loaded:.3f} inference_seconds={elapsed:.3f} "
              f"empty={result.is_empty}")
        if args.show_text:
            print(result.text)
    except (OSError, ValueError, RuntimeError) as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    main()
