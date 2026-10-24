/** BLE packet codec — port of python/mcring_core/mcring_core/proto.py. All ints little-endian. */

export const UUID_SERVICE = '7a3b0001-9c2e-4f3a-b1d4-6d6372696e67';
export const UUID_CONTROL = '7a3b0002-9c2e-4f3a-b1d4-6d6372696e67';
export const UUID_STATUS = '7a3b0003-9c2e-4f3a-b1d4-6d6372696e67';
export const UUID_XFER_META = '7a3b0004-9c2e-4f3a-b1d4-6d6372696e67';
export const UUID_XFER_DATA = '7a3b0005-9c2e-4f3a-b1d4-6d6372696e67';
export const UUID_FEEDBACK = '7a3b0006-9c2e-4f3a-b1d4-6d6372696e67';

export enum Op { CAPTURE = 0x01, ACK_TRANSFER = 0x02, SET_CONFIG = 0x03, PING = 0x04, ABORT = 0x05, RECORD_AUDIO = 0x06, SLEEP = 0x07, GET_STATUS = 0x08 }
export enum Fb { MORSE_TEXT = 0x10, PATTERN = 0x11, STOP = 0x12, RGB = 0x13, MORSE_UNITS = 0x14, MORSE_UNITS_CONT = 0x15 }
export enum Channel { LED = 1, HAPTIC = 2, BUZZER = 4, AUX = 8 }
export enum Cfg { TRIGGER_MASK = 1, DEFAULT_QUALITY = 2, DEFAULT_FRAMESIZE = 3, IDLE_SLEEP_S = 4, LED_BRIGHTNESS = 5, HAPTIC_STRENGTH = 6, MORSE_WPM = 7, FEEDBACK_CHANNELS = 8 }
export enum RingState { IDLE = 0, CAPTURING = 1, TRANSFERRING = 2, RECORDING = 3, FEEDBACK = 4, ERROR = 5 }
export enum XferType { JPEG = 1, ADPCM = 2, END = 0xff }

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

// ---- ring → phone --------------------------------------------------------------
export interface Status {
  version: number; state: RingState; batteryMv: number; batteryPct: number; flags: number;
  uptimeS: number; lastError: number; queued: number;
}
export function unpackStatus(b: Uint8Array): Status {
  return { version: b[0], state: b[1], batteryMv: rd16(b, 2), batteryPct: b[4], flags: b[5], uptimeS: rd32(b, 6), lastError: b[10], queued: b[11] };
}
export const statusFlags = (s: Status) => ({
  charging: !!(s.flags & 1), camera: !!(s.flags & 2), imu: !!(s.flags & 4), mic: !!(s.flags & 8), haptic: !!(s.flags & 16), queued: !!(s.flags & 32),
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
