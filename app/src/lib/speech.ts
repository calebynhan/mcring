/** Answer playback on the phone: on-device TTS (expo-speech) or a server mp3 (expo-av). Audio follows the phone's
 *  normal route, so connected Bluetooth headphones get it automatically. */
import * as Speech from 'expo-speech';
import { Audio } from 'expo-av';
import * as FileSystem from 'expo-file-system';
import { toBase64 } from './proto';

let current: Audio.Sound | null = null;

/** Play mp3 bytes and resolve when playback finishes (or is stopped). */
export async function playMp3(mp3: Uint8Array): Promise<void> {
  await stopSpeaking();
  const path = `${FileSystem.cacheDirectory}mcring-answer.mp3`;
  await FileSystem.writeAsStringAsync(path, toBase64(mp3), { encoding: FileSystem.EncodingType.Base64 });
  const { sound } = await Audio.Sound.createAsync({ uri: path }, { shouldPlay: true });
  current = sound;
  await new Promise<void>((resolve) => {
    sound.setOnPlaybackStatusUpdate((st) => {
      if (!st.isLoaded) {
        resolve();
        return;
      }
      if (st.didJustFinish) {
        void sound.unloadAsync().catch(() => undefined);
        if (current === sound) current = null;
        resolve();
      }
    });
  });
}

/** Speak with the phone's TTS, or play server-rendered mp3 bytes when given. `voice` is an expo-speech voice identifier. */
export async function speak(text: string, mp3: Uint8Array | null, language = 'en-US', voice = ''): Promise<void> {
  if (mp3 && mp3.length) {
    await playMp3(mp3);
    return;
  }
  if (!text.trim()) return;
  await Speech.stop();
  await new Promise<void>((resolve) =>
    Speech.speak(text.slice(0, Speech.maxSpeechInputLength || 4000), {
      language, rate: 1.0, voice: voice || undefined, onDone: resolve, onStopped: resolve, onError: () => resolve(),
    }),
  );
}

export async function stopSpeaking(): Promise<void> {
  await Speech.stop().catch(() => undefined);
  const s = current;
  current = null;
  if (s) {
    await s.stopAsync().catch(() => undefined);
    await s.unloadAsync().catch(() => undefined);
  }
}

/** Voices installed on the phone, optionally filtered by language prefix ('en' matches en-US, en-GB, ...). */
export async function listVoices(language = ''): Promise<Speech.Voice[]> {
  const all = await Speech.getAvailableVoicesAsync().catch(() => [] as Speech.Voice[]);
  const pfx = language.split('-')[0].toLowerCase();
  return pfx ? all.filter((v) => v.language.toLowerCase().startsWith(pfx)) : all;
}
