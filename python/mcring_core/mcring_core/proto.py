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

ATT_HDR_LEN = 3
XFER_CHUNK_HDR_LEN = 4


class Op(IntEnum):
    CAPTURE = 0x01
    ACK_TRANSFER = 0x02
    SET_CONFIG = 0x03
    PING = 0x04
    ABORT = 0x05
    RECORD_AUDIO = 0x06
    SLEEP = 0x07
    GET_STATUS = 0x08


class Fb(IntEnum):
    MORSE_TEXT = 0x10
    PATTERN = 0x11
    STOP = 0x12
    RGB = 0x13
    MORSE_UNITS = 0x14
    MORSE_UNITS_CONT = 0x15


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
    MORSE_WPM = 7
    FEEDBACK_CHANNELS = 8


class State(IntEnum):
    IDLE = 0
    CAPTURING = 1
    TRANSFERRING = 2
    RECORDING = 3
    FEEDBACK = 4
    ERROR = 5


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


# ---- Ring -> phone -----------------------------------------------------------

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
