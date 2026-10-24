import * as P from '../src/lib/proto';

const hex = (b: Uint8Array) => Buffer.from(b).toString('hex');

test('control packets match the Python codec', () => {
  expect(hex(P.capture(12, 2))).toBe('010c02');
  expect(hex(P.ackTransfer(7))).toBe('020700000000');
  expect(hex(P.ackTransfer(7, [1, 300]))).toBe('02070001020001002c01');
  expect(hex(P.setConfig(P.Cfg.MORSE_WPM, -1))).toBe('0307ffffffff');
  expect(hex(P.fbMorseText('SOS', 15, 3))).toBe('100f0303534f53');
  expect(hex(P.fbRgb(1, 2, 3, 500))).toBe('13010203f401');
});

test('MORSE_UNITS split and reassemble', () => {
  const units = Array.from({ length: 600 }, (_, i) => (i % 200) + 1);
  const writes = P.fbMorseUnits(units, 80, 3, 100);
  expect(writes[0][0]).toBe(P.Fb.MORSE_UNITS);
  expect(writes[0][3] | (writes[0][4] << 8)).toBe(600);
  expect(writes.every((w) => w.length <= 100)).toBe(true);
  const buf = new Uint8Array(600);
  buf.set(writes[0].subarray(5), 0);
  for (const w of writes.slice(1)) buf.set(w.subarray(3), w[1] | (w[2] << 8));
  expect(Array.from(buf)).toEqual(units);
});

test('status and transfer decoding', () => {
  const st = P.unpackStatus(Uint8Array.from([1, 2, 0xe4, 0x0e, 77, 0x22, 0xd2, 0x04, 0, 0, 0, 1]));
  expect(st).toEqual({ version: 1, state: 2, batteryMv: 3812, batteryPct: 77, flags: 0x22, uptimeS: 1234, lastError: 0, queued: 1 });
  expect(P.statusFlags(st).camera).toBe(true);

  const data = Uint8Array.from(Array.from({ length: 2560 }, (_, i) => i & 255));
  const chunkLen = P.chunkLenForMtu(185);
  expect(chunkLen).toBe(178);
  const n = Math.ceil(data.length / chunkLen);
  const start: P.XferStart = { type: P.XferType.JPEG, xferId: 5, totalLen: data.length, chunkLen, nChunks: n, crc32: P.crc32(data), width: 320, height: 240, seqFlags: 1 };
  const asm = new P.TransferAssembler(start);
  for (let i = 0; i < n; i++) if (i !== 3) asm.add(i, data.subarray(i * chunkLen, (i + 1) * chunkLen));
  expect(asm.missing).toEqual([3]);
  expect(() => asm.assemble()).toThrow();
  asm.add(3, data.subarray(3 * chunkLen, 4 * chunkLen));
  expect(Array.from(asm.assemble())).toEqual(Array.from(data));
});

test('crc32 and base64', () => {
  expect(P.crc32(new TextEncoder().encode('123456789'))).toBe(0xcbf43926);
  const b = Uint8Array.from([0, 1, 2, 253, 254, 255]);
  expect(P.toBase64(b)).toBe(Buffer.from(b).toString('base64'));
  expect(Array.from(P.fromBase64(P.toBase64(b)))).toEqual(Array.from(b));
  expect(Array.from(P.fromBase64('AQ=='))).toEqual([1]);
});
