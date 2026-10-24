import { useCallback, useEffect, useRef, useState } from 'react';
import * as FileSystem from 'expo-file-system';
import { RingClient, Transfer } from '../ble/RingClient';
import * as P from '../lib/proto';

export interface Capture {
  uri: string;          // file:// path of the JPEG
  bytes: number;
  width: number;
  height: number;
  seconds: number;
  xferId: number;
  at: number;
  voiceAdpcm?: Uint8Array;
}

export function useRing() {
  const clientRef = useRef<RingClient | null>(null);
  const [connected, setConnected] = useState(false);
  const [busy, setBusy] = useState<'idle' | 'scanning' | 'connecting'>('idle');
  const [status, setStatus] = useState<P.Status | null>(null);
  const [progress, setProgress] = useState<number | null>(null);
  const [lastCapture, setLastCapture] = useState<Capture | null>(null);
  const [log, setLog] = useState<string[]>([]);
  const pendingVoice = useRef<Uint8Array | null>(null);
  const [error, setError] = useState<string | null>(null);

  const push = useCallback((line: string) => setLog((l) => [`${new Date().toLocaleTimeString()} ${line}`, ...l].slice(0, 80)), []);

  useEffect(() => {
    const c = new RingClient({
      onLog: push,
      onStatus: setStatus,
      onProgress: (_id, f) => setProgress(f >= 1 ? null : f),
      onConnection: (ok) => {
        setConnected(ok);
        if (!ok) setProgress(null);
      },
      onTransfer: async (t: Transfer) => {
        if (t.start.type === P.XferType.JPEG) {
          const uri = `${FileSystem.cacheDirectory}mcring-${t.start.xferId}-${Date.now()}.jpg`;
          await FileSystem.writeAsStringAsync(uri, P.toBase64(t.data), { encoding: FileSystem.EncodingType.Base64 });
          const cap: Capture = { uri, bytes: t.data.length, width: t.start.width, height: t.start.height, seconds: t.seconds, xferId: t.start.xferId, at: Date.now() };
          if (pendingVoice.current) {
            cap.voiceAdpcm = pendingVoice.current;
            pendingVoice.current = null;
          }
          setLastCapture(cap);
          push(`photo ${t.start.width}x${t.start.height}, ${t.data.length} B in ${t.seconds.toFixed(2)} s`);
        } else if (t.start.type === P.XferType.ADPCM) {
          push(`voice clip ${t.data.length} B`);
          // Attach to the most recent capture if it arrived within 10 s, else keep for the next photo.
          setLastCapture((prev) => {
            if (prev && Date.now() - prev.at < 10000 && !prev.voiceAdpcm) return { ...prev, voiceAdpcm: t.data, at: Date.now() };
            pendingVoice.current = t.data;
            return prev;
          });
        }
      },
    });
    clientRef.current = c;
    return () => c.destroy();
  }, [push]);

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

  return { client: clientRef, connected, busy, status, progress, lastCapture, log, error, connect, disconnect, push };
}
