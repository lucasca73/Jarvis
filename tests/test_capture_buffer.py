"""Behavior tests for bounded pre-roll retention."""

import unittest

from jarvis.audio import AudioChunk
from jarvis.capture import PreRollBuffer


def chunk(value, frames=1600, captured_at=0):
    return AudioChunk(bytes([value, 0]) * frames, 16000, captured_at=captured_at)


class PreRollBufferTests(unittest.TestCase):
    def test_retains_only_latest_audio_over_many_appends(self):
        buffer = PreRollBuffer(0.2)
        for index in range(100):
            buffer.append(chunk(index, captured_at=index))
            self.assertLessEqual(buffer.frame_count, 3200)
        self.assertEqual([part.data[0] for part in buffer.snapshot()], [98, 99])
        self.assertAlmostEqual(buffer.duration_seconds, 0.2)

    def test_trims_oldest_chunk_at_frame_boundary(self):
        buffer = PreRollBuffer(0.15)
        buffer.append(chunk(1))
        buffer.append(chunk(2))
        retained = buffer.snapshot()
        self.assertEqual([part.frame_count for part in retained], [800, 1600])
        self.assertEqual(retained[0].data, bytes([1, 0]) * 800)

    def test_oversized_chunk_keeps_its_tail(self):
        buffer = PreRollBuffer(2 / 16000)
        buffer.append(AudioChunk(b'\x01\x00\x02\x00\x03\x00', 16000, captured_at=10))
        self.assertEqual(buffer.snapshot()[0].data, b'\x02\x00\x03\x00')
        self.assertEqual(buffer.snapshot()[0].captured_at, 10)

    def test_snapshot_survives_eviction_and_clear(self):
        buffer = PreRollBuffer(0.1)
        first = chunk(1)
        buffer.append(first)
        snapshot = buffer.snapshot()
        buffer.append(chunk(2))
        buffer.clear()
        self.assertEqual(snapshot, (first,))
        self.assertEqual(buffer.snapshot(), ())
        self.assertEqual(buffer.duration_seconds, 0)
        buffer.append(AudioChunk(bytes(1600), 8000, captured_at=-1))
        self.assertEqual(buffer.frame_count, 800)

    def test_invalid_append_does_not_modify_buffer(self):
        buffer = PreRollBuffer()
        first = chunk(1, captured_at=10)
        buffer.append(first)
        for invalid in (AudioChunk(bytes(4), 8000),
                        AudioChunk(bytes(4), 16000, channels=2),
                        AudioChunk(bytes(4), 16000, sample_width_bytes=1),
                        chunk(2, captured_at=9), chunk(2, captured_at=float('nan'))):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                buffer.append(invalid)
            self.assertEqual(buffer.snapshot(), (first,))
            self.assertEqual(buffer.frame_count, 1600)

    def test_rejects_invalid_limits(self):
        for duration in (0, -1, float('nan'), float('inf')):
            with self.subTest(duration=duration), self.assertRaises(ValueError):
                PreRollBuffer(duration)
        buffer = PreRollBuffer(0.000001)
        with self.assertRaises(ValueError):
            buffer.append(chunk(1))
        self.assertEqual(buffer.snapshot(), ())

    def test_empty_snapshot(self):
        self.assertEqual(PreRollBuffer().snapshot(), ())
