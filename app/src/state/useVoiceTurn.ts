/**
 * The voice-first turn: hold (ring button, phone button or double tap) → record a question with the ring mic or the
 * phone/headset mic → POST /v1/ask with the latest photo if one is fresh → show the transcript → speak the answer on
 * the phone (→ headphones) and/or stream it to the ring speaker.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { AskResult, AudioUpload, BackendClient, SpeechFormat } from '../api/backend';
import * as P from '../lib/proto';
import { PhoneRecorder } from '../lib/recorder';
import type { AppSettings } from '../lib/settings';
import { speak, stopSpeaking } from '../lib/speech';
import { pulse } from '../lib/vibrate';
import type { Capture, Ring } from './useRing';

export type Phase = 'idle' | 'listening' | 'thinking' | 'speaking';
export type Role = 'you' | 'claude' | 'system';

export interface Turn {
  id: string;
  role: Role;
  text: string;
  at: number;
  imageUri?: string;
  subject?: string;
  confidence?: number;
  warnings?: string[];
  followUp?: string | null;
  meta?: string;
  pending?: boolean;
}

/** A photo counts as "what I am looking at" for this long after it arrived. */
export const FRESH_PHOTO_MS = 20_000;
/** A press held at least this long (BUTTON_UP.arg in tenths) is an "ask", shorter is a photo. */
export const LONG_PRESS_TENTHS = 7;
export const LONG_PRESS_MS = 700;
/** Hands-free (double tap) recording length with the phone mic. */
export const DOUBLE_TAP_RECORD_MS = 8_000;
/** How long to wait for a photo the ring is capturing for this turn. */
export const PHOTO_WAIT_MS = 4_000;
/** After a ring-mic press ends, its ADPCM clip is expected within this long; photos arriving meanwhile wait for it. */
export const EXPECT_VOICE_MS = 15_000;

let turnSeq = 0;
const newId = () => `${Date.now().toString(36)}-${(turnSeq++).toString(36)}`;

export interface AskInput {
  audio?: AudioUpload | null;
  imageUri?: string | null;
  question?: string;
  /** Shown in the transcript while the request is in flight. */
  label?: string;
}

export function useVoiceTurn(ring: Ring, settings: AppSettings) {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [phase, setPhase] = useState<Phase>('idle');
  const [sessionId, setSessionId] = useState('');
  const [typed, setTyped] = useState('');

  const settingsRef = useRef(settings);
  settingsRef.current = settings;
  const ringRef = useRef(ring);
  ringRef.current = ring;
  const typedRef = useRef('');
  typedRef.current = typed;
  const sessionRef = useRef('');
  const phaseRef = useRef<Phase>('idle');
  const busyRef = useRef(false);
  const recorder = useMemo(() => new PhoneRecorder(), []);
  const sentPhotoRef = useRef<string | null>(null);
  const expectVoiceUntil = useRef(0);
  const holdTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const autoStopTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const photoInFlight = useRef<Promise<Capture | null> | null>(null);
  const listeningRef = useRef<'phone' | 'ring' | null>(null);
  /** Bumped by stop/cancel so a startListening() still awaiting the recorder knows the press already ended. */
  const startSeq = useRef(0);

  const setPhaseBoth = useCallback((p: Phase) => {
    phaseRef.current = p;
    setPhase(p);
  }, []);

  const push = useCallback((t: Omit<Turn, 'id' | 'at'>) => {
    const turn: Turn = { ...t, id: newId(), at: Date.now() };
    setTurns((prev) => [...prev, turn].slice(-80));
    return turn.id;
  }, []);
  const patch = useCallback((id: string, p: Partial<Turn>) => setTurns((prev) => prev.map((t) => (t.id === id ? { ...t, ...p } : t))), []);
  const system = useCallback((text: string) => push({ role: 'system', text }), [push]);

  /** The latest ring photo if it is fresh and has not been sent to the backend yet (the session keeps the last one). */
  const freshPhotoUri = useCallback((): string | null => {
    const cap = ringRef.current.lastCapture;
    if (!cap || Date.now() - cap.at > FRESH_PHOTO_MS) return null;
    return cap.uri === sentPhotoRef.current ? null : cap.uri;
  }, []);

  const speakAnswer = useCallback(async (res: AskResult) => {
    const s = settingsRef.current;
    const r = ringRef.current;
    const jobs: Promise<unknown>[] = [];
    if (s.speak) jobs.push(speak(res.speechText, s.speakVia === 'server' ? res.speechMp3 : null, s.language, s.voice).catch((e) => r.push(`speech failed: ${(e as Error).message}`)));
    if (s.ringSpeaker && r.connected) {
      if (res.speechAdpcm) jobs.push(r.streamAudio(res.speechAdpcm.bytes, 255).then((o) => o && o !== 'done' && r.push(`ring speaker: ${o}`)));
      else r.push(`ring speaker: no audio from server${res.speechError ? ` (${res.speechError})` : ''}`);
    }
    if (!jobs.length) return;
    setPhaseBoth('speaking');
    await Promise.all(jobs);
  }, [setPhaseBoth]);

  /** One request/answer cycle. */
  const runAsk = useCallback(async (input: AskInput): Promise<AskResult | null> => {
    if (busyRef.current) {
      system('Still working on the previous question…');
      return null;
    }
    const s = settingsRef.current;
    const r = ringRef.current;
    busyRef.current = true;
    setPhaseBoth('thinking');
    const question = (input.question ?? '').trim();
    const imageUri = input.imageUri ?? null;
    const youId = push({ role: 'you', text: input.label ?? (question || (input.audio ? '🎤 …' : 'What is this?')), imageUri: imageUri ?? undefined, pending: !!input.audio && !question });
    void r.flash(0, 0, 60, 300);
    try {
      const wantsPhoneMp3 = s.speak && s.speakVia === 'server';
      const wantsRing = s.ringSpeaker && r.connected && (r.speakerOk || !r.status);
      const speechFormat: SpeechFormat = wantsPhoneMp3 && wantsRing ? 'both' : wantsRing ? 'adpcm16k' : 'mp3';
      const be = new BackendClient(s.backendUrl, s.token);
      const res = await be.ask(imageUri, {
        question,
        mode: imageUri ? s.mode : (sessionRef.current ? s.mode : 'chat'),
        provider: s.provider,
        sessionId: sessionRef.current,
        language: s.language,
        audio: input.audio ?? null,
        wantSpeech: wantsPhoneMp3 || wantsRing,
        speechFormat,
        voice: s.speakVia === 'server' ? s.voice : '',
      });
      sessionRef.current = res.sessionId;
      setSessionId(res.sessionId);
      if (imageUri) sentPhotoRef.current = imageUri;
      const youText = res.transcript ? (question ? `${question} — ${res.transcript}` : res.transcript) : question || (input.audio ? '(voice question)' : 'What is this?');
      patch(youId, { text: youText, pending: false, meta: res.transcriptError ? `transcription failed: ${res.transcriptError}` : undefined });
      push({
        role: 'claude', text: res.answer, followUp: res.followUp, subject: res.subject, confidence: res.confidence, warnings: res.warnings,
        meta: `${res.hadImage ? 'photo · ' : ''}${res.model || res.provider} · ${res.latencyMs} ms${res.speechError ? ` · speech: ${res.speechError}` : ''}`,
      });
      r.push(`${res.subject || res.mode} (${Math.round(res.confidence * 100)}%, ${res.latencyMs} ms)`);
      void r.cue(P.Cue.ANSWER_READY);
      await speakAnswer(res);
      return res;
    } catch (e) {
      const msg = (e as Error).message;
      patch(youId, { pending: false });
      system(`Sorry — ${msg}`);
      r.push(`ask failed: ${msg}`);
      void r.cue(P.Cue.ERROR);
      return null;
    } finally {
      busyRef.current = false;
      if (phaseRef.current !== 'listening') setPhaseBoth('idle');
    }
  }, [push, patch, system, speakAnswer, setPhaseBoth]);

  /** Capture a photo for this turn if the mode wants one and none is fresh. */
  const photoForTurn = useCallback(async (): Promise<string | null> => {
    const fresh = freshPhotoUri();
    if (fresh) return fresh;
    const inflight = photoInFlight.current;
    photoInFlight.current = null;
    if (inflight) return (await inflight)?.uri ?? null;
    const r = ringRef.current;
    if (settingsRef.current.mode === 'chat' || !r.connected) return null;
    const p = r.waitForPhoto(PHOTO_WAIT_MS);
    await r.capture();
    return (await p)?.uri ?? null;
  }, [freshPhotoUri]);

  const clearTimers = () => {
    if (holdTimer.current) clearTimeout(holdTimer.current);
    if (autoStopTimer.current) clearTimeout(autoStopTimer.current);
    holdTimer.current = null;
    autoStopTimer.current = null;
  };

  /**
   * Start recording a question. `origin` decides whether the ring is told to record or the phone records.
   * Pressing while an answer is being spoken interrupts it (barge-in); pressing while thinking is ignored.
   */
  const startListening = useCallback(async (origin: 'phone-button' | 'ring-button' | 'double-tap') => {
    if (listeningRef.current || phaseRef.current === 'thinking') return;
    const s = settingsRef.current;
    const r = ringRef.current;
    const useRingMic = s.micSource === 'ring' && r.connected && origin !== 'ring-button';
    // Claim the slot synchronously so a BUTTON_UP that lands during the awaits below is seen by stop/cancel.
    const token = ++startSeq.current;
    listeningRef.current = useRingMic ? 'ring' : 'phone';
    const alive = () => startSeq.current === token && listeningRef.current !== null;
    pulse();
    await stopSpeaking();
    void r.stopAudio();
    if (!alive()) return;
    if (useRingMic) {
      // The ring records itself (RECORD_START); its clip arrives as an ADPCM transfer and is asked about on arrival.
      expectVoiceUntil.current = Date.now() + EXPECT_VOICE_MS;
      await r.recordStart();
      if (!alive()) {
        void r.recordStop();                      // the press ended before RECORD_START went out
        return;
      }
    } else {
      try {
        await recorder.start();
      } catch (e) {
        if (alive()) {
          listeningRef.current = null;
          setPhaseBoth('idle');
          system(`Microphone: ${(e as Error).message}`);
        }
        return;
      }
      if (!alive()) {
        await recorder.cancel();                  // the press ended while the recorder was starting
        return;
      }
      if (origin !== 'ring-button') void r.cue(P.Cue.LISTENING);   // the ring already ticks for its own button
    }
    setPhaseBoth('listening');
    if (origin === 'double-tap' && !useRingMic) {
      autoStopTimer.current = setTimeout(() => void stopListeningRef.current(), DOUBLE_TAP_RECORD_MS);
    }
  }, [recorder, system, setPhaseBoth]);

  /** Wait (briefly) for an interrupted answer to wind down before starting the next request. */
  const waitIdle = async (ms: number) => {
    const until = Date.now() + ms;
    while (busyRef.current && Date.now() < until) await new Promise((res) => setTimeout(res, 50));
  };

  /** Stop recording and ask. */
  const stopListening = useCallback(async () => {
    clearTimers();
    startSeq.current++;
    const mode = listeningRef.current;
    listeningRef.current = null;
    if (!mode) return;
    const r = ringRef.current;
    if (mode === 'ring') {
      await r.recordStop();              // REC_STOPPED + ADPCM transfer follow; the lastVoice effect asks
      if (phaseRef.current === 'listening') setPhaseBoth('idle');
      return;
    }
    const clip = await recorder.stop();
    if (!clip) {
      if (phaseRef.current === 'listening') setPhaseBoth('idle');
      r.push('voice clip too short, ignored');
      return;
    }
    setPhaseBoth('thinking');
    await waitIdle(2000);
    const imageUri = await photoForTurn();
    await runAsk({ audio: clip, imageUri, question: typedRef.current, label: typedRef.current || `🎤 ${(clip.durationMs / 1000).toFixed(1)} s` });
    setTyped('');
  }, [recorder, photoForTurn, runAsk, setPhaseBoth]);
  const stopListeningRef = useRef(stopListening);
  stopListeningRef.current = stopListening;

  /** Abandon the current recording (short press = photo only). */
  const cancelListening = useCallback(async () => {
    clearTimers();
    startSeq.current++;
    const mode = listeningRef.current;
    listeningRef.current = null;
    photoInFlight.current = null;
    if (mode === 'phone') await recorder.cancel();
    if (mode === 'ring') void ringRef.current.recordStop();
    if (phaseRef.current === 'listening') setPhaseBoth('idle');
  }, [recorder, setPhaseBoth]);

  // ---- ring events -------------------------------------------------------------------------------------------
  useEffect(() => ring.addEventListener((e) => {
    const s = settingsRef.current;
    const r = ringRef.current;
    switch (e.event) {
      case P.RingEvent.BUTTON_DOWN:
        if (s.micSource === 'phone') {
          void startListening('ring-button');
          clearTimers();
          // Once the press is clearly an "ask", grab a photo now so it is ready when the question ends.
          holdTimer.current = setTimeout(() => {
            holdTimer.current = null;
            if (listeningRef.current === 'phone' && s.mode !== 'chat' && !freshPhotoUri()) {
              photoInFlight.current = r.waitForPhoto(PHOTO_WAIT_MS + LONG_PRESS_MS);
              void r.capture();
            }
          }, LONG_PRESS_MS);
        }
        break;
      case P.RingEvent.BUTTON_UP:
        if (s.micSource === 'phone') {
          if (e.arg < LONG_PRESS_TENTHS) void cancelListening();    // short press: the ring takes a photo itself
          else void stopListening();
        } else if (e.arg >= LONG_PRESS_TENTHS) {
          expectVoiceUntil.current = Date.now() + EXPECT_VOICE_MS;  // ring mic: REC_STOPPED + ADPCM follow
        }
        break;
      case P.RingEvent.DOUBLE_TAP:
        if (s.micSource === 'phone') {
          if (listeningRef.current) void stopListening();
          else void startListening('double-tap');
        } else {
          expectVoiceUntil.current = Date.now() + EXPECT_VOICE_MS;
        }
        break;
      case P.RingEvent.REC_STARTED:
        if (!listeningRef.current) {
          void stopSpeaking();
          void r.stopAudio();
        }
        expectVoiceUntil.current = Date.now() + EXPECT_VOICE_MS;
        setPhaseBoth('listening');
        break;
      case P.RingEvent.REC_STOPPED:
        if (listeningRef.current === 'ring') listeningRef.current = null;
        if (e.arg === 0) {
          expectVoiceUntil.current = 0;
          if (phaseRef.current === 'listening') setPhaseBoth('idle');
          r.push('ring discarded the recording');
        } else if (phaseRef.current === 'listening') {
          setPhaseBoth('thinking');   // the ADPCM transfer is on its way
        }
        break;
      case P.RingEvent.CAPTURE_DONE:
        if (e.arg === 0) system('The ring could not take a photo.');
        break;
      case P.RingEvent.LOW_BATTERY:
        system(`Ring battery low (${e.arg}%).`);
        break;
      default:
        break;
    }
  }), [ring.addEventListener, startListening, stopListening, cancelListening, freshPhotoUri, system, setPhaseBoth]);

  // ---- ring-mic clips: ask on arrival, with the latest fresh photo -----------------------------------------------
  const lastVoice = ring.lastVoice;
  useEffect(() => {
    if (!lastVoice || lastVoice.claimed) return;
    expectVoiceUntil.current = 0;
    void (async () => {
      const imageUri = await photoForTurn();
      await runAsk({ audio: lastVoice.adpcm, imageUri, question: typedRef.current, label: typedRef.current || `🎤 ${(lastVoice.durationMs / 1000).toFixed(1)} s` });
      setTyped('');
    })();
  }, [lastVoice, photoForTurn, runAsk]);

  // ---- photos without a voice question: ask right away (unless a voice clip is about to attach to it) ----------------
  const lastCapture = ring.lastCapture;
  useEffect(() => {
    if (!lastCapture || lastCapture.claimed) return;
    if (Date.now() < expectVoiceUntil.current || listeningRef.current || photoInFlight.current) return;
    if (!settingsRef.current.autoAskPhoto) return;
    void runAsk({ imageUri: lastCapture.uri, question: typedRef.current, label: typedRef.current || undefined }).then((res) => res && setTyped(''));
  }, [lastCapture, runAsk]);

  // ---- public actions -------------------------------------------------------------------------------------------
  const askText = useCallback(async (q: string) => {
    const question = q.trim();
    if (!question) return;
    setTyped('');
    await runAsk({ question, imageUri: freshPhotoUri() });
  }, [runAsk, freshPhotoUri]);

  const askAboutPhoto = useCallback(async (cap: Capture | null) => {
    if (!cap) return;
    sentPhotoRef.current = null;
    await runAsk({ imageUri: cap.uri, question: typedRef.current, label: typedRef.current || undefined });
    setTyped('');
  }, [runAsk]);

  const interrupt = useCallback(async () => {
    await stopSpeaking();
    await ringRef.current.stopAudio();
  }, []);

  const newConversation = useCallback(async () => {
    await interrupt();
    sessionRef.current = '';
    sentPhotoRef.current = null;
    setSessionId('');
    setTurns([]);
  }, [interrupt]);

  useEffect(() => () => {
    clearTimers();
    void recorder.cancel();
  }, [recorder]);

  return {
    turns, phase, sessionId, typed, setTyped,
    startListening, stopListening, cancelListening, askText, askAboutPhoto, interrupt, newConversation,
    listening: phase === 'listening', busy: phase === 'thinking' || phase === 'speaking',
  };
}
