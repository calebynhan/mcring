import React, { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, Image, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { BackendClient, AskResult } from '../api/backend';
import * as P from '../lib/proto';
import { speak } from '../lib/speech';
import { AppSettings } from '../lib/storage';
import { vibrateUnits } from '../lib/vibrate';
import { Capture, useRing } from '../state/useRing';

interface Props {
  settings: AppSettings;
  onOpenSettings: () => void;
}

export function HomeScreen({ settings, onOpenSettings }: Props) {
  const ring = useRing();
  const [question, setQuestion] = useState('');
  const [asking, setAsking] = useState(false);
  const [result, setResult] = useState<AskResult | null>(null);
  const [sessionId, setSessionId] = useState('');
  const [answered, setAnswered] = useState<number | null>(null);

  const ask = useCallback(
    async (cap: Capture | null, q: string) => {
      setAsking(true);
      try {
        await ring.client.current?.flash(0, 0, 60, 300).catch(() => undefined);
        const be = new BackendClient(settings.backendUrl, settings.token);
        const res = await be.ask(cap?.uri ?? null, {
          question: q,
          mode: settings.mode,
          provider: settings.provider,
          sessionId: cap ? '' : sessionId,
          wantSpeech: settings.speak && settings.serverTts,
          charWpm: settings.charWpm,
          overallWpm: settings.overallWpm,
          channels: settings.channels,
          language: settings.language,
          audioAdpcm: cap?.voiceAdpcm ?? null,
        });
        setResult(res);
        setSessionId(res.sessionId);
        ring.push(`${res.subject || res.short} (${Math.round(res.confidence * 100)}%, ${res.latencyMs} ms)`);
        if (res.morse && ring.connected) {
          await ring.client.current?.playUnits(res.morse.units, res.morse.unitMs, settings.channels);
        }
        if (res.morse && settings.phoneMorse) vibrateUnits(res.morse.units, res.morse.unitMs);
        if (settings.speak) await speak(res.answer, res.speechMp3, settings.language);
      } catch (e) {
        ring.push(`ask failed: ${(e as Error).message}`);
        await ring.client.current?.playMorseText('HH', 20, P.Channel.LED).catch(() => undefined);
      } finally {
        setAsking(false);
      }
    },
    [ring, settings, sessionId],
  );

  // Auto-ask whenever a new photo arrives from the ring.
  useEffect(() => {
    const cap = ring.lastCapture;
    if (cap && cap.at !== answered) {
      setAnswered(cap.at);
      void ask(cap, question);
    }
  }, [ring.lastCapture, answered, ask, question]);

  const flags = ring.status ? P.statusFlags(ring.status) : null;

  return (
    <ScrollView contentContainerStyle={st.container}>
      <View style={st.row}>
        <Text style={st.title}>mcring</Text>
        <Pressable onPress={onOpenSettings}><Text style={st.link}>Settings</Text></Pressable>
      </View>

      <View style={st.card}>
        <View style={st.row}>
          <Text style={st.h2}>{ring.connected ? 'Ring connected' : ring.busy !== 'idle' ? `${ring.busy}…` : 'Ring not connected'}</Text>
          {ring.busy !== 'idle' ? <ActivityIndicator /> : (
            <Pressable style={st.btn} onPress={ring.connected ? ring.disconnect : ring.connect}>
              <Text style={st.btnText}>{ring.connected ? 'Disconnect' : 'Connect'}</Text>
            </Pressable>
          )}
        </View>
        {ring.status && (
          <Text style={st.meta}>
            {P.RingState[ring.status.state]?.toLowerCase()} · battery {ring.status.batteryPct === 255 ? '?' : `${ring.status.batteryPct}%`} ({ring.status.batteryMv} mV)
            {flags?.camera ? ' · cam' : ' · NO CAM'}{flags?.imu ? ' · imu' : ''}{flags?.mic ? ' · mic' : ''}{flags?.haptic ? ' · haptic' : ''}
            {ring.status.queued ? ` · ${ring.status.queued} queued` : ''}{ring.status.lastError ? ` · err ${P.ERROR_NAMES[ring.status.lastError]}` : ''}
          </Text>
        )}
        {ring.error && <Text style={st.err}>{ring.error}</Text>}
        {ring.progress !== null && <View style={st.bar}><View style={[st.fill, { width: `${Math.round(ring.progress * 100)}%` }]} /></View>}
      </View>

      <View style={st.card}>
        <TextInput style={st.input} placeholder="Optional question (e.g. is it safe to touch?)" value={question} onChangeText={setQuestion} />
        <View style={st.row}>
          <Pressable style={[st.btn, !ring.connected && st.btnDisabled]} disabled={!ring.connected} onPress={() => ring.client.current?.capture()}>
            <Text style={st.btnText}>Take photo</Text>
          </Pressable>
          <Pressable style={[st.btn, (!ring.lastCapture || asking) && st.btnDisabled]} disabled={!ring.lastCapture || asking} onPress={() => ask(ring.lastCapture, question)}>
            <Text style={st.btnText}>Ask again</Text>
          </Pressable>
          <Pressable style={[st.btn, (!sessionId || asking) && st.btnDisabled]} disabled={!sessionId || asking} onPress={() => ask(null, question)}>
            <Text style={st.btnText}>Follow-up</Text>
          </Pressable>
        </View>
      </View>

      {ring.lastCapture && (
        <View style={st.card}>
          <Image source={{ uri: ring.lastCapture.uri }} style={st.photo} resizeMode="contain" />
          <Text style={st.meta}>{ring.lastCapture.width}×{ring.lastCapture.height} · {ring.lastCapture.bytes} B · {ring.lastCapture.seconds.toFixed(2)} s{ring.lastCapture.voiceAdpcm ? ' · + voice' : ''}</Text>
        </View>
      )}

      <View style={st.card}>
        {asking && <ActivityIndicator />}
        {result && (
          <>
            <Text style={st.h2}>{result.subject || result.short}</Text>
            <Text style={st.answer}>{result.answer}</Text>
            {result.transcript && <Text style={st.meta}>You asked: “{result.transcript}”</Text>}
            {result.warnings.map((w) => <Text key={w} style={st.warn}>⚠ {w}</Text>)}
            <Text style={st.morse}>{result.short}</Text>
            {result.morse && (
              <View style={st.row}>
                <Text style={st.meta}>Morse {Math.round(result.morse.durationMs / 100) / 10} s · {Math.round(result.confidence * 100)}% · {result.model}</Text>
                <Pressable onPress={() => { if (result.morse) { void ring.client.current?.playUnits(result.morse.units, result.morse.unitMs, settings.channels); if (settings.phoneMorse) vibrateUnits(result.morse.units, result.morse.unitMs); } }}>
                  <Text style={st.link}>Replay</Text>
                </Pressable>
              </View>
            )}
          </>
        )}
      </View>

      <View style={st.card}>
        {ring.log.slice(0, 12).map((l, i) => <Text key={i} style={st.log}>{l}</Text>)}
      </View>
    </ScrollView>
  );
}

const st = StyleSheet.create({
  container: { padding: 16, gap: 12 },
  row: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 8, flexWrap: 'wrap' },
  title: { fontSize: 28, fontWeight: '700' },
  h2: { fontSize: 18, fontWeight: '600' },
  link: { color: '#2563eb', fontWeight: '600' },
  card: { backgroundColor: '#f3f4f6', borderRadius: 12, padding: 12, gap: 8 },
  meta: { color: '#6b7280', fontSize: 13 },
  err: { color: '#b91c1c' },
  warn: { color: '#b45309', fontWeight: '600' },
  answer: { fontSize: 16, lineHeight: 22 },
  morse: { fontFamily: 'monospace', fontSize: 18, letterSpacing: 2 },
  input: { backgroundColor: 'white', borderRadius: 8, padding: 10 },
  btn: { backgroundColor: '#111827', paddingHorizontal: 14, paddingVertical: 10, borderRadius: 8 },
  btnDisabled: { opacity: 0.4 },
  btnText: { color: 'white', fontWeight: '600' },
  photo: { width: '100%', aspectRatio: 4 / 3, borderRadius: 8, backgroundColor: 'black' },
  bar: { height: 6, backgroundColor: '#e5e7eb', borderRadius: 3, overflow: 'hidden' },
  fill: { height: 6, backgroundColor: '#2563eb' },
  log: { fontFamily: 'monospace', fontSize: 11, color: '#374151' },
});
