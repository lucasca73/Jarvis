"""Test source and bundled resource path resolution."""

import importlib
from pathlib import Path
import sys
import unittest

from jarvis.resources import runtime_path, runtime_root


class ResourceTests(unittest.TestCase):
    def test_source_paths_use_working_directory(self):
        self.assertEqual(runtime_root(), Path.cwd())
        self.assertEqual(runtime_path("models/vad/silero_vad.onnx"),
                         Path.cwd() / "models/vad/silero_vad.onnx")

    def test_bundle_paths_use_meipass(self):
        sentinel = object()
        old = getattr(sys, "_MEIPASS", sentinel)
        try:
            sys._MEIPASS = "/tmp/jarvis-bundle"
            import jarvis.resources as resources
            importlib.reload(resources)
            self.assertEqual(resources.runtime_root(), Path("/tmp/jarvis-bundle"))
            self.assertEqual(resources.runtime_path("models/vad/silero_vad.onnx"),
                             Path("/tmp/jarvis-bundle/models/vad/silero_vad.onnx"))
        finally:
            if old is sentinel:
                del sys._MEIPASS
            else:
                sys._MEIPASS = old
            importlib.reload(resources)
