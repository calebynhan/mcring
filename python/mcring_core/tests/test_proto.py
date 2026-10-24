import struct
import subprocess
import zlib

import pytest

from mcring_core import proto


def test_uuids():
    assert proto.UUID_SERVICE == "7a3b0001-9c2e-4f3a-b1d4-6d6372696e67"
    assert bytes.fromhex("6d6372696e67") == b"mcring"


def test_control_packets():
    assert proto.capture(12, 2) == b"\x01\x0c\x02"
    assert proto.ack_transfer(7) == b"\x02\x07\x00\x00\x00\x00"
    assert proto.ack_transfer(7, [1, 300]) == b"\x02\x07\x00\x01\x02\x00\x01\x00\x2c\x01"
    assert proto.ack_transfer(7, abort=True)[3] == 2
    assert proto.set_config(proto.Cfg.MORSE_WPM, -1) == b"\x03\x07\xff\xff\xff\xff"
    assert proto.record_audio(99) == b"\x06\x08"


def test_feedback_packets():
    p = proto.fb_morse_text("SOS", 15, proto.Channel.LED | proto.Channel.HAPTIC)
    assert p == b"\x10\x0f\x03\x03SOS"
    p = proto.fb_pattern([1, 3, 1], 80, proto.Channel.HAPTIC)
    assert p == b"\x11\x50\x02\x03\x01\x03\x01"
    assert proto.fb_rgb(1, 2, 3, 500) == b"\x13\x01\x02\x03\xf4\x01"


def test_morse_units_split():
    units = list(range(1, 201)) * 3  # 600 units
    units = [min(255, u) for u in units]
    writes = proto.fb_morse_units(units, 80, 3, max_write=100)
    assert writes[0][0] == proto.Fb.MORSE_UNITS
    assert struct.unpack_from("<H", writes[0], 3)[0] == 600
    assert all(w[0] == proto.Fb.MORSE_UNITS_CONT for w in writes[1:])
    assert all(len(w) <= 100 for w in writes)
    # reassemble
    buf = bytearray(600)
    first = writes[0][5:]
    buf[: len(first)] = first
    for w in writes[1:]:
        off = struct.unpack_from("<H", w, 1)[0]
        buf[off : off + len(w) - 3] = w[3:]
    assert list(buf) == units


def test_status_roundtrip():
    s = proto.Status(1, proto.State.TRANSFERRING, 3812, 77, proto.Status and 0x22, 1234, 0, 1)
    b = s.pack()
    assert len(b) == proto.Status.SIZE == 12
    s2 = proto.Status.unpack(b)
    assert s2 == s
    assert s2.state_name == "transferring"


def test_xfer_roundtrip_and_assembler():
    data = bytes(range(256)) * 40  # 10240 bytes
    chunk_len = proto.chunk_len_for_mtu(185)
    assert chunk_len == 178
    chunks = proto.split_for_transfer(data, chunk_len)
    start = proto.XferStart(proto.XferType.JPEG, 5, len(data), chunk_len, len(chunks), proto.crc32(data), 320, 240, 1)
    b = start.pack()
    assert len(b) == 20
    assert proto.XferStart.unpack(b) == start
    asm = proto.TransferAssembler(start)
    for i, c in enumerate(chunks):
        if i not in (3, 17):
            asm.add(*proto.unpack_chunk(proto.pack_chunk(5, i, c))[1:])
    assert asm.missing == [3, 17]
    assert not asm.complete
    with pytest.raises(ValueError):
        asm.assemble()
    asm.add(3, chunks[3])
    asm.add(17, chunks[17])
    assert asm.assemble() == data
    assert proto.is_xfer_end(proto.pack_xfer_end(5)) and proto.xfer_end_id(proto.pack_xfer_end(5)) == 5


def test_chunk_len_bounds():
    assert proto.chunk_len_for_mtu(23) == 16
    assert proto.chunk_len_for_mtu(517) == 510
    assert proto.chunk_len_for_mtu(10000) == 510


def test_crc_matches_c(c_tool):
    data = b"mcring" * 1000 + bytes(range(256))
    out = subprocess.run([str(c_tool), "crc"], input=data, capture_output=True, check=True).stdout
    assert int(out.strip(), 16) == zlib.crc32(data) & 0xFFFFFFFF == proto.crc32(data)
