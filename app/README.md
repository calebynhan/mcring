# mcring companion app (React Native + Expo)

Phone side of the loop: connects to the ring over BLE, receives photos (and voice clips),
asks the backend, speaks the answer with the phone's text-to-speech and sends the Morse pattern
back to the ring (and optionally mirrors it on the phone's vibration motor).

`react-native-ble-plx` needs native code, so this is an **Expo dev-client / prebuild** app,
not Expo Go.

```bash
cd app
npm install
npx expo prebuild            # generates ios/ and android/
npx expo run:android         # or: npx expo run:ios  (needs Xcode + a real iPhone for BLE)
```

Then open **Settings** in the app and point *Backend URL* at your machine running
`uvicorn app.main:app --host 0.0.0.0 --port 8000` (same Wi-Fi, e.g. `http://192.168.1.10:8000`).

## Flow

1. **Connect** → scans for the `mcring` service UUID, connects, requests MTU 517, subscribes to
   status / transfer notifications.
2. Press the ring button (or *Take photo*). Chunks arrive, missing ones are re-requested, CRC
   is checked, the JPEG is written to the cache and shown.
3. The app POSTs the photo (+ optional typed question, + voice clip if the ring sent one) to the
   backend, speaks the answer and writes the `MORSE_UNITS` pattern to the ring, split to the MTU.
4. *Follow-up* re-asks about the same photo using the backend session id.

## Code map

```
src/lib/proto.ts      packet codec + CRC32 + transfer reassembly (same bytes as the Python/C versions)
src/lib/morse.ts      Morse encoder (byte-identical to the firmware/backend encoders)
src/ble/RingClient.ts BLE transport (react-native-ble-plx)
src/api/backend.ts    POST /v1/ask client
src/state/useRing.ts  React hook: connection, status, captures
src/screens/*         Home + Settings
__tests__/*           jest tests; fixtures generated from the Python reference
```

`npm test` runs the codec tests; `npm run typecheck` runs `tsc`.
