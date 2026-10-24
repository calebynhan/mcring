import React, { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Switch, Text, TextInput, View } from 'react-native';
import type { Voice } from 'expo-speech';
import { MODES, Mode, Provider } from '../api/backend';
import { listVoices } from '../lib/speech';
import { AppSettings, CUE_BEEP, CUE_HAPTIC, CUE_LED, MicSource, SpeakVia } from '../lib/storage';

interface Props {
  settings: AppSettings;
  onSave: (s: AppSettings) => void;
  onBack: () => void;
}

const PROVIDERS: Provider[] = ['', 'anthropic', 'openai'];
const MIC_SOURCES: { v: MicSource; label: string; help: string }[] = [
  { v: 'ring', label: 'Ring mic', help: 'the ring records while its button is held and sends the clip over BLE' },
  { v: 'phone', label: 'Phone / headset mic', help: 'the phone records while the ring button is held (better quality with Bluetooth headphones)' },
];
const SPEAK_VIA: { v: SpeakVia; label: string }[] = [{ v: 'phone-tts', label: 'Phone voice' }, { v: 'server', label: 'Server voice (mp3)' }];
const VOLUMES = [{ v: 0, n: 'Off' }, { v: 64, n: 'Low' }, { v: 128, n: 'Mid' }, { v: 200, n: 'High' }, { v: 255, n: 'Max' }];
const CUES = [{ b: CUE_HAPTIC, n: 'Haptic' }, { b: CUE_LED, n: 'LED' }, { b: CUE_BEEP, n: 'Beep' }];

export function SettingsScreen({ settings, onSave, onBack }: Props) {
  const [s, setS] = useState<AppSettings>({ ...settings });
  const [voices, setVoices] = useState<Voice[] | null>(null);
  const set = <K extends keyof AppSettings>(k: K, v: AppSettings[K]) => setS((prev) => ({ ...prev, [k]: v }));

  return (
    <ScrollView contentContainerStyle={st.container}>
      <Text style={st.title}>Settings</Text>

      <Text style={st.section}>Backend</Text>
      <Text style={st.label}>Backend URL</Text>
      <TextInput style={st.input} autoCapitalize="none" autoCorrect={false} value={s.backendUrl} onChangeText={(v) => set('backendUrl', v)} />
      <Text style={st.label}>API token (optional)</Text>
      <TextInput style={st.input} autoCapitalize="none" secureTextEntry value={s.token} onChangeText={(v) => set('token', v)} />
      <Text style={st.label}>Model provider</Text>
      <View style={st.chips}>{PROVIDERS.map((p) => <Chip key={p || 'server'} label={p || 'server default'} on={s.provider === p} onPress={() => set('provider', p)} />)}</View>

      <Text style={st.section}>Asking</Text>
      <Text style={st.label}>Mode when a photo is attached</Text>
      <View style={st.chips}>{MODES.map((m: Mode) => <Chip key={m} label={m} on={s.mode === m} onPress={() => set('mode', m)} />)}</View>
      <Text style={st.help}>Questions without a photo are plain chat. “chat” never attaches a photo automatically.</Text>
      <Row label="Ask about a photo as soon as it arrives (short press / Take photo)" value={s.autoAskPhoto} onChange={(v) => set('autoAskPhoto', v)} />
      <Text style={st.label}>Language (BCP-47)</Text>
      <TextInput style={st.input} autoCapitalize="none" value={s.language} onChangeText={(v) => set('language', v)} />

      <Text style={st.section}>Voice in</Text>
      <View style={st.chips}>{MIC_SOURCES.map((m) => <Chip key={m.v} label={m.label} on={s.micSource === m.v} onPress={() => set('micSource', m.v)} />)}</View>
      <Text style={st.help}>{MIC_SOURCES.find((m) => m.v === s.micSource)?.help}</Text>

      <Text style={st.section}>Voice out</Text>
      <Row label="Speak answers on the phone (→ connected headphones)" value={s.speak} onChange={(v) => set('speak', v)} />
      {s.speak && (
        <>
          <View style={st.chips}>{SPEAK_VIA.map((o) => <Chip key={o.v} label={o.label} on={s.speakVia === o.v} onPress={() => set('speakVia', o.v)} />)}</View>
          <Text style={st.label}>Voice {s.speakVia === 'server' ? '(server TTS voice name, blank = default)' : '(phone voice identifier, blank = default)'}</Text>
          <TextInput style={st.input} autoCapitalize="none" autoCorrect={false} value={s.voice} onChangeText={(v) => set('voice', v)} placeholder={s.speakVia === 'server' ? 'e.g. alloy' : 'e.g. com.apple.voice.compact.en-US.Samantha'} />
          {s.speakVia === 'phone-tts' && (
            <>
              <Pressable onPress={() => void listVoices(s.language).then(setVoices)}><Text style={st.link}>{voices ? `${voices.length} phone voices for ${s.language}` : 'List phone voices…'}</Text></Pressable>
              {voices && (
                <View style={st.chips}>
                  <Chip label="default" on={!s.voice} onPress={() => set('voice', '')} />
                  {voices.slice(0, 12).map((v) => <Chip key={v.identifier} label={`${v.name} (${v.quality === 'Enhanced' ? 'HQ' : v.language})`} on={s.voice === v.identifier} onPress={() => set('voice', v.identifier)} />)}
                </View>
              )}
            </>
          )}
        </>
      )}

      <Text style={st.section}>Ring</Text>
      <Row label="Also play answers on the ring speaker" value={s.ringSpeaker} onChange={(v) => set('ringSpeaker', v)} />
      <Text style={st.help}>Needs a ring built with a speaker (status flag “speaker”). The phone streams 16 kHz ADPCM over BLE.</Text>
      <Text style={st.label}>Ring speaker volume ({s.speakerVolume})</Text>
      <View style={st.chips}>{VOLUMES.map((o) => <Chip key={o.n} label={o.n} on={s.speakerVolume === o.v} onPress={() => set('speakerVolume', o.v)} />)}</View>
      <Text style={st.label}>Confirmation cues (listening tick, answer-ready double tick, error buzz)</Text>
      <View style={st.chips}>{CUES.map((c) => <Chip key={c.n} label={c.n} on={!!(s.cuesMask & c.b)} onPress={() => set('cuesMask', s.cuesMask ^ c.b)} />)}</View>

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
  container: { padding: 16, gap: 10, paddingBottom: 40 },
  title: { fontSize: 24, fontWeight: '700' },
  section: { fontSize: 13, fontWeight: '700', color: '#6b7280', textTransform: 'uppercase', marginTop: 16 },
  label: { fontWeight: '600', marginTop: 4 },
  help: { color: '#6b7280', fontSize: 12 },
  link: { color: '#2563eb', fontWeight: '600' },
  input: { backgroundColor: '#f3f4f6', borderRadius: 8, padding: 10 },
  row: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  chip: { paddingHorizontal: 12, paddingVertical: 6, borderRadius: 16, backgroundColor: '#e5e7eb' },
  chipOn: { backgroundColor: '#111827' },
  chipText: { fontWeight: '600' },
  btn: { backgroundColor: '#111827', paddingHorizontal: 16, paddingVertical: 10, borderRadius: 8, marginTop: 12 },
  ghost: { backgroundColor: '#e5e7eb' },
  btnText: { color: 'white', fontWeight: '600' },
});
