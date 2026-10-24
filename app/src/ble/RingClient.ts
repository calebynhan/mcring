/**
 * Ring BLE client on react-native-ble-plx, implementing protocol/ble-gatt.md.
 * Emits: status, transfer (complete image/audio), progress, connection changes.
 */
import { BleError, BleManager, Characteristic, Device, State, Subscription } from 'react-native-ble-plx';
import * as P from '../lib/proto';

export interface Transfer {
  start: P.XferStart;
  data: Uint8Array;
  seconds: number;
}

export interface RingEvents {
  onStatus?: (s: P.Status) => void;
  onTransfer?: (t: Transfer) => void;
  onProgress?: (xferId: number, fraction: number) => void;
  onConnection?: (connected: boolean, device?: Device) => void;
  onLog?: (line: string) => void;
}

export class RingClient {
  private manager = new BleManager();
  private device: Device | null = null;
  private subs: Subscription[] = [];
  private asm: P.TransferAssembler | null = null;
  private t0 = 0;
  private writeSize = 180;
  status: P.Status | null = null;

  constructor(private ev: RingEvents = {}) {}

  private log(line: string) {
    this.ev.onLog?.(line);
  }

  get connected() {
    return !!this.device;
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
    this.writeSize = Math.max(20, Math.min(512, mtu - 3));
    this.device = d;
    this.log(`connected, MTU ${mtu}`);
    this.subs.push(
      d.monitorCharacteristicForService(P.UUID_SERVICE, P.UUID_STATUS, (e, c) => this.onStatus(e, c)),
      d.monitorCharacteristicForService(P.UUID_SERVICE, P.UUID_XFER_META, (e, c) => this.onMeta(e, c)),
      d.monitorCharacteristicForService(P.UUID_SERVICE, P.UUID_XFER_DATA, (e, c) => this.onData(e, c)),
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

  capture = (quality = 0, frameSize = 0) => this.writeControl(P.capture(quality, frameSize));
  ping = () => this.writeControl(P.ping());
  setConfig = (key: P.Cfg, value: number) => this.writeControl(P.setConfig(key, value));
  recordAudio = (seconds: number) => this.writeControl(P.recordAudio(seconds));
  stopFeedback = () => this.writeFeedback(P.fbStop());
  flash = (r: number, g: number, b: number, ms: number) => this.writeFeedback(P.fbRgb(r, g, b, ms));

  async playUnits(units: number[], unitMs: number, channels: number) {
    for (const w of P.fbMorseUnits(units, unitMs, channels, this.writeSize)) {
      await this.writeFeedback(w);
    }
  }
  playMorseText = (text: string, wpm: number, channels: number) => this.writeFeedback(P.fbMorseText(text, wpm, channels));

  destroy() {
    this.cleanup();
    this.manager.destroy();
  }
}
