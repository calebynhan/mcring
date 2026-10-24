/**
 * Client for backend/ (FastAPI): POST /v1/ask, POST /v1/transcribe, POST /v1/speech, GET /v1/health.
 * Voice-first: a question is text and/or a voice clip, a photo is optional.
 */
import { fromBase64 } from '../lib/proto';

export type Mode = 'identify' | 'describe' | 'read_text' | 'translate' | 'chat' | 'custom';
export const MODES: Mode[] = ['identify', 'describe', 'read_text', 'translate', 'chat', 'custom'];
export type Provider = '' | 'anthropic' | 'openai';
/** What /v1/ask should render: mp3 for the phone/headphones, adpcm16k for the ring speaker, or both. */
export type SpeechFormat = 'mp3' | 'adpcm16k' | 'both';

/** A recording made on the phone (file:// URI from expo-av) … */
export interface AudioFile { uri: string; name: string; type: string }
/** … or raw mcring-ADPCM bytes from the ring mic. */
export type AudioUpload = AudioFile | Uint8Array;

export interface AskOptions {
  question?: string;
  mode?: Mode;
  provider?: Provider;
  sessionId?: string;
  language?: string;
  /** Voice question. */
  audio?: AudioUpload | null;
  /** null/undefined = server default (TTS when the backend has a provider). */
  wantSpeech?: boolean | null;
  speechFormat?: SpeechFormat;
  voice?: string;
  /** Legacy "silent pattern" output; off by default. */
  wantMorse?: boolean;
}

export interface SpeechClip {
  format: string;        // mp3 | adpcm16k
  mime: string;
  bytes: Uint8Array;
  voice: string;
  sampleRate: number | null;
  blocks: number | null;
  durationMs: number | null;
}

export interface MorseOut { text: string; unitMs: number; units: number[]; durationMs: number }

export interface AskResult {
  id: string;
  sessionId: string;
  answer: string;
  /** answer (+ follow_up): exactly what to read aloud. */
  speechText: string;
  followUp: string | null;
  subject: string;
  confidence: number;
  warnings: string[];
  mode: string;
  hadImage: boolean;
  transcript: string | null;
  transcriptError: string | null;
  /** mp3 for the phone / headphones (when speech was rendered). */
  speechMp3: Uint8Array | null;
  speech: SpeechClip | null;
  /** 16 kHz mcring-ADPCM for the ring speaker (when speech_format was adpcm16k/both). */
  speechAdpcm: SpeechClip | null;
  speechError: string | null;
  /** Legacy silent pattern (only when wantMorse). */
  short: string | null;
  morse: MorseOut | null;
  provider: string;
  model: string;
  latencyMs: number;
}

export interface TranscribeResult { text: string; provider: string; model: string; audioFormat: string; language: string | null; latencyMs: number }
export interface HealthResult { status: string; version: string; provider: string; model: string; tts: string; stt: string; speechDefault: boolean; speechFormats: string[] }

type Json = Record<string, unknown>;
const str = (v: unknown, d = '') => (typeof v === 'string' ? v : d);
const num = (v: unknown, d = 0) => (typeof v === 'number' && Number.isFinite(v) ? v : d);
const optStr = (v: unknown) => (typeof v === 'string' && v.length ? v : null);
const optNum = (v: unknown) => (typeof v === 'number' ? v : null);

export function parseSpeechClip(j: unknown): SpeechClip | null {
  if (!j || typeof j !== 'object') return null;
  const s = j as Json;
  if (!str(s.audio_b64)) return null;
  return {
    format: str(s.format, 'mp3'), mime: str(s.mime, 'audio/mpeg'), bytes: fromBase64(str(s.audio_b64)), voice: str(s.voice),
    sampleRate: optNum(s.sample_rate), blocks: optNum(s.blocks), durationMs: optNum(s.duration_ms),
  };
}

/** Parse an /v1/ask JSON body (new shape: `short` optional, `follow_up` optional, speech + speech_adpcm). */
export function parseAskResponse(j: Json): AskResult {
  const speech = parseSpeechClip(j.speech);
  const speechAdpcm = parseSpeechClip(j.speech_adpcm);
  const m = j.morse && typeof j.morse === 'object' ? (j.morse as Json) : null;
  const answer = str(j.answer);
  const followUp = optStr(j.follow_up);
  return {
    id: str(j.id),
    sessionId: str(j.session_id),
    answer,
    speechText: str(j.speech_text) || (followUp ? `${answer} ${followUp}`.trim() : answer),
    followUp,
    subject: str(j.subject),
    confidence: num(j.confidence, 0),
    warnings: Array.isArray(j.warnings) ? (j.warnings as unknown[]).filter((w): w is string => typeof w === 'string') : [],
    mode: str(j.mode, j.had_image === false ? 'chat' : ''),
    hadImage: j.had_image === true,
    transcript: optStr(j.transcript),
    transcriptError: optStr(j.transcript_error),
    speechMp3: speech && speech.format === 'mp3' ? speech.bytes : null,
    speech,
    speechAdpcm,
    speechError: optStr(j.speech_error),
    short: optStr(j.short) ?? (m ? optStr(m.text) : null),
    morse: m && Array.isArray(m.units) ? { text: str(m.text), unitMs: num(m.unit_ms, 80), units: m.units as number[], durationMs: num(m.duration_ms) } : null,
    provider: str(j.provider),
    model: str(j.model),
    latencyMs: num(j.latency_ms),
  };
}

/** Multipart field name/filename/mime for an audio upload (the backend sniffs by filename/mime, then content). */
export function audioPart(a: AudioUpload): { uri: string; name: string; type: string } {
  if (a instanceof Uint8Array) {
    // RN FormData has no Blob for raw bytes on all platforms; send as a base64 data URI "file".
    return { uri: `data:audio/x-mcring-adpcm;base64,${btoaBytes(a)}`, name: 'voice.adpcm', type: 'audio/x-mcring-adpcm' };
  }
  return { uri: a.uri, name: a.name || 'voice.m4a', type: a.type || 'audio/mp4' };
}

async function errorDetail(r: Response): Promise<string> {
  let detail = `${r.status}`;
  try {
    const j = (await r.json()) as Json;
    detail = str(j.detail, detail);
  } catch {
    /* non-JSON error body */
  }
  return detail;
}

export class BackendClient {
  constructor(private baseUrl: string, private token = '') {}

  private url(path: string) { return `${this.baseUrl.replace(/\/$/, '')}${path}`; }

  private headers(extra: Record<string, string> = {}): Record<string, string> {
    return this.token ? { Authorization: `Bearer ${this.token}`, ...extra } : extra;
  }

  async health(): Promise<HealthResult> {
    const r = await fetch(this.url('/v1/health'), { headers: this.headers() });
    if (!r.ok) throw new Error(`health ${r.status}`);
    const j = (await r.json()) as Json;
    return {
      status: str(j.status), version: str(j.version), provider: str(j.provider), model: str(j.model), tts: str(j.tts), stt: str(j.stt),
      speechDefault: j.speech_default === true, speechFormats: Array.isArray(j.speech_formats) ? (j.speech_formats as string[]) : ['mp3'],
    };
  }

  /**
   * One voice/text turn. `imageUri` is a file:// URI or null (pure chat, or re-use the session's photo).
   * React Native FormData accepts {uri,name,type} objects as files.
   */
  async ask(imageUri: string | null, o: AskOptions = {}): Promise<AskResult> {
    const fd = new FormData();
    if (imageUri) fd.append('image', { uri: imageUri, name: 'ring.jpg', type: 'image/jpeg' } as unknown as Blob);
    if (o.audio) fd.append('audio', audioPart(o.audio) as unknown as Blob);
    fd.append('question', o.question ?? '');
    fd.append('mode', o.mode ?? (imageUri ? 'identify' : 'chat'));
    fd.append('provider', o.provider ?? '');
    fd.append('session_id', o.sessionId ?? '');
    fd.append('language', o.language ?? 'en');
    if (o.wantSpeech !== undefined && o.wantSpeech !== null) fd.append('want_speech', o.wantSpeech ? 'true' : 'false');
    fd.append('speech_format', o.speechFormat ?? 'mp3');
    if (o.voice) fd.append('voice', o.voice);
    fd.append('want_morse', o.wantMorse ? 'true' : 'false');

    const r = await fetch(this.url('/v1/ask'), { method: 'POST', body: fd, headers: this.headers() });
    if (!r.ok) throw new Error(`backend error: ${await errorDetail(r)}`);
    return parseAskResponse((await r.json()) as Json);
  }

  /** Speech-to-text only (push-to-talk preview / typed-correction flows). */
  async transcribe(audio: AudioUpload, language = ''): Promise<TranscribeResult> {
    const fd = new FormData();
    fd.append('audio', audioPart(audio) as unknown as Blob);
    fd.append('language', language);
    const r = await fetch(this.url('/v1/transcribe'), { method: 'POST', body: fd, headers: this.headers() });
    if (!r.ok) throw new Error(`transcribe error: ${await errorDetail(r)}`);
    const j = (await r.json()) as Json;
    return { text: str(j.text), provider: str(j.provider), model: str(j.model), audioFormat: str(j.audio_format), language: optStr(j.language), latencyMs: num(j.latency_ms) };
  }

  /** Text-to-speech: mp3 for the phone, or adpcm16k for the ring speaker. */
  async speech(text: string, o: { voice?: string; format?: 'mp3' | 'adpcm16k' } = {}): Promise<SpeechClip> {
    const r = await fetch(this.url('/v1/speech'), {
      method: 'POST',
      headers: this.headers({ 'Content-Type': 'application/json', Accept: 'application/json' }),
      body: JSON.stringify({ text, voice: o.voice ?? '', format: o.format ?? 'mp3' }),
    });
    if (!r.ok) throw new Error(`speech error: ${await errorDetail(r)}`);
    const clip = parseSpeechClip(await r.json());
    if (!clip) throw new Error('speech error: empty audio');
    return clip;
  }
}

function btoaBytes(b: Uint8Array): string {
  let s = '';
  for (let i = 0; i < b.length; i += 0x8000) s += String.fromCharCode.apply(null, Array.from(b.subarray(i, i + 0x8000)));
  // global btoa exists in RN (Hermes) and browsers
  return (globalThis as unknown as { btoa: (s: string) => string }).btoa(s);
}
