"""BLE client for the ring (bleak). Receives transfers, sends control/feedback writes."""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Awaitable, Callable

from bleak import BleakClient, BleakScanner
from bleak.backends.device import BLEDevice

from mcring_core import proto

log = logging.getLogger("mcring.ring")


@dataclass
class Transfer:
    start: proto.XferStart
    data: bytes
    seconds: float


TransferHandler = Callable[[Transfer], Awaitable[None]]
StatusHandler = Callable[[proto.Status], None]


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
    def __init__(self, device: BLEDevice | str, on_transfer: TransferHandler, on_status: StatusHandler | None = None):
        self.device = device
        self.on_transfer = on_transfer
        self.on_status = on_status
        self.client: BleakClient | None = None
        self._asm: proto.TransferAssembler | None = None
        self._t0 = 0.0
        self._write_size = 180
        self.status: proto.Status | None = None

    async def __aenter__(self):
        self.client = BleakClient(self.device, disconnected_callback=lambda c: log.warning("ring disconnected"))
        await self.client.connect()
        mtu = getattr(self.client, "mtu_size", 23) or 23
        self._write_size = max(20, min(512, mtu - 3))
        log.info("connected; MTU %s", mtu)
        await self.client.start_notify(proto.UUID_STATUS, self._on_status)
        await self.client.start_notify(proto.UUID_XFER_META, self._on_meta)
        await self.client.start_notify(proto.UUID_XFER_DATA, self._on_data)
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
            log.info("status: %s batt=%dmV(%d%%) flags=0x%02x err=%s queued=%d",
                     self.status.state_name, self.status.battery_mv, self.status.battery_pct,
                     self.status.flags, self.status.error_name, self.status.queued)
            if self.on_status:
                self.on_status(self.status)

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

    # ---- commands --------------------------------------------------------------
    async def write_control(self, packet: bytes):
        assert self.client
        await self.client.write_gatt_char(proto.UUID_CONTROL, packet, response=False)

    async def write_feedback(self, packet: bytes):
        assert self.client
        await self.client.write_gatt_char(proto.UUID_FEEDBACK, packet, response=False)

    async def capture(self, quality: int = 0, frame_size: int = 0):
        await self.write_control(proto.capture(quality, frame_size))

    async def ping(self):
        await self.write_control(proto.ping())

    async def set_config(self, key: int, value: int):
        await self.write_control(proto.set_config(key, value))

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
