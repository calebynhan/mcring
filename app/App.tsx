import React, { useEffect, useState } from 'react';
import { SafeAreaView, StatusBar } from 'react-native';
import { HomeScreen } from './src/screens/HomeScreen';
import { SettingsScreen } from './src/screens/SettingsScreen';
import { AppSettings, DEFAULTS, loadSettings, saveSettings } from './src/lib/storage';

export default function App() {
  const [settings, setSettings] = useState<AppSettings>(DEFAULTS);
  const [screen, setScreen] = useState<'home' | 'settings'>('home');

  useEffect(() => {
    void loadSettings().then(setSettings);
  }, []);

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: 'white' }}>
      <StatusBar barStyle="dark-content" />
      {screen === 'home' ? (
        <HomeScreen settings={settings} onOpenSettings={() => setScreen('settings')} />
      ) : (
        <SettingsScreen settings={settings} onBack={() => setScreen('home')} onSave={(s) => { setSettings(s); void saveSettings(s); }} />
      )}
    </SafeAreaView>
  );
}
