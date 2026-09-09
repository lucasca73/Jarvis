"""Continuous PCM capture using sounddevice's raw input stream."""

from __future__ import annotations

from queue import Empty, Full, Queue
from threading import Lock
from typing import Any, Callable

from jarvis.audio.devices import SoundDeviceDeviceCatalog
from jarvis.audio.input import AudioInput
from jarvis.audio.models import AudioChunk, AudioConfig, AudioDevice


class SoundDeviceAudioInput(AudioInput):
    """Capture in-memory signed 16-bit PCM chunks from an input device."""

    def __init__(
        self,
        *,
        chunk_duration_ms: int = 100,
        max_queued_chunks: int = 50,
        backend: Any | None = None,
    ) -> None:
        if chunk_duration_ms <= 0:
            raise ValueError("chunk_duration_ms must be greater than zero")
        if max_queued_chunks <= 0:
            raise ValueError("max_queued_chunks must be greater than zero")

        self._backend = backend if backend is not None else self._load_backend()
        self._catalog = SoundDeviceDeviceCatalog(self._backend)
        self._chunk_duration_ms = chunk_duration_ms
        self._max_queued_chunks = max_queued_chunks
        self._chunks: Queue[AudioChunk] = Queue(maxsize=max_queued_chunks)
        self._lock = Lock()
        self._stream: Any | None = None
        self._config: AudioConfig | None = None
        self._is_running = False

    def list_input_devices(self) -> list[AudioDevice]:
        """Return input devices reported by sounddevice."""
        return self._catalog.list_input_devices()

    @property
    def is_running(self) -> bool:
        """Whether microphone capture is active."""
        with self._lock:
            return self._is_running

    def start(self, config: AudioConfig) -> None:
        """Start capturing signed 16-bit PCM audio into an in-memory queue."""
        if config.sample_width_bytes != 2:
            raise ValueError("SoundDeviceAudioInput only supports 16-bit PCM audio")

        with self._lock:
            if self._is_running:
                raise RuntimeError("audio capture is already running")

            self._chunks = Queue(maxsize=self._max_queued_chunks)
            self._config = config
            stream = self._backend.RawInputStream(
                samplerate=config.sample_rate,
                blocksize=self._block_size(config.sample_rate),
                device=config.device,
                channels=config.channels,
                dtype="int16",
                callback=self._on_audio,
            )
            self._stream = stream
            self._is_running = True

        try:
            stream.start()
        except Exception:
            with self._lock:
                self._stream = None
                self._config = None
                self._is_running = False
            stream.close()
            raise

    def read_chunk(self, timeout: float | None = None) -> AudioChunk:
        """Return the next PCM chunk or raise TimeoutError when it does not arrive."""
        if timeout is not None and timeout < 0:
            raise ValueError("timeout must be greater than or equal to zero")
        if not self.is_running:
            raise RuntimeError("audio capture is not running")

        try:
            return self._chunks.get(timeout=timeout)
        except Empty as error:
            raise TimeoutError("timed out while waiting for an audio chunk") from error

    def stop(self) -> None:
        """Stop capture, release the stream, and discard buffered audio."""
        with self._lock:
            stream = self._stream
            self._stream = None
            self._config = None
            self._is_running = False
            self._chunks = Queue(maxsize=self._max_queued_chunks)

        if stream is not None:
            stream.stop()
            stream.close()

    def _on_audio(self, indata: Any, *_: Any) -> None:
        """Receive raw audio from the backend without blocking its callback thread."""
        with self._lock:
            config = self._config
            is_running = self._is_running

        if not is_running or config is None:
            return

        chunk = AudioChunk.from_pcm(bytes(indata), config)
        try:
            self._chunks.put_nowait(chunk)
        except Full:
            try:
                self._chunks.get_nowait()
            except Empty:
                pass
            self._chunks.put_nowait(chunk)

    def _block_size(self, sample_rate: int) -> int:
        """Return a whole number of frames for the configured chunk duration."""
        return max(1, round(sample_rate * self._chunk_duration_ms / 1_000))

    @staticmethod
    def _load_backend() -> Any:
        return SoundDeviceDeviceCatalog._load_backend()
