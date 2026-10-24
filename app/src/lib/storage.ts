import AsyncStorage from '@react-native-async-storage/async-storage';
import { AppSettings, DEFAULTS, migrateSettings } from './settings';

export * from './settings';

export const KEY = 'mcring.settings.v2';
export const LEGACY_KEY = 'mcring.settings.v1';

export async function loadSettings(): Promise<AppSettings> {
  try {
    const raw = (await AsyncStorage.getItem(KEY)) ?? (await AsyncStorage.getItem(LEGACY_KEY));
    return raw ? migrateSettings(JSON.parse(raw)) : { ...DEFAULTS };
  } catch {
    return { ...DEFAULTS };
  }
}

export async function saveSettings(s: AppSettings): Promise<void> {
  await AsyncStorage.setItem(KEY, JSON.stringify(s));
}
