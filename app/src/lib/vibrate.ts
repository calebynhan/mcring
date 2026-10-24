import { Vibration } from 'react-native';

/** Mirror a Morse unit pattern on the phone's vibration motor (Android honours patterns; iOS only buzzes). */
export function vibrateUnits(units: number[], unitMs: number): void {
  // RN pattern: [wait, vibrate, wait, vibrate, ...]; our pattern starts with ON.
  const pattern = [0, ...units.map((u) => u * unitMs)];
  Vibration.vibrate(pattern, false);
}

export function stopVibration(): void {
  Vibration.cancel();
}
