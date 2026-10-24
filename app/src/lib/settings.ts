/** App settings: types, defaults and the (pure) migration from stored JSON. No React Native imports, so jest can test it. */
import type { Mode, Provider } from '../api/backend';

/** Where the spoken question is recorded: the ring's PDM mic, or the phone / connected headset mic. */
export type MicSource = 'ring' | 'phone';
/** How the answer is voiced on the phone side: on-device TTS, or server-rendered mp3 (same voice everywhere). */
export type SpeakVia = 'phone-tts' | 'server';

/** CUES_MASK bits (SET_CONFIG key 10). */
export const CUE_HAPTIC = 1;
export const CUE_LED = 2;
export const CUE_BEEP = 4;

export interface AppSettings {
  backendUrl: string;
  token: string;
  provider: Provider;
  /** Mode used when a photo is attached (pure voice turns are 'chat' on the backend anyway). */
  mode: Mode;
  language: string;
  micSource: MicSource;
  /** Speak answers on the phone (routes to connected Bluetooth headphones automatically). */
  speak: boolean;
  speakVia: SpeakVia;
  /** Voice name: an expo-speech voice identifier for phone-tts, or the server TTS voice name. */
  voice: string;
  /** Also play answers on the ring's own speaker (stage-1 oversized ring; needs SPEAKER_OK). */
  ringSpeaker: boolean;
  /** SET_CONFIG 9: 0..255 master volume of the ring speaker. */
  speakerVolume: number;
  /** SET_CONFIG 10: bit0 haptic, bit1 LED, bit2 beep. */
  cuesMask: number;
  /** A photo that arrives without a voice question (short press / Take photo) is asked about right away. */
  autoAskPhoto: boolean;
}

export const DEFAULTS: AppSettings = {
  backendUrl: 'http://192.168.1.10:8000',
  token: '',
  provider: '',
  mode: 'identify',
  language: 'en-US',
  micSource: 'ring',
  speak: true,
  speakVia: 'phone-tts',
  voice: '',
  ringSpeaker: false,
  speakerVolume: 200,
  cuesMask: CUE_HAPTIC | CUE_LED,
  autoAskPhoto: true,
};

export const MODE_VALUES: Mode[] = ['identify', 'describe', 'read_text', 'translate', 'chat', 'custom'];

const clampByte = (v: unknown, d: number) => (typeof v === 'number' && Number.isFinite(v) ? Math.max(0, Math.min(255, Math.round(v))) : d);

/** Merge a stored (possibly older / partial) settings object onto the defaults. */
export function migrateSettings(raw: unknown): AppSettings {
  if (!raw || typeof raw !== 'object') return { ...DEFAULTS };
  const r = raw as Record<string, unknown>;
  const s: AppSettings = { ...DEFAULTS };
  if (typeof r.backendUrl === 'string') s.backendUrl = r.backendUrl;
  if (typeof r.token === 'string') s.token = r.token;
  if (r.provider === '' || r.provider === 'anthropic' || r.provider === 'openai') s.provider = r.provider;
  if (typeof r.mode === 'string' && (MODE_VALUES as string[]).includes(r.mode)) s.mode = r.mode as Mode;
  if (typeof r.language === 'string' && r.language) s.language = r.language;
  if (r.micSource === 'ring' || r.micSource === 'phone') s.micSource = r.micSource;
  if (typeof r.speak === 'boolean') s.speak = r.speak;
  if (r.speakVia === 'phone-tts' || r.speakVia === 'server') s.speakVia = r.speakVia;
  else if (typeof r.serverTts === 'boolean') s.speakVia = r.serverTts ? 'server' : 'phone-tts';   // v1 field
  if (typeof r.voice === 'string') s.voice = r.voice;
  if (typeof r.ringSpeaker === 'boolean') s.ringSpeaker = r.ringSpeaker;
  s.speakerVolume = clampByte(r.speakerVolume, DEFAULTS.speakerVolume);
  s.cuesMask = clampByte(r.cuesMask, DEFAULTS.cuesMask) & 7;
  if (typeof r.autoAskPhoto === 'boolean') s.autoAskPhoto = r.autoAskPhoto;
  // v1 Morse fields (charWpm, overallWpm, channels, phoneMorse) are dropped: Morse is no longer part of the app UX.
  return s;
}
