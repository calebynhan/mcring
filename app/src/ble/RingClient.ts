/**
 * Ring BLE client on react-native-ble-plx, implementing protocol/ble-gatt.md.
 * Emits: status, events (button/record/audio lifecycle), transfers (complete image/audio), progress, connection changes.
 * Sends: control (capture, record start/stop, config), feedback cues, and ADPCM audio for the on-ring speaker.
 */
import { BleError, BleManager, Characteristic, Device, State, Subscription } from 'react-native-ble-plx';
import * as P from '../lib/proto';
import { streamAdpcm } from '../lib/audioStream';
import type { MicSource } from '../lib/settings';

export interface Transfer {
  start: P.XferStart;
  data: Uint8Array;
  seconds: number;
}

export interface RingEvents {
  onStatus?: (s: P.Status) => void;
  onEvent?: (e: P.Event) => void;
  onTransfer?: (t: Transfer) => void;
  onProgress?: (xferId: number, fraction: number) => void;
  onAudioProgress?: (blocksSent: number, totalBlocks: number) => void;
  onConnection?: (connected: boolean, device?: Device) => void;
  onLog?: (line: string) => void;
}

/** How a speaker stream ended. */
export type AudioOutcome = 'done' | 'stopped' | 'timeout' | 'cancelled';

export interface VoiceConfig {
  speakerVolume: number;
  cuesMask: number;
  micSource: MicSource;
}

interface Waiter { event: P.RingEvent; resolve: (e: P.Event | null) => void }

export class RingClient {
  private manager = new BleManager();
  private device: Device | null = null;
  private subs: Subscription[] = [];
  private asm: P.TransferAssembler | null = null;
  private t0 = 0;
  private writeSize = 180;
  private waiters: Waiter[] = [];
  private audioJob: { cancelled: boolean } | null = null;
  status: P.Status | null = null;

  constructor(private ev: RingEvents = {}) {}

  private log(line: string) {
    this.ev.onLog?.(line);
  }

  get connected() {
    return !!this.device;
  }

  /** Largest write-without-response payload for the negotiated MTU. */
  get maxWrite() {
    return this.writeSize;
  }

  async waitForBluetooth(): Promise<void> {
    const st = await this.manager.state();
    if (st === State.PoweredOn) return;
    await new Promise<void>((resolve) => {
      const sub = this.manager.onStateChange((s) => {
        if (s === State.PoweredOn) {
          sub.remove();
          resolve();
        }
      }, true);
    });
  }

  /** Scan for a ring (by service UUID or name prefix). Resolves with the first match. */
  scan(timeoutMs = 10000): Promise<Device> {
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.manager.stopDeviceScan();
        reject(new Error('no ring found'));
      }, timeoutMs);
      this.manager.startDeviceScan([P.UUID_SERVICE], { allowDuplicates: false }, (err, dev) => {
        if (err) {
          clearTimeout(timer);
          this.manager.stopDeviceScan();
          reject(err);
          return;
        }
        if (dev && (dev.name?.startsWith('mcring') || dev.serviceUUIDs?.map((u) => u.toLowerCase()).includes(P.UUID_SERVICE))) {
          clearTimeout(timer);
          this.manager.stopDeviceScan();
          resolve(dev);
        }
      });
    });
  }

  async connect(dev: Device): Promise<void> {
    this.log(`connecting to ${dev.name ?? dev.id}`);
    const d = await dev.connect({ requestMTU: 517 });
    await d.discoverAllServicesAndCharacteristics();
    const mtu = d.mtu || 23;
    this.writeSize = P.maxWriteForMtu(Math.min(mtu, 515));
    this.device = d;
    this.log(`connected, MTU ${mtu} (${P.audioBlocksPerWrite(this.writeSize)} audio block(s)/write)`);
    this.subs.push(
      d.monitorCharacteristicForService(P.UUID_SERVICE, P.UUID_STATUS, (e, c) => this.onStatus(e, c)),
      d.monitorCharacteristicForService(P.UUID_SERVICE, P.UUID_XFER_META, (e, c) => this.onMeta(e, c)),
      d.monitorCharacteristicForService(P.UUID_SERVICE, P.UUID_XFER_DATA, (e, c) => this.onData(e, c)),
      // Older firmware has no 0007: the monitor just errors once and we carry on without events.
      d.monitorCharacteristicForService(P.UUID_SERVICE, P.UUID_EVENTS, (e, c) => this.onEvent(e, c)),
      this.manager.onDeviceDisconnected(d.id, () => {
        this.log('disconnected');
        this.cleanup();
        this.ev.onConnection?.(false);
      }),
    );
    try {
      const c = await d.readCharacteristicForService(P.UUID_SERVICE, P.UUID_STATUS);
      if (c.value) this.handleStatus(P.fromBase64(c.value));
    } catch {
      /* status read is best-effort */
    }
    this.ev.onConnection?.(true, d);
  }

  async disconnect() {
    const d = this.device;
    this.cleanup();
    if (d) await this.manager.cancelDeviceConnection(d.id).catch(() => undefined);
    this.ev.onConnection?.(false);
  }

  private cleanup() {
    this.subs.forEach((s) => s.remove());
    this.subs = [];
    this.device = null;
    this.asm = null;
    if (this.audioJob) this.audioJob.cancelled = true;
    this.audioJob = null;
    const w = this.waiters;
    this.waiters = [];
    w.forEach((x) => x.resolve(null));
  }

  // ---- notifications ----------------------------------------------------------------
  private onStatus(err: BleError | null, c: Characteristic | null) {
    if (err || !c?.value) return;
    this.handleStatus(P.fromBase64(c.value));
  }
  private handleStatus(b: Uint8Array) {
    if (b.length < 12) return;
    this.status = P.unpackStatus(b);
    this.ev.onStatus?.(this.status);
  }

  private onEvent(err: BleError | null, c: Characteristic | null) {
    if (err) {
      this.log(`events unavailable (${err.message})`);
      return;
    }
    if (!c?.value) return;
    const b = P.fromBase64(c.value);
    if (b.length < P.EVENT_LEN) return;
    const e = P.unpackEvent(b);
    if (e.event === P.RingEvent.AUDIO_UNDERRUN) this.log('ring speaker underrun');
    const keep: Waiter[] = [];
    for (const w of this.waiters) (w.event === e.event ? w.resolve(e) : keep.push(w));
    this.waiters = keep;
    this.ev.onEvent?.(e);
  }

  /** Resolve with the next event of this kind, or null after timeoutMs / on disconnect. */
  waitForEvent(event: P.RingEvent, timeoutMs: number): Promise<P.Event | null> {
    return new Promise((resolve) => {
      const w: Waiter = { event, resolve: (e) => { clearTimeout(timer); resolve(e); } };
      const timer = setTimeout(() => {
        this.waiters = this.waiters.filter((x) => x !== w);
        resolve(null);
      }, timeoutMs);
      this.waiters.push(w);
    });
  }

  private onMeta(err: BleError | null, c: Characteristic | null) {
    if (err || !c?.value) return;
    const b = P.fromBase64(c.value);
    if (P.isXferEnd(b)) {
      void this.finish(P.xferEndId(b));
      return;
    }
    if (b.length >= 20) {
      const start = P.unpackXferStart(b);
      this.asm = new P.TransferAssembler(start);
      this.t0 = Date.now();
      this.log(`transfer ${start.xferId}: ${start.totalLen} B in ${start.nChunks} chunks`);
    }
  }

  private onData(err: BleError | null, c: Characteristic | null) {
    if (err || !c?.value || !this.asm) return;
    const { xferId, idx, payload } = P.unpackChunk(P.fromBase64(c.value));
    if (xferId !== this.asm.start.xferId) return;
    this.asm.add(idx, payload);
    if ((idx & 7) === 0) this.ev.onProgress?.(xferId, this.asm.progress);
  }

  private async finish(xferId: number) {
    const asm = this.asm;
    if (!asm || asm.start.xferId !== xferId) return;
    const missing = asm.missing;
    if (missing.length) {
      this.log(`transfer ${xferId}: ${missing.length} missing, requesting resend`);
      await this.writeControl(P.ackTransfer(xferId, missing.slice(0, 200)));
      return;
    }
    let data: Uint8Array;
    try {
      data = asm.assemble();
    } catch (e) {
      this.log(`transfer ${xferId} corrupt (${(e as Error).message}); full resend`);
      await this.writeControl(P.ackTransfer(xferId, Array.from({ length: asm.start.nChunks }, (_, i) => i).slice(0, 200)));
      return;
    }
    await this.writeControl(P.ackTransfer(xferId));
    this.asm = null;
    const seconds = (Date.now() - this.t0) / 1000;
    this.ev.onProgress?.(xferId, 1);
    this.ev.onTransfer?.({ start: asm.start, data, seconds });
  }

  // ---- writes ----------------------------------------------------------------------------
  private async write(uuid: string, pkt: Uint8Array) {
    if (!this.device) throw new Error('not connected');
    await this.device.writeCharacteristicWithoutResponseForService(P.UUID_SERVICE, uuid, P.toBase64(pkt));
  }
  writeControl = (pkt: Uint8Array) => this.write(P.UUID_CONTROL, pkt);
  writeFeedback = (pkt: Uint8Array) => this.write(P.UUID_FEEDBACK, pkt);
  writeAudio = (pkt: Uint8Array) => this.write(P.UUID_AUDIO_OUT, pkt);

  capture = (quality = 0, frameSize = 0) => this.writeControl(P.capture(quality, frameSize));
  ping = () => this.writeControl(P.ping());
  abort = () => this.writeControl(P.abort());
  setConfig = (key: P.Cfg, value: number) => this.writeControl(P.setConfig(key, value));
  /** Fixed-length ring-mic clip (legacy); prefer recordStart/recordStop for push-to-talk. */
  recordAudio = (seconds: number) => this.writeControl(P.recordAudio(seconds));
  /** Ring-mic push-to-talk: record now, until recordStop() or 8 s; the clip arrives as an ADPCM transfer. */
  recordStart = () => this.writeControl(P.recordStart());
  recordStop = () => this.writeControl(P.recordStop());
  /** Built-in confirmation cue (listening tick / answer-ready double tick / error buzz), honouring the ring's CUES_MASK. */
  cue = (c: P.Cue) => this.writeFeedback(P.fbCue(c));
  stopFeedback = () => this.writeFeedback(P.fbStop());
  flash = (r: number, g: number, b: number, ms: number) => this.writeFeedback(P.fbRgb(r, g, b, ms));

  /** Push the app's voice settings to the ring (SET_CONFIG 9 / 10 / 11). */
  async applyVoiceConfig(cfg: VoiceConfig): Promise<void> {
    await this.setConfig(P.Cfg.SPEAKER_VOLUME, Math.max(0, Math.min(255, Math.round(cfg.speakerVolume))));
    await this.setConfig(P.Cfg.CUES_MASK, cfg.cuesMask & 7);
    await this.setConfig(P.Cfg.MIC_SOURCE_HINT, cfg.micSource === 'phone' ? P.MicSource.PHONE : P.MicSource.RING);
  }

  /** Legacy silent-pattern output (optional feature; not used by the main UX). */
  async playUnits(units: number[], unitMs: number, channels: number) {
    for (const w of P.fbMorseUnits(units, unitMs, channels, this.writeSize)) {
      await this.writeFeedback(w);
    }
  }
  playMorseText = (text: string, wpm: number, channels: number) => this.writeFeedback(P.fbMorseText(text, wpm, channels));

  // ---- on-ring speaker ---------------------------------------------------------------------
  /**
   * Play a 16 kHz mcring-ADPCM clip on the ring speaker: AUDIO_START, AUDIO_DATA writes sized to the MTU (whole
   * 132-byte blocks only) paced to roughly real time in small bursts, AUDIO_END, then (by default) wait for the
   * ring's AUDIO_DONE. A new stream cancels a running one. `volume` is the per-stream level (255 = unity; the
   * SPEAKER_VOLUME config is the master).
   */
  async streamAudio(adpcm: Uint8Array, volume = 255, opts: { awaitDone?: boolean } = {}): Promise<AudioOutcome> {
    if (!this.device) throw new Error('not connected');
    if (this.audioJob) this.audioJob.cancelled = true;
    const job = { cancelled: false };
    this.audioJob = job;
    const total = Math.floor(adpcm.length / P.ADPCM_BLOCK_BYTES);
    this.log(`speaker: ${total} blocks (${(total * 16) / 1000} s), ${P.audioBlocksPerWrite(this.writeSize)} block(s)/write`);
    // Subscribe to AUDIO_DONE before AUDIO_END goes out so a fast ring cannot beat us to it.
    const donePromise = this.waitForEvent(P.RingEvent.AUDIO_DONE, total * 16 + 10_000);
    const res = await streamAdpcm(adpcm, volume, { maxWrite: this.writeSize }, {
      write: this.writeAudio,
      cancelled: () => job.cancelled,
      onProgress: this.ev.onAudioProgress,
    });
    if (res.cancelled) return 'cancelled';
    if (opts.awaitDone === false) {
      if (this.audioJob === job) this.audioJob = null;
      return 'done';
    }
    const timeout = new Promise<null>((resolve) => setTimeout(() => resolve(null), res.remainingMs + 1500));
    const done = await Promise.race([donePromise, timeout]);
    if (this.audioJob === job) this.audioJob = null;
    if (!done) return job.cancelled ? 'cancelled' : 'timeout';
    return done.arg === 0 ? 'done' : 'stopped';
  }

  /** Flush and stop speaker playback immediately. */
  async stopAudio(): Promise<void> {
    if (this.audioJob) this.audioJob.cancelled = true;
    this.audioJob = null;
    if (this.device) await this.writeAudio(P.audioStop()).catch(() => undefined);
  }

  destroy() {
    this.cleanup();
    this.manager.destroy();
  }
}
