import { audioPart, parseAskResponse, parseSpeechClip } from '../src/api/backend';
import { toBase64 } from '../src/lib/proto';

const adpcm = Uint8Array.from({ length: 132 * 3 }, (_, i) => (i * 7) & 255);

const NEW_SHAPE = {
  id: 'abc', session_id: 's1', answer: 'A foxglove.', speech_text: 'A foxglove. Want to know if it is toxic?', follow_up: 'Want to know if it is toxic?',
  subject: 'Digitalis purpurea', confidence: 0.91, warnings: ['toxic if eaten'], mode: 'identify', had_image: true,
  transcript: 'what is this plant', transcript_error: null,
  speech: { format: 'mp3', mime: 'audio/mpeg', audio_b64: toBase64(Uint8Array.from([0xff, 0xfb, 1, 2])), voice: 'alloy' },
  speech_adpcm: { format: 'adpcm16k', mime: 'audio/x-mcring-adpcm', audio_b64: toBase64(adpcm), voice: 'alloy', sample_rate: 16000, blocks: 3, duration_ms: 48 },
  speech_error: null, short: null, morse: null, provider: 'anthropic', model: 'claude', latency_ms: 1234, usage: { input_tokens: 1, output_tokens: 2 }, fallback_model: null,
};

test('parses the voice-first /v1/ask response (no short, optional follow_up, mp3 + adpcm speech)', () => {
  const r = parseAskResponse(NEW_SHAPE);
  expect(r.answer).toBe('A foxglove.');
  expect(r.followUp).toBe('Want to know if it is toxic?');
  expect(r.speechText).toBe('A foxglove. Want to know if it is toxic?');
  expect(r.short).toBeNull();
  expect(r.morse).toBeNull();
  expect(r.hadImage).toBe(true);
  expect(r.transcript).toBe('what is this plant');
  expect(r.speechMp3).toEqual(Uint8Array.from([0xff, 0xfb, 1, 2]));
  expect(r.speechAdpcm?.bytes).toEqual(adpcm);
  expect(r.speechAdpcm?.blocks).toBe(3);
  expect(r.speechAdpcm?.durationMs).toBe(48);
  expect(r.warnings).toEqual(['toxic if eaten']);
  expect(r.latencyMs).toBe(1234);
});

test('tolerates a minimal chat response and derives speech_text', () => {
  const r = parseAskResponse({ id: 'x', session_id: 's', answer: 'Hello.', confidence: 0.5, mode: 'chat', had_image: false, provider: 'openai', model: 'gpt', latency_ms: 10 });
  expect(r.speechText).toBe('Hello.');
  expect(r.followUp).toBeNull();
  expect(r.speech).toBeNull();
  expect(r.speechAdpcm).toBeNull();
  expect(r.speechMp3).toBeNull();
  expect(r.warnings).toEqual([]);
  expect(r.mode).toBe('chat');
});

test('legacy silent-pattern fields are still read when the server was asked for them', () => {
  const r = parseAskResponse({ ...NEW_SHAPE, short: 'R FOXGLOVE', morse: { text: 'R FOXGLOVE', unit_ms: 80, units: [1, 1, 3], duration_ms: 400, ring_packet_b64: '', char_wpm: 15, overall_wpm: 8 } });
  expect(r.short).toBe('R FOXGLOVE');
  expect(r.morse).toEqual({ text: 'R FOXGLOVE', unitMs: 80, units: [1, 1, 3], durationMs: 400 });
});

test('speech clip parsing rejects empty audio', () => {
  expect(parseSpeechClip(null)).toBeNull();
  expect(parseSpeechClip({ format: 'mp3', audio_b64: '' })).toBeNull();
  expect(parseSpeechClip({ format: 'adpcm16k', audio_b64: toBase64(adpcm) })?.bytes).toEqual(adpcm);
});

test('audio uploads: ring ADPCM as a data URI, phone recordings as a file', () => {
  const ring = audioPart(adpcm);
  expect(ring.name).toBe('voice.adpcm');
  expect(ring.type).toBe('audio/x-mcring-adpcm');
  expect(ring.uri).toBe(`data:audio/x-mcring-adpcm;base64,${toBase64(adpcm)}`);
  const phone = audioPart({ uri: 'file:///tmp/v.m4a', name: 'voice.m4a', type: 'audio/mp4' });
  expect(phone).toEqual({ uri: 'file:///tmp/v.m4a', name: 'voice.m4a', type: 'audio/mp4' });
});
