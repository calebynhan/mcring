/** React hook around RingClient: connection, status, ring events, photos and ring-mic voice clips. */
import { useCallback, useEffect, useRef, useState } from 'react';
import * as FileSystem from 'expo-file-system';
import { AudioOutcome, RingClient, Transfer } from '../ble/RingClient';
import * as P from '../lib/proto';
import type { AppSettings } from '../lib/settings';

export interface Capture {
  uri: string;          // file:// path of the JPEG
  bytes: number;
  width: number;
  height: number;
  seconds: number;
  xferId: number;
  at: number;
  /** Set when a waiting voice turn consumed this photo (so it is not auto-asked a second time). */
  claimed?: boolean;
}

/** A voice clip recorded by the ring's own mic (16 kHz mcring-ADPCM). */
export interface RingVoice {
  adpcm: Uint8Array;
  at: number;
  seconds: number;
  durationMs: number;
  claimed?: boolean;
}

type EventListener = (e: P.Event) => void;

export function useRing(settings: AppSettings) {
  const clientRef = useRef<RingClient | null>(null);
  const [connected, setConnected] = useState(false);
  const [busy, setBusy] = useState<'idle' | 'scanning' | 'connecting'>('idle');
  const [status, setStatus] = useState<P.Status | null>(null);
  const [progress, setProgress] = useState<number | null>(null);
  const [audioProgress, setAudioProgress] = useState<number | null>(null);
  const [lastCapture, setLastCapture] = useState<Capture | null>(null);
  const [lastVoice, setLastVoice] = useState<RingVoice | null>(null);
  const [lastEvent, setLastEvent] = useState<P.Event | null>(null);
  const [log, setLog] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const listeners = useRef(new Set<EventListener>());
  const photoWaiters = useRef<((c: Capture) => void)[]>([]);
  const voiceWaiters = useRef<((v: RingVoice) => void)[]>([]);

  const push = useCallback((line: string) => setLog((l) => [`${new Date().toLocaleTimeString()} ${line}`, ...l].slice(0, 80)), []);

  useEffect(() => {
    const c = new RingClient({
      onLog: push,
      onStatus: setStatus,
      onProgress: (_id, f) => setProgress(f >= 1 ? null : f),
      onAudioProgress: (sent, total) => setAudioProgress(sent >= total ? null : sent / Math.max(1, total)),
      onConnection: (ok) => {
        setConnected(ok);
        if (!ok) {
          setProgress(null);
          setAudioProgress(null);
        }
      },
      onEvent: (e) => {
        setLastEvent(e);
        if (e.event === P.RingEvent.LOW_BATTERY) push(`ring battery low (${e.arg}%)`);
        listeners.current.forEach((fn) => {
          try {
            fn(e);
          } catch (err) {
            push(`event handler failed: ${(err as Error).message}`);
          }
        });
      },
      onTransfer: async (t: Transfer) => {
        if (t.start.type === P.XferType.JPEG) {
          const uri = `${FileSystem.cacheDirectory}mcring-${t.start.xferId}-${Date.now()}.jpg`;
          await FileSystem.writeAsStringAsync(uri, P.toBase64(t.data), { encoding: FileSystem.EncodingType.Base64 });
          const cap: Capture = { uri, bytes: t.data.length, width: t.start.width, height: t.start.height, seconds: t.seconds, xferId: t.start.xferId, at: Date.now() };
          const w = photoWaiters.current;
          photoWaiters.current = [];
          if (w.length) cap.claimed = true;
          w.forEach((fn) => fn(cap));
          setLastCapture(cap);
          push(`photo ${t.start.width}x${t.start.height}, ${t.data.length} B in ${t.seconds.toFixed(2)} s`);
        } else if (t.start.type === P.XferType.ADPCM) {
          const durationMs = Math.floor(t.data.length / P.ADPCM_BLOCK_BYTES) * 16;
          const v: RingVoice = { adpcm: t.data, at: Date.now(), seconds: t.seconds, durationMs };
          const w = voiceWaiters.current;
          voiceWaiters.current = [];
          if (w.length) v.claimed = true;
          w.forEach((fn) => fn(v));
          setLastVoice(v);
          push(`voice clip ${(durationMs / 1000).toFixed(1)} s (${t.data.length} B)`);
        }
      },
    });
    clientRef.current = c;
    return () => c.destroy();
  }, [push]);

  // Keep the ring's voice settings in sync (SET_CONFIG 9/10/11) whenever we are connected.
  const { speakerVolume, cuesMask, micSource } = settings;
  useEffect(() => {
    const c = clientRef.current;
    if (!connected || !c) return;
    c.applyVoiceConfig({ speakerVolume, cuesMask, micSource })
      .then(() => push(`ring config: volume ${speakerVolume}, cues ${cuesMask}, mic ${micSource}`))
      .catch((e) => push(`ring config failed: ${(e as Error).message}`));
  }, [connected, speakerVolume, cuesMask, micSource, push]);

  const connect = useCallback(async () => {
    const c = clientRef.current;
    if (!c) return;
    setError(null);
    try {
      setBusy('scanning');
      await c.waitForBluetooth();
      const dev = await c.scan(12000);
      setBusy('connecting');
      await c.connect(dev);
    } catch (e) {
      setError((e as Error).message);
      push(`connect failed: ${(e as Error).message}`);
    } finally {
      setBusy('idle');
    }
  }, [push]);

  const disconnect = useCallback(() => clientRef.current?.disconnect(), []);

  /** Subscribe to ring events; returns the unsubscribe function. Stable identity. */
  const addEventListener = useCallback((fn: EventListener) => {
    listeners.current.add(fn);
    return () => {
      listeners.current.delete(fn);
    };
  }, []);

  /** Resolve with the next photo from the ring (marked claimed), or null after timeoutMs. */
  const waitForPhoto = useCallback((timeoutMs: number) => new Promise<Capture | null>((resolve) => {
    const fn = (c: Capture) => {
      clearTimeout(timer);
      resolve(c);
    };
    const timer = setTimeout(() => {
      photoWaiters.current = photoWaiters.current.filter((x) => x !== fn);
      resolve(null);
    }, timeoutMs);
    photoWaiters.current.push(fn);
  }), []);

  /** Resolve with the next ring-mic clip (marked claimed), or null after timeoutMs. */
  const waitForVoice = useCallback((timeoutMs: number) => new Promise<RingVoice | null>((resolve) => {
    const fn = (v: RingVoice) => {
      clearTimeout(timer);
      resolve(v);
    };
    const timer = setTimeout(() => {
      voiceWaiters.current = voiceWaiters.current.filter((x) => x !== fn);
      resolve(null);
    }, timeoutMs);
    voiceWaiters.current.push(fn);
  }), []);

  // Best-effort command wrappers: a disconnected ring is not an error for the UI, just a log line.
  const guard = useCallback(<T,>(what: string, run: (c: RingClient) => Promise<T>): Promise<T | null> => {
    const c = clientRef.current;
    if (!c || !c.connected) return Promise.resolve(null);
    return run(c).catch((e) => {
      push(`${what} failed: ${(e as Error).message}`);
      return null;
    });
  }, [push]);

  const capture = useCallback(() => guard('capture', (c) => c.capture()), [guard]);
  const recordStart = useCallback(() => guard('record start', (c) => c.recordStart()), [guard]);
  const recordStop = useCallback(() => guard('record stop', (c) => c.recordStop()), [guard]);
  const cue = useCallback((k: P.Cue) => guard('cue', (c) => c.cue(k)), [guard]);
  const flash = useCallback((r: number, g: number, b: number, ms: number) => guard('flash', (c) => c.flash(r, g, b, ms)), [guard]);
  const streamAudio = useCallback((adpcm: Uint8Array, volume = 255): Promise<AudioOutcome | null> => guard('speaker', (c) => c.streamAudio(adpcm, volume)), [guard]);
  const stopAudio = useCallback(() => guard('speaker stop', (c) => c.stopAudio()), [guard]);

  const speakerOk = !!status && !!(status.flags & P.Flag.SPEAKER_OK);

  return {
    client: clientRef, connected, busy, status, speakerOk, progress, audioProgress, lastCapture, lastVoice, lastEvent, log, error,
    connect, disconnect, push, addEventListener, waitForPhoto, waitForVoice,
    capture, recordStart, recordStop, cue, flash, streamAudio, stopAudio,
  };
}

export type Ring = ReturnType<typeof useRing>;
