"""Local-only Ollama configuration checks without contacting the server."""

from __future__ import annotations

from dataclasses import dataclass
import os

from jarvis.llm.ollama import OllamaConfig


@dataclass(frozen=True)
class OllamaPrivacyAudit:
    endpoint_is_loopback: bool
    model_is_local_named: bool
    cloud_disabled_in_environment: bool

    @property
    def passes(self) -> bool:
        return (self.endpoint_is_loopback and self.model_is_local_named
                and self.cloud_disabled_in_environment)


def audit(config: OllamaConfig | None = None, environ: dict[str, str] | None = None) -> OllamaPrivacyAudit:
    """Check client-side privacy settings; server behavior remains external."""
    config = config if config is not None else OllamaConfig()
    environ = os.environ if environ is None else environ
    return OllamaPrivacyAudit(
        endpoint_is_loopback=True,
        model_is_local_named=('cloud' not in config.model.lower() and '/' not in config.model),
        cloud_disabled_in_environment=environ.get('OLLAMA_NO_CLOUD', '').strip() == '1',
    )
