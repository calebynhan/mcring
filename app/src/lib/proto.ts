/** BLE packet codec — port of python/mcring_core/mcring_core/proto.py. All ints little-endian. */

export const UUID_SERVICE = '7a3b0001-9c2e-4f3a-b1d4-6d6372696e67';
export const UUID_CONTROL = '7a3b0002-9c2e-4f3a-b1d4-6d6372696e67';
export const UUID_STATUS = '7a3b0003-9c2e-4f3a-b1d4-6d6372696e67';
export const UUID_XFER_META = '7a3b0004-9c2e-4f3a-b1d4-6d6372696e67';
export const UUID_XFER_DATA = '7a3b0005-9c2e-4f3a-b1d4-6d6372696e67';
export const UUID_FEEDBACK = '7a3b0006-9c2e-4f3a-b1d4-6d6372696e67';
/** Events (notify, ring → phone): button down/up, taps, capture/record lifecycle, battery, audio-out. */
export const UUID_EVENTS = '7a3b0007-9c2e-4f3a-b1d4-6d6372696e67';
/** Audio out (write-no-response, phone → ring speaker): ADPCM stream. */
export const UUID_AUDIO_OUT = '7a3b0008-9c2e-4f3a-b1d4-6d6372696e67';

export enum Op { CAPTURE = 0x01, ACK_TRANSFER = 0x02, SET_CONFIG = 0x03, PING = 0x04, ABORT = 0x05, RECORD_AUDIO = 0x06, SLEEP = 0x07, GET_STATUS = 0x08, RECORD_START = 0x09, RECORD_STOP = 0x0a }
/** MORSE_* are the legacy / optional "silent pattern" mode; CUE plays a built-in cue honouring CUES_MASK. */
export enum Fb { MORSE_TEXT = 0x10, PATTERN = 0x11, STOP = 0x12, RGB = 0x13, MORSE_UNITS = 0x14, MORSE_UNITS_CONT = 0x15, CUE = 0x16 }
export enum Cue { LISTENING = 1, ANSWER_READY = 2, ERROR = 3, OK = 4 }
export enum Channel { LED = 1, HAPTIC = 2, BUZZER = 4, AUX = 8 }
export enum Cfg { TRIGGER_MASK = 1, DEFAULT_QUALITY = 2, DEFAULT_FRAMESIZE = 3, IDLE_SLEEP_S = 4, LED_BRIGHTNESS = 5, HAPTIC_STRENGTH = 6, MORSE_WPM = 7, FEEDBACK_CHANNELS = 8, SPEAKER_VOLUME = 9, CUES_MASK = 10, MIC_SOURCE_HINT = 11 }
/** CUES_MASK bits (Cfg.CUES_MASK). */
export enum Cues { HAPTIC = 1, LED = 2, BEEP = 4 }
/** MIC_SOURCE_HINT values (Cfg.MIC_SOURCE_HINT). */
export enum MicSource { RING = 0, PHONE = 1 }
export enum RingState { IDLE = 0, CAPTURING = 1, TRANSFERRING = 2, RECORDING = 3, FEEDBACK = 4, ERROR = 5 }
export enum Flag { CHARGING = 1, CAMERA_OK = 2, IMU_OK = 4, MIC_OK = 8, HAPTIC_OK = 16, QUEUED = 32, SPEAKER_OK = 64 }
export enum XferType { JPEG = 1, ADPCM = 2, END = 0xff }
/** Audio-out opcodes (phone → ring speaker). */
export enum Ao { START = 0x20, DATA = 0x21, END = 0x22, STOP = 0x23 }
export const AUDIO_CODEC_ADPCM = 2;
/** Ring → phone events (characteristic 0007). */
export enum RingEvent {
  BUTTON_DOWN = 1, BUTTON_UP = 2 /* arg = held tenths of a second */, DOUBLE_TAP = 3, TOUCH = 4,
  CAPTURE_STARTED = 5, CAPTURE_DONE = 6 /* arg = queued */, REC_STARTED = 7 /* arg = max s */, REC_STOPPED = 8 /* arg = tenths */,
  LOW_BATTERY = 9 /* arg = pct */, AUDIO_UNDERRUN = 10, AUDIO_DONE = 11 /* arg 0 drained, 1 stopped */,
}
export const EVENT_LEN = 6;
export const AUDIO_DATA_HDR_LEN = 3;
/** mcring-ADPCM block: 256 samples @ 16 kHz = 16 ms. Must match lib/mcring_adpcm. */
export const ADPCM_BLOCK_BYTES = 132;
/** The ring starts playing once this many blocks are queued (~400 ms). */
export const AUDIO_PREBUFFER_BLOCKS = 24;

export const ERROR_NAMES: Record<number, string> = { 0: 'none', 1: 'camera_init', 2: 'capture_failed', 3: 'transfer_timeout', 4: 'oom', 5: 'mic' };

const u16 = (v: number) => [v & 0xff, (v >> 8) & 0xff];
const i32 = (v: number) => [v & 0xff, (v >> 8) & 0xff, (v >> 16) & 0xff, (v >>> 24) & 0xff];
const rd16 = (b: Uint8Array, o: number) => b[o] | (b[o + 1] << 8);
const rd32 = (b: Uint8Array, o: number) => (b[o] | (b[o + 1] << 8) | (b[o + 2] << 16) | (b[o + 3] << 24)) >>> 0;

export function chunkLenForMtu(mtu: number): number {
  return Math.max(16, Math.min(510, mtu - 3 - 4));
}

// ---- control -------------------------------------------------------------
export const capture = (quality = 0, frameSize = 0) => Uint8Array.from([Op.CAPTURE, quality & 0xff, frameSize & 0xff]);
export function ackTransfer(xferId: number, missing: number[] = [], abort = false): Uint8Array {
  const status = abort ? 2 : missing.length ? 1 : 0;
  return Uint8Array.from([Op.ACK_TRANSFER, ...u16(xferId), status, ...u16(missing.length), ...missing.flatMap(u16)]);
}
export const setConfig = (key: number, value: number) => Uint8Array.from([Op.SET_CONFIG, key, ...i32(value)]);
export const ping = () => Uint8Array.from([Op.PING]);
export const abort = () => Uint8Array.from([Op.ABORT]);
export const recordAudio = (seconds: number) => Uint8Array.from([Op.RECORD_AUDIO, Math.max(1, Math.min(8, seconds))]);
export const sleep = () => Uint8Array.from([Op.SLEEP]);
export const getStatus = () => Uint8Array.from([Op.GET_STATUS]);
/** Begin a ring-mic recording now; ends on recordStop() or after 8 s. */
export const recordStart = () => Uint8Array.from([Op.RECORD_START]);
export const recordStop = () => Uint8Array.from([Op.RECORD_STOP]);

// ---- feedback --------------------------------------------------------------
export function fbMorseText(text: string, wpm = 15, channels = Channel.LED | Channel.HAPTIC): Uint8Array {
  const b = Array.from(text).map((c) => c.charCodeAt(0)).filter((c) => c < 128).slice(0, 255);
  return Uint8Array.from([Fb.MORSE_TEXT, wpm, channels, b.length, ...b]);
}
export function fbPattern(units: number[], unitMs: number, channels: number): Uint8Array {
  const u = units.slice(0, 255).map((x) => Math.min(255, Math.max(1, x)));
  return Uint8Array.from([Fb.PATTERN, unitMs, channels, u.length, ...u]);
}
export const fbStop = () => Uint8Array.from([Fb.STOP]);
export const fbRgb = (r: number, g: number, b: number, ms: number) => Uint8Array.from([Fb.RGB, r, g, b, ...u16(ms)]);
/** Play one of the ring's built-in cues (haptic/LED/beep per the ring's CUES_MASK). */
export const fbCue = (cue: Cue) => Uint8Array.from([Fb.CUE, cue & 0xff]);
/** Split a long unit pattern into MORSE_UNITS + MORSE_UNITS_CONT writes that fit maxWrite bytes. */
export function fbMorseUnits(units: number[], unitMs: number, channels: number, maxWrite = 180): Uint8Array[] {
  const u = units.map((x) => Math.min(255, Math.max(1, x)));
  const hdr = [Fb.MORSE_UNITS, unitMs, channels, ...u16(u.length)];
  const firstRoom = maxWrite - hdr.length;
  const writes = [Uint8Array.from([...hdr, ...u.slice(0, firstRoom)])];
  let off = firstRoom;
  while (off < u.length) {
    const room = maxWrite - 3;
    writes.push(Uint8Array.from([Fb.MORSE_UNITS_CONT, ...u16(off), ...u.slice(off, off + room)]));
    off += room;
  }
  return writes;
}

// ---- audio out (phone → ring speaker) ----------------------------------------------
export const audioStart = (sampleRate = 16000, codec = AUDIO_CODEC_ADPCM, volume = 255) =>
  Uint8Array.from([Ao.START, ...u16(Math.floor(sampleRate / 100)), codec & 0xff, volume & 0xff]);
/** One AUDIO_DATA packet: seq + one or more whole 132-byte ADPCM blocks. */
export function audioData(seq: number, blocks: Uint8Array): Uint8Array {
  if (blocks.length === 0 || blocks.length % ADPCM_BLOCK_BYTES !== 0) throw new Error(`payload must be a non-empty multiple of ${ADPCM_BLOCK_BYTES} bytes`);
  const out = new Uint8Array(AUDIO_DATA_HDR_LEN + blocks.length);
  out[0] = Ao.DATA; out[1] = seq & 0xff; out[2] = (seq >> 8) & 0xff;
  out.set(blocks, AUDIO_DATA_HDR_LEN);
  return out;
}
export const audioEnd = () => Uint8Array.from([Ao.END]);
export const audioStop = () => Uint8Array.from([Ao.STOP]);
/** Largest write-without-response payload for a negotiated ATT MTU. */
export const maxWriteForMtu = (mtu: number) => Math.max(20, mtu - 3);
export const audioBlocksPerWrite = (maxWrite: number) => Math.max(1, Math.floor((maxWrite - AUDIO_DATA_HDR_LEN) / ADPCM_BLOCK_BYTES));
/**
 * Split an ADPCM byte string into AUDIO_DATA writes of whole blocks that fit maxWrite bytes.
 * maxWrite defaults to the iOS MTU (185 - 3): one block per write; pass 514 at MTU 517 for 3 blocks.
 * Byte-identical to mcring_core.proto.audio_data_writes().
 */
export function audioDataWrites(adpcm: Uint8Array, maxWrite = 182, seqStart = 0): Uint8Array[] {
  if (adpcm.length % ADPCM_BLOCK_BYTES !== 0) throw new Error(`ADPCM length ${adpcm.length} is not a multiple of ${ADPCM_BLOCK_BYTES}`);
  const step = audioBlocksPerWrite(maxWrite) * ADPCM_BLOCK_BYTES;
  const out: Uint8Array[] = [];
  for (let off = 0, i = 0; off < adpcm.length; off += step, i++) out.push(audioData((seqStart + i) & 0xffff, adpcm.subarray(off, Math.min(adpcm.length, off + step))));
  return out;
}
/** AUDIO_START, the data writes, AUDIO_END — everything needed to play one clip on the ring. */
export const audioOutSequence = (adpcm: Uint8Array, maxWrite = 182, volume = 255, sampleRate = 16000): Uint8Array[] =>
  [audioStart(sampleRate, AUDIO_CODEC_ADPCM, volume), ...audioDataWrites(adpcm, maxWrite), audioEnd()];

// ---- ring → phone --------------------------------------------------------------
export interface Event { event: RingEvent; arg: number; tMs: number }
export function unpackEvent(b: Uint8Array): Event {
  if (b.length < EVENT_LEN) throw new Error(`event packet too short (${b.length})`);
  return { event: b[0], arg: b[1], tMs: rd32(b, 2) };
}
export const packEvent = (event: RingEvent, arg = 0, tMs = 0) => Uint8Array.from([event & 0xff, arg & 0xff, ...i32(tMs)]);
export const eventName = (e: number) => (RingEvent[e] ?? `unknown(${e})`).toLowerCase();

export interface Status {
  version: number; state: RingState; batteryMv: number; batteryPct: number; flags: number;
  uptimeS: number; lastError: number; queued: number;
}
export function unpackStatus(b: Uint8Array): Status {
  return { version: b[0], state: b[1], batteryMv: rd16(b, 2), batteryPct: b[4], flags: b[5], uptimeS: rd32(b, 6), lastError: b[10], queued: b[11] };
}
export const statusFlags = (s: Status) => ({
  charging: !!(s.flags & Flag.CHARGING), camera: !!(s.flags & Flag.CAMERA_OK), imu: !!(s.flags & Flag.IMU_OK), mic: !!(s.flags & Flag.MIC_OK),
  haptic: !!(s.flags & Flag.HAPTIC_OK), queued: !!(s.flags & Flag.QUEUED), speaker: !!(s.flags & Flag.SPEAKER_OK),
});

export interface XferStart {
  type: XferType; xferId: number; totalLen: number; chunkLen: number; nChunks: number; crc32: number;
  width: number; height: number; seqFlags: number;
}
export function unpackXferStart(b: Uint8Array): XferStart {
  return { type: b[0], xferId: rd16(b, 1), totalLen: rd32(b, 3), chunkLen: rd16(b, 7), nChunks: rd16(b, 9), crc32: rd32(b, 11), width: rd16(b, 15), height: rd16(b, 17), seqFlags: b[19] };
}
export const isXferEnd = (b: Uint8Array) => b.length >= 3 && b[0] === XferType.END;
export const xferEndId = (b: Uint8Array) => rd16(b, 1);
export function unpackChunk(b: Uint8Array): { xferId: number; idx: number; payload: Uint8Array } {
  return { xferId: rd16(b, 0), idx: rd16(b, 2), payload: b.subarray(4) };
}

// ---- CRC-32 (IEEE) --------------------------------------------------------------
const CRC_TABLE = (() => {
  const t = new Uint32Array(256);
  for (let n = 0; n < 256; n++) {
    let c = n;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    t[n] = c >>> 0;
  }
  return t;
})();
export function crc32(data: Uint8Array): number {
  let c = 0xffffffff;
  for (let i = 0; i < data.length; i++) c = CRC_TABLE[(c ^ data[i]) & 0xff] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}

export class TransferAssembler {
  readonly chunks = new Map<number, Uint8Array>();
  constructor(readonly start: XferStart) {}
  add(idx: number, payload: Uint8Array) {
    if (idx >= 0 && idx < this.start.nChunks) this.chunks.set(idx, payload);
  }
  get missing(): number[] {
    const m: number[] = [];
    for (let i = 0; i < this.start.nChunks; i++) if (!this.chunks.has(i)) m.push(i);
    return m;
  }
  get complete() { return this.missing.length === 0; }
  get progress() { return this.chunks.size / Math.max(1, this.start.nChunks); }
  assemble(): Uint8Array {
    if (!this.complete) throw new Error(`missing ${this.missing.length} chunks`);
    const out = new Uint8Array(this.start.totalLen);
    let o = 0;
    for (let i = 0; i < this.start.nChunks; i++) {
      const c = this.chunks.get(i)!;
      const n = Math.min(c.length, out.length - o);
      out.set(c.subarray(0, n), o);
      o += n;
    }
    if (o !== this.start.totalLen) throw new Error(`length mismatch ${o} != ${this.start.totalLen}`);
    if (crc32(out) !== this.start.crc32) throw new Error('crc mismatch');
    return out;
  }
}

// ---- base64 helpers (react-native-ble-plx speaks base64) -----------------------------
const B64 = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';
export function toBase64(bytes: Uint8Array): string {
  let s = '';
  for (let i = 0; i < bytes.length; i += 3) {
    const a = bytes[i], b = bytes[i + 1], c = bytes[i + 2];
    const n = (a << 16) | ((b ?? 0) << 8) | (c ?? 0);
    s += B64[(n >> 18) & 63] + B64[(n >> 12) & 63] + (b === undefined ? '=' : B64[(n >> 6) & 63]) + (c === undefined ? '=' : B64[n & 63]);
  }
  return s;
}
export function fromBase64(s: string): Uint8Array {
  const clean = s.replace(/[^A-Za-z0-9+/]/g, '');
  const out: number[] = [];
  for (let i = 0; i < clean.length; i += 4) {
    const n = [0, 1, 2, 3].reduce((acc, k) => (acc << 6) | (B64.indexOf(clean[i + k] ?? 'A') & 63), 0);
    const pad = 4 - Math.min(4, clean.length - i);
    out.push((n >> 16) & 255);
    if (pad < 2) out.push((n >> 8) & 255);
    if (pad < 1) out.push(n & 255);
  }
  return Uint8Array.from(out);
}
