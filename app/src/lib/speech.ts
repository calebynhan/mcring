import * as Speech from 'expo-speech';
import { Audio } from 'expo-av';
import * as FileSystem from 'expo-file-system';
import { toBase64 } from './proto';

/** Speak with the phone's TTS, or play server-rendered MP3 bytes when present. */
export async function speak(text: string, mp3: Uint8Array | null, language = 'en-US'): Promise<void> {
  if (mp3 && mp3.length) {
    const path = `${FileSystem.cacheDirectory}mcring-answer.mp3`;
    await FileSystem.writeAsStringAsync(path, toBase64(mp3), { encoding: FileSystem.EncodingType.Base64 });
    const { sound } = await Audio.Sound.createAsync({ uri: path }, { shouldPlay: true });
    await new Promise<void>((resolve) => {
      sound.setOnPlaybackStatusUpdate((st) => {
        if ('didJustFinish' in st && st.didJustFinish) {
          void sound.unloadAsync();
          resolve();
        }
      });
    });
    return;
  }
  Speech.stop();
  await new Promise<void>((resolve) => Speech.speak(text, { language, rate: 1.0, onDone: resolve, onError: () => resolve() }));
}
