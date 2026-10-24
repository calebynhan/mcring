import AsyncStorage from '@react-native-async-storage/async-storage';

export interface AppSettings {
  backendUrl: string;
  token: string;
  provider: '' | 'anthropic' | 'openai';
  mode: 'identify' | 'describe' | 'read_text' | 'translate' | 'custom';
  charWpm: number;
  overallWpm: number;
  channels: number;
  speak: boolean;
  serverTts: boolean;
  phoneMorse: boolean;   // also vibrate the phone with the pattern
  language: string;
}

export const DEFAULTS: AppSettings = {
  backendUrl: 'http://192.168.1.10:8000',
  token: '',
  provider: '',
  mode: 'identify',
  charWpm: 15,
  overallWpm: 8,
  channels: 3,
  speak: true,
  serverTts: false,
  phoneMorse: false,
  language: 'en-US',
};

const KEY = 'mcring.settings.v1';

export async function loadSettings(): Promise<AppSettings> {
  try {
    const raw = await AsyncStorage.getItem(KEY);
    return raw ? { ...DEFAULTS, ...JSON.parse(raw) } : { ...DEFAULTS };
  } catch {
    return { ...DEFAULTS };
  }
}

export async function saveSettings(s: AppSettings): Promise<void> {
  await AsyncStorage.setItem(KEY, JSON.stringify(s));
}
