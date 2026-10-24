/**
 * Pacing for streaming mcring-ADPCM (16 kHz, 132-byte / 16 ms blocks) to the ring speaker
 * over the AUDIO_OUT characteristic (protocol/ble-gatt.md, 0008).
 *
 * The ring buffers AUDIO_PREBUFFER_BLOCKS (~400 ms) before it starts playing, so the first
 * blocks go out as fast as BLE allows. After that we model the ring's playback clock (one block
 * every 16 ms from the moment the prebuffer was complete) and keep at most `maxLeadBlocks`
 * unplayed blocks queued on the ring: writes go out in bursts of `burstBlocks`, separated by
 * short awaits, so a slow link never overruns the ring's queue and a fast link never floods it.
 *
 * Pure (no BLE, injectable clock) so it is unit-testable; RingClient.streamAudio drives it.
 */
import * as P from './proto';

export const BLOCK_MS = 16;

export interface PacerOptions {
  /** Largest write-without-response payload (ATT MTU - 3). */
  maxWrite: number;
  /** Blocks sent as fast as possible before pacing starts (the ring starts playing at this depth). */
  prebufferBlocks?: number;
  /** Never have more than this many unplayed blocks queued on the ring (keep <= its guaranteed buffer). */
  maxLeadBlocks?: number;
  /** Blocks per burst between pauses. */
  burstBlocks?: number;
  /** Milliseconds of audio per block (16 at 16 kHz). */
  blockMs?: number;
}

export interface ResolvedPacerOptions {
  maxWrite: number; prebufferBlocks: number; maxLeadBlocks: number; burstBlocks: number; blockMs: number;
}

export function resolvePacerOptions(o: PacerOptions): ResolvedPacerOptions {
  const prebuffer = Math.max(1, o.prebufferBlocks ?? P.AUDIO_PREBUFFER_BLOCKS);
  // 2 blocks (32 ms) of headroom below the ring's guaranteed buffer absorbs BLE latency jitter.
  const maxLead = Math.max(1, o.maxLeadBlocks ?? P.AUDIO_PREBUFFER_BLOCKS - 2);
  return {
    maxWrite: o.maxWrite,
    prebufferBlocks: prebuffer,
    maxLeadBlocks: maxLead,
    burstBlocks: Math.max(1, Math.min(o.burstBlocks ?? 6, maxLead)),
    blockMs: o.blockMs ?? BLOCK_MS,
  };
}

/** Trim to whole blocks (the backend always sends whole blocks; this guards against a truncated download). */
export function wholeBlocks(adpcm: Uint8Array): Uint8Array {
  const n = adpcm.length - (adpcm.length % P.ADPCM_BLOCK_BYTES);
  return n === adpcm.length ? adpcm : adpcm.subarray(0, n);
}

export const adpcmBlocks = (adpcm: Uint8Array) => Math.floor(adpcm.length / P.ADPCM_BLOCK_BYTES);
export const adpcmDurationMs = (adpcm: Uint8Array, blockMs = BLOCK_MS) => adpcmBlocks(adpcm) * blockMs;

/**
 * Tracks what the ring has been sent vs. what it has (modelled) played, and says how long to wait
 * before the next write. The ring's clock is anchored when the prebuffer is complete and re-anchored
 * if we ever fall behind it (after a stall the queue is refilled quickly, then pacing resumes).
 */
export class AudioPacer {
  readonly opts: ResolvedPacerOptions;
  private sent = 0;
  private playStart: number | null = null;

  constructor(opts: PacerOptions, private readonly now: () => number = () => Date.now()) {
    this.opts = resolvePacerOptions(opts);
  }

  get blocksSent() { return this.sent; }

  /** Blocks the ring has (by our model) played so far. */
  private consumed(at: number): number {
    if (this.playStart === null) return 0;
    const c = Math.floor((at - this.playStart) / this.opts.blockMs);
    if (c > this.sent) {
      // We fell behind the ring (it underran): assume its queue is empty right now.
      this.playStart = at - this.sent * this.opts.blockMs;
      return this.sent;
    }
    return Math.max(0, c);
  }

  /** Unplayed blocks currently queued on the ring (modelled). */
  lead(at = this.now()): number {
    return this.sent - this.consumed(at);
  }

  /** Milliseconds to wait before sending a write of `nBlocks` (0 = send now). */
  delayBefore(nBlocks: number): number {
    if (this.sent < this.opts.prebufferBlocks) return 0;
    const at = this.now();
    const lead = this.lead(at);
    if (lead + nBlocks <= this.opts.maxLeadBlocks) return 0;
    // Wait until a whole burst fits, so writes go out in bursts instead of one per 16 ms.
    const target = Math.max(0, this.opts.maxLeadBlocks - this.opts.burstBlocks);
    return Math.max(1, (lead - target) * this.opts.blockMs);
  }

  markSent(nBlocks: number): void {
    this.sent += nBlocks;
    if (this.playStart === null && this.sent >= this.opts.prebufferBlocks) this.playStart = this.now();
  }

  /** Milliseconds of queued audio still to play on the ring (for an AUDIO_DONE timeout). */
  remainingMs(): number {
    return this.lead() * this.opts.blockMs;
  }
}

export interface StreamDeps {
  write: (pkt: Uint8Array) => Promise<void>;
  sleep?: (ms: number) => Promise<void>;
  now?: () => number;
  /** Polled between writes; return true to abort (AUDIO_STOP is then the caller's job). */
  cancelled?: () => boolean;
  onProgress?: (blocksSent: number, totalBlocks: number) => void;
}

export interface StreamResult {
  /** Blocks actually written. */
  blocks: number;
  totalBlocks: number;
  /** Writes performed (AUDIO_START/AUDIO_END included). */
  writes: number;
  cancelled: boolean;
  /** Modelled milliseconds of audio still queued on the ring when AUDIO_END was sent. */
  remainingMs: number;
}

const defaultSleep = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));

/**
 * AUDIO_START, paced AUDIO_DATA writes (whole blocks only, sized to the MTU), AUDIO_END.
 * Does not wait for the ring's AUDIO_DONE event — RingClient does that.
 */
export async function streamAdpcm(adpcm: Uint8Array, volume: number, opts: PacerOptions, deps: StreamDeps): Promise<StreamResult> {
  const data = wholeBlocks(adpcm);
  const pacer = new AudioPacer(opts, deps.now);
  const sleep = deps.sleep ?? defaultSleep;
  const totalBlocks = adpcmBlocks(data);
  const writes = P.audioDataWrites(data, opts.maxWrite);
  let n = 1;
  await deps.write(P.audioStart(16000, P.AUDIO_CODEC_ADPCM, volume));
  for (const w of writes) {
    if (deps.cancelled?.()) return { blocks: pacer.blocksSent, totalBlocks, writes: n, cancelled: true, remainingMs: pacer.remainingMs() };
    const blocks = (w.length - P.AUDIO_DATA_HDR_LEN) / P.ADPCM_BLOCK_BYTES;
    const wait = pacer.delayBefore(blocks);
    if (wait > 0) await sleep(wait);
    if (deps.cancelled?.()) return { blocks: pacer.blocksSent, totalBlocks, writes: n, cancelled: true, remainingMs: pacer.remainingMs() };
    await deps.write(w);
    n++;
    pacer.markSent(blocks);
    deps.onProgress?.(pacer.blocksSent, totalBlocks);
  }
  await deps.write(P.audioEnd());
  n++;
  return { blocks: pacer.blocksSent, totalBlocks, writes: n, cancelled: false, remainingMs: pacer.remainingMs() };
}
