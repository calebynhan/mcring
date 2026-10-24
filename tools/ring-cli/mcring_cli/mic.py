"""Laptop microphone for push-to-talk (`mcring talk`). Optional dependency: sounddevice (pip install 'mcring-cli[mic]').

Records 16 kHz mono 16-bit PCM and hands back a WAV file the backend's speech-to-text accepts directly.
"""
from __future__ import annotations

import struct
import threading
import time

SAMPLE_RATE = 16000


class MicUnavailable(RuntimeError):
    pass


def pcm_bytes_to_wav(pcm: bytes, sample_rate: int = SAMPLE_RATE, channels: int = 1) -> bytes:
    hdr = b"RIFF" + struct.pack("<I", 36 + len(pcm)) + b"WAVEfmt " + struct.pack(
        "<IHHIIHH", 16, 1, channels, sample_rate, sample_rate * 2 * channels, 2 * channels, 16
    ) + b"data" + struct.pack("<I", len(pcm))
    return hdr + pcm


def _sounddevice():
    try:
        import sounddevice  # type: ignore
    except (ImportError, OSError) as e:          # OSError: PortAudio library missing
        raise MicUnavailable("laptop mic needs the optional dependency sounddevice "
                             "(pip install 'mcring-cli[mic]'), or use --ring-mic") from e
    return sounddevice


def is_available() -> bool:
    try:
        _sounddevice()
        return True
    except MicUnavailable:
        return False


class Recorder:
    """start() … stop() → WAV bytes. Thread-safe enough for one recording at a time."""

    def __init__(self, sample_rate: int = SAMPLE_RATE, device=None):
        self.sample_rate = sample_rate
        self.device = device
        self._chunks: list[bytes] = []
        self._stream = None
        self._lock = threading.Lock()
        self._t0 = 0.0

    @property
    def active(self) -> bool:
        return self._stream is not None

    @property
    def duration_s(self) -> float:
        return (time.monotonic() - self._t0) if self._stream is not None else 0.0

    def start(self) -> None:
        if self._stream is not None:
            return
        sd = _sounddevice()
        self._chunks = []

        def cb(indata, frames, t, status):  # noqa: ARG001
            with self._lock:
                self._chunks.append(bytes(indata))

        try:
            self._stream = sd.RawInputStream(samplerate=self.sample_rate, channels=1, dtype="int16",
                                             device=self.device, callback=cb)
            self._stream.start()
        except Exception as e:  # noqa: BLE001
            self._stream = None
            raise MicUnavailable(f"could not open the microphone: {e}") from e
        self._t0 = time.monotonic()

    def stop(self) -> bytes:
        """Stop and return the recording as WAV (empty data chunk if nothing was captured)."""
        st = self._stream
        self._stream = None
        if st is not None:
            try:
                st.stop()
                st.close()
            except Exception:  # noqa: BLE001
                pass
        with self._lock:
            pcm = b"".join(self._chunks)
            self._chunks = []
        return pcm_bytes_to_wav(pcm, self.sample_rate)

    def cancel(self) -> None:
        self.stop()
