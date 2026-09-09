"""Run local keyword spotting on a microphone or a PCM WAV file."""

from __future__ import annotations

import argparse
from time import monotonic
import wave

from jarvis.audio import AudioChunk, AudioConfig, SoundDeviceAudioInput
from jarvis.audio.diagnostics import parse_device
from jarvis.wakeword import SherpaOnnxWakeWordDetector, WakeWordConfig
from jarvis.wakeword.sherpa import DEFAULT_KEYWORDS, DEFAULT_MODEL_DIR


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model-dir', default=str(DEFAULT_MODEL_DIR))
    parser.add_argument('--keywords-file', default=str(DEFAULT_KEYWORDS))
    parser.add_argument('--wav', help='read a 16 kHz mono 16-bit PCM WAV instead of the microphone')
    parser.add_argument('--device', type=parse_device)
    parser.add_argument('--duration', type=float, default=30)
    parser.add_argument('--threshold', type=float, default=0.25)
    args = parser.parse_args()
    if not 0 < args.duration < float('inf'):
        parser.error('--duration must be finite and greater than zero')

    def report(detector, chunk):
        result = detector.process(chunk)
        if result:
            print(f'Wake word detected: {result.wake_word}', flush=True)

    try:
        with SherpaOnnxWakeWordDetector(
            args.model_dir, keywords_file=args.keywords_file,
            config=WakeWordConfig(threshold=args.threshold),
        ) as detector:
            if args.wav:
                with wave.open(args.wav, 'rb') as source:
                    if (source.getframerate(), source.getnchannels(), source.getsampwidth()) != (16000, 1, 2):
                        raise ValueError('WAV input must be 16 kHz mono 16-bit PCM')
                    while True:
                        data = source.readframes(1600)
                        if not data:
                            break
                        # WAV PCM is little-endian; microphone PCM is native-endian.
                        import sys
                        if sys.byteorder != 'little':
                            from array import array
                            samples = array('h', data)
                            samples.byteswap()
                            data = samples.tobytes()
                        report(detector, AudioChunk(data, 16000))
                for _ in range(10):
                    report(detector, AudioChunk(bytes(3200), 16000))
            else:
                print('Listening locally. Audio is kept in memory. Press Ctrl+C to stop.')
                with SoundDeviceAudioInput() as source:
                    source.start(AudioConfig(device=args.device))
                    deadline = monotonic() + args.duration
                    while monotonic() < deadline:
                        try:
                            chunk = source.read_chunk(timeout=max(0, deadline - monotonic()))
                        except TimeoutError:
                            break
                        report(detector, chunk)
    except KeyboardInterrupt:
        print('\nWake-word diagnostic stopped.')
    except (ValueError, RuntimeError, OSError, wave.Error) as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == '__main__':
    main()
