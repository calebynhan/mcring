import React, { useEffect, useRef } from 'react';
import { ActivityIndicator, Animated, Image, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import * as P from '../lib/proto';
import { AppSettings } from '../lib/storage';
import { useRing } from '../state/useRing';
import { Turn, useVoiceTurn } from '../state/useVoiceTurn';

interface Props {
  settings: AppSettings;
  onOpenSettings: () => void;
}

const PHASE_LABEL = { idle: '', listening: 'Listening…', thinking: 'Thinking…', speaking: 'Speaking…' } as const;

export function HomeScreen({ settings, onOpenSettings }: Props) {
  const ring = useRing(settings);
  const voice = useVoiceTurn(ring, settings);
  const scroll = useRef<ScrollView | null>(null);
  const pulseAnim = useRef(new Animated.Value(1)).current;

  // Subtle pulse on the talk button while a question is being recorded.
  useEffect(() => {
    if (!voice.listening) {
      pulseAnim.setValue(1);
      return;
    }
    const loop = Animated.loop(Animated.sequence([
      Animated.timing(pulseAnim, { toValue: 1.08, duration: 450, useNativeDriver: true }),
      Animated.timing(pulseAnim, { toValue: 1, duration: 450, useNativeDriver: true }),
    ]));
    loop.start();
    return () => loop.stop();
  }, [voice.listening, pulseAnim]);

  useEffect(() => {
    const t = setTimeout(() => scroll.current?.scrollToEnd({ animated: true }), 50);
    return () => clearTimeout(t);
  }, [voice.turns.length, voice.phase]);

  const flags = ring.status ? P.statusFlags(ring.status) : null;
  const micHint = settings.micSource === 'ring' && ring.connected ? 'ring mic' : settings.micSource === 'ring' ? 'phone mic (ring not connected)' : 'phone / headset mic';
  const outHint = [settings.speak ? (settings.speakVia === 'server' ? 'server voice' : 'phone voice') : null, settings.ringSpeaker ? (ring.speakerOk ? 'ring speaker' : 'ring speaker (n/a)') : null].filter(Boolean).join(' + ') || 'text only';

  return (
    <View style={st.root}>
      <View style={[st.row, st.header]}>
        <Text style={st.title}>mcring</Text>
        <View style={st.row}>
          {voice.turns.length > 0 && <Pressable onPress={() => void voice.newConversation()}><Text style={st.link}>New chat</Text></Pressable>}
          <Pressable onPress={onOpenSettings}><Text style={st.link}>Settings</Text></Pressable>
        </View>
      </View>

      <View style={st.card}>
        <View style={st.row}>
          <Text style={st.h2}>{ring.connected ? 'Ring connected' : ring.busy !== 'idle' ? `${ring.busy}…` : 'Ring not connected'}</Text>
          {ring.busy !== 'idle' ? <ActivityIndicator /> : (
            <Pressable style={st.btnSmall} onPress={ring.connected ? ring.disconnect : ring.connect}>
              <Text style={st.btnText}>{ring.connected ? 'Disconnect' : 'Connect'}</Text>
            </Pressable>
          )}
        </View>
        {ring.status && (
          <Text style={st.meta}>
            {P.RingState[ring.status.state]?.toLowerCase()} · battery {ring.status.batteryPct === 255 ? '?' : `${ring.status.batteryPct}%`}
            {flags?.camera ? ' · cam' : ' · NO CAM'}{flags?.mic ? ' · mic' : ''}{flags?.speaker ? ' · speaker' : ''}{flags?.haptic ? ' · haptic' : ''}
            {ring.status.queued ? ` · ${ring.status.queued} queued` : ''}{ring.status.lastError ? ` · err ${P.ERROR_NAMES[ring.status.lastError]}` : ''}
          </Text>
        )}
        <Text style={st.meta}>in: {micHint} · out: {outHint}</Text>
        {ring.error && <Text style={st.err}>{ring.error}</Text>}
        {ring.progress !== null && <View style={st.bar}><View style={[st.fill, { width: `${Math.round(ring.progress * 100)}%` }]} /></View>}
        {ring.audioProgress !== null && <View style={st.bar}><View style={[st.fill, st.fillAudio, { width: `${Math.round(ring.audioProgress * 100)}%` }]} /></View>}
      </View>

      <ScrollView ref={scroll} style={st.transcript} contentContainerStyle={st.transcriptInner}>
        {voice.turns.length === 0 && (
          <Text style={st.hint}>
            Hold the ring button (or the button below) and ask a question — with or without looking at something.
            {'\n'}A short press takes a photo and asks about it. Answers play on your phone or headphones.
          </Text>
        )}
        {voice.turns.map((t) => <Bubble key={t.id} turn={t} />)}
        {voice.phase === 'thinking' && <View style={[st.bubble, st.claude]}><ActivityIndicator /></View>}
      </ScrollView>

      {ring.lastCapture && (
        <View style={[st.row, st.photoRow]}>
          <Image source={{ uri: ring.lastCapture.uri }} style={st.thumb} resizeMode="cover" />
          <Text style={[st.meta, { flex: 1 }]}>{ring.lastCapture.width}×{ring.lastCapture.height} · {Math.round(ring.lastCapture.bytes / 1024)} kB · {Math.round((Date.now() - ring.lastCapture.at) / 1000)} s ago</Text>
          <Pressable style={[st.btnSmall, voice.busy && st.btnDisabled]} disabled={voice.busy} onPress={() => void voice.askAboutPhoto(ring.lastCapture)}>
            <Text style={st.btnText}>Ask about photo</Text>
          </Pressable>
        </View>
      )}

      <View style={st.talkRow}>
        <Pressable style={[st.btnSmall, !ring.connected && st.btnDisabled]} disabled={!ring.connected} onPress={() => void ring.capture()}>
          <Text style={st.btnText}>Take photo</Text>
        </Pressable>
        <Animated.View style={{ transform: [{ scale: pulseAnim }] }}>
          <Pressable
            style={[st.talk, voice.listening && st.talkActive, voice.busy && st.talkBusy]}
            onPressIn={() => void voice.startListening('phone-button')}
            onPressOut={() => void voice.stopListening()}
          >
            <Text style={st.talkText}>{voice.listening ? 'Release to ask' : voice.phase === 'speaking' ? 'Hold to interrupt' : voice.phase === 'thinking' ? '…' : 'Hold to talk'}</Text>
          </Pressable>
        </Animated.View>
        <View style={st.row}>
          <Text style={[st.meta, st.phase]}>{PHASE_LABEL[voice.phase]}</Text>
          {voice.phase === 'speaking' && <Pressable onPress={() => void voice.interrupt()}><Text style={st.link}>Stop</Text></Pressable>}
        </View>
      </View>

      <View style={st.row}>
        <TextInput style={[st.input, { flex: 1 }]} placeholder="…or type a question" value={voice.typed} onChangeText={voice.setTyped} onSubmitEditing={() => void voice.askText(voice.typed)} returnKeyType="send" />
        <Pressable style={[st.btnSmall, (!voice.typed.trim() || voice.busy) && st.btnDisabled]} disabled={!voice.typed.trim() || voice.busy} onPress={() => void voice.askText(voice.typed)}>
          <Text style={st.btnText}>Send</Text>
        </Pressable>
      </View>

      <View style={st.log}>
        {ring.log.slice(0, 3).map((l, i) => <Text key={i} style={st.logLine} numberOfLines={1}>{l}</Text>)}
      </View>
    </View>
  );
}

function Bubble({ turn }: { turn: Turn }) {
  if (turn.role === 'system') return <Text style={st.system}>{turn.text}</Text>;
  const you = turn.role === 'you';
  return (
    <View style={[st.bubble, you ? st.you : st.claude]}>
      {turn.imageUri && <Image source={{ uri: turn.imageUri }} style={st.bubbleImage} resizeMode="cover" />}
      {!you && turn.subject ? <Text style={st.subject}>{turn.subject}{turn.confidence !== undefined ? ` · ${Math.round(turn.confidence * 100)}%` : ''}</Text> : null}
      <Text style={[st.bubbleText, you && st.youText, turn.pending && st.pending]}>{turn.text}</Text>
      {turn.followUp ? <Text style={st.followUp}>{turn.followUp}</Text> : null}
      {turn.warnings?.map((w) => <Text key={w} style={st.warn}>⚠ {w}</Text>)}
      {turn.meta ? <Text style={[st.meta, you && st.youMeta]}>{turn.meta}</Text> : null}
    </View>
  );
}

const st = StyleSheet.create({
  root: { flex: 1, padding: 16, gap: 10 },
  header: { marginBottom: 2 },
  row: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 10, flexWrap: 'wrap' },
  title: { fontSize: 28, fontWeight: '700' },
  h2: { fontSize: 17, fontWeight: '600' },
  link: { color: '#2563eb', fontWeight: '600', marginLeft: 12 },
  card: { backgroundColor: '#f3f4f6', borderRadius: 12, padding: 12, gap: 6 },
  meta: { color: '#6b7280', fontSize: 12 },
  err: { color: '#b91c1c' },
  warn: { color: '#b45309', fontWeight: '600' },
  hint: { color: '#6b7280', textAlign: 'center', marginTop: 24, lineHeight: 20 },
  transcript: { flex: 1, backgroundColor: '#fafafa', borderRadius: 12 },
  transcriptInner: { padding: 10, gap: 8 },
  bubble: { maxWidth: '88%', borderRadius: 14, padding: 10, gap: 4 },
  you: { alignSelf: 'flex-end', backgroundColor: '#111827' },
  claude: { alignSelf: 'flex-start', backgroundColor: '#e5e7eb' },
  bubbleText: { fontSize: 16, lineHeight: 22, color: '#111827' },
  youText: { color: 'white' },
  youMeta: { color: '#d1d5db' },
  pending: { opacity: 0.6 },
  subject: { fontWeight: '700', color: '#374151' },
  followUp: { fontStyle: 'italic', color: '#374151' },
  system: { alignSelf: 'center', color: '#6b7280', fontSize: 13, textAlign: 'center' },
  bubbleImage: { width: 200, height: 150, borderRadius: 8, backgroundColor: 'black' },
  photoRow: { backgroundColor: '#f3f4f6', borderRadius: 12, padding: 8 },
  thumb: { width: 56, height: 42, borderRadius: 6, backgroundColor: 'black' },
  talkRow: { alignItems: 'center', gap: 8 },
  talk: { width: 150, height: 150, borderRadius: 75, backgroundColor: '#2563eb', alignItems: 'center', justifyContent: 'center' },
  talkActive: { backgroundColor: '#dc2626' },
  talkBusy: { backgroundColor: '#6b7280' },
  talkText: { color: 'white', fontWeight: '700', fontSize: 18 },
  phase: { minHeight: 16 },
  input: { backgroundColor: '#f3f4f6', borderRadius: 8, padding: 10 },
  btnSmall: { backgroundColor: '#111827', paddingHorizontal: 12, paddingVertical: 8, borderRadius: 8 },
  btnDisabled: { opacity: 0.4 },
  btnText: { color: 'white', fontWeight: '600' },
  bar: { height: 5, backgroundColor: '#e5e7eb', borderRadius: 3, overflow: 'hidden' },
  fill: { height: 5, backgroundColor: '#2563eb' },
  fillAudio: { backgroundColor: '#16a34a' },
  log: { minHeight: 14 },
  logLine: { fontFamily: 'monospace', fontSize: 10, color: '#9ca3af' },
});
