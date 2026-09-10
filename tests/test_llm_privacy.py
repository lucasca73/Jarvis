import unittest

from jarvis.llm import OllamaConfig, audit


class OllamaPrivacyTests(unittest.TestCase):
    def test_audit_requires_server_cloud_disable_flag(self):
        config = OllamaConfig()
        self.assertFalse(audit(config, {}).passes)
        result = audit(config, {'OLLAMA_NO_CLOUD': '1'})
        self.assertTrue(result.passes)

    def test_whitespace_and_other_values_do_not_claim_local_only(self):
        self.assertFalse(audit(environ={'OLLAMA_NO_CLOUD': ' true '}).cloud_disabled_in_environment)

    def test_client_config_already_rejects_cloud_model(self):
        with self.assertRaises(ValueError):
            OllamaConfig(model='gpt-oss:20b-cloud')
