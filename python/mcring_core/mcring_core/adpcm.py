"""IMA ADPCM codec, block format identical to firmware/ring-esp32s3/lib/mcring_adpcm."""
from __future__ import annotations

import struct

BLOCK_SAMPLES = 256
BLOCK_BYTES = 4 + (BLOCK_SAMPLES - 1 + 1) // 2  # 132

INDEX_TABLE = [-1, -1, -1, -1, 2, 4, 6, 8, -1, -1, -1, -1, 2, 4, 6, 8]
STEP_TABLE = [
    7, 8, 9, 10, 11, 12, 13, 14, 16, 17, 19, 21, 23, 25, 28, 31, 34, 37, 41, 45, 50, 55, 60, 66,
    73, 80, 88, 97, 107, 118, 130, 143, 157, 173, 190, 209, 230, 253, 279, 307, 337, 371, 408,
    449, 494, 544, 598, 658, 724, 796, 876, 963, 1060, 1166, 1282, 1411, 1552, 1707, 1878, 2066,
    2272, 2499, 2749, 3024, 3327, 3660, 4026, 4428, 4871, 5358, 5894, 6484, 7132, 7845, 8630,
    9493, 10442, 11487, 12635, 13899, 15289, 16818, 18500, 20350, 22385, 24623, 27086, 29794, 32767,
]


def _clamp16(v: int) -> int:
    return 32767 if v > 32767 else (-32768 if v < -32768 else v)


def _clamp_idx(v: int) -> int:
    return 0 if v < 0 else (88 if v > 88 else v)


class State:
    __slots__ = ("predictor", "step_index")

    def __init__(self, predictor: int = 0, step_index: int = 0):
        self.predictor = predictor
        self.step_index = step_index

    def encode_sample(self, sample: int) -> int:
        step = STEP_TABLE[self.step_index]
        diff = sample - self.predictor
        code = 0
        if diff < 0:
            code = 8
            diff = -diff
        vpdiff = step >> 3
        if diff >= step:
            code |= 4
            diff -= step
            vpdiff += step
        step >>= 1
        if diff >= step:
            code |= 2
            diff -= step
            vpdiff += step
        step >>= 1
        if diff >= step:
            code |= 1
            vpdiff += step
        self.predictor = _clamp16(self.predictor - vpdiff if code & 8 else self.predictor + vpdiff)
        self.step_index = _clamp_idx(self.step_index + INDEX_TABLE[code])
        return code

    def decode_sample(self, code: int) -> int:
        step = STEP_TABLE[self.step_index]
        vpdiff = step >> 3
        if code & 4:
            vpdiff += step
        if code & 2:
            vpdiff += step >> 1
        if code & 1:
            vpdiff += step >> 2
        self.predictor = _clamp16(self.predictor - vpdiff if code & 8 else self.predictor + vpdiff)
        self.step_index = _clamp_idx(self.step_index + INDEX_TABLE[code & 15])
        return self.predictor


def encode_block(pcm: list[int], st: State | None = None) -> bytes:
    """Encode one block. If `st` is given its step index carries over (and it is updated)."""
    assert len(pcm) == BLOCK_SAMPLES
    if st is None:
        st = State()
    st.predictor = pcm[0]
    st.step_index = _clamp_idx(st.step_index)
    out = bytearray(struct.pack("<hBB", pcm[0], st.step_index, 0))
    acc = None
    for s in pcm[1:]:
        c = st.encode_sample(s)
        if acc is None:
            acc = c
        else:
            out.append(acc | (c << 4))
            acc = None
    if acc is not None:
        out.append(acc)
    return bytes(out)


def decode_block(block: bytes) -> list[int]:
    pred, idx, _ = struct.unpack_from("<hBB", block, 0)
    st = State(predictor=pred, step_index=_clamp_idx(idx))
    pcm = [pred]
    o = 4
    while len(pcm) < BLOCK_SAMPLES:
        b = block[o]
        o += 1
        pcm.append(st.decode_sample(b & 0x0F))
        if len(pcm) < BLOCK_SAMPLES:
            pcm.append(st.decode_sample(b >> 4))
    return pcm


def encode(pcm: list[int]) -> bytes:
    out = bytearray()
    st = State()
    for off in range(0, len(pcm), BLOCK_SAMPLES):
        blk = pcm[off : off + BLOCK_SAMPLES]
        if len(blk) < BLOCK_SAMPLES:
            blk = blk + [0] * (BLOCK_SAMPLES - len(blk))
        out += encode_block(blk, st)
    return bytes(out)


def decode(data: bytes) -> list[int]:
    pcm: list[int] = []
    for off in range(0, len(data) - BLOCK_BYTES + 1, BLOCK_BYTES):
        pcm.extend(decode_block(data[off : off + BLOCK_BYTES]))
    return pcm


def pcm_to_wav(pcm: list[int], sample_rate: int = 16000) -> bytes:
    data = struct.pack(f"<{len(pcm)}h", *pcm)
    hdr = b"RIFF" + struct.pack("<I", 36 + len(data)) + b"WAVEfmt " + struct.pack(
        "<IHHIIHH", 16, 1, 1, sample_rate, sample_rate * 2, 2, 16
    ) + b"data" + struct.pack("<I", len(data))
    return hdr + data


def adpcm_to_wav(data: bytes, sample_rate: int = 16000) -> bytes:
    return pcm_to_wav(decode(data), sample_rate)
