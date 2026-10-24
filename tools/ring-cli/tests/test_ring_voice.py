"""Ring: events, cues, voice config and speaker streaming over a fake bleak client."""
import asyncio

from mcring_core import proto

from mcring_cli.ring import Ring


class FakeClient:
    is_connected = True

    def __init__(self):
        self.writes: list[tuple[str, bytes]] = []

    async def write_gatt_char(self, uuid, data, response=False):
        self.writes.append((uuid, bytes(data)))


def make_ring(on_event=None):
    r = Ring("00:11", lambda t: asyncio.sleep(0), None, on_event)
    r.client = FakeClient()
    r._write_size = 182
    return r


def test_events_dispatch_and_wait():
    seen = []
    r = make_ring(seen.append)

    async def run():
        waiter = asyncio.ensure_future(r.wait_event(proto.Event.BUTTON_UP, 1.0))
        await asyncio.sleep(0)
        r._on_event(None, bytearray(proto.pack_event(proto.Event.BUTTON_DOWN, 0, 1000)))
        r._on_event(None, bytearray(proto.pack_event(proto.Event.BUTTON_UP, 12, 2200)))
        ev = await waiter
        assert ev.event == proto.Event.BUTTON_UP and ev.arg == 12 and ev.t_ms == 2200
        assert await r.wait_event(proto.Event.AUDIO_DONE, 0.01) is None

    asyncio.run(run())
    assert [e.name for e in seen] == ["button_down", "button_up"]
    assert r.last_event.name == "button_up"


def test_cue_and_voice_config_writes():
    r = make_ring()

    async def run():
        await r.cue(proto.Cue.ANSWER_READY)
        await r.apply_voice_config(200, 3, 1)
        await r.record_start()
        await r.record_stop()

    asyncio.run(run())
    w = r.client.writes
    assert w[0] == (proto.UUID_FEEDBACK, proto.fb_cue(proto.Cue.ANSWER_READY))
    assert w[1] == (proto.UUID_CONTROL, proto.set_config(proto.Cfg.SPEAKER_VOLUME, 200))
    assert w[2] == (proto.UUID_CONTROL, proto.set_config(proto.Cfg.CUES_MASK, 3))
    assert w[3] == (proto.UUID_CONTROL, proto.set_config(proto.Cfg.MIC_SOURCE_HINT, 1))
    assert w[4] == (proto.UUID_CONTROL, proto.record_start())
    assert w[5] == (proto.UUID_CONTROL, proto.record_stop())


def test_stream_audio_frames_and_waits_for_audio_done():
    r = make_ring()
    adpcm = bytes((i & 255) for i in range(proto.ADPCM_BLOCK_BYTES * 10))

    async def run():
        task = asyncio.ensure_future(r.stream_audio(adpcm, volume=180))
        # Wait until AUDIO_END went out, then the ring reports it drained.
        for _ in range(200):
            await asyncio.sleep(0.005)
            if any(d[0] == proto.Ao.END for u, d in r.client.writes if u == proto.UUID_AUDIO_OUT):
                break
        r._on_event(None, bytearray(proto.pack_event(proto.Event.AUDIO_DONE, 0, 5000)))
        return await task

    outcome = asyncio.run(run())
    assert outcome == "done"
    audio = [d for u, d in r.client.writes if u == proto.UUID_AUDIO_OUT]
    assert audio[0] == proto.audio_start(16000, proto.AUDIO_CODEC_ADPCM, 180)
    assert audio[-1] == proto.audio_end()
    assert len(audio) == 12                                      # start + 10 blocks (1/write at MTU 185) + end
    assert all(len(d) <= 182 for d in audio)
    assert b"".join(b"".join(proto.unpack_audio_data(d)[1]) for d in audio[1:-1]) == adpcm


def test_stop_audio_cancels_and_flushes():
    r = make_ring()
    adpcm = bytes(proto.ADPCM_BLOCK_BYTES * 300)                 # ~4.8 s: long enough to be mid-stream

    async def run():
        task = asyncio.ensure_future(r.stream_audio(adpcm))
        await asyncio.sleep(0.05)
        await r.stop_audio()
        return await task

    assert asyncio.run(run()) == "cancelled"
    audio = [d for u, d in r.client.writes if u == proto.UUID_AUDIO_OUT]
    assert audio[-1] == proto.audio_stop()
    assert not any(d[0] == proto.Ao.END for d in audio)
