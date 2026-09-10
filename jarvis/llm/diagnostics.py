"""Run a fixed, nonsensitive prompt against local Ollama."""

import argparse
import time

from jarvis.llm.client import LanguageModelError, TextRequest
from jarvis.llm.ollama import OllamaConfig, OllamaLanguageModel


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', default='llama3.2:3b')
    parser.add_argument('--endpoint', default='http://127.0.0.1:11434')
    parser.add_argument('--show-text', action='store_true')
    args = parser.parse_args()
    try:
        config = OllamaConfig(model=args.model, endpoint=args.endpoint)
        with OllamaLanguageModel(config) as model:
            started = time.monotonic()
            result = model.respond(TextRequest('Why is the sky blue?'))
            elapsed = time.monotonic() - started
        print(f'response_seconds={elapsed:.3f} characters={len(result.text)}')
        if args.show_text:
            print(result.text)
    except (ValueError, LanguageModelError) as exc:
        raise SystemExit(str(exc)) from None


if __name__ == '__main__':
    main()
