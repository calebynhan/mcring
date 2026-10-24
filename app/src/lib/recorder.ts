/** Push-to-talk recording with the phone (or a connected Bluetooth headset) mic via expo-av: 16 kHz mono AAC in .m4a,
 *  which the backend's speech-to-text accepts directly. */
import { Audio, InterruptionModeAndroid, InterruptionModeIOS } from 'expo-av';
import type { AudioFile } from '../api/backend';

export interface VoiceClip extends AudioFile { durationMs: number }

/** Clips shorter than this are treated as an accidental tap. */
export const MIN_CLIP_MS = 300;

export const VOICE_RECORDING_OPTIONS: Audio.RecordingOptions = {
  isMeteringEnabled: false,
  android: {
    extension: '.m4a', outputFormat: Audio.AndroidOutputFormat.MPEG_4, audioEncoder: Audio.AndroidAudioEncoder.AAC,
    sampleRate: 16000, numberOfChannels: 1, bitRate: 32000,
  },
  ios: {
    extension: '.m4a', outputFormat: Audio.IOSOutputFormat.MPEG4AAC, audioQuality: Audio.IOSAudioQuality.MEDIUM,
    sampleRate: 16000, numberOfChannels: 1, bitRate: 32000,
  },
  web: { mimeType: 'audio/webm', bitsPerSecond: 32000 },
};

/** iOS needs allowsRecordingIOS while recording; turning it off afterwards puts playback back on the loud route. */
async function audioMode(recording: boolean): Promise<void> {
  await Audio.setAudioModeAsync({
    allowsRecordingIOS: recording,
    playsInSilentModeIOS: true,
    staysActiveInBackground: true,
    interruptionModeIOS: InterruptionModeIOS.DoNotMix,
    interruptionModeAndroid: InterruptionModeAndroid.DoNotMix,
    shouldDuckAndroid: true,
    playThroughEarpieceAndroid: false,
  });
}

export class PhoneRecorder {
  private rec: Audio.Recording | null = null;
  private startedAt = 0;

  get active() { return !!this.rec; }

  static async ensurePermission(): Promise<boolean> {
    const p = await Audio.requestPermissionsAsync();
    return p.granted;
  }

  async start(): Promise<void> {
    if (this.rec) return;
    if (!(await PhoneRecorder.ensurePermission())) throw new Error('microphone permission denied');
    await audioMode(true);
    const rec = new Audio.Recording();
    try {
      await rec.prepareToRecordAsync(VOICE_RECORDING_OPTIONS);
      await rec.startAsync();
    } catch (e) {
      await rec.stopAndUnloadAsync().catch(() => undefined);
      await audioMode(false).catch(() => undefined);
      throw e;
    }
    this.rec = rec;
    this.startedAt = Date.now();
  }

  /** Stop and return the clip, or null when nothing usable was recorded. */
  async stop(): Promise<VoiceClip | null> {
    const rec = this.rec;
    if (!rec) return null;
    this.rec = null;
    let durationMs = Date.now() - this.startedAt;
    try {
      const st = await rec.stopAndUnloadAsync();
      if (st.durationMillis) durationMs = st.durationMillis;
    } catch {
      /* already stopped */
    }
    await audioMode(false).catch(() => undefined);
    const uri = rec.getURI();
    if (!uri || durationMs < MIN_CLIP_MS) return null;
    return { uri, name: 'voice.m4a', type: 'audio/mp4', durationMs };
  }

  async cancel(): Promise<void> {
    const rec = this.rec;
    this.rec = null;
    if (rec) await rec.stopAndUnloadAsync().catch(() => undefined);
    await audioMode(false).catch(() => undefined);
  }
}
