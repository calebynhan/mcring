import asyncio

from mcring_core import proto

from mcring_cli import cli


def test_morse_hex(capsys):
    assert cli.main(["morse", "e", "--wpm", "15", "--overall-wpm", "15", "--hex"]) == 0
    out = capsys.readouterr().out.strip().splitlines()[-1]
    # opcode 0x14, unit_ms 80 (0x50), channels 3, n=1 (LE u16), one dot
    assert out == "145003010001"


def test_play_ring_packet_resplits(monkeypatch):
    """A backend packet is re-split into MTU-sized writes with correct offsets."""
    from mcring_cli.ring import Ring

    writes = []

    class FakeClient:
        is_connected = True

        async def write_gatt_char(self, uuid, data, response=False):
            writes.append(bytes(data))

    r = Ring("00:11", lambda t: asyncio.sleep(0))
    r.client = FakeClient()
    r._write_size = 50
    units = [1, 3] * 100
    pkt = proto.fb_morse_units(units, 80, 3, max_write=65535)[0]
    asyncio.run(r.play_ring_packet(pkt))
    assert writes[0][0] == proto.Fb.MORSE_UNITS and all(len(w) <= 50 for w in writes)
    buf = bytearray(len(units))
    buf[: len(writes[0]) - 5] = writes[0][5:]
    for w in writes[1:]:
        off = int.from_bytes(w[1:3], "little")
        buf[off : off + len(w) - 3] = w[3:]
    assert list(buf) == units


def test_transfer_reassembly_and_ack():
    from mcring_cli.ring import Ring

    got = {}
    acks = []

    async def on_transfer(t):
        got["data"] = t.data

    class FakeClient:
        is_connected = True

        async def write_gatt_char(self, uuid, data, response=False):
            acks.append(bytes(data))

    r = Ring("00:11", on_transfer)
    r.client = FakeClient()
    data = bytes(range(256)) * 10
    chunks = proto.split_for_transfer(data, 178)
    start = proto.XferStart(proto.XferType.JPEG, 3, len(data), 178, len(chunks), proto.crc32(data), 320, 240, 1)

    async def run():
        r._on_meta(None, bytearray(start.pack()))
        for i, c in enumerate(chunks):
            if i != 4:
                r._on_data(None, bytearray(proto.pack_chunk(3, i, c)))
        await r._finish(3)                       # missing chunk 4 → NACK
        assert acks[-1] == proto.ack_transfer(3, [4])
        r._on_data(None, bytearray(proto.pack_chunk(3, 4, chunks[4])))
        await r._finish(3)
        assert acks[-1] == proto.ack_transfer(3)

    asyncio.run(run())
    assert got["data"] == data
