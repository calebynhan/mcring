"""BLE packet (de)serialisation mirroring firmware/ring-esp32s3/lib/mcring_proto."""
from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass
from enum import IntEnum

PROTO_VERSION = 1

UUID_BASE = "7a3b{:04x}-9c2e-4f3a-b1d4-6d6372696e67"
UUID_SERVICE = UUID_BASE.format(0x0001)
UUID_CONTROL = UUID_BASE.format(0x0002)
UUID_STATUS = UUID_BASE.format(0x0003)
UUID_XFER_META = UUID_BASE.format(0x0004)
UUID_XFER_DATA = UUID_BASE.format(0x0005)
UUID_FEEDBACK = UUID_BASE.format(0x0006)
UUID_EVENTS = UUID_BASE.format(0x0007)      # notify, ring -> phone
UUID_AUDIO_OUT = UUID_BASE.format(0x0008)   # write-no-response, phone -> ring speaker

ATT_HDR_LEN = 3
XFER_CHUNK_HDR_LEN = 4
EVENT_LEN = 6
AUDIO_DATA_HDR_LEN = 3          # opcode + u16 seq
ADPCM_BLOCK_BYTES = 132         # == adpcm.BLOCK_BYTES (256 samples @ 16 kHz = 16 ms)
AUDIO_PREBUFFER_BLOCKS = 24     # ring starts playing after this many blocks (~400 ms)


class Op(IntEnum):
    CAPTURE = 0x01
    ACK_TRANSFER = 0x02
    SET_CONFIG = 0x03
    PING = 0x04
    ABORT = 0x05
    RECORD_AUDIO = 0x06
    SLEEP = 0x07
    GET_STATUS = 0x08
    RECORD_START = 0x09   # ring-mic recording until RECORD_STOP / 8 s
    RECORD_STOP = 0x0A


class Fb(IntEnum):
    MORSE_TEXT = 0x10        # legacy / optional "silent pattern" mode
    PATTERN = 0x11
    STOP = 0x12
    RGB = 0x13
    MORSE_UNITS = 0x14       # legacy
    MORSE_UNITS_CONT = 0x15  # legacy
    CUE = 0x16               # {u8 cue}: built-in cue honouring CUES_MASK


class Cue(IntEnum):
    LISTENING = 1       # 1 short tick
    ANSWER_READY = 2    # 2 ticks
    ERROR = 3           # long buzz
    OK = 4              # 1 short tick


class Cues(IntEnum):
    """CUES_MASK bits (config key 10)."""
    HAPTIC = 0x01
    LED = 0x02
    BEEP = 0x04


class MicSource(IntEnum):
    """MIC_SOURCE_HINT values (config key 11)."""
    RING = 0
    PHONE = 1


class Ao(IntEnum):
    """Audio-out opcodes (phone -> ring, characteristic 0008)."""
    START = 0x20
    DATA = 0x21
    END = 0x22
    STOP = 0x23


AUDIO_CODEC_ADPCM = 2


class Event(IntEnum):
    """Ring -> phone events (characteristic 0007)."""
    BUTTON_DOWN = 1
    BUTTON_UP = 2          # arg = held tenths of a second (capped 255)
    DOUBLE_TAP = 3
    TOUCH = 4
    CAPTURE_STARTED = 5
    CAPTURE_DONE = 6       # arg = queued count (0 = failed)
    REC_STARTED = 7        # arg = max seconds
    REC_STOPPED = 8        # arg = recorded tenths of a second (0 = discarded)
    LOW_BATTERY = 9        # arg = pct
    AUDIO_UNDERRUN = 10
    AUDIO_DONE = 11        # arg = 0 drained, 1 stopped


class Channel(IntEnum):
    LED = 0x01
    HAPTIC = 0x02
    BUZZER = 0x04
    AUX = 0x08


class Cfg(IntEnum):
    TRIGGER_MASK = 1
    DEFAULT_QUALITY = 2
    DEFAULT_FRAMESIZE = 3
    IDLE_SLEEP_S = 4
    LED_BRIGHTNESS = 5
    HAPTIC_STRENGTH = 6
    MORSE_WPM = 7          # legacy
    FEEDBACK_CHANNELS = 8  # legacy
    SPEAKER_VOLUME = 9     # 0..255
    CUES_MASK = 10         # Cues bits
    MIC_SOURCE_HINT = 11   # MicSource


class State(IntEnum):
    IDLE = 0
    CAPTURING = 1
    TRANSFERRING = 2
    RECORDING = 3
    FEEDBACK = 4   # playing: cue / pattern / speaker audio
    ERROR = 5


class Flag(IntEnum):
    """Status.flags bits."""
    CHARGING = 0x01
    CAMERA_OK = 0x02
    IMU_OK = 0x04
    MIC_OK = 0x08
    HAPTIC_OK = 0x10
    QUEUED = 0x20
    SPEAKER_OK = 0x40


class XferType(IntEnum):
    JPEG = 0x01
    ADPCM = 0x02
    END = 0xFF


class FrameSize(IntEnum):
    DEFAULT = 0
    QQVGA = 1
    QVGA = 2
    VGA = 3
    SVGA = 4
    XGA = 5


ERROR_NAMES = {0: "none", 1: "camera_init", 2: "capture_failed", 3: "transfer_timeout", 4: "oom", 5: "mic"}


def crc32(data: bytes) -> int:
    return zlib.crc32(data) & 0xFFFFFFFF


def chunk_len_for_mtu(mtu: int) -> int:
    n = mtu - ATT_HDR_LEN - XFER_CHUNK_HDR_LEN
    return max(16, min(510, n))


# ---- Control (phone -> ring) -------------------------------------------------

def capture(quality: int = 0, frame_size: int = 0) -> bytes:
    return struct.pack("<BBB", Op.CAPTURE, quality & 0xFF, frame_size & 0xFF)


def ack_transfer(xfer_id: int, missing: list[int] | None = None, abort: bool = False) -> bytes:
    missing = missing or []
    status = 2 if abort else (1 if missing else 0)
    return struct.pack("<BHBH", Op.ACK_TRANSFER, xfer_id, status, len(missing)) + struct.pack(
        f"<{len(missing)}H", *missing
    )


def set_config(key: int, value: int) -> bytes:
    return struct.pack("<BBi", Op.SET_CONFIG, key, value)


def ping() -> bytes:
    return bytes([Op.PING])


def abort() -> bytes:
    return bytes([Op.ABORT])


def record_audio(seconds: int) -> bytes:
    return struct.pack("<BB", Op.RECORD_AUDIO, max(1, min(8, seconds)))


def sleep() -> bytes:
    return bytes([Op.SLEEP])


def get_status() -> bytes:
    return bytes([Op.GET_STATUS])


def record_start() -> bytes:
    """Begin a ring-mic recording now; ends on record_stop() or after 8 s."""
    return bytes([Op.RECORD_START])


def record_stop() -> bytes:
    return bytes([Op.RECORD_STOP])


# ---- Feedback (phone -> ring) ------------------------------------------------

def fb_morse_text(text: str, wpm: int = 15, channels: int = Channel.LED | Channel.HAPTIC) -> bytes:
    b = text.encode("ascii", "ignore")[:255]
    return struct.pack("<BBBB", Fb.MORSE_TEXT, wpm, channels, len(b)) + b


def fb_pattern(units: list[int], unit_ms: int, channels: int) -> bytes:
    u = bytes(min(255, max(1, x)) for x in units[:255])
    return struct.pack("<BBBB", Fb.PATTERN, unit_ms, channels, len(u)) + u


def fb_stop() -> bytes:
    return bytes([Fb.STOP])


def fb_rgb(r: int, g: int, b: int, ms: int) -> bytes:
    return struct.pack("<BBBBH", Fb.RGB, r, g, b, ms)


def fb_cue(cue: int) -> bytes:
    """Play one of the ring's built-in cues (Cue.*), honouring the ring's CUES_MASK."""
    return struct.pack("<BB", Fb.CUE, cue)


def fb_morse_units(units: list[int], unit_ms: int, channels: int, max_write: int = 180) -> list[bytes]:
    """Build one or more writes for a MORSE_UNITS pattern that may exceed one ATT write."""
    u = bytes(min(255, max(1, x)) for x in units)
    hdr = struct.pack("<BBBH", Fb.MORSE_UNITS, unit_ms, channels, len(u))
    first_room = max_write - len(hdr)
    writes = [hdr + u[:first_room]]
    off = first_room
    while off < len(u):
        room = max_write - 3
        writes.append(struct.pack("<BH", Fb.MORSE_UNITS_CONT, off) + u[off : off + room])
        off += room
    return writes


# ---- Audio out (phone -> ring speaker) ---------------------------------------

def audio_start(sample_rate: int = 16000, codec: int = AUDIO_CODEC_ADPCM, volume: int = 255) -> bytes:
    return struct.pack("<BHBB", Ao.START, (sample_rate // 100) & 0xFFFF, codec & 0xFF, volume & 0xFF)


def audio_data(seq: int, blocks: bytes) -> bytes:
    """One AUDIO_DATA packet carrying one or more whole 132-byte ADPCM blocks."""
    if not blocks or len(blocks) % ADPCM_BLOCK_BYTES:
        raise ValueError(f"payload must be a non-empty multiple of {ADPCM_BLOCK_BYTES} bytes")
    return struct.pack("<BH", Ao.DATA, seq & 0xFFFF) + bytes(blocks)


def audio_end() -> bytes:
    return bytes([Ao.END])


def audio_stop() -> bytes:
    return bytes([Ao.STOP])


def max_write_for_mtu(mtu: int) -> int:
    """Largest write-without-response payload for a negotiated ATT MTU."""
    return max(20, mtu - ATT_HDR_LEN)


def audio_blocks_per_write(max_write: int) -> int:
    return max(1, (max_write - AUDIO_DATA_HDR_LEN) // ADPCM_BLOCK_BYTES)


def audio_data_writes(adpcm: bytes, max_write: int = 182, seq_start: int = 0) -> list[bytes]:
    """Split an ADPCM byte string into AUDIO_DATA writes of whole blocks that fit max_write.

    max_write defaults to the iOS MTU (185 - 3): one block per write. At MTU 517 pass 514 → 3 blocks.
    """
    if len(adpcm) % ADPCM_BLOCK_BYTES:
        raise ValueError(f"ADPCM length {len(adpcm)} is not a multiple of {ADPCM_BLOCK_BYTES}")
    step = audio_blocks_per_write(max_write) * ADPCM_BLOCK_BYTES
    return [audio_data(seq_start + i, adpcm[off : off + step]) for i, off in enumerate(range(0, len(adpcm), step))]


def audio_out_sequence(adpcm: bytes, max_write: int = 182, volume: int = 255, sample_rate: int = 16000) -> list[bytes]:
    """AUDIO_START, the data writes, AUDIO_END — everything needed to play one clip on the ring."""
    return [audio_start(sample_rate, AUDIO_CODEC_ADPCM, volume), *audio_data_writes(adpcm, max_write), audio_end()]


@dataclass
class AudioStart:
    sample_rate_div100: int
    codec: int
    volume: int

    FMT = "<BHBB"
    SIZE = 5

    @classmethod
    def unpack(cls, b: bytes) -> "AudioStart":
        op, sr, codec, vol = struct.unpack(cls.FMT, bytes(b[: cls.SIZE]))
        if op != Ao.START:
            raise ValueError(f"not an AUDIO_START packet (op 0x{op:02x})")
        return cls(sr, codec, vol)

    @property
    def sample_rate(self) -> int:
        return self.sample_rate_div100 * 100


def unpack_audio_data(b: bytes) -> tuple[int, list[bytes]]:
    """(seq, [block, ...]) from an AUDIO_DATA packet; raises on a partial block."""
    if len(b) < AUDIO_DATA_HDR_LEN or b[0] != Ao.DATA:
        raise ValueError("not an AUDIO_DATA packet")
    body = bytes(b[AUDIO_DATA_HDR_LEN:])
    if not body or len(body) % ADPCM_BLOCK_BYTES:
        raise ValueError("AUDIO_DATA body is not whole blocks")
    seq = struct.unpack_from("<H", b, 1)[0]
    return seq, [body[i : i + ADPCM_BLOCK_BYTES] for i in range(0, len(body), ADPCM_BLOCK_BYTES)]


# ---- Ring -> phone -----------------------------------------------------------

@dataclass
class RingEvent:
    event: int
    arg: int
    t_ms: int

    FMT = "<BBI"
    SIZE = EVENT_LEN

    @classmethod
    def unpack(cls, b: bytes) -> "RingEvent":
        return cls(*struct.unpack(cls.FMT, bytes(b[: cls.SIZE])))

    def pack(self) -> bytes:
        return struct.pack(self.FMT, self.event & 0xFF, self.arg & 0xFF, self.t_ms & 0xFFFFFFFF)

    @property
    def name(self) -> str:
        try:
            return Event(self.event).name.lower()
        except ValueError:
            return f"unknown({self.event})"


def pack_event(event: int, arg: int = 0, t_ms: int = 0) -> bytes:
    return RingEvent(event, arg, t_ms).pack()


def unpack_event(b: bytes) -> RingEvent:
    return RingEvent.unpack(b)


@dataclass
class Status:
    version: int
    state: int
    battery_mv: int
    battery_pct: int
    flags: int
    uptime_s: int
    last_error: int
    queued: int

    FMT = "<BBHBBIBB"
    SIZE = 12

    @classmethod
    def unpack(cls, b: bytes) -> "Status":
        return cls(*struct.unpack(cls.FMT, bytes(b[: cls.SIZE])))

    def pack(self) -> bytes:
        return struct.pack(
            self.FMT, self.version, self.state, self.battery_mv, self.battery_pct,
            self.flags, self.uptime_s, self.last_error, self.queued,
        )

    @property
    def state_name(self) -> str:
        try:
            return State(self.state).name.lower()
        except ValueError:
            return f"unknown({self.state})"

    @property
    def error_name(self) -> str:
        return ERROR_NAMES.get(self.last_error, f"unknown({self.last_error})")

    def has(self, flag: int) -> bool:
        return bool(self.flags & flag)

    @property
    def speaker_ok(self) -> bool:
        return self.has(Flag.SPEAKER_OK)


@dataclass
class XferStart:
    type: int
    xfer_id: int
    total_len: int
    chunk_len: int
    n_chunks: int
    crc32: int
    width: int
    height: int
    seq_flags: int

    FMT = "<BHIHHIHHB"
    SIZE = 20

    @classmethod
    def unpack(cls, b: bytes) -> "XferStart":
        return cls(*struct.unpack(cls.FMT, bytes(b[: cls.SIZE])))

    def pack(self) -> bytes:
        return struct.pack(
            self.FMT, self.type, self.xfer_id, self.total_len, self.chunk_len, self.n_chunks,
            self.crc32, self.width, self.height, self.seq_flags,
        )


def is_xfer_end(b: bytes) -> bool:
    return len(b) >= 3 and b[0] == XferType.END


def xfer_end_id(b: bytes) -> int:
    return struct.unpack_from("<H", b, 1)[0]


def pack_xfer_end(xfer_id: int) -> bytes:
    return struct.pack("<BH", XferType.END, xfer_id)


def unpack_chunk(b: bytes) -> tuple[int, int, bytes]:
    xfer_id, idx = struct.unpack_from("<HH", b, 0)
    return xfer_id, idx, bytes(b[4:])


def pack_chunk(xfer_id: int, idx: int, payload: bytes) -> bytes:
    return struct.pack("<HH", xfer_id, idx) + payload


class TransferAssembler:
    """Reassembles a chunked transfer; tells you which chunks to ask for again."""

    def __init__(self, start: XferStart):
        self.start = start
        self.chunks: dict[int, bytes] = {}

    def add(self, idx: int, payload: bytes) -> None:
        if 0 <= idx < self.start.n_chunks:
            self.chunks[idx] = payload

    @property
    def missing(self) -> list[int]:
        return [i for i in range(self.start.n_chunks) if i not in self.chunks]

    @property
    def complete(self) -> bool:
        return not self.missing

    @property
    def progress(self) -> float:
        return len(self.chunks) / max(1, self.start.n_chunks)

    def assemble(self) -> bytes:
        if not self.complete:
            raise ValueError(f"missing {len(self.missing)} chunks")
        data = b"".join(self.chunks[i] for i in range(self.start.n_chunks))
        data = data[: self.start.total_len]
        if len(data) != self.start.total_len:
            raise ValueError(f"length mismatch {len(data)} != {self.start.total_len}")
        if crc32(data) != self.start.crc32:
            raise ValueError("crc mismatch")
        return data


def split_for_transfer(data: bytes, chunk_len: int) -> list[bytes]:
    return [data[i : i + chunk_len] for i in range(0, len(data), chunk_len)] or [b""]
