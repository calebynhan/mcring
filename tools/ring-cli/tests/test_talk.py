"""Companion (shared by `talk` and `listen`): photo/voice pairing, cues, speaker streaming, Morse opt-in. No BLE, no HTTP."""
import asyncio
import time
import types

from mcring_core import proto

from mcring_cli import cli, mic
from mcring_cli.backend_client import AskResult
from mcring_cli.ring import Transfer


class FakeRing:
    def __init__(self):
        self.calls = []

    async def flash(self, *a):
        self.calls.append(("flash",))

    async def cue(self, c):
        self.calls.append(("cue", int(c)))

    async def capture(self):
        self.calls.append(("capture",))

    async def stream_audio(self, data, volume=255):
        self.calls.append(("stream", len(data), volume))
        return "done"

    async def play_units(self, units, unit_ms, channels):
        self.calls.append(("units", len(units)))


class FakeBackend:
    def __init__(self, **extra):
        self.requests = []
        self.extra = extra

    def ask(self, image, question, mode, session, provider, **kw):
        self.requests.append({"image": image, "question": question, "mode": mode, "session": session, **kw})
        return AskResult(answer="It is a cup.", speech_text="It is a cup.", subject="cup", confidence=0.8, session_id="sess",
                         had_image=image is not None, **self.extra)


def args(**over):
    base = dict(question="", mode="identify", provider="", session="", language="en", speak=False, server_tts=False,
                voice="", ring_speaker=False, morse=False, wpm=15, overall_wpm=8, channels=3, beep=False, echo=False,
                save_dir="/tmp/mcring-test-captures", image=None, auto_photo=True, photo=True, ring_mic=True)
    base.update(over)
    return types.SimpleNamespace(**base)


def jpeg_transfer(data=b"\xff\xd8photo"):
    return Transfer(proto.XferStart(proto.XferType.JPEG, 1, len(data), 178, 1, proto.crc32(data), 320, 240, 1), data, 0.5)


def adpcm_transfer(blocks=5):
    data = bytes(proto.ADPCM_BLOCK_BYTES * blocks)
    return Transfer(proto.XferStart(proto.XferType.ADPCM, 2, len(data), 178, 1, proto.crc32(data), 0, 160, 1), data, 0.2)


def test_photo_alone_is_asked_and_ring_gets_cue(tmp_path):
    be, ring = FakeBackend(), FakeRing()
    comp = cli.Companion(args(save_dir=str(tmp_path)), be, ring)
    asyncio.run(comp.on_transfer(jpeg_transfer()))
    assert be.requests[0]["image"] == b"\xff\xd8photo" and be.requests[0]["mode"] == "identify"
    assert be.requests[0]["want_morse"] is False and be.requests[0]["speech_format"] == "mp3"
    assert ("cue", int(proto.Cue.ANSWER_READY)) in ring.calls and ("flash",) in ring.calls
    assert comp.session == "sess"


def test_long_press_photo_waits_for_the_ring_mic_clip(tmp_path):
    be, ring = FakeBackend(), FakeRing()
    comp = cli.Companion(args(save_dir=str(tmp_path)), be, ring)
    comp.on_event(proto.RingEvent(proto.Event.BUTTON_UP, 15, 1000))        # held 1.5 s → a clip is coming
    asyncio.run(comp.on_transfer(jpeg_transfer()))
    assert be.requests == []                                                # photo parked, not asked yet
    asyncio.run(comp.on_transfer(adpcm_transfer()))
    assert len(be.requests) == 1
    req = be.requests[0]
    assert req["image"] == b"\xff\xd8photo" and req["audio_name"] == "voice.adpcm" and len(req["audio"]) == 5 * 132


def test_ring_speaker_streams_adpcm_and_speech_format_follows_outputs(tmp_path):
    be = FakeBackend(speech_adpcm=bytes(132 * 4))
    ring = FakeRing()
    comp = cli.Companion(args(save_dir=str(tmp_path), ring_speaker=True, speak=True, server_tts=True), be, ring)
    asyncio.run(comp.ask(question="hello"))
    assert be.requests[0]["speech_format"] == "both" and be.requests[0]["want_speech"] is True
    assert be.requests[0]["mode"] == "chat"                                 # no photo, no session → chat
    assert ("stream", 132 * 4, 255) in ring.calls


def test_morse_is_opt_in(tmp_path):
    be = FakeBackend(morse_units=[1, 1, 3], morse_unit_ms=80, short="R CUP")
    ring = FakeRing()
    comp = cli.Companion(args(save_dir=str(tmp_path)), be, ring)
    asyncio.run(comp.ask(question="x"))
    assert not any(c[0] == "units" for c in ring.calls)
    comp = cli.Companion(args(save_dir=str(tmp_path), morse=True), be, ring)
    asyncio.run(comp.ask(question="x"))
    assert be.requests[-1]["want_morse"] is True and ("units", 3) in ring.calls


def test_photo_for_turn_captures_when_nothing_fresh(tmp_path):
    be, ring = FakeBackend(), FakeRing()
    comp = cli.Companion(args(save_dir=str(tmp_path)), be, ring)

    async def run():
        task = asyncio.ensure_future(comp.photo_for_turn())
        await asyncio.sleep(0.01)
        assert ("capture",) in ring.calls
        await comp.on_transfer(jpeg_transfer(b"\xff\xd8new"))
        return await task

    assert asyncio.run(run()) == b"\xff\xd8new"
    assert be.requests == []                                                # claimed by the turn, not auto-asked
    comp.last_photo = (b"old", time.time() - 60)
    comp.session = "s"                                                      # static image no longer substitutes
    assert comp.fresh_photo() is None


def test_backend_error_cues_error(tmp_path):
    class Boom:
        def ask(self, *a, **k):
            raise RuntimeError("502")

    ring = FakeRing()
    comp = cli.Companion(args(save_dir=str(tmp_path)), Boom(), ring)
    assert asyncio.run(comp.ask(question="x")) is None
    assert ("cue", int(proto.Cue.ERROR)) in ring.calls


def test_parser_defaults_are_voice_first():
    p = cli.build_parser()
    a = p.parse_args(["listen"])
    assert a.speak is True and a.morse is False and a.ring_speaker is False and a.cues == 3 and a.volume == 200
    a = p.parse_args(["talk", "--ring-mic", "--ring-speaker", "--quiet", "--mode", "chat"])
    assert a.ring_mic and a.ring_speaker and a.speak is False and a.mode == "chat"
    a = p.parse_args(["ask", "x.jpg", "--morse", "--speech-format", "adpcm16k"])
    assert a.morse and a.speech_format == "adpcm16k" and a.speak is False
    a = p.parse_args(["config", "speaker_volume", "200"])
    assert a.key == "speaker_volume"
    a = p.parse_args(["say", "hi", "--ring-speaker"])
    assert a.ring_speaker
    a = p.parse_args(["listen", "--speak", "--echo"])            # the old documented invocation still parses
    assert a.speak is True and a.echo is True


def test_format_event():
    assert cli.format_event(proto.RingEvent(proto.Event.BUTTON_UP, 12, 1500)) == "event button_up held 1.2 s (ask)  t=1.5s"
    assert "photo" in cli.format_event(proto.RingEvent(proto.Event.BUTTON_UP, 3, 0))
    assert "discarded" in cli.format_event(proto.RingEvent(proto.Event.REC_STOPPED, 0, 0))


def test_mic_wav_header_and_missing_dependency(monkeypatch):
    wav = mic.pcm_bytes_to_wav(b"\x00\x01" * 16000)
    assert wav[:4] == b"RIFF" and wav[8:12] == b"WAVE" and len(wav) == 44 + 32000
    assert int.from_bytes(wav[24:28], "little") == 16000 and int.from_bytes(wav[22:24], "little") == 1
    import sys

    monkeypatch.setitem(sys.modules, "sounddevice", None)                   # makes `import sounddevice` fail
    assert mic.is_available() is False
    r = mic.Recorder()
    try:
        r.start()
    except mic.MicUnavailable as e:
        assert "ring-mic" in str(e)
    else:
        raise AssertionError("expected MicUnavailable")
