"""Pacing for streaming mcring-ADPCM (16 kHz, 132-byte / 16 ms blocks) to the ring speaker over AUDIO_OUT (0008).

Mirrors app/src/lib/audioStream.ts. The ring buffers AUDIO_PREBUFFER_BLOCKS (~400 ms) before it starts playing,
so the first blocks go out as fast as BLE allows. After that we model the ring's playback clock (one block every
16 ms from the moment the prebuffer was complete) and keep at most `max_lead_blocks` unplayed blocks queued on
the ring: writes go out in bursts of `burst_blocks`, separated by short sleeps. Pure (injectable clock/sleep).
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Awaitable, Callable

from mcring_core import proto

BLOCK_MS = 16


@dataclass
class PacerOptions:
    max_write: int = 182                                   # ATT MTU - 3 (182 at the iOS MTU of 185)
    prebuffer_blocks: int = proto.AUDIO_PREBUFFER_BLOCKS   # ring starts playing at this depth
    max_lead_blocks: int = proto.AUDIO_PREBUFFER_BLOCKS - 2  # headroom under the ring's guaranteed buffer
    burst_blocks: int = 6
    block_ms: int = BLOCK_MS

    def __post_init__(self):
        self.prebuffer_blocks = max(1, self.prebuffer_blocks)
        self.max_lead_blocks = max(1, self.max_lead_blocks)
        self.burst_blocks = max(1, min(self.burst_blocks, self.max_lead_blocks))


def whole_blocks(adpcm: bytes) -> bytes:
    n = len(adpcm) - len(adpcm) % proto.ADPCM_BLOCK_BYTES
    return adpcm[:n]


def adpcm_blocks(adpcm: bytes) -> int:
    return len(adpcm) // proto.ADPCM_BLOCK_BYTES


def adpcm_duration_ms(adpcm: bytes, block_ms: int = BLOCK_MS) -> int:
    return adpcm_blocks(adpcm) * block_ms


def _now_ms() -> float:
    return time.monotonic() * 1000.0


class AudioPacer:
    """Tracks blocks sent vs. (modelled) played and says how long to wait before the next write."""

    def __init__(self, opts: PacerOptions | None = None, now_ms: Callable[[], float] = _now_ms):
        self.opts = opts or PacerOptions()
        self._now = now_ms
        self.sent = 0
        self._play_start: float | None = None

    def _consumed(self, at: float) -> int:
        if self._play_start is None:
            return 0
        c = int((at - self._play_start) // self.opts.block_ms)
        if c > self.sent:
            # We fell behind the ring (it underran): assume its queue is empty right now.
            self._play_start = at - self.sent * self.opts.block_ms
            return self.sent
        return max(0, c)

    def lead(self, at: float | None = None) -> int:
        """Unplayed blocks currently queued on the ring (modelled)."""
        return self.sent - self._consumed(self._now() if at is None else at)

    def delay_before(self, n_blocks: int) -> float:
        """Milliseconds to wait before sending a write of n_blocks (0 = send now)."""
        if self.sent < self.opts.prebuffer_blocks:
            return 0.0
        lead = self.lead()
        if lead + n_blocks <= self.opts.max_lead_blocks:
            return 0.0
        target = max(0, self.opts.max_lead_blocks - self.opts.burst_blocks)
        return max(1.0, (lead - target) * self.opts.block_ms)

    def mark_sent(self, n_blocks: int) -> None:
        self.sent += n_blocks
        if self._play_start is None and self.sent >= self.opts.prebuffer_blocks:
            self._play_start = self._now()

    def remaining_ms(self) -> float:
        return self.lead() * self.opts.block_ms


@dataclass
class StreamResult:
    blocks: int
    total_blocks: int
    writes: int
    cancelled: bool
    remaining_ms: float


Writer = Callable[[bytes], Awaitable[None]]


async def stream_adpcm(write: Writer, adpcm: bytes, volume: int = 255, opts: PacerOptions | None = None, *,
                       sleep: Callable[[float], Awaitable[None]] | None = None,
                       now_ms: Callable[[], float] = _now_ms,
                       cancelled: Callable[[], bool] | None = None,
                       on_progress: Callable[[int, int], None] | None = None) -> StreamResult:
    """AUDIO_START, paced AUDIO_DATA writes (whole blocks only, sized to max_write), AUDIO_END.

    Does not wait for the ring's AUDIO_DONE event — Ring.stream_audio does that.
    """
    opts = opts or PacerOptions()
    data = whole_blocks(bytes(adpcm))
    pacer = AudioPacer(opts, now_ms)
    total = adpcm_blocks(data)
    _sleep = sleep or (lambda ms: asyncio.sleep(ms / 1000.0))
    writes = proto.audio_data_writes(data, opts.max_write)
    n = 1
    await write(proto.audio_start(16000, proto.AUDIO_CODEC_ADPCM, volume))
    for w in writes:
        if cancelled and cancelled():
            return StreamResult(pacer.sent, total, n, True, pacer.remaining_ms())
        blocks = (len(w) - proto.AUDIO_DATA_HDR_LEN) // proto.ADPCM_BLOCK_BYTES
        wait = pacer.delay_before(blocks)
        if wait > 0:
            await _sleep(wait)
        if cancelled and cancelled():
            return StreamResult(pacer.sent, total, n, True, pacer.remaining_ms())
        await write(w)
        n += 1
        pacer.mark_sent(blocks)
        if on_progress:
            on_progress(pacer.sent, total)
    await write(proto.audio_end())
    n += 1
    return StreamResult(pacer.sent, total, n, False, pacer.remaining_ms())
