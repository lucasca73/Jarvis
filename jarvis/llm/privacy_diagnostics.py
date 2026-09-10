"""Report client-side local-only Ollama checks without making an API request."""

from jarvis.llm.privacy import audit


def main() -> None:
    result = audit()
    print(f'endpoint_loopback={result.endpoint_is_loopback} '
          f'model_local={result.model_is_local_named} '
          f'cloud_disabled_in_environment={result.cloud_disabled_in_environment} '
          f'passes={result.passes}')
    if not result.passes:
        raise SystemExit('Set OLLAMA_NO_CLOUD=1 before starting Ollama for local-only mode')


if __name__ == '__main__':
    main()
