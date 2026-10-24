import { CUE_HAPTIC, CUE_LED, DEFAULTS, migrateSettings } from '../src/lib/settings';

test('defaults are voice-first: ring mic, phone speech, cues on, no Morse fields', () => {
  expect(DEFAULTS.micSource).toBe('ring');
  expect(DEFAULTS.speak).toBe(true);
  expect(DEFAULTS.speakVia).toBe('phone-tts');
  expect(DEFAULTS.ringSpeaker).toBe(false);
  expect(DEFAULTS.cuesMask).toBe(CUE_HAPTIC | CUE_LED);
  expect(Object.keys(DEFAULTS)).not.toEqual(expect.arrayContaining(['charWpm', 'overallWpm', 'channels', 'phoneMorse']));
});

test('migrates v1 settings (serverTts → speakVia) and drops the Morse options', () => {
  const v1 = { backendUrl: 'http://10.0.0.5:8000', token: 't', provider: 'anthropic', mode: 'describe', charWpm: 15, overallWpm: 8, channels: 3, speak: false, serverTts: true, phoneMorse: true, language: 'de-DE' };
  const s = migrateSettings(v1);
  expect(s.backendUrl).toBe('http://10.0.0.5:8000');
  expect(s.provider).toBe('anthropic');
  expect(s.mode).toBe('describe');
  expect(s.speak).toBe(false);
  expect(s.speakVia).toBe('server');
  expect(s.language).toBe('de-DE');
  expect(s.micSource).toBe('ring');
  expect((s as unknown as Record<string, unknown>).phoneMorse).toBeUndefined();
});

test('clamps and validates stored values', () => {
  const s = migrateSettings({ speakerVolume: 999, cuesMask: 0xff, mode: 'bogus', micSource: 'laptop', speakVia: 'x', provider: 'nope' });
  expect(s.speakerVolume).toBe(255);
  expect(s.cuesMask).toBe(7);
  expect(s.mode).toBe(DEFAULTS.mode);
  expect(s.micSource).toBe(DEFAULTS.micSource);
  expect(s.speakVia).toBe(DEFAULTS.speakVia);
  expect(s.provider).toBe('');
  expect(migrateSettings(null)).toEqual(DEFAULTS);
  expect(migrateSettings('junk')).toEqual(DEFAULTS);
});
