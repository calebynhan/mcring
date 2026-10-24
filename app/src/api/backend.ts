/** Client for backend/ (POST /v1/ask). */
import { fromBase64 } from '../lib/proto';

export interface AskOptions {
  question?: string;
  mode?: 'identify' | 'describe' | 'read_text' | 'translate' | 'custom';
  provider?: '' | 'anthropic' | 'openai';
  sessionId?: string;
  wantSpeech?: boolean;
  charWpm?: number;
  overallWpm?: number;
  channels?: number;
  language?: string;
  audioAdpcm?: Uint8Array | null;
}

export interface AskResult {
  id: string;
  sessionId: string;
  answer: string;
  short: string;
  subject: string;
  confidence: number;
  warnings: string[];
  morse: { text: string; unitMs: number; units: number[]; durationMs: number } | null;
  speechMp3: Uint8Array | null;
  transcript: string | null;
  provider: string;
  model: string;
  latencyMs: number;
}

export class BackendClient {
  constructor(private baseUrl: string, private token = '') {}

  private headers(): Record<string, string> {
    return this.token ? { Authorization: `Bearer ${this.token}` } : {};
  }

  async health(): Promise<{ status: string; provider: string; model: string }> {
    const r = await fetch(`${this.baseUrl.replace(/\/$/, '')}/v1/health`, { headers: this.headers() });
    if (!r.ok) throw new Error(`health ${r.status}`);
    return r.json();
  }

  /** `imageUri` is a file:// URI (React Native FormData accepts {uri,name,type}). */
  async ask(imageUri: string | null, o: AskOptions = {}): Promise<AskResult> {
    const fd = new FormData();
    if (imageUri) fd.append('image', { uri: imageUri, name: 'ring.jpg', type: 'image/jpeg' } as unknown as Blob);
    if (o.audioAdpcm) {
      // RN FormData has no Blob for raw bytes on all platforms; send as base64 data URI file.
      fd.append('audio', { uri: `data:audio/x-mcring-adpcm;base64,${btoaBytes(o.audioAdpcm)}`, name: 'voice.adpcm', type: 'audio/x-mcring-adpcm' } as unknown as Blob);
    }
    fd.append('question', o.question ?? '');
    fd.append('mode', o.mode ?? 'identify');
    fd.append('provider', o.provider ?? '');
    fd.append('session_id', o.sessionId ?? '');
    fd.append('want_morse', 'true');
    fd.append('want_speech', o.wantSpeech ? 'true' : 'false');
    fd.append('morse_char_wpm', String(o.charWpm ?? 15));
    fd.append('morse_overall_wpm', String(o.overallWpm ?? 8));
    fd.append('morse_channels', String(o.channels ?? 3));
    fd.append('language', o.language ?? 'en');

    const r = await fetch(`${this.baseUrl.replace(/\/$/, '')}/v1/ask`, { method: 'POST', body: fd, headers: this.headers() });
    if (!r.ok) {
      let detail = `${r.status}`;
      try {
        detail = (await r.json()).detail ?? detail;
      } catch {
        /* ignore */
      }
      throw new Error(`backend error: ${detail}`);
    }
    const j = await r.json();
    return {
      id: j.id,
      sessionId: j.session_id,
      answer: j.answer,
      short: j.short,
      subject: j.subject ?? '',
      confidence: j.confidence,
      warnings: j.warnings ?? [],
      morse: j.morse ? { text: j.morse.text, unitMs: j.morse.unit_ms, units: j.morse.units, durationMs: j.morse.duration_ms } : null,
      speechMp3: j.speech?.audio_b64 ? fromBase64(j.speech.audio_b64) : null,
      transcript: j.transcript ?? null,
      provider: j.provider,
      model: j.model,
      latencyMs: j.latency_ms,
    };
  }
}

function btoaBytes(b: Uint8Array): string {
  let s = '';
  for (let i = 0; i < b.length; i++) s += String.fromCharCode(b[i]);
  // global btoa exists in RN (Hermes) and browsers
  return (globalThis as unknown as { btoa: (s: string) => string }).btoa(s);
}
