import * as P from '../src/lib/proto';
import { AudioPacer, adpcmDurationMs, resolvePacerOptions, streamAdpcm, wholeBlocks } from '../src/lib/audioStream';

const BLOCK = P.ADPCM_BLOCK_BYTES;
const clip = (blocks: number) => Uint8Array.from({ length: blocks * BLOCK }, (_, i) => i & 255);

/** Deterministic driver: the fake clock only advances through sleep(). */
async function drive(adpcm: Uint8Array, maxWrite: number, volume = 200) {
  let now = 1000;
  const writes: Uint8Array[] = [];
  const sleeps: number[] = [];
  const leadLog: number[] = [];
  const pacer = new AudioPacer({ maxWrite }, () => now);           // shadow model to assert the ring queue depth
  const res = await streamAdpcm(adpcm, volume, { maxWrite }, {
    write: async (pkt) => {
      writes.push(pkt);
      if (pkt[0] === P.Ao.DATA) {
        const n = (pkt.length - P.AUDIO_DATA_HDR_LEN) / BLOCK;
        leadLog.push(pacer.lead() + n);
        pacer.markSent(n);
      }
    },
    sleep: async (ms) => { sleeps.push(ms); now += ms; },
    now: () => now,
  });
  return { res, writes, sleeps, leadLog, pacer };
}

test('frames: AUDIO_START, whole-block AUDIO_DATA writes that fit the MTU, AUDIO_END', async () => {
  const { res, writes } = await drive(clip(50), 182);
  expect(writes[0]).toEqual(P.audioStart(16000, P.AUDIO_CODEC_ADPCM, 200));
  expect(writes[writes.length - 1]).toEqual(P.audioEnd());
  const data = writes.slice(1, -1);
  expect(data).toHaveLength(50);                                           // 1 block per write at the iOS MTU
  data.forEach((w, i) => {
    expect(w[0]).toBe(P.Ao.DATA);
    expect(w[1] | (w[2] << 8)).toBe(i);
    expect(w.length).toBeLessThanOrEqual(182);
    expect((w.length - P.AUDIO_DATA_HDR_LEN) % BLOCK).toBe(0);
  });
  expect(res).toMatchObject({ blocks: 50, totalBlocks: 50, cancelled: false, writes: 52 });
});

test('at MTU 517 three blocks go in one write and the payload round-trips', async () => {
  const adpcm = clip(10);
  const { writes } = await drive(adpcm, 514);
  const data = writes.slice(1, -1);
  expect(data).toHaveLength(4);                                            // 3+3+3+1
  expect(data[0].length).toBe(P.AUDIO_DATA_HDR_LEN + 3 * BLOCK);
  const joined = new Uint8Array(adpcm.length);
  let o = 0;
  for (const w of data) { joined.set(w.subarray(P.AUDIO_DATA_HDR_LEN), o); o += w.length - P.AUDIO_DATA_HDR_LEN; }
  expect(joined).toEqual(adpcm);
});

test('pacing: prebuffer goes out at once, then bursts keep the ring queue within its guaranteed buffer', async () => {
  const total = 200;                                                       // 3.2 s of speech
  const { sleeps, leadLog, res } = await drive(clip(total), 182);
  const o = resolvePacerOptions({ maxWrite: 182 });
  // The first `prebuffer` blocks were written without any sleep.
  expect(sleeps.length).toBeGreaterThan(0);
  expect(leadLog.slice(0, o.prebufferBlocks).every((_, i) => i < o.prebufferBlocks)).toBe(true);
  // The ring's queue never exceeds what it is guaranteed to hold (the prebuffer depth), and once playback has
  // started it stays at or below maxLead (a little headroom under that guarantee).
  expect(Math.max(...leadLog)).toBeLessThanOrEqual(P.AUDIO_PREBUFFER_BLOCKS);
  expect(Math.max(...leadLog.slice(o.prebufferBlocks))).toBeLessThanOrEqual(o.maxLeadBlocks);
  expect(o.maxLeadBlocks).toBeLessThan(P.AUDIO_PREBUFFER_BLOCKS);
  // Bursty: pauses are a multiple of several blocks, not one await per block.
  expect(sleeps.length).toBeLessThan(total - o.prebufferBlocks);
  expect(Math.max(...sleeps)).toBeGreaterThanOrEqual(o.burstBlocks * 16 - 16);
  // Roughly real time: total sleep ≈ clip duration minus what is left queued at AUDIO_END.
  const slept = sleeps.reduce((a, b) => a + b, 0);
  expect(slept + res.remainingMs).toBeGreaterThanOrEqual(adpcmDurationMs(clip(total)) - o.prebufferBlocks * 16 - 16);
  expect(slept).toBeLessThanOrEqual(adpcmDurationMs(clip(total)));
});

test('pacer re-anchors after a stall instead of flooding the ring', () => {
  let now = 0;
  const p = new AudioPacer({ maxWrite: 182, prebufferBlocks: 4, maxLeadBlocks: 8, burstBlocks: 2 }, () => now);
  for (let i = 0; i < 8; i++) { expect(p.delayBefore(1)).toBe(0); p.markSent(1); }
  expect(p.lead()).toBe(8);
  expect(p.delayBefore(1)).toBeGreaterThan(0);                             // queue full: must wait
  now += 10_000;                                                           // the app was suspended for 10 s
  expect(p.lead()).toBe(0);                                                // ring drained everything: queue is empty
  // Refill: up to maxLead blocks immediately, then pacing again.
  for (let i = 0; i < 8; i++) { expect(p.delayBefore(1)).toBe(0); p.markSent(1); }
  expect(p.delayBefore(1)).toBeGreaterThan(0);
});

test('short clips and odd lengths', async () => {
  const { res, writes } = await drive(clip(3), 182);
  expect(res.blocks).toBe(3);
  expect(writes).toHaveLength(5);
  const ragged = Uint8Array.from([...clip(2), 1, 2, 3]);
  expect(wholeBlocks(ragged).length).toBe(2 * BLOCK);
  const r2 = await drive(ragged, 182);
  expect(r2.res.blocks).toBe(2);
});

test('cancellation stops the data writes', async () => {
  let cancelled = false;
  const writes: Uint8Array[] = [];
  const res = await streamAdpcm(clip(40), 255, { maxWrite: 182 }, {
    write: async (pkt) => { writes.push(pkt); if (writes.length === 10) cancelled = true; },
    sleep: async () => undefined,
    cancelled: () => cancelled,
  });
  expect(res.cancelled).toBe(true);
  expect(writes.length).toBe(10);
  expect(writes.some((w) => w[0] === P.Ao.END)).toBe(false);
});
