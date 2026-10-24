"""BLE client for the ring (bleak). Receives status / events / transfers; sends control, cues and speaker audio."""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Awaitable, Callable

from bleak import BleakClient, BleakScanner
from bleak.backends.device import BLEDevice

from mcring_core import proto

from .audio_out import PacerOptions, adpcm_blocks, stream_adpcm

log = logging.getLogger("mcring.ring")


@dataclass
class Transfer:
    start: proto.XferStart
    data: bytes
    seconds: float


TransferHandler = Callable[[Transfer], Awaitable[None]]
StatusHandler = Callable[[proto.Status], None]
EventHandler = Callable[[proto.RingEvent], None]


async def find_ring(name_prefix: str = "mcring", timeout: float = 10.0) -> BLEDevice | None:
    log.info("scanning for %s* (%.0fs)…", name_prefix, timeout)
    devices = await BleakScanner.discover(timeout=timeout, return_adv=True)
    for d, adv in devices.values():
        name = d.name or adv.local_name or ""
        uuids = [u.lower() for u in (adv.service_uuids or [])]
        if name.startswith(name_prefix) or proto.UUID_SERVICE in uuids:
            return d
    return None


class Ring:
    def __init__(self, device: BLEDevice | str, on_transfer: TransferHandler, on_status: StatusHandler | None = None,
                 on_event: EventHandler | None = None):
        self.device = device
        self.on_transfer = on_transfer
        self.on_status = on_status
        self.on_event = on_event
        self.client: BleakClient | None = None
        self._asm: proto.TransferAssembler | None = None
        self._t0 = 0.0
        self._write_size = 180
        self._waiters: list[tuple[int, asyncio.Future]] = []
        self._audio_cancel = False
        self.status: proto.Status | None = None
        self.last_event: proto.RingEvent | None = None

    @property
    def max_write(self) -> int:
        return self._write_size

    async def __aenter__(self):
        self.client = BleakClient(self.device, disconnected_callback=lambda c: log.warning("ring disconnected"))
        await self.client.connect()
        mtu = getattr(self.client, "mtu_size", 23) or 23
        self._write_size = proto.max_write_for_mtu(min(mtu, 515))
        log.info("connected; MTU %s (%d audio block(s)/write)", mtu, proto.audio_blocks_per_write(self._write_size))
        await self.client.start_notify(proto.UUID_STATUS, self._on_status)
        await self.client.start_notify(proto.UUID_XFER_META, self._on_meta)
        await self.client.start_notify(proto.UUID_XFER_DATA, self._on_data)
        try:
            await self.client.start_notify(proto.UUID_EVENTS, self._on_event)
        except Exception as e:  # noqa: BLE001 - older firmware without 0007
            log.warning("ring has no EVENTS characteristic (%s); button events unavailable", e)
        try:
            raw = await self.client.read_gatt_char(proto.UUID_STATUS)
            self._on_status(None, raw)
        except Exception as e:  # noqa: BLE001
            log.debug("status read failed: %s", e)
        return self

    async def __aexit__(self, *exc):
        if self.client and self.client.is_connected:
            await self.client.disconnect()

    # ---- notifications -------------------------------------------------------
    def _on_status(self, _char, data: bytearray):
        if len(data) >= proto.Status.SIZE:
            self.status = proto.Status.unpack(bytes(data))
            log.info("status: %s batt=%dmV(%d%%) flags=0x%02x%s err=%s queued=%d",
                     self.status.state_name, self.status.battery_mv, self.status.battery_pct,
                     self.status.flags, " speaker" if self.status.speaker_ok else "", self.status.error_name, self.status.queued)
            if self.on_status:
                self.on_status(self.status)

    def _on_event(self, _char, data: bytearray):
        if len(data) < proto.EVENT_LEN:
            return
        ev = proto.unpack_event(bytes(data))
        self.last_event = ev
        log.debug("event %s arg=%d t=%d", ev.name, ev.arg, ev.t_ms)
        keep = []
        for kind, fut in self._waiters:
            if kind == ev.event and not fut.done():
                fut.set_result(ev)
            elif not fut.done():
                keep.append((kind, fut))
        self._waiters = keep
        if self.on_event:
            self.on_event(ev)

    async def wait_event(self, event: int, timeout: float) -> proto.RingEvent | None:
        """The next event of this kind, or None after `timeout` seconds."""
        fut: asyncio.Future = asyncio.get_event_loop().create_future()
        self._waiters.append((int(event), fut))
        try:
            return await asyncio.wait_for(fut, timeout)
        except asyncio.TimeoutError:
            self._waiters = [(k, f) for k, f in self._waiters if f is not fut]
            return None

    def _on_meta(self, _char, data: bytearray):
        b = bytes(data)
        if proto.is_xfer_end(b):
            xid = proto.xfer_end_id(b)
            asyncio.get_event_loop().create_task(self._finish(xid))
            return
        if len(b) >= proto.XferStart.SIZE:
            start = proto.XferStart.unpack(b)
            self._asm = proto.TransferAssembler(start)
            self._t0 = time.time()
            log.info("transfer %d start: type=%d %d bytes in %d chunks of %d (%dx%d)",
                     start.xfer_id, start.type, start.total_len, start.n_chunks, start.chunk_len, start.width, start.height)

    def _on_data(self, _char, data: bytearray):
        if not self._asm:
            return
        xid, idx, payload = proto.unpack_chunk(bytes(data))
        if xid == self._asm.start.xfer_id:
            self._asm.add(idx, payload)

    async def _finish(self, xid: int):
        asm = self._asm
        if not asm or asm.start.xfer_id != xid:
            log.warning("END for unknown transfer %d", xid)
            return
        missing = asm.missing
        if missing:
            log.info("transfer %d: %d chunks missing, requesting resend", xid, len(missing))
            await self.write_control(proto.ack_transfer(xid, missing[:200]))
            return
        try:
            data = asm.assemble()
        except ValueError as e:
            log.error("transfer %d corrupt (%s), asking for a full resend", xid, e)
            await self.write_control(proto.ack_transfer(xid, list(range(asm.start.n_chunks))[:200]))
            return
        secs = time.time() - self._t0
        await self.write_control(proto.ack_transfer(xid))
        log.info("transfer %d complete: %d bytes in %.2fs (%.1f kB/s)", xid, len(data), secs, len(data) / 1024 / max(secs, 1e-3))
        self._asm = None
        await self.on_transfer(Transfer(asm.start, data, secs))

    # ---- writes -----------------------------------------------------------------
    async def write_control(self, packet: bytes):
        assert self.client
        await self.client.write_gatt_char(proto.UUID_CONTROL, packet, response=False)

    async def write_feedback(self, packet: bytes):
        assert self.client
        await self.client.write_gatt_char(proto.UUID_FEEDBACK, packet, response=False)

    async def write_audio(self, packet: bytes):
        assert self.client
        await self.client.write_gatt_char(proto.UUID_AUDIO_OUT, packet, response=False)

    # ---- commands --------------------------------------------------------------
    async def capture(self, quality: int = 0, frame_size: int = 0):
        await self.write_control(proto.capture(quality, frame_size))

    async def ping(self):
        await self.write_control(proto.ping())

    async def abort(self):
        await self.write_control(proto.abort())

    async def set_config(self, key: int, value: int):
        await self.write_control(proto.set_config(key, value))

    async def record_start(self):
        """Ring-mic push-to-talk: record now until record_stop() / 8 s; the clip arrives as an ADPCM transfer."""
        await self.write_control(proto.record_start())

    async def record_stop(self):
        await self.write_control(proto.record_stop())

    async def cue(self, cue: int):
        """Built-in confirmation cue (proto.Cue.*), honouring the ring's CUES_MASK."""
        await self.write_feedback(proto.fb_cue(int(cue)))

    async def flash(self, r: int, g: int, b: int, ms: int):
        await self.write_feedback(proto.fb_rgb(r, g, b, ms))

    async def apply_voice_config(self, speaker_volume: int = 200, cues_mask: int = 3, mic_source: int = 0):
        """SET_CONFIG 9 / 10 / 11."""
        await self.set_config(proto.Cfg.SPEAKER_VOLUME, max(0, min(255, speaker_volume)))
        await self.set_config(proto.Cfg.CUES_MASK, cues_mask & 7)
        await self.set_config(proto.Cfg.MIC_SOURCE_HINT, 1 if mic_source else 0)

    # ---- legacy silent pattern (optional feature) ----------------------------------
    async def play_morse_text(self, text: str, wpm: int = 15, channels: int = 3):
        await self.write_feedback(proto.fb_morse_text(text, wpm, channels))

    async def play_units(self, units: list[int], unit_ms: int, channels: int = 3):
        for w in proto.fb_morse_units(units, unit_ms, channels, max_write=self._write_size):
            await self.write_feedback(w)
            await asyncio.sleep(0.01)

    async def play_ring_packet(self, packet: bytes):
        """Send a backend-built MORSE_UNITS packet, re-splitting it for our MTU."""
        if packet[0] != proto.Fb.MORSE_UNITS:
            await self.write_feedback(packet)
            return
        n = int.from_bytes(packet[3:5], "little")
        units = list(packet[5 : 5 + n])
        await self.play_units(units, packet[1], packet[2])

    async def stop_feedback(self):
        await self.write_feedback(proto.fb_stop())

    # ---- on-ring speaker --------------------------------------------------------------
    async def stream_audio(self, adpcm: bytes, volume: int = 255, await_done: bool = True) -> str:
        """Play a 16 kHz mcring-ADPCM clip on the ring speaker (AUDIO_START, paced AUDIO_DATA writes sized to the
        MTU, AUDIO_END) and wait for AUDIO_DONE. Returns 'done' | 'stopped' | 'timeout' | 'cancelled'."""
        self._audio_cancel = False
        total = adpcm_blocks(adpcm)
        log.info("speaker: %d blocks (%.1f s), %d block(s)/write", total, total * 0.016, proto.audio_blocks_per_write(self._write_size))
        done = asyncio.get_event_loop().create_future()
        self._waiters.append((int(proto.Event.AUDIO_DONE), done))
        res = await stream_adpcm(self.write_audio, adpcm, volume, PacerOptions(max_write=self._write_size),
                                 cancelled=lambda: self._audio_cancel)
        if res.cancelled:
            self._waiters = [(k, f) for k, f in self._waiters if f is not done]
            return "cancelled"
        if not await_done:
            self._waiters = [(k, f) for k, f in self._waiters if f is not done]
            return "done"
        try:
            ev = await asyncio.wait_for(done, res.remaining_ms / 1000.0 + 1.5)
        except asyncio.TimeoutError:
            self._waiters = [(k, f) for k, f in self._waiters if f is not done]
            return "timeout"
        return "done" if ev.arg == 0 else "stopped"

    async def stop_audio(self):
        self._audio_cancel = True
        await self.write_audio(proto.audio_stop())
