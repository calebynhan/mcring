"""PCM helpers for speech: decode provider audio to 16-bit mono PCM, resample, encode ring ADPCM.

The ring speaker path is 16 kHz mono IMA-ADPCM in the mcring block format (lib/mcring_adpcm,
mcring_core.adpcm): 132 bytes per 256 samples. TTS providers hand us 24 kHz PCM (or WAV), so we
low-pass and resample 3:2 here. numpy (optional) gives a proper polyphase FIR; without it we fall
back to linear interpolation, which is fine for speech on a 10 mm speaker.
"""
from __future__ import annotations

import io
import struct
import wave
from math import gcd

from mcring_core import adpcm as adpcm_codec

RING_RATE = 16000
BLOCK_BYTES = adpcm_codec.BLOCK_BYTES        # 132
BLOCK_SAMPLES = adpcm_codec.BLOCK_SAMPLES    # 256

try:  # pragma: no cover - import guard
    import numpy as _np
except ImportError:  # pragma: no cover
    _np = None

AUDIO_EXT = {"wav": "wav", "m4a": "m4a", "mp4": "m4a", "mp3": "mp3", "ogg": "ogg", "oga": "ogg",
             "flac": "flac", "webm": "webm", "adpcm": "adpcm", "aac": "aac", "caf": "caf"}
AUDIO_MIME = {"audio/wav": "wav", "audio/x-wav": "wav", "audio/wave": "wav", "audio/vnd.wave": "wav",
              "audio/mp4": "m4a", "audio/x-m4a": "m4a", "audio/m4a": "m4a", "video/mp4": "m4a",
              "audio/aac": "aac", "audio/mpeg": "mp3", "audio/mp3": "mp3", "audio/ogg": "ogg",
              "audio/flac": "flac", "audio/x-flac": "flac", "audio/webm": "webm",
              "audio/x-caf": "caf", "audio/x-mcring-adpcm": "adpcm"}


# ---------------------------------------------------------------------------
# Sniffing uploads
# ---------------------------------------------------------------------------
_MAX_STEP_INDEX = len(adpcm_codec.STEP_TABLE) - 1   # 88


def is_ring_adpcm(data: bytes) -> bool:
    """Structural check for a headerless mcring clip: whole 132-byte blocks, each starting with
    {int16 first sample, u8 step_index <= 88, u8 reserved == 0}. Checked on every block, so a
    compressed stream whose length happens to be a multiple of 132 does not pass."""
    if not data or len(data) % BLOCK_BYTES:
        return False
    return all(data[i + 2] <= _MAX_STEP_INDEX and data[i + 3] == 0 for i in range(0, len(data), BLOCK_BYTES))


def is_mpeg_frame(data: bytes) -> bool:
    """A plausible bare MPEG audio frame header (no ID3 tag): sync word plus non-reserved version,
    layer, bitrate-index and sample-rate-index fields. A ring clip whose first sample is -1, -257, ...
    (bytes FF FF / FF FE) carries the sync word too, so callers test is_ring_adpcm() first."""
    if len(data) < 4 or data[0] != 0xFF or (data[1] & 0xE0) != 0xE0:
        return False
    version, layer = (data[1] >> 3) & 3, (data[1] >> 1) & 3
    bitrate, sample_rate = data[2] >> 4, (data[2] >> 2) & 3
    return version != 1 and layer != 0 and bitrate != 0xF and sample_rate != 3


def sniff_audio(data: bytes, filename: str = "", content_type: str = "") -> str:
    """Return one of wav|m4a|mp3|ogg|flac|webm|aac|caf|adpcm|unknown for an uploaded clip."""
    ct = (content_type or "").lower().split(";")[0].strip()
    ext = filename.rsplit(".", 1)[-1].lower() if "." in (filename or "") else ""
    if ext == "adpcm" or ct == "audio/x-mcring-adpcm":
        return "adpcm"
    if data[:4] == b"RIFF" and data[8:12] == b"WAVE":
        return "wav"
    if data[4:8] == b"ftyp":
        return "m4a"
    if data[:3] == b"ID3":
        return "mp3"
    if is_ring_adpcm(data):
        return "adpcm"   # ring voice clips are whole 132-byte blocks with no header
    if is_mpeg_frame(data):
        return "mp3"
    if data[:4] == b"OggS":
        return "ogg"
    if data[:4] == b"fLaC":
        return "flac"
    if data[:4] == b"\x1aE\xdf\xa3":
        return "webm"
    if data[:4] == b"caff":
        return "caf"
    if ext in AUDIO_EXT:
        return AUDIO_EXT[ext]
    if ct in AUDIO_MIME:
        return AUDIO_MIME[ct]
    if data and len(data) % BLOCK_BYTES == 0:
        return "adpcm"   # ring voice clips are whole 132-byte blocks with no header
    return "unknown"


# ---------------------------------------------------------------------------
# PCM <-> bytes / WAV
# ---------------------------------------------------------------------------
def pcm16_from_bytes(data: bytes) -> list[int]:
    n = len(data) // 2
    return list(struct.unpack(f"<{n}h", data[: n * 2])) if n else []


def pcm16_to_bytes(pcm: list[int]) -> bytes:
    return struct.pack(f"<{len(pcm)}h", *pcm)


def wav_to_pcm(data: bytes) -> tuple[list[int], int]:
    """16-bit PCM WAV -> (mono samples, rate). Multi-channel input is averaged down to mono."""
    with wave.open(io.BytesIO(data)) as w:
        ch, sw, rate, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        frames = w.readframes(n)
    if sw != 2:
        raise ValueError(f"unsupported WAV sample width {sw * 8} bit (need 16-bit PCM)")
    samples = pcm16_from_bytes(frames)
    if ch > 1:
        samples = [sum(samples[i : i + ch]) // ch for i in range(0, len(samples) - ch + 1, ch)]
    return samples, rate


def decode_to_pcm(audio: bytes, mime: str) -> tuple[list[int], int]:
    """Decode raw PCM ('audio/pcm;rate=24000', 16-bit LE mono) or WAV. Anything else raises ValueError."""
    m = (mime or "").lower()
    parts = [p.strip() for p in m.split(";")]
    base = parts[0]
    params = dict(p.split("=", 1) for p in parts[1:] if "=" in p)
    if base in ("audio/wav", "audio/x-wav", "audio/wave", "audio/vnd.wave") or audio[:4] == b"RIFF":
        return wav_to_pcm(audio)
    if base in ("audio/pcm", "audio/l16", "audio/x-raw", "application/octet-stream", ""):
        try:
            rate = int(params.get("rate", 24000))
        except ValueError:
            rate = 24000
        return pcm16_from_bytes(audio), rate
    raise ValueError(f"cannot decode {mime!r} to PCM (only raw PCM and 16-bit WAV are supported; "
                     "ask the TTS provider for pcm/wav instead of mp3)")


# ---------------------------------------------------------------------------
# Resampling
# ---------------------------------------------------------------------------
def _clamp16(v: float) -> int:
    i = int(round(v))
    return 32767 if i > 32767 else (-32768 if i < -32768 else i)


def resample(pcm: list[int], src_rate: int, dst_rate: int) -> list[int]:
    """Resample 16-bit mono PCM. Polyphase FIR with numpy, linear interpolation without."""
    if src_rate <= 0 or dst_rate <= 0:
        raise ValueError("sample rates must be positive")
    if src_rate == dst_rate or not pcm:
        return list(pcm)
    if _np is not None:
        return _resample_polyphase(pcm, src_rate, dst_rate)
    return _resample_linear(pcm, src_rate, dst_rate)


def _resample_linear(pcm: list[int], src_rate: int, dst_rate: int) -> list[int]:
    n_out = max(1, round(len(pcm) * dst_rate / src_rate))
    step = src_rate / dst_rate
    last = len(pcm) - 1
    out: list[int] = []
    for i in range(n_out):
        pos = i * step
        i0 = int(pos)
        frac = pos - i0
        s0 = pcm[i0 if i0 <= last else last]
        s1 = pcm[i0 + 1 if i0 + 1 <= last else last]
        out.append(_clamp16(s0 + (s1 - s0) * frac))
    return out


def _resample_polyphase(pcm: list[int], src_rate: int, dst_rate: int) -> list[int]:
    np = _np
    x = np.asarray(pcm, dtype=np.float64)
    g = gcd(src_rate, dst_rate)
    up, down = dst_rate // g, src_rate // g
    if up > 32 or down > 32:
        # Awkward ratio: plain interpolation is good enough.
        n_out = max(1, round(len(x) * dst_rate / src_rate))
        t = np.arange(n_out) * (src_rate / dst_rate)
        y = np.interp(t, np.arange(len(x)), x)
    else:
        # Zero-stuff to the common rate, windowed-sinc low-pass at the lower Nyquist, decimate.
        fs_up = src_rate * up
        y = np.zeros(len(x) * up)
        y[::up] = x * up
        cutoff = 0.5 * min(src_rate, dst_rate) / fs_up * 0.92   # cycles/sample, a little below Nyquist
        taps = 32 * max(up, down) + 1
        n = np.arange(taps) - (taps - 1) / 2
        h = 2 * cutoff * np.sinc(2 * cutoff * n) * np.hamming(taps)
        h /= h.sum()
        y = np.convolve(y, h, mode="same")[::down]
    return np.clip(np.rint(y), -32768, 32767).astype(np.int16).tolist()


# ---------------------------------------------------------------------------
# Ring ADPCM
# ---------------------------------------------------------------------------
def pcm_to_ring_adpcm(pcm16k: list[int]) -> bytes:
    """16 kHz mono PCM -> mcring ADPCM blocks (last block zero-padded)."""
    return adpcm_codec.encode(list(pcm16k))


def adpcm_blocks(data: bytes) -> int:
    return len(data) // BLOCK_BYTES


def adpcm_duration_ms(data: bytes, rate: int = RING_RATE) -> int:
    return adpcm_blocks(data) * BLOCK_SAMPLES * 1000 // rate


def pcm_to_ring_adpcm_from(pcm: list[int], rate: int) -> bytes:
    """Any-rate 16-bit mono PCM -> ring ADPCM at 16 kHz."""
    return pcm_to_ring_adpcm(resample(pcm, rate, RING_RATE))
