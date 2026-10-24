# 2. System architecture

Four components, one protocol, three shared codecs — arranged so that the phone is the audio hub
and the ring stays a BLE-only peripheral.

```
 ring (firmware) ──BLE GATT──▶ companion (phone app | desktop CLI) ──HTTPS──▶ backend (FastAPI) ──▶ Claude
   ▲    ▲                              │           │                                │
   │    │  events · ADPCM clip · JPEG  │           └── phone audio routing ──▶ Bluetooth headphones
   │    └──── cues (CUE) ◀─────────────┤                 (phone TTS or server mp3)
   └──────── AUDIO_OUT stream ◀────────┘  (optional on-ring speaker, 16 kHz ADPCM)
                                                   STT (OpenAI / local whisper) · TTS (OpenAI, optional)
```

Diagrams (Mermaid): `hardware/block-diagram.md`.

## Components

| Component | Dir | Language / stack | Role |
|---|---|---|---|
| Ring firmware (stage 0/1) | `firmware/ring-esp32s3` | C++17, Arduino-ESP32 2.0.x, NimBLE 2.x, esp_camera, legacy I2S | button/tap/touch → **events**; ring-mic push-to-talk (PDM → ADPCM); JPEG capture → reliable BLE transfer; cues; **ADPCM → I2S speaker** playback; power management; legacy pattern player |
| Ring firmware (stage 2 skeleton) | `firmware/ring-nrf52840` | C, Zephyr / nRF Connect SDK | same service, transfer and feedback on an nRF52840; camera HAL stubbed; EVENTS / AUDIO_OUT not yet ported |
| Shared codecs | `firmware/ring-esp32s3/lib/*`, `python/mcring_core`, `app/src/lib` | C99, Python, TypeScript | packet encoding incl. events and audio-out framing, CRC-32, IMA-ADPCM encoder **and decoder**, Morse → units; byte-identical, cross-tested |
| Phone companion | `app/` | React Native + Expo dev client, react-native-ble-plx, expo-av, expo-speech | BLE central; push-to-talk state machine (`useVoiceTurn`); phone-mic recording between button events; backend client; TTS / mp3 playback → headphones; ring-speaker streaming with pacing; settings → `SET_CONFIG` |
| Desktop companion | `tools/ring-cli` | Python, bleak, httpx, optional sounddevice | `mcring talk` (keyboard or ring-button push-to-talk), `listen`, `say`, `events`, `config`; no-hardware `ask` |
| Backend | `backend/` | Python, FastAPI, Anthropic SDK (OpenAI optional), openai (STT/TTS), numpy | speech-to-text, Claude Q&A with structured JSON (photo optional), read-aloud `speech_text`, optional TTS as mp3 and/or ring ADPCM, session memory; optional Morse |

## Why these boundaries

* **The ring does the minimum**: record a clip, capture, compress (hardware JPEG on the OV2640),
  ship bytes, tick, and — on the oversized ring — decode a stream it is handed. No Wi-Fi, no TLS,
  no LLM client, no Classic Bluetooth. That keeps the stage-2 nRF52840 port realistic and the
  power budget sane.
* **The phone is the audio hub and the internet gateway** (as every shipping smart ring does).
  It records with the headset mic if asked, speaks through whatever is paired to it, and streams
  to the ring speaker when the user prefers that. Bluetooth headphones never see the ring.
* **The backend holds the API keys** and the prompt, and does all speech processing the phone
  cannot: speech-to-text (OpenAI `gpt-4o-mini-transcribe` or local faster-whisper), structured
  Claude answers written to be read aloud, and optional text-to-speech rendered straight into
  the ring's ADPCM block format so the phone can forward it byte-for-byte.
* **Two mic paths, one answer path.** Ring-mic clips and phone recordings arrive at the same
  `/v1/ask` field; the response is the same whether it is spoken by the phone, by the server's
  voice, or by the ring.

## Protocol (`protocol/`)

* One 128-bit service, **seven characteristics**: control (0002), status (0003), transfer meta
  (0004), transfer data (0005), feedback/cues (0006), **events (0007, notify)**, **audio out
  (0008, write-no-response)**. Little-endian packed packets; see `protocol/ble-gatt.md` and
  `protocol/schemas/ring_packets.md`.
* **Events** (`{u8 event, u8 arg, u32 t_ms}`): `BUTTON_DOWN`, `BUTTON_UP(held tenths)`,
  `DOUBLE_TAP`, `TOUCH`, `CAPTURE_STARTED`, `CAPTURE_DONE(queued)`, `REC_STARTED(max s)`,
  `REC_STOPPED(tenths)`, `LOW_BATTERY(pct)`, `AUDIO_UNDERRUN`, `AUDIO_DONE(0 drained / 1 stopped)`.
  This is what lets the phone record with the headset mic for exactly as long as the ring
  button is held.
* **Control**: `CAPTURE`, `ACK_TRANSFER`, `SET_CONFIG` (keys 1–11, incl. 9 `SPEAKER_VOLUME`,
  10 `CUES_MASK`, 11 `MIC_SOURCE_HINT`), `PING`/`GET_STATUS`, `ABORT`, `RECORD_AUDIO(s)`,
  `RECORD_START` / `RECORD_STOP`, `SLEEP`.
* **Transfer** (JPEG or ADPCM clip): START → N data notifications (no per-chunk ack) → END →
  phone ACK with a missing-index list → selective retransmit (≤ 5 rounds). Chunk size follows
  the negotiated MTU (178 B on iOS, up to 510 B on Android). CRC-32 over the whole payload.
* **Audio out**: `AUDIO_START {sr/100 = 160, codec = 2, volume}`, `AUDIO_DATA {seq, whole 132-byte
  ADPCM blocks}`, `AUDIO_END`, `AUDIO_STOP`. The ring queues 48 blocks, starts after 24
  (~400 ms), inserts silence and reports `AUDIO_UNDERRUN` if starved, and reports `AUDIO_DONE`.
  1 block per write at MTU 185, 3 at 517; the companion bursts the prebuffer then paces at
  real time (`app/src/lib/audioStream.ts`, `tools/ring-cli/mcring_cli/audio_out.py`).
* **Feedback**: `CUE {1 listening, 2 answer ready, 3 error, 4 ok}` honouring `CUES_MASK`;
  `PATTERN`, `RGB`, `STOP`; `MORSE_TEXT` / `MORSE_UNITS` (optional, legacy).
* **Status**: 12-byte struct on connect/change/30 s; flag bit6 `SPEAKER_OK` tells the companion
  whether to offer the ring speaker at all.

## Data flow for one voice turn

1. **Hold (≥ 700 ms) or double tap.** The ring emits `BUTTON_DOWN` at once and plays the
   listening cue when the press becomes an "ask".
   * *Ring mic* (`MIC_SOURCE_HINT = 0`, default): `camera_capture()` grabs a QVGA JPEG (q12,
     ≈ 8–15 KB, camera powered only for the shot), then `audio_start_recording()` runs the PDM
     mic → IMA-ADPCM (16 kHz, 132-byte blocks) until release or 8 s. On release: `BUTTON_UP`,
     `REC_STOPPED(tenths)`, then the JPEG and ADPCM transfers.
   * *Phone / headset mic* (`MIC_SOURCE_HINT = 1`): the ring only cues and emits
     `BUTTON_DOWN` / `BUTTON_UP`. The companion starts `expo-av` (16 kHz mono m4a) or the laptop
     mic on `BUTTON_DOWN`, stops on `BUTTON_UP`, and sends `CAPTURE` itself ~700 ms into the
     press when it wants a photo.
   * A short press (< 700 ms) or a touch is a photo only; with *auto-ask photo* on, the
     companion asks about it immediately.
2. `transfer::tick()` streams chunks under a ~15 ms-per-loop budget with TX credits; the
   companion reassembles, verifies CRC, ACKs, keeps the JPEG as "latest photo" (fresh for 20 s).
3. Companion `POST /v1/ask` with `audio` (`.adpcm` or `.m4a`) and/or `question`, the fresh photo
   if any, `mode`, `session_id`, `speech_format` (`mp3` | `adpcm16k` | `both`) and `want_speech`.
4. Backend: sniff and transcribe the audio (ring ADPCM is converted to WAV first); normalise the
   image if present; build the prompt (`app/prompts.py`, read-aloud style); call Claude with a
   JSON schema (`answer`, `subject`, `confidence`, `warnings`, `follow_up`), server-side refusal
   fallbacks on, prompt caching on the system prompt. With no photo in the request or the
   session, every mode degrades to `chat` and the question is used verbatim.
5. Backend returns `speech_text` (= answer + follow-up), `transcript`, `mode`, `had_image`, and —
   if a TTS provider is configured — `speech` (mp3) and/or `speech_adpcm` (24 kHz PCM from the
   provider, low-passed and resampled to 16 kHz, encoded with `mcring_core.adpcm`). TTS failure
   is best-effort (`speech_error`); the text still comes back.
6. Companion shows the exchange in the transcript, sends `CUE 2` (answer ready) to the ring, and
   speaks: `expo-speech` / OS voice or the server mp3 through the phone's current audio route
   (Bluetooth headphones when paired), and/or `streamAudio()` to the ring speaker.
7. Ring (speaker path): buffers 24 blocks, installs the I2S TX driver, decodes and scales
   (stream volume × `SPEAKER_VOLUME`), plays, drains, emits `AUDIO_DONE(0)`. `ABORT` or
   `AUDIO_STOP` flush immediately. Holding the button while an answer plays interrupts it
   (barge-in) and starts the next question.

## Backend API in one table

| Endpoint | Purpose |
|---|---|
| `POST /v1/ask` | one voice turn: `audio` and/or `question`, optional `image`, `mode`, `session_id`, `language`, `want_speech`, `speech_format`, `voice`, `provider`; optional `want_morse` |
| `POST /v1/transcribe` | speech-to-text only (push-to-talk preview) |
| `GET|POST /v1/speech` | text → mp3 or ring ADPCM (`format=adpcm16k`, headers `X-Mcring-Blocks`, `X-Mcring-Duration-Ms`) |
| `POST /v1/morse` | optional silent pattern, no LLM |
| `GET /v1/health` | `{status, version, provider, model, tts, stt, speech_default, speech_formats}` |

Providers: `MCRING_PROVIDER` anthropic (Claude Opus 5.5) | openai; `MCRING_STT_PROVIDER` openai
(default) | local (faster-whisper) | none; `MCRING_TTS_PROVIDER` none (default — the phone speaks
`speech_text`) | openai. All `/v1/*` except health take `Authorization: Bearer <MCRING_API_TOKEN>`
when a token is set; unconfigured features answer 501 with a plain message.

## Cross-implementation guarantees

`python/mcring_core/tests/test_proto.py` compiles the firmware's `mcring_proto.c` (and the ADPCM
and Morse C libraries) and asserts that event packets, `AUDIO_START`, transfer and control packets
encode to the same bytes as Python; `app/__tests__/proto.test.ts` asserts the same hex strings in
TypeScript. `test_morse_cross.py` compares the C and Python Morse encoders on a corpus;
`app/__tests__/fixtures/morse_fixtures.json` is generated from Python and checked by jest. The
firmware's native Unity tests (`pio test -e native`, 14 tests) cover event and `AUDIO_START` encoding,
the audio-data block helpers and an ADPCM encode → decode round trip with the C decoder the speaker
path uses. The app's speaker pacing model (`audioStream.ts`) and the CLI's (`audio_out.py`) are
unit-tested against the same rules: burst the 24-block prebuffer, then keep ≤ 22 unplayed blocks
queued (the firmware holds 48 and drops beyond ~40).
