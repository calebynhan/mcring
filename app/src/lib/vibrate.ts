import { Vibration } from 'react-native';

/** A short phone-side haptic tick (e.g. "listening" when the ring button goes down). */
export function pulse(ms = 30): void {
  Vibration.vibrate(ms);
}

/** Mirror a unit pattern on the phone's vibration motor (legacy silent-pattern mode; Android honours patterns, iOS only buzzes). */
export function vibrateUnits(units: number[], unitMs: number): void {
  // RN pattern: [wait, vibrate, wait, vibrate, ...]; our pattern starts with ON.
  const pattern = [0, ...units.map((u) => u * unitMs)];
  Vibration.vibrate(pattern, false);
}

export function stopVibration(): void {
  Vibration.cancel();
}
