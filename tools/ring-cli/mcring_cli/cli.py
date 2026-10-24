"""mcring desktop companion.

  mcring listen  --backend http://localhost:8000      # bridge: ring → backend → ring (needs BLE)
  mcring ask     photo.jpg -q "what is this?"         # no ring: run the LLM loop on a file
  mcring morse   "FOXGLOVE TOXIC" --beep              # play Morse locally
  mcring scan                                         # list rings in range
  mcring send    "R TOXIC"                            # play Morse on the ring
  mcring config  morse_wpm 12                         # SET_CONFIG on the ring
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import pathlib
import subprocess
import sys
import tempfile

from mcring_core import adpcm, morse, proto

from .backend_client import BackendClient, save_capture
from .player import play_units

log = logging.getLogger("mcring")


def _speak(text: str, mp3: bytes | None) -> None:
    """Best-effort local speech: play server MP3 if given, else use the OS TTS."""
    try:
        if mp3:
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                f.write(mp3)
            for cmd in (["afplay", f.name], ["mpg123", "-q", f.name], ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", f.name]):
                try:
                    subprocess.run(cmd, check=True, timeout=60)
                    return
                except (FileNotFoundError, subprocess.CalledProcessError):
                    continue
        for cmd in (["say", text], ["espeak-ng", text], ["espeak", text], ["spd-say", text]):
            try:
                subprocess.run(cmd, check=True, timeout=60)
                return
            except (FileNotFoundError, subprocess.CalledProcessError):
                continue
    except Exception as e:  # noqa: BLE001
        log.debug("speech failed: %s", e)
    print(f"🔈 {text}")


def _print_answer(res) -> None:
    conf = f"{res.confidence:.0%}"
    print(f"\n{res.subject or '(no subject)'}  [{conf}]  via {res.model} in {res.latency_ms} ms")
    print(f"  answer: {res.answer}")
    print(f"  short : {res.short}")
    for w in res.warnings:
        print(f"  ⚠ {w}")


# ---------------------------------------------------------------------------
def cmd_ask(a) -> int:
    client = BackendClient(a.backend, a.token)
    image = pathlib.Path(a.image).read_bytes() if a.image else None
    audio = pathlib.Path(a.audio).read_bytes() if a.audio else None
    res = client.ask(image, a.question, a.mode, a.session, a.provider, want_speech=a.speak and a.server_tts,
                     audio_adpcm=audio, char_wpm=a.wpm, overall_wpm=a.overall_wpm)
    _print_answer(res)
    if a.speak:
        _speak(res.answer, res.speech_mp3)
    if res.morse_units and not a.no_morse:
        play_units(res.morse_units, res.morse_unit_ms, beep=a.beep, label=res.short)
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


async def _with_ring(a, on_transfer, on_status=None):
    from .ring import Ring, find_ring

    target = a.address or await find_ring(timeout=a.timeout)
    if not target:
        print("ring not found", file=sys.stderr)
        return None
    return Ring(target, on_transfer, on_status)


async def _listen(a) -> int:
    from .ring import Transfer

    client = BackendClient(a.backend, a.token)
    try:
        h = client.health()
        log.info("backend ok: %s %s", h.get("provider"), h.get("model"))
    except Exception as e:  # noqa: BLE001
        print(f"backend not reachable at {a.backend}: {e}", file=sys.stderr)
        return 2

    out_dir = pathlib.Path(a.save_dir)
    state = {"session": a.session, "pending_image": None, "ring": None}

    async def handle(t: Transfer):
        ring = state["ring"]
        if t.start.type == proto.XferType.JPEG:
            p = save_capture(t.data, out_dir, ".jpg")
            log.info("saved %s", p)
            state["pending_image"] = t.data
            # Give a possible voice clip 1.5 s to arrive before asking.
            await asyncio.sleep(1.5 if a.wait_voice else 0)
            if state["pending_image"] is None:
                return
            await ask_and_reply(state.pop("pending_image"), None)
        elif t.start.type == proto.XferType.ADPCM:
            wav = adpcm.adpcm_to_wav(t.data, t.start.height * 100 or 16000)
            p = save_capture(wav, out_dir, ".wav")
            log.info("saved voice %s", p)
            img = state["pending_image"]
            state["pending_image"] = None
            await ask_and_reply(img, t.data)

    async def ask_and_reply(image: bytes | None, voice: bytes | None):
        ring = state["ring"]
        try:
            await ring.write_feedback(proto.fb_rgb(0, 0, 60, 300))
            res = await asyncio.get_event_loop().run_in_executor(
                None, lambda: client.ask(image, a.question, a.mode, state["session"], a.provider,
                                         want_speech=a.speak and a.server_tts, audio_adpcm=voice,
                                         char_wpm=a.wpm, overall_wpm=a.overall_wpm, channels=a.channels))
        except Exception as e:  # noqa: BLE001
            log.error("backend error: %s", e)
            await ring.play_morse_text("HH", 20, proto.Channel.LED)
            return
        state["session"] = res.session_id
        _print_answer(res)
        if a.speak:
            await asyncio.get_event_loop().run_in_executor(None, _speak, res.answer, res.speech_mp3)
        if res.morse_units:
            await ring.play_units(res.morse_units, res.morse_unit_ms, a.channels)
            if a.echo:
                play_units(res.morse_units, res.morse_unit_ms, beep=a.beep, label=res.short)

    ring = await _with_ring(a, handle)
    if ring is None:
        return 1
    state["ring"] = ring
    async with ring:
        await ring.set_config(proto.Cfg.MORSE_WPM, a.wpm)
        await ring.set_config(proto.Cfg.FEEDBACK_CHANNELS, a.channels)
        print("listening — press the ring button (or Ctrl-C). 'c' + Enter captures from here.")
        loop = asyncio.get_event_loop()
        while True:
            line = await loop.run_in_executor(None, sys.stdin.readline)
            if not line:
                await asyncio.sleep(3600)
                continue
            cmd = line.strip().lower()
            if cmd in ("c", "capture"):
                await ring.capture()
            elif cmd in ("p", "ping"):
                await ring.ping()
            elif cmd.startswith("say "):
                await ring.play_morse_text(cmd[4:], a.wpm, a.channels)
            elif cmd in ("q", "quit"):
                return 0


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


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="mcring", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    def common_backend(sp):
        sp.add_argument("--backend", default="http://localhost:8000")
        sp.add_argument("--token", default="")
        sp.add_argument("-q", "--question", default="")
        sp.add_argument("--mode", default="identify", choices=["identify", "describe", "read_text", "translate", "custom"])
        sp.add_argument("--provider", default="", choices=["", "anthropic", "openai"])
        sp.add_argument("--session", default="")
        sp.add_argument("--speak", action="store_true", help="speak the answer (OS TTS, or server MP3 with --server-tts)")
        sp.add_argument("--server-tts", action="store_true")
        sp.add_argument("--beep", action="store_true", help="audible Morse on this computer")
        sp.add_argument("--wpm", type=int, default=15)
        sp.add_argument("--overall-wpm", type=int, default=8)
        sp.add_argument("--channels", type=int, default=3, help="bit0 LED, bit1 haptic, bit2 buzzer, bit3 aux")

    def common_ble(sp):
        sp.add_argument("--address", default="", help="BLE address (skip scanning)")
        sp.add_argument("--timeout", type=float, default=10.0)

    s = sub.add_parser("ask", help="run the LLM loop on an image file (no ring needed)")
    s.add_argument("image", nargs="?")
    s.add_argument("--audio", help="voice question (.adpcm from the ring or .wav)")
    s.add_argument("--no-morse", action="store_true")
    common_backend(s)

    s = sub.add_parser("morse", help="play Morse locally")
    s.add_argument("text")
    s.add_argument("--wpm", type=int, default=15)
    s.add_argument("--overall-wpm", type=int, default=8)
    s.add_argument("--beep", action="store_true")
    s.add_argument("--hex", action="store_true", help="print the ring MORSE_UNITS packet")
    s.add_argument("--channels", type=int, default=3)

    s = sub.add_parser("scan", help="list rings in range")
    common_ble(s)

    s = sub.add_parser("listen", help="bridge ring ↔ backend")
    s.add_argument("--save-dir", default="captures")
    s.add_argument("--echo", action="store_true", help="also show the Morse pattern in the terminal")
    s.add_argument("--wait-voice", action="store_true", help="wait 1.5 s after a photo for a voice clip")
    common_backend(s)
    common_ble(s)

    s = sub.add_parser("send", help="play Morse text on the ring")
    s.add_argument("text")
    s.add_argument("--wpm", type=int, default=15)
    s.add_argument("--overall-wpm", type=int, default=8)
    s.add_argument("--channels", type=int, default=3)
    common_ble(s)

    s = sub.add_parser("config", help="SET_CONFIG key value (e.g. morse_wpm 12, trigger_mask 3)")
    s.add_argument("key", choices=[c.name.lower() for c in proto.Cfg])
    s.add_argument("value", type=int)
    common_ble(s)

    a = p.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if a.verbose else logging.INFO, format="%(levelname).1s %(name)s: %(message)s")

    if a.cmd == "ask":
        return cmd_ask(a)
    if a.cmd == "morse":
        return cmd_morse(a)
    coro = {"scan": _scan, "listen": _listen, "send": _send, "config": _config}[a.cmd](a)
    try:
        return asyncio.run(coro) or 0
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
