import io
import sys
import unittest
import wave
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from jarvis.stt import diagnostics


class SttDiagnosticsTests(unittest.TestCase):
    def test_rejects_wrong_wav_format_before_loading_model(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "bad.wav"
            with wave.open(str(path), "wb") as output:
                output.setnchannels(2); output.setsampwidth(2); output.setframerate(16000); output.writeframes(b"\0" * 8)
            with patch.object(diagnostics, "SherpaWhisperTranscriber") as transcriber, patch.object(sys, "argv", ["diagnostics", str(path)]):
                with self.assertRaises(SystemExit):
                    diagnostics.main()
                transcriber.assert_not_called()

    def test_default_output_excludes_transcript(self):
        sample = Path("models/stt/sherpa-onnx-whisper-tiny.en/test_wavs/0.wav")
        output = io.StringIO()
        with patch.object(sys, "argv", ["diagnostics", str(sample)]), redirect_stdout(output):
            diagnostics.main()
        self.assertIn("inference_seconds=", output.getvalue())
        self.assertNotIn("After early nightfall", output.getvalue())
