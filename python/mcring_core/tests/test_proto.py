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


# ---- voice-first additions (events, audio out, record start/stop, new keys) ----------------

def test_new_uuids_and_constants():
    assert proto.UUID_EVENTS == "7a3b0007-9c2e-4f3a-b1d4-6d6372696e67"
    assert proto.UUID_AUDIO_OUT == "7a3b0008-9c2e-4f3a-b1d4-6d6372696e67"
    assert proto.Op.RECORD_START == 0x09 and proto.Op.RECORD_STOP == 0x0A
    assert (proto.Ao.START, proto.Ao.DATA, proto.Ao.END, proto.Ao.STOP) == (0x20, 0x21, 0x22, 0x23)
    assert proto.Cfg.SPEAKER_VOLUME == 9 and proto.Cfg.CUES_MASK == 10 and proto.Cfg.MIC_SOURCE_HINT == 11
    assert proto.Flag.SPEAKER_OK == 0x40
    assert [int(e) for e in proto.Event] == list(range(1, 12))
    from mcring_core import adpcm
    assert proto.ADPCM_BLOCK_BYTES == adpcm.BLOCK_BYTES == 132


def test_record_and_cue_packets():
    assert proto.record_start() == b"\x09"
    assert proto.record_stop() == b"\x0a"
    assert proto.get_status() == b"\x08"
    assert proto.fb_cue(proto.Cue.ANSWER_READY) == b"\x16\x02"
    assert proto.set_config(proto.Cfg.MIC_SOURCE_HINT, proto.MicSource.PHONE) == b"\x03\x0b\x01\x00\x00\x00"
    assert proto.set_config(proto.Cfg.CUES_MASK, proto.Cues.HAPTIC | proto.Cues.LED) == b"\x03\x0a\x03\x00\x00\x00"


def test_event_roundtrip():
    b = proto.pack_event(proto.Event.BUTTON_UP, 23, 0x01020304)
    assert b == b"\x02\x17\x04\x03\x02\x01" and len(b) == proto.EVENT_LEN == 6
    e = proto.unpack_event(b)
    assert e == proto.RingEvent(2, 23, 0x01020304)
    assert e.name == "button_up"
    assert proto.unpack_event(b"\x63\x00\x00\x00\x00\x00").name == "unknown(99)"
    # extra trailing bytes are tolerated (future extensions)
    assert proto.unpack_event(b + b"\xff").arg == 23


def test_audio_start_packets():
    assert proto.audio_start() == b"\x20\xa0\x00\x02\xff"
    assert proto.audio_start(8000, 2, 128) == b"\x20\x50\x00\x02\x80"
    a = proto.AudioStart.unpack(proto.audio_start(16000, 2, 200))
    assert a.sample_rate == 16000 and a.codec == 2 and a.volume == 200
    with pytest.raises(ValueError):
        proto.AudioStart.unpack(proto.audio_end() + b"\x00\x00\x00\x00")
    assert proto.audio_end() == b"\x22" and proto.audio_stop() == b"\x23"


def test_audio_data_split_whole_blocks():
    blocks = bytes(range(256)) * 10  # 2560 bytes: not a multiple of 132
    with pytest.raises(ValueError):
        proto.audio_data_writes(blocks)
    adpcm = bytes((i * 7) & 0xFF for i in range(132 * 10))  # 10 blocks
    # iOS-sized writes: 1 block each
    w = proto.audio_data_writes(adpcm, max_write=182)
    assert len(w) == 10 and all(len(x) == 135 for x in w)
    assert w[0][:3] == b"\x21\x00\x00" and w[9][:3] == b"\x21\x09\x00"
    # Android-sized writes: 3 blocks each, last one short
    w = proto.audio_data_writes(adpcm, max_write=proto.max_write_for_mtu(517), seq_start=65534)
    assert proto.audio_blocks_per_write(514) == 3
    assert [len(x) for x in w] == [3 + 3 * 132] * 3 + [3 + 132]
    assert [struct.unpack_from("<H", x, 1)[0] for x in w] == [65534, 65535, 0, 1]  # seq wraps
    assert all(len(x) <= 514 for x in w)
    # reassemble
    out = b"".join(b"".join(proto.unpack_audio_data(x)[1]) for x in w)
    assert out == adpcm
    assert proto.unpack_audio_data(w[0])[0] == 65534
    with pytest.raises(ValueError):
        proto.unpack_audio_data(b"\x21\x00\x00" + b"\x00" * 131)
    seq = proto.audio_out_sequence(adpcm, max_write=182, volume=180)
    assert seq[0] == proto.audio_start(16000, 2, 180) and seq[-1] == proto.audio_end() and len(seq) == 12
    # tiny MTU still produces one block per write
    assert proto.audio_blocks_per_write(20) == 1


def test_status_speaker_flag():
    s = proto.Status(1, 0, 3800, 50, proto.Flag.SPEAKER_OK | proto.Flag.MIC_OK, 1, 0, 0)
    assert s.speaker_ok and s.has(proto.Flag.MIC_OK) and not s.has(proto.Flag.CAMERA_OK)


def test_event_and_audio_start_match_c(c_tool):
    out = subprocess.run([str(c_tool), "event", "6", "2", "123456789"], capture_output=True, text=True, check=True).stdout
    assert bytes.fromhex(out.strip()) == proto.pack_event(proto.Event.CAPTURE_DONE, 2, 123456789)
    out = subprocess.run([str(c_tool), "event", "255", "255", "4294967295"], capture_output=True, text=True, check=True).stdout
    assert bytes.fromhex(out.strip()) == proto.pack_event(255, 255, 0xFFFFFFFF)
    pkt = proto.audio_start(16000, 2, 77)
    out = subprocess.run([str(c_tool), "start", pkt.hex()], capture_output=True, text=True, check=True).stdout
    assert out.split() == ["16000", "2", "77"]
    out = subprocess.run([str(c_tool), "start", proto.audio_end().hex()], capture_output=True, text=True, check=True).stdout
    assert out.strip() == "err"
    # C encoder for the START packet matches Python too
    out = subprocess.run([str(c_tool), "mkstart", "16000", "2", "77"], capture_output=True, text=True, check=True).stdout
    assert bytes.fromhex(out.strip()) == pkt
