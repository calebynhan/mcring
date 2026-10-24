import math
import struct
import subprocess

from mcring_core import adpcm


def tone(n=4096, f=440.0, sr=16000, amp=12000):
    return [int(amp * math.sin(2 * math.pi * f * i / sr)) for i in range(n)]


def test_block_sizes():
    pcm = tone(256)
    blk = adpcm.encode_block(pcm)
    assert len(blk) == adpcm.BLOCK_BYTES == 132
    assert len(adpcm.encode(tone(1000))) == 4 * 132


def test_roundtrip_snr():
    pcm = tone()
    dec = adpcm.decode(adpcm.encode(pcm))[: len(pcm)]
    noise = sum((a - b) ** 2 for a, b in zip(pcm, dec)) / len(pcm)
    sig = sum(a * a for a in pcm) / len(pcm)
    snr_db = 10 * math.log10(sig / max(noise, 1e-9))
    assert snr_db > 20, snr_db


def test_c_encoder_matches_python(c_tool):
    pcm = tone(2048, f=700.0) + [0] * 100 + tone(300, f=120.0, amp=30000)
    raw = struct.pack(f"<{len(pcm)}h", *pcm)
    c_out = subprocess.run([str(c_tool), "adpcm"], input=raw, capture_output=True, check=True).stdout
    assert c_out == adpcm.encode(pcm)


def test_wav_header():
    w = adpcm.pcm_to_wav([0, 1, -1], 16000)
    assert w[:4] == b"RIFF" and w[8:12] == b"WAVE" and len(w) == 44 + 6
