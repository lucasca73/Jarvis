"""Local wake-word detection for Jarvis."""

from jarvis.wakeword.detector import WakeWordDetector
from jarvis.wakeword.models import WakeWordConfig, WakeWordDetection

from jarvis.wakeword.sherpa import SherpaOnnxWakeWordDetector

__all__ = [
    "SherpaOnnxWakeWordDetector",
    "WakeWordConfig",
    "WakeWordDetection",
    "WakeWordDetector",
]
