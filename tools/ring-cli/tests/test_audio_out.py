import asyncio

from mcring_core import proto

from mcring_cli.audio_out import AudioPacer, PacerOptions, adpcm_duration_ms, stream_adpcm, whole_blocks

BLOCK = proto.ADPCM_BLOCK_BYTES


def clip(blocks: int) -> bytes:
    return bytes((i & 255) for i in range(blocks * BLOCK))


def drive(adpcm: bytes, max_write: int, volume: int = 200):
    """Deterministic driver: the fake clock only advances through sleep()."""
    state = {"now": 1000.0}
    writes, sleeps, leads = [], [], []
    opts = PacerOptions(max_write=max_write)
    shadow = AudioPacer(opts, lambda: state["now"])

    async def write(pkt: bytes):
        writes.append(pkt)
        if pkt[0] == proto.Ao.DATA:
            n = (len(pkt) - proto.AUDIO_DATA_HDR_LEN) // BLOCK
            leads.append(shadow.lead() + n)
            shadow.mark_sent(n)

    async def sleep(ms: float):
        sleeps.append(ms)
        state["now"] += ms

    res = asyncio.run(stream_adpcm(write, adpcm, volume, opts, sleep=sleep, now_ms=lambda: state["now"]))
    return res, writes, sleeps, leads, opts


def test_framing_one_block_per_write_at_ios_mtu():
    res, writes, _, _, _ = drive(clip(50), 182)
    assert writes[0] == proto.audio_start(16000, proto.AUDIO_CODEC_ADPCM, 200)
    assert writes[-1] == proto.audio_end()
    data = writes[1:-1]
    assert len(data) == 50
    for i, w in enumerate(data):
        seq, blocks = proto.unpack_audio_data(w)
        assert seq == i and len(blocks) == 1 and len(w) <= 182
    assert (res.blocks, res.total_blocks, res.cancelled, res.writes) == (50, 50, False, 52)


def test_three_blocks_per_write_at_mtu_517_round_trips():
    adpcm = clip(10)
    _, writes, _, _, _ = drive(adpcm, 514)
    data = writes[1:-1]
    assert len(data) == 4                      # 3+3+3+1
    assert len(data[0]) == proto.AUDIO_DATA_HDR_LEN + 3 * BLOCK
    joined = b"".join(b"".join(proto.unpack_audio_data(w)[1]) for w in data)
    assert joined == adpcm


def test_pacing_keeps_ring_queue_bounded_and_bursty():
    total = 200                                # 3.2 s of speech
    res, _, sleeps, leads, o = drive(clip(total), 182)
    assert sleeps                                               # it did pace
    assert max(leads) <= proto.AUDIO_PREBUFFER_BLOCKS           # never beyond the ring's guaranteed buffer
    assert max(leads[o.prebuffer_blocks:]) <= o.max_lead_blocks  # and with headroom once playback runs
    assert o.max_lead_blocks < proto.AUDIO_PREBUFFER_BLOCKS
    assert len(sleeps) < total - o.prebuffer_blocks             # bursts, not one await per block
    assert max(sleeps) >= o.burst_blocks * 16 - 16
    slept = sum(sleeps)
    assert slept <= adpcm_duration_ms(clip(total))
    assert slept + res.remaining_ms >= adpcm_duration_ms(clip(total)) - o.prebuffer_blocks * 16 - 16


def test_pacer_reanchors_after_a_stall():
    state = {"now": 0.0}
    p = AudioPacer(PacerOptions(max_write=182, prebuffer_blocks=4, max_lead_blocks=8, burst_blocks=2), lambda: state["now"])
    for _ in range(8):
        assert p.delay_before(1) == 0
        p.mark_sent(1)
    assert p.lead() == 8 and p.delay_before(1) > 0
    state["now"] += 10_000                      # the laptop slept for 10 s: the ring drained everything
    assert p.lead() == 0
    for _ in range(8):
        assert p.delay_before(1) == 0           # refill quickly …
        p.mark_sent(1)
    assert p.delay_before(1) > 0                # … then pace again


def test_short_and_ragged_clips_and_cancel():
    res, writes, _, _, _ = drive(clip(3), 182)
    assert res.blocks == 3 and len(writes) == 5
    ragged = clip(2) + b"\x01\x02\x03"
    assert len(whole_blocks(ragged)) == 2 * BLOCK
    assert drive(ragged, 182)[0].blocks == 2

    flag = {"cancel": False}
    writes = []

    async def write(pkt):
        writes.append(pkt)
        if len(writes) == 10:
            flag["cancel"] = True

    async def nosleep(ms):
        pass

    res = asyncio.run(stream_adpcm(write, clip(40), 255, PacerOptions(max_write=182), sleep=nosleep, cancelled=lambda: flag["cancel"]))
    assert res.cancelled and len(writes) == 10 and not any(w[0] == proto.Ao.END for w in writes)
