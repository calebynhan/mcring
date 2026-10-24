import React, { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Switch, Text, TextInput, View } from 'react-native';
import { AppSettings } from '../lib/storage';

interface Props {
  settings: AppSettings;
  onSave: (s: AppSettings) => void;
  onBack: () => void;
}

const MODES: AppSettings['mode'][] = ['identify', 'describe', 'read_text', 'translate', 'custom'];
const PROVIDERS: AppSettings['provider'][] = ['', 'anthropic', 'openai'];

export function SettingsScreen({ settings, onSave, onBack }: Props) {
  const [s, setS] = useState<AppSettings>({ ...settings });
  const num = (k: 'charWpm' | 'overallWpm' | 'channels') => (v: string) => setS({ ...s, [k]: parseInt(v, 10) || 0 });

  return (
    <ScrollView contentContainerStyle={st.container}>
      <Text style={st.title}>Settings</Text>

      <Text style={st.label}>Backend URL</Text>
      <TextInput style={st.input} autoCapitalize="none" value={s.backendUrl} onChangeText={(v) => setS({ ...s, backendUrl: v })} />
      <Text style={st.label}>API token (optional)</Text>
      <TextInput style={st.input} autoCapitalize="none" secureTextEntry value={s.token} onChangeText={(v) => setS({ ...s, token: v })} />

      <Text style={st.label}>Default mode</Text>
      <View style={st.chips}>{MODES.map((m) => <Chip key={m} label={m} on={s.mode === m} onPress={() => setS({ ...s, mode: m })} />)}</View>

      <Text style={st.label}>Model provider</Text>
      <View style={st.chips}>{PROVIDERS.map((p) => <Chip key={p || 'server'} label={p || 'server default'} on={s.provider === p} onPress={() => setS({ ...s, provider: p })} />)}</View>

      <Text style={st.label}>Morse: character WPM / overall WPM (Farnsworth)</Text>
      <View style={st.row}>
        <TextInput style={[st.input, st.half]} keyboardType="number-pad" value={String(s.charWpm)} onChangeText={num('charWpm')} />
        <TextInput style={[st.input, st.half]} keyboardType="number-pad" value={String(s.overallWpm)} onChangeText={num('overallWpm')} />
      </View>

      <Text style={st.label}>Ring channels (bit0 LED, bit1 haptic, bit2 buzzer, bit3 aux)</Text>
      <View style={st.chips}>
        {[{ b: 1, n: 'LED' }, { b: 2, n: 'Haptic' }, { b: 4, n: 'Buzzer' }, { b: 8, n: 'Aux' }].map(({ b, n }) => (
          <Chip key={n} label={n} on={!!(s.channels & b)} onPress={() => setS({ ...s, channels: s.channels ^ b })} />
        ))}
      </View>

      <Row label="Speak the answer" value={s.speak} onChange={(v) => setS({ ...s, speak: v })} />
      <Row label="Use server speech (MP3) instead of phone TTS" value={s.serverTts} onChange={(v) => setS({ ...s, serverTts: v })} />
      <Row label="Also vibrate the phone in Morse" value={s.phoneMorse} onChange={(v) => setS({ ...s, phoneMorse: v })} />

      <Text style={st.label}>Language (BCP-47)</Text>
      <TextInput style={st.input} autoCapitalize="none" value={s.language} onChangeText={(v) => setS({ ...s, language: v })} />

      <View style={st.row}>
        <Pressable style={st.btn} onPress={() => { onSave(s); onBack(); }}><Text style={st.btnText}>Save</Text></Pressable>
        <Pressable style={[st.btn, st.ghost]} onPress={onBack}><Text style={[st.btnText, { color: '#111827' }]}>Cancel</Text></Pressable>
      </View>
    </ScrollView>
  );
}

function Chip({ label, on, onPress }: { label: string; on: boolean; onPress: () => void }) {
  return (
    <Pressable onPress={onPress} style={[st.chip, on && st.chipOn]}>
      <Text style={[st.chipText, on && { color: 'white' }]}>{label}</Text>
    </Pressable>
  );
}

function Row({ label, value, onChange }: { label: string; value: boolean; onChange: (v: boolean) => void }) {
  return (
    <View style={st.row}>
      <Text style={{ flex: 1 }}>{label}</Text>
      <Switch value={value} onValueChange={onChange} />
    </View>
  );
}

const st = StyleSheet.create({
  container: { padding: 16, gap: 10 },
  title: { fontSize: 24, fontWeight: '700' },
  label: { fontWeight: '600', marginTop: 8 },
  input: { backgroundColor: '#f3f4f6', borderRadius: 8, padding: 10 },
  half: { flex: 1 },
  row: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  chip: { paddingHorizontal: 12, paddingVertical: 6, borderRadius: 16, backgroundColor: '#e5e7eb' },
  chipOn: { backgroundColor: '#111827' },
  chipText: { fontWeight: '600' },
  btn: { backgroundColor: '#111827', paddingHorizontal: 16, paddingVertical: 10, borderRadius: 8, marginTop: 12 },
  ghost: { backgroundColor: '#e5e7eb' },
  btnText: { color: 'white', fontWeight: '600' },
});
