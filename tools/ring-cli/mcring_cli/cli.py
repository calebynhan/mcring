"""mcring desktop companion — voice-first.

  mcring talk    --backend http://localhost:8000     # push-to-talk from the keyboard (or the ring button) → hear the answer
  mcring listen  --backend http://localhost:8000     # bridge: ring photos / voice clips → backend → spoken answer + ring cues
  mcring ask     photo.jpg -q "what is this?"        # no ring: run the LLM loop on a file (and/or an --audio clip)
  mcring say     "hello from the ring" --ring-speaker  # text → speech on this computer or on the ring speaker
  mcring events                                      # print ring events (button, taps, record, audio) and status
  mcring scan                                        # list rings in range
  mcring config  speaker_volume 200                  # SET_CONFIG on the ring (speaker_volume, cues_mask, mic_source_hint, ...)
  mcring morse   "FOXGLOVE TOXIC" --beep             # legacy silent pattern: play Morse locally
  mcring send    "R TOXIC"                           # legacy silent pattern: play Morse on the ring

Audio: the ring talks BLE to this computer; the answer plays on the computer's speakers / headphones (OS TTS or the
server's mp3) and optionally on the ring speaker (--ring-speaker streams 16 kHz ADPCM). The ring itself only plays
short confirmation cues (listening tick, answer-ready double tick, error buzz).
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import pathlib
import subprocess
import sys
import tempfile
import time

from mcring_core import adpcm, morse, proto

from . import mic
from .backend_client import MODES, AskResult, BackendClient, audio_mime_for, save_capture
from .player import play_units

log = logging.getLogger("mcring")

FRESH_PHOTO_S = 20.0      # a photo this recent is "what I am looking at"
EXPECT_VOICE_S = 15.0     # after a long press with the ring mic, its clip arrives within this long
PHOTO_WAIT_S = 4.0        # how long a voice turn waits for the photo it asked the ring for
LONG_PRESS_TENTHS = 7     # BUTTON_UP.arg below this = short press (photo), else "ask"
MIN_CLIP_BYTES = 44 + int(16000 * 2 * 0.3)   # WAV shorter than 300 ms = accidental tap


# ---------------------------------------------------------------------------
# local output
# ---------------------------------------------------------------------------
def speak_local(text: str, mp3: bytes | None = None) -> None:
    """Best-effort local speech: play the server mp3 if given, else the OS text-to-speech, else print."""
    try:
        if mp3:
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                f.write(mp3)
            for cmd in (["afplay", f.name], ["mpg123", "-q", f.name], ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", f.name]):
                try:
                    subprocess.run(cmd, check=True, timeout=120)
                    return
                except (FileNotFoundError, subprocess.CalledProcessError):
                    continue
        for cmd in (["say", text], ["espeak-ng", text], ["espeak", text], ["spd-say", "--wait", text]):
            try:
                subprocess.run(cmd, check=True, timeout=120)
                return
            except (FileNotFoundError, subprocess.CalledProcessError):
                continue
    except Exception as e:  # noqa: BLE001
        log.debug("speech failed: %s", e)
    print(f"🔈 {text}")


def print_answer(res: AskResult) -> None:
    conf = f"{res.confidence:.0%}"
    head = res.subject or res.mode or "answer"
    print(f"\n{head}  [{conf}]  via {res.model or res.provider} in {res.latency_ms} ms{'  (photo)' if res.had_image else ''}")
    if res.transcript:
        print(f"  you   : {res.transcript}")
    if res.transcript_error:
        print(f"  (transcription failed: {res.transcript_error})")
    print(f"  claude: {res.answer}")
    if res.follow_up:
        print(f"          {res.follow_up}")
    for w in res.warnings:
        print(f"  ⚠ {w}")
    if res.speech_error:
        print(f"  (speech: {res.speech_error})")
    if res.short:
        print(f"  pattern: {res.short}")


def format_event(ev: proto.RingEvent) -> str:
    hint = ""
    if ev.event == proto.Event.BUTTON_UP:
        hint = f" held {ev.arg / 10:.1f} s ({'ask' if ev.arg >= LONG_PRESS_TENTHS else 'photo'})"
    elif ev.event == proto.Event.REC_STOPPED:
        hint = f" {ev.arg / 10:.1f} s" if ev.arg else " (discarded)"
    elif ev.event == proto.Event.REC_STARTED:
        hint = f" max {ev.arg} s"
    elif ev.event == proto.Event.CAPTURE_DONE:
        hint = f" queued={ev.arg}" if ev.arg else " FAILED"
    elif ev.event == proto.Event.LOW_BATTERY:
        hint = f" {ev.arg}%"
    elif ev.event == proto.Event.AUDIO_DONE:
        hint = " (drained)" if ev.arg == 0 else " (stopped)"
    return f"event {ev.name}{hint}  t={ev.t_ms / 1000:.1f}s"


# ---------------------------------------------------------------------------
# the voice turn shared by `talk` and `listen`
# ---------------------------------------------------------------------------
class Companion:
    """Keeps the latest photo, runs /v1/ask, speaks the answer locally and/or on the ring, cues the ring."""

    def __init__(self, a, client: BackendClient, ring=None):
        self.a = a
        self.client = client
        self.ring = ring
        self.session: str = getattr(a, "session", "") or ""
        self.last_photo: tuple[bytes, float] | None = None
        self.expect_voice_until = 0.0
        self.recording = False
        self.busy = False
        self.out_dir = pathlib.Path(getattr(a, "save_dir", "captures"))
        self.static_image: bytes | None = pathlib.Path(a.image).read_bytes() if getattr(a, "image", None) else None
        self._photo_waiters: list[asyncio.Future] = []

    # ---- photos --------------------------------------------------------------
    def fresh_photo(self) -> bytes | None:
        if self.static_image is not None and not self.session:
            return self.static_image            # a file stands in for the ring camera on the first turn
        if self.last_photo and time.time() - self.last_photo[1] < FRESH_PHOTO_S:
            return self.last_photo[0]
        return None

    async def wait_photo(self, timeout: float) -> bytes | None:
        fut: asyncio.Future = asyncio.get_running_loop().create_future()
        self._photo_waiters.append(fut)
        try:
            return await asyncio.wait_for(fut, timeout)
        except asyncio.TimeoutError:
            self._photo_waiters = [f for f in self._photo_waiters if f is not fut]
            return None

    async def photo_for_turn(self) -> bytes | None:
        """The fresh photo, or (visual modes, ring connected) a new one captured now."""
        img = self.fresh_photo()
        if img is not None or self.a.mode == "chat" or self.ring is None or not getattr(self.a, "photo", True):
            return img
        waiter = asyncio.ensure_future(self.wait_photo(PHOTO_WAIT_S))
        await self.ring.capture()
        return await waiter

    # ---- ring callbacks ------------------------------------------------------
    async def on_transfer(self, t) -> None:
        if t.start.type == proto.XferType.JPEG:
            p = save_capture(t.data, self.out_dir, ".jpg")
            log.info("saved %s", p)
            self.last_photo = (t.data, time.time())
            waiters, self._photo_waiters = self._photo_waiters, []
            for f in waiters:
                if not f.done():
                    f.set_result(t.data)
            if waiters or self.recording or time.time() < self.expect_voice_until:
                return                              # a voice turn will attach this photo
            if getattr(self.a, "auto_photo", True):
                await self.ask(image=t.data)        # photo alone: ask about it
        elif t.start.type == proto.XferType.ADPCM:
            wav = adpcm.adpcm_to_wav(t.data, t.start.height * 100 or 16000)
            p = save_capture(wav, self.out_dir, ".wav")
            log.info("saved voice %s", p)
            self.expect_voice_until = 0.0
            await self.ask(audio=t.data, audio_name="voice.adpcm", image=self.fresh_photo())

    def on_event(self, ev: proto.RingEvent) -> None:
        print(format_event(ev))
        if ev.event in (proto.Event.BUTTON_UP, proto.Event.DOUBLE_TAP) and getattr(self.a, "ring_mic", True):
            if ev.event == proto.Event.DOUBLE_TAP or ev.arg >= LONG_PRESS_TENTHS:
                self.expect_voice_until = time.time() + EXPECT_VOICE_S
        if ev.event == proto.Event.REC_STOPPED and ev.arg == 0:
            self.expect_voice_until = 0.0

    # ---- the turn ---------------------------------------------------------------
    def _speech_plan(self) -> tuple[bool | None, str, bool]:
        """(want_speech, speech_format, ring_speaker)"""
        ring_speaker = bool(getattr(self.a, "ring_speaker", False) and self.ring is not None)
        want_mp3 = bool(self.a.speak and getattr(self.a, "server_tts", False))
        fmt = "both" if (want_mp3 and ring_speaker) else ("adpcm16k" if ring_speaker else "mp3")
        return (True if (want_mp3 or ring_speaker) else False), fmt, ring_speaker

    async def ask(self, *, image: bytes | None = None, audio: bytes | None = None, audio_name: str = "voice.wav",
                  question: str | None = None) -> AskResult | None:
        if self.busy:
            print("(still answering the previous question)")
            return None
        self.busy = True
        a = self.a
        loop = asyncio.get_running_loop()
        try:
            if self.ring is not None:
                await self.ring.flash(0, 0, 60, 300)
            want_speech, fmt, ring_speaker = self._speech_plan()
            q = question if question is not None else a.question
            mode = a.mode if (image is not None or self.session) else "chat"
            try:
                res = await loop.run_in_executor(None, lambda: self.client.ask(
                    image, q, mode, self.session, a.provider, audio=audio, audio_name=audio_name,
                    want_speech=want_speech, speech_format=fmt, voice=getattr(a, "voice", ""), language=getattr(a, "language", "en"),
                    want_morse=getattr(a, "morse", False), char_wpm=getattr(a, "wpm", 15), overall_wpm=getattr(a, "overall_wpm", 8),
                    channels=getattr(a, "channels", 3)))
            except Exception as e:  # noqa: BLE001
                log.error("backend error: %s", e)
                if self.ring is not None:
                    await self.ring.cue(proto.Cue.ERROR)
                return None
            self.session = res.session_id
            print_answer(res)
            if self.ring is not None:
                await self.ring.cue(proto.Cue.ANSWER_READY)
            jobs = []
            if a.speak:
                mp3 = res.speech_mp3 if getattr(a, "server_tts", False) else None
                jobs.append(loop.run_in_executor(None, speak_local, res.speech_text, mp3))
            if ring_speaker:
                if res.speech_adpcm:
                    jobs.append(self.ring.stream_audio(res.speech_adpcm, 255))
                else:
                    print(f"  (ring speaker: no audio from the server{': ' + res.speech_error if res.speech_error else ''})")
            if getattr(a, "morse", False) and res.morse_units:
                if self.ring is not None:
                    jobs.append(self.ring.play_units(res.morse_units, res.morse_unit_ms, getattr(a, "channels", 3)))
                if getattr(a, "echo", False):
                    jobs.append(loop.run_in_executor(None, lambda: play_units(res.morse_units, res.morse_unit_ms, beep=getattr(a, "beep", False), label=res.short or "")))
            if jobs:
                for r in await asyncio.gather(*jobs, return_exceptions=True):
                    if isinstance(r, Exception):
                        log.warning("output failed: %s", r)
                    elif isinstance(r, str) and r not in ("done", None):
                        print(f"  (ring speaker: {r})")
            return res
        finally:
            self.busy = False


# ---------------------------------------------------------------------------
# commands
# ---------------------------------------------------------------------------
def cmd_ask(a) -> int:
    client = BackendClient(a.backend, a.token)
    image = pathlib.Path(a.image).read_bytes() if a.image else None
    audio = pathlib.Path(a.audio).read_bytes() if a.audio else None
    name = pathlib.Path(a.audio).name if a.audio else "voice.wav"
    want_mp3 = a.speak and a.server_tts
    fmt = a.speech_format or "mp3"
    res = client.ask(image, a.question, a.mode if image is not None or a.session else "chat", a.session, a.provider,
                     audio=audio, audio_name=name, audio_mime=audio_mime_for(name),
                     want_speech=True if (want_mp3 or fmt != "mp3") else None, speech_format=fmt, voice=a.voice,
                     language=a.language, want_morse=a.morse, char_wpm=a.wpm, overall_wpm=a.overall_wpm, channels=a.channels)
    print_answer(res)
    if a.speak:
        speak_local(res.speech_text, res.speech_mp3 if a.server_tts else None)
    if a.save_speech and (res.speech_adpcm or res.speech_mp3):
        p = pathlib.Path(a.save_speech)
        p.write_bytes(res.speech_adpcm if p.suffix == ".adpcm" and res.speech_adpcm else (res.speech_mp3 or b""))
        print(f"speech saved to {p}")
    if a.morse and res.morse_units:
        play_units(res.morse_units, res.morse_unit_ms, beep=a.beep, label=res.short or "")
    print(f"session: {res.session_id}")
    return 0


def cmd_morse(a) -> int:
    sp = morse.Spacing.farnsworth(a.wpm, a.overall_wpm) if a.overall_wpm < a.wpm else morse.Spacing()
    units, _ = morse.encode(a.text, sp)
    play_units(units, morse.unit_ms(a.wpm), beep=a.beep, label=morse.shorten_for_morse(a.text, 64))
    if a.hex:
        pkt = proto.fb_morse_units(units, morse.unit_ms(a.wpm), a.channels, max_write=65535)[0]
        print(pkt.hex())
    return 0


async def _scan(a) -> int:
    from bleak import BleakScanner

    devs = await BleakScanner.discover(timeout=a.timeout, return_adv=True)
    found = 0
    for d, adv in devs.values():
        name = d.name or adv.local_name or ""
        if name.startswith("mcring") or proto.UUID_SERVICE in [u.lower() for u in adv.service_uuids or []]:
            print(f"{d.address}  {name}  rssi={adv.rssi}")
            found += 1
    if not found:
        print("no ring found (is it advertising? try pressing the button to wake it)")
    return 0


async def _with_ring(a, on_transfer, on_status=None, on_event=None):
    from .ring import Ring, find_ring

    target = a.address or await find_ring(timeout=a.timeout)
    if not target:
        print("ring not found", file=sys.stderr)
        return None
    return Ring(target, on_transfer, on_status, on_event)


def _backend_or_exit(a) -> BackendClient | None:
    client = BackendClient(a.backend, a.token)
    try:
        h = client.health()
        log.info("backend ok: %s %s (tts=%s stt=%s)", h.get("provider"), h.get("model"), h.get("tts"), h.get("stt"))
    except Exception as e:  # noqa: BLE001
        print(f"backend not reachable at {a.backend}: {e}", file=sys.stderr)
        return None
    return client


async def _apply_voice_config(ring, a) -> None:
    try:
        await ring.apply_voice_config(a.volume, a.cues, 0 if getattr(a, "ring_mic", True) else 1)
    except Exception as e:  # noqa: BLE001
        log.warning("voice config not applied: %s", e)


async def _stdin_lines():
    loop = asyncio.get_running_loop()
    while True:
        line = await loop.run_in_executor(None, sys.stdin.readline)
        if not line:
            await asyncio.sleep(3600)
            continue
        yield line.rstrip("\n")


async def _talk(a) -> int:
    client = _backend_or_exit(a)
    if client is None:
        return 2
    if not a.ring_mic and not mic.is_available() and not a.no_ring:
        print("laptop mic unavailable (pip install 'mcring-cli[mic]') — falling back to --ring-mic", file=sys.stderr)
        a.ring_mic = True
    comp = Companion(a, client)
    ring = None
    if not a.no_ring:
        ring = await _with_ring(a, comp.on_transfer, None, comp.on_event)
        if ring is None and (a.ring_mic or a.ring_speaker):
            return 1
    if ring is None:
        if a.ring_mic:
            print("no ring: --ring-mic needs one", file=sys.stderr)
            return 1
        print("no ring — laptop mic + local speech only")
    comp.ring = ring
    recorder = mic.Recorder()
    if not a.ring_mic:
        try:
            recorder.start()
            recorder.cancel()                # fail early if the mic cannot be opened
        except mic.MicUnavailable as e:
            print(str(e), file=sys.stderr)
            return 1

    async def start_rec(origin: str):
        if comp.recording or comp.busy:
            return
        comp.recording = True
        if a.ring_mic:
            comp.expect_voice_until = time.time() + EXPECT_VOICE_S
            await ring.record_start()
        else:
            recorder.start()
            if ring is not None and origin != "ring":
                await ring.cue(proto.Cue.LISTENING)
        print("● recording… (Enter to stop)" if origin != "ring" else "● recording (release the button to ask)")

    async def stop_rec(cancel: bool = False):
        if not comp.recording:
            return
        comp.recording = False
        if a.ring_mic:
            await ring.record_stop()         # REC_STOPPED + ADPCM transfer follow → comp.on_transfer asks
            return
        wav = recorder.stop()
        if cancel or len(wav) < MIN_CLIP_BYTES:
            print("(recording discarded)")
            return
        print(f"■ {(len(wav) - 44) / 32000:.1f} s — asking…")
        image = await comp.photo_for_turn()
        await comp.ask(audio=wav, audio_name="voice.wav", image=image)

    def on_event(ev: proto.RingEvent):
        comp.on_event(ev)
        if a.ring_mic:
            return
        if ev.event == proto.Event.BUTTON_DOWN:
            asyncio.ensure_future(start_rec("ring"))
        elif ev.event == proto.Event.BUTTON_UP:
            asyncio.ensure_future(stop_rec(cancel=ev.arg < LONG_PRESS_TENTHS))   # short press = photo only
        elif ev.event == proto.Event.DOUBLE_TAP:
            asyncio.ensure_future(stop_rec() if comp.recording else start_rec("tap"))

    if ring is not None:
        ring.on_event = on_event

    async def loop_body():
        print("talk — Enter: start recording · Enter: stop & ask · c: photo · t <text>: ask by text · q: quit")
        if ring is not None:
            print(f"ring: hold the button to ask (short press = photo); mic = {'ring' if a.ring_mic else 'this computer'}; "
                  f"answers on {'ring speaker + ' if a.ring_speaker else ''}{'this computer' if a.speak else 'screen only'}")
        async for line in _stdin_lines():
            cmd = line.strip()
            low = cmd.lower()
            if low in ("", "r", "rec"):
                await (stop_rec() if comp.recording else start_rec("key"))
            elif low in ("c", "capture") and ring is not None:
                await ring.capture()
            elif low.startswith("t "):
                await comp.ask(question=cmd[2:].strip(), image=comp.fresh_photo())
            elif low in ("q", "quit", "exit"):
                return 0
            elif low in ("p", "ping") and ring is not None:
                await ring.ping()
            elif low in ("s", "stop"):
                if ring is not None:
                    await ring.stop_audio()
            else:
                print("Enter = record/stop · c = photo · t <text> · s = stop ring audio · q = quit")

    if ring is None:
        return await loop_body() or 0
    async with ring:
        await _apply_voice_config(ring, a)
        return await loop_body() or 0


async def _listen(a) -> int:
    client = _backend_or_exit(a)
    if client is None:
        return 2
    comp = Companion(a, client)
    ring = await _with_ring(a, comp.on_transfer, None, comp.on_event)
    if ring is None:
        return 1
    comp.ring = ring
    async with ring:
        await _apply_voice_config(ring, a)
        if a.morse:
            await ring.set_config(proto.Cfg.MORSE_WPM, a.wpm)
            await ring.set_config(proto.Cfg.FEEDBACK_CHANNELS, a.channels)
        print("listening — press the ring button (short = photo, hold = ask) or Ctrl-C. "
              "'c' + Enter captures, 'r' starts/stops a ring-mic recording, 't <text>' asks by text, 'q' quits.")
        async for line in _stdin_lines():
            cmd = line.strip()
            low = cmd.lower()
            if low in ("c", "capture"):
                await ring.capture()
            elif low in ("r", "rec"):
                comp.recording = not comp.recording
                if comp.recording:
                    comp.expect_voice_until = time.time() + EXPECT_VOICE_S
                    await ring.record_start()
                    print("● ring recording… ('r' to stop)")
                else:
                    await ring.record_stop()
            elif low in ("p", "ping"):
                await ring.ping()
            elif low.startswith("t "):
                await comp.ask(question=cmd[2:].strip(), image=comp.fresh_photo())
            elif low.startswith("say "):
                text = cmd[4:].strip()
                if a.ring_speaker:
                    data = await asyncio.get_running_loop().run_in_executor(None, lambda: client.speech(text, a.voice, "adpcm16k"))
                    print(f"  ring speaker: {await ring.stream_audio(data, 255)}")
                elif a.morse:
                    await ring.play_morse_text(text, a.wpm, a.channels)
                else:
                    print("(use --ring-speaker to play speech on the ring, or --morse for the legacy pattern)")
            elif low in ("q", "quit"):
                return 0


async def _say(a) -> int:
    client = BackendClient(a.backend, a.token)
    if not a.ring_speaker:
        mp3 = client.speech(a.text, a.voice, "mp3") if a.server_tts else None
        speak_local(a.text, mp3)
        return 0
    data = client.speech(a.text, a.voice, "adpcm16k")
    print(f"{len(data) // proto.ADPCM_BLOCK_BYTES} blocks ({len(data) // proto.ADPCM_BLOCK_BYTES * 16 / 1000:.1f} s)")
    ring = await _with_ring(a, lambda t: asyncio.sleep(0), None, lambda ev: print(format_event(ev)))
    if ring is None:
        return 1
    async with ring:
        await ring.set_config(proto.Cfg.SPEAKER_VOLUME, a.volume)
        print(f"ring speaker: {await ring.stream_audio(data, 255)}")
    return 0


async def _events(a) -> int:
    def on_transfer_sync(t):
        print(f"transfer type={t.start.type} {len(t.data)} B in {t.seconds:.2f} s")

    async def on_transfer(t):
        on_transfer_sync(t)

    ring = await _with_ring(a, on_transfer, None, lambda ev: print(format_event(ev)))
    if ring is None:
        return 1
    async with ring:
        print("events — press the ring button; Ctrl-C to stop")
        while True:
            await asyncio.sleep(3600)


async def _send(a) -> int:
    ring = await _with_ring(a, lambda t: asyncio.sleep(0))
    if ring is None:
        return 1
    async with ring:
        sp = morse.Spacing.farnsworth(a.wpm, a.overall_wpm) if a.overall_wpm < a.wpm else morse.Spacing()
        units, _ = morse.encode(a.text, sp)
        await ring.play_units(units, morse.unit_ms(a.wpm), a.channels)
        await asyncio.sleep(morse.pattern_units(units) * morse.unit_ms(a.wpm) / 1000 + 0.5)
    return 0


async def _config(a) -> int:
    key = getattr(proto.Cfg, a.key.upper())
    ring = await _with_ring(a, lambda t: asyncio.sleep(0))
    if ring is None:
        return 1
    async with ring:
        await ring.set_config(int(key), int(a.value))
        await ring.ping()
        await asyncio.sleep(1)
    return 0


# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="mcring", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    def common_backend(sp, speak_default: bool):
        sp.add_argument("--backend", default="http://localhost:8000")
        sp.add_argument("--token", default="")
        sp.add_argument("-q", "--question", default="", help="typed question (added to the spoken one)")
        sp.add_argument("--mode", default="identify", choices=list(MODES), help="mode when a photo is attached ('chat' never attaches one)")
        sp.add_argument("--provider", default="", choices=["", "anthropic", "openai"])
        sp.add_argument("--session", default="")
        sp.add_argument("--language", default="en")
        if speak_default:
            sp.add_argument("--quiet", "--no-speak", dest="speak", action="store_false", help="do not speak answers on this computer")
            sp.add_argument("--speak", dest="speak", action="store_true", help=argparse.SUPPRESS)   # compat: now the default
        else:
            sp.add_argument("--speak", action="store_true", help="speak the answer (OS TTS, or server mp3 with --server-tts)")
        sp.add_argument("--server-tts", action="store_true", help="play the server's mp3 instead of the OS voice")
        sp.add_argument("--voice", default="", help="server TTS voice name")

    def common_morse(sp):
        g = sp.add_argument_group("legacy silent pattern (off by default)")
        g.add_argument("--morse", action="store_true", help="also request / play the Morse pattern")
        g.add_argument("--wpm", type=int, default=15)
        g.add_argument("--overall-wpm", type=int, default=8)
        g.add_argument("--channels", type=int, default=3, help="bit0 LED, bit1 haptic, bit2 buzzer, bit3 aux")
        g.add_argument("--beep", action="store_true", help="audible Morse on this computer")
        g.add_argument("--echo", action="store_true", help="show the pattern in the terminal")

    def common_ble(sp):
        sp.add_argument("--address", default="", help="BLE address (skip scanning)")
        sp.add_argument("--timeout", type=float, default=10.0)

    def common_voice(sp):
        sp.add_argument("--ring-speaker", action="store_true", help="also stream the answer to the ring speaker (16 kHz ADPCM)")
        sp.add_argument("--volume", type=int, default=200, help="ring speaker volume 0..255 (SET_CONFIG 9)")
        sp.add_argument("--cues", type=int, default=3, help="ring cues mask: bit0 haptic, bit1 LED, bit2 beep (SET_CONFIG 10)")
        sp.add_argument("--save-dir", default="captures")
        sp.add_argument("--no-auto-photo", dest="auto_photo", action="store_false", help="do not ask about a photo that arrives alone")

    s = sub.add_parser("talk", help="push-to-talk: Enter to start, Enter to stop → hear the answer (ring optional)")
    s.add_argument("--ring-mic", action="store_true", help="record with the ring's mic (RECORD_START/STOP) instead of this computer's")
    s.add_argument("--no-ring", action="store_true", help="do not look for a ring (laptop mic + local speech only)")
    s.add_argument("--image", help="a photo file to attach to the first question (no ring camera needed)")
    s.add_argument("--no-photo", dest="photo", action="store_false", help="never ask the ring for a photo during a voice turn")
    common_backend(s, speak_default=True)
    common_voice(s)
    common_ble(s)
    common_morse(s)

    s = sub.add_parser("listen", help="bridge ring ↔ backend: photos and ring-mic clips → spoken answer + cues")
    common_backend(s, speak_default=True)
    common_voice(s)
    common_ble(s)
    common_morse(s)

    s = sub.add_parser("ask", help="run the LLM loop on an image and/or audio file (no ring needed)")
    s.add_argument("image", nargs="?")
    s.add_argument("--audio", help="voice question (.wav/.m4a/.mp3, or .adpcm from the ring)")
    s.add_argument("--speech-format", default="mp3", choices=["mp3", "adpcm16k", "both"])
    s.add_argument("--save-speech", help="write the returned speech to this file (.mp3 or .adpcm)")
    common_backend(s, speak_default=False)
    common_morse(s)

    s = sub.add_parser("say", help="text → speech on this computer (OS/server voice) or on the ring speaker")
    s.add_argument("text")
    s.add_argument("--backend", default="http://localhost:8000")
    s.add_argument("--token", default="")
    s.add_argument("--voice", default="")
    s.add_argument("--server-tts", action="store_true", help="use the server's mp3 instead of the OS voice")
    s.add_argument("--ring-speaker", action="store_true", help="play on the ring speaker (needs a ring)")
    s.add_argument("--volume", type=int, default=200)
    common_ble(s)

    s = sub.add_parser("events", help="print ring events and status")
    common_ble(s)

    s = sub.add_parser("scan", help="list rings in range")
    common_ble(s)

    s = sub.add_parser("send", help="legacy: play Morse text on the ring")
    s.add_argument("text")
    s.add_argument("--wpm", type=int, default=15)
    s.add_argument("--overall-wpm", type=int, default=8)
    s.add_argument("--channels", type=int, default=3)
    common_ble(s)

    s = sub.add_parser("config", help="SET_CONFIG key value (e.g. speaker_volume 200, cues_mask 3, mic_source_hint 1, trigger_mask 3)")
    s.add_argument("key", choices=[c.name.lower() for c in proto.Cfg])
    s.add_argument("value", type=int)
    common_ble(s)

    s = sub.add_parser("morse", help="legacy: play Morse locally")
    s.add_argument("text")
    s.add_argument("--wpm", type=int, default=15)
    s.add_argument("--overall-wpm", type=int, default=8)
    s.add_argument("--beep", action="store_true")
    s.add_argument("--hex", action="store_true", help="print the ring MORSE_UNITS packet")
    s.add_argument("--channels", type=int, default=3)
    return p


def main(argv: list[str] | None = None) -> int:
    a = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if a.verbose else logging.INFO, format="%(levelname).1s %(name)s: %(message)s")

    if a.cmd == "ask":
        return cmd_ask(a)
    if a.cmd == "morse":
        return cmd_morse(a)
    coro = {"scan": _scan, "talk": _talk, "listen": _listen, "say": _say, "events": _events, "send": _send, "config": _config}[a.cmd](a)
    try:
        return asyncio.run(coro) or 0
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
