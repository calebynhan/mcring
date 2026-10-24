# mcring companion app (React Native + Expo)

Phone side of the loop, **voice-first**: hold the ring button (or the big button in the app) and ask a
question — with or without looking at something — and hear Claude's answer in your Bluetooth
headphones. The app connects to the ring over BLE, records (or receives) the spoken question,
sends it with the latest photo to the backend, shows the conversation as a transcript and
speaks the answer.

Audio topology: ring ↔ phone over BLE; phone ↔ your own Bluetooth headphones through the phone's
normal audio routing (the ring never pairs to headphones); phone ↔ backend ↔ Claude. Optionally the
phone also streams the answer to the on-ring speaker (stage-1 oversized ring).

`react-native-ble-plx` and `expo-av` need native code, so this is an **Expo dev-client / prebuild**
app, not Expo Go.

```bash
cd app
npm install
npx expo prebuild            # generates ios/ and android/
npx expo run:android         # or: npx expo run:ios  (needs Xcode + a real iPhone for BLE)
```

Then open **Settings** in the app and point *Backend URL* at your machine running
`uvicorn app.main:app --host 0.0.0.0 --port 8000` (same Wi-Fi, e.g. `http://192.168.1.10:8000`).

## The voice turn

1. **Connect** → scans for the `mcring` service UUID, connects, requests MTU 517, subscribes to
   status / transfer / **events** notifications and pushes the voice settings to the ring
   (`SET_CONFIG` 9 speaker volume, 10 cues mask, 11 mic source hint).
2. **Ask** — any of:
   * **Hold the ring button** (≥ 0.7 s). *Ring mic* (default): the ring records while the button is
     held and sends the clip (16 kHz mcring-ADPCM) over BLE. *Phone / headset mic*: the ring sends
     `BUTTON_DOWN` / `BUTTON_UP` events and the phone records in between with `expo-av`
     (16 kHz mono AAC); once the press is clearly an "ask", the app also asks the ring for a photo.
   * **Double-tap** the ring: hands-free ask (ring mic records up to 8 s; phone mic records up to 8 s
     or until the next double tap).
   * **Hold the big button** in the app (uses the ring mic when connected and selected, else the phone).
   * **Short press / Take photo**: the photo alone is asked about right away (configurable).
   * **Type** a question as a fallback.
3. The question (audio and/or text) goes to `POST /v1/ask` with the latest photo if one arrived in
   the last 20 s (no photo = plain chat; the backend keeps the session's last photo referenced).
   The transcript shows *you* (with the transcription) and *Claude* (answer, follow-up, warnings).
4. **Hear the answer**: phone TTS (`expo-speech`) or the server's mp3 (`expo-av`) — routed to
   connected headphones automatically — and/or streamed to the **ring speaker** as 16 kHz ADPCM
   over the `AUDIO_OUT` characteristic (paced in small bursts so the ring's ~400 ms buffer never
   overruns). The ring plays short confirmation cues only: "listening" tick, "answer ready" double
   tick, error buzz.

Morse output is no longer part of the app. The encoder (`src/lib/morse.ts`) and the ring's
pattern feedback stay available as an optional, off-by-default "silent pattern" capability.

## Settings

| Setting | Meaning |
|---|---|
| Backend URL / token / provider | where `/v1/ask` lives |
| Mode | `identify`, `describe`, `read_text`, `translate`, `chat`, `custom` — used when a photo is attached |
| Auto-ask photo | ask about a photo as soon as it arrives without a voice question |
| Voice in | `Ring mic` or `Phone / headset mic` (writes `MIC_SOURCE_HINT`) |
| Speak answers | on the phone → headphones; via `Phone voice` (expo-speech, pick a voice) or `Server voice` (mp3) |
| Ring speaker | also stream answers to the ring (needs the `speaker` status flag); volume = `SPEAKER_VOLUME` |
| Cues | haptic / LED / beep confirmation cues (`CUES_MASK`) |

## Code map

```
src/lib/proto.ts        packet codec + CRC32 + transfer reassembly + events / audio-out builders (same bytes as Python/C)
src/lib/audioStream.ts  pacing of ADPCM writes to the ring speaker (pure; unit-tested)
src/lib/recorder.ts     push-to-talk recording with expo-av (16 kHz mono m4a)
src/lib/speech.ts       phone TTS / server mp3 playback
src/lib/settings.ts     settings types, defaults, migration (pure)   src/lib/storage.ts  AsyncStorage load/save
src/lib/morse.ts        Morse encoder (legacy silent-pattern mode; unchanged)
src/ble/RingClient.ts   BLE transport (react-native-ble-plx): status, events, transfers, cues, streamAudio/stopAudio
src/api/backend.ts      /v1/ask (image + audio optional), /v1/transcribe, /v1/speech, /v1/health
src/state/useRing.ts    React hook: connection, status, events, photos, ring-mic clips, voice config sync
src/state/useVoiceTurn.ts  the push-to-talk state machine: record → ask → transcript → speak
src/screens/*           Home (transcript + hold-to-talk) and Settings
__tests__/*             jest: codec, Morse fixtures, audio pacing, backend parsing, settings migration
```

`npm test` runs the tests; `npm run typecheck` runs `tsc`.
