"""Synthesize a fixed English sentence in memory and optionally play it."""

import argparse
import time

from jarvis.llm import TextResponse
from jarvis.tts.piper import DEFAULT_MODEL_DIR, SherpaPiperSynthesizer
from jarvis.tts.player import SoundDeviceAudioPlayer


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model-dir', default=str(DEFAULT_MODEL_DIR))
    parser.add_argument('--play', action='store_true', help='play through the output device')
    parser.add_argument('--device', help='output device ID or name')
    args = parser.parse_args()
    device = int(args.device) if args.device and args.device.isdecimal() else args.device
    try:
        started = time.monotonic()
        with SherpaPiperSynthesizer(args.model_dir) as synth:
            loaded = time.monotonic() - started
            started = time.monotonic()
            audio = synth.synthesize(TextResponse('Hello. I am Jarvis, your local voice assistant.'))
            elapsed = time.monotonic() - started
        print(f'load_seconds={loaded:.3f} synthesis_seconds={elapsed:.3f} '
              f'audio_seconds={audio.duration_seconds:.3f} sample_rate={audio.sample_rate}', flush=True)
        if args.play:
            print('Playing locally.', flush=True)
            with SoundDeviceAudioPlayer(device) as player:
                player.play(audio)
            print('Playback complete.')
    except KeyboardInterrupt:
        print('TTS diagnostic interrupted.')
    except (ValueError, RuntimeError, OSError) as exc:
        raise SystemExit(str(exc)) from None


if __name__ == '__main__':
    main()
