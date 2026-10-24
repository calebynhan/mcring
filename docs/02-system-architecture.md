# 2. System architecture

Four components, one protocol, three shared codecs.

```
 ring (firmware)  ──BLE GATT──▶  companion (phone app | desktop CLI)  ──HTTPS──▶  backend (FastAPI)  ──▶  LLM
      ▲                                       │                                                │
      └───── Feedback: MORSE_UNITS ◀──────────┴──────── answer + short + morse units ◀──────────┘
```

Diagrams (Mermaid): `hardware/block-diagram.md`.

## Components

| Component | Dir | Language / stack | Role |
|---|---|---|---|
| Ring firmware (stage 0/1) | `firmware/ring-esp32s3` | C++17, Arduino-ESP32 2.0.x, NimBLE 2.x, esp_camera | trigger → JPEG → reliable BLE transfer; Morse player; power management |
| Ring firmware (stage 2 skeleton) | `firmware/ring-nrf52840` | C, Zephyr / nRF Connect SDK | same protocol on an nRF52840; camera HAL stubbed |
| Shared codecs | `firmware/ring-esp32s3/lib/*`, `python/mcring_core`, `app/src/lib` | C99, Python, TypeScript | packet encoding, CRC-32, Morse → units, IMA-ADPCM; byte-identical, cross-tested |
| Phone companion | `app/` | React Native + Expo dev client, react-native-ble-plx, expo-speech | BLE central, reassembly, backend client, TTS, Morse write-back |
| Desktop companion | `tools/ring-cli` | Python, bleak, httpx | same as the app for a laptop; plus a no-hardware `ask` mode |
| Backend | `backend/` | Python, FastAPI, Anthropic SDK (OpenAI optional) | vision Q&A with structured JSON; Morse pattern + ring packet; optional TTS; session memory |

## Why these boundaries

* **The ring does the minimum**: capture, compress (hardware JPEG on the OV2640 or a small
  encoder), ship bytes, play patterns. No Wi-Fi, no TLS, no LLM client on the ring. That keeps
  the stage-2 nRF52840 port realistic and the power budget sane.
* **The phone is the internet gateway** (as every shipping smart ring does). It also owns TTS,
  which is free and offline on both platforms.
* **The backend holds the API keys** and the prompt. Swapping Claude for OpenAI is a form field.
  The Morse encoder also lives here so the phone/CLI can be dumb, but the ring can still
  encode `MORSE_TEXT` itself for offline/debug use.

## Protocol (`protocol/`)

* One 128-bit service, five characteristics (control, status, transfer meta, transfer data,
  feedback). Little-endian packed packets; see `protocol/ble-gatt.md` and `protocol/schemas/ring_packets.md`.
* **Transfer**: START → N data notifications (no per-chunk ack) → END → phone ACK with a
  missing-index list → selective retransmit (≤ 5 rounds). Chunk size follows the negotiated
  MTU (178 B on iOS, up to 510 B on Android). CRC-32 over the whole payload.
* **Feedback**: `MORSE_TEXT` (ring encodes), `MORSE_UNITS` (+ `_CONT` continuation writes)
  for sender-computed Farnsworth patterns, raw `PATTERN`, `RGB`, `STOP`.
* **Status**: 12-byte struct on connect/change/30 s.

## Data flow for one question

1. Trigger → `camera_capture()` powers the sensor, discards 3 frames for AEC, grabs a JPEG
   (QVGA q12 ≈ 8–15 KB), copies it to PSRAM, powers the sensor down. `<SN>` blink.
2. `transfer::tick()` streams chunks under a ~15 ms-per-loop budget with TX credits.
3. Companion reassembles, verifies CRC, ACKs, writes the JPEG to cache.
4. Companion `POST /v1/ask` (image + typed/voice question + session id).
5. Backend normalises the image, builds the prompt (`app/prompts.py`), calls Claude with a
   JSON schema (`answer`, `short`, `subject`, `confidence`, `warnings`), server-side refusal
   fallbacks on, prompt caching on the system prompt.
6. Backend shortens `short` to A–Z 0–9, encodes Morse with Farnsworth spacing, returns units,
   duration and a ready `MORSE_UNITS` packet.
7. Companion speaks `answer`, writes the pattern to the ring (re-split to its MTU), optionally
   vibrates the phone in the same pattern.
8. Ring plays the pattern on LED/haptic/buzzer/aux; `STOP` cancels.

## Cross-implementation guarantees

`python/mcring_core/tests/test_morse_cross.py` compiles the firmware's C encoder and compares it
to Python on a corpus; `app/__tests__/fixtures/morse_fixtures.json` is generated from Python
and checked by jest; packet hex strings are asserted identically in all three test suites.
