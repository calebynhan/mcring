# mcring — a ring you talk to; Claude answers in your ear

Hold the ring's button (or double-tap it), ask a question out loud — about what your hand is
pointing at, or about anything at all — and a few seconds later Claude answers through your own
Bluetooth headphones. The ring carries a pinhole camera for optional visual context, a microphone,
and a haptic motor for short confirmation cues; your phone does the rest. This repository is the
complete plan and the complete software for building it, in three hardware stages:

| Stage | Form factor | Brain | Status |
|---|---|---|---|
| **0 — bench** | Seeed XIAO ESP32S3 Sense + breadboard parts (optional MAX98357A + 10 mm speaker) | ESP32-S3 | **software complete, ready to flash** |
| **1 — oversized ring** | 30 mm OD printed ring, custom board, 30–40 mAh cell; optional on-ring speaker | ESP32-S3-MINI-1U (or nRF52840) | BOM, schematic, enclosure model, same firmware |
| **2 — Oura-size** | 8 mm band ≤ 3 mm + 4–5 mm camera pod, 16–24 mAh curved cell; headphones only | nRF52840 WLCSP / ISP1807 | research-backed spec, Zephyr skeleton with stubbed camera |

```
                  BLE                                    HTTPS
ring ◀──────────────────────────▶ phone app / desktop CLI ◀─────────▶ backend ──▶ Claude (+ STT / TTS)
 │   button events · mic clip ·            │
 │   photo · cues · speaker stream         └── normal phone audio routing ──▶ your Bluetooth headphones
 └── optional on-ring speaker (stage-1 oversized ring only)
```

The ring never pairs to headphones itself: ESP32-S3 and nRF52 have no Classic-Bluetooth audio
(A2DP/HFP) and a ring cell has no power budget for it. The phone owns the audio, the internet and
the API keys; the ring records, photographs, cues and — on the big stage-1 ring — can play the
answer through its own small speaker.

## One voice turn

1. **Hold** the ring button (≥ 0.7 s) or **double-tap** it. The ring ticks once: *listening*.
2. **Ask.** Either the ring's PDM mic records while you hold (16 kHz mcring-ADPCM over BLE), or —
   with *Phone / headset mic* selected in the app — the phone records between the ring's
   `BUTTON_DOWN` and `BUTTON_UP` events, using your headset's microphone.
3. **Optional photo.** In ring-mic mode the ring snaps a QVGA JPEG as you start talking; in
   phone-mic mode the app requests one when it wants visual context. A short press or a touch is
   just a photo. A pure voice question needs no photo at all.
4. The companion posts audio (+ photo, + session id) to `POST /v1/ask`. The backend transcribes
   it, asks Claude for a read-aloud answer (one to three sentences plus an optional follow-up),
   and returns `speech_text` — and, when a TTS provider is configured, mp3 and/or 16 kHz ADPCM.
5. **Hear it.** The phone speaks (on-device TTS or the server mp3) into your headphones and the
   ring ticks twice: *answer ready*. On a stage-1 ring with a speaker the phone can instead stream
   the ADPCM to the ring's `AUDIO_OUT` characteristic and the ring plays it over I2S.
6. **Follow up** ("is it edible?") in the same session; the last photo stays referenced.

## What's in the box

| Path | Contents |
|---|---|
| `docs/ring-anatomy.html` | interactive 3D model of the stage-1 ring: orbit, explode, section cut, click any part for its part number and job ([published copy](https://claude.ai/artifact/9KUQfEg7CHZFahAvKjhaeG)); rebuild with `python3 tools/ring-viz/export_mesh.py` |
| `docs/09-fundamentals.md` + `docs/fundamentals/` | the course that goes with the project: electronics, power, firmware, BLE, cameras, audio/haptics, PCB, CAD, software — each chapter tied to the repo files, with verified video/course/interactive links and exercises |
| `docs/` | [vision & requirements](docs/01-vision-and-requirements.md), [architecture](docs/02-system-architecture.md), [hardware spec](docs/03-hardware-spec.md), [feasibility & risks](docs/04-feasibility-and-risks.md), [roadmap](docs/05-roadmap.md), [getting started](docs/06-getting-started.md), [build guide](docs/07-build-guide.md), [**projection v2 note**](docs/08-projection-v2.md); `docs/research/` three sourcing reports (cameras · MCU/radio/power · actuators/triggers) |
| `protocol/` | [BLE GATT spec](protocol/ble-gatt.md) — control, status, transfer, feedback/cues, **events**, **audio-out**; packet layouts; JSON schemas; Morse timing (optional/legacy) |
| `firmware/ring-esp32s3/` | PlatformIO firmware (stage 0/1): button/double-tap/touch with **event notifications**, ring-mic push-to-talk (≤ 8 s ADPCM), capture + reliable chunked transfer, **I2S speaker playback** of a phone-streamed ADPCM answer, haptic/LED/beep cues, deep sleep; legacy pattern player |
| `firmware/ring-nrf52840/` | Zephyr skeleton (stage 2): same GATT service/transfer/feedback, camera HAL stub — predates the voice pivot (no EVENTS / AUDIO_OUT yet) |
| `python/mcring_core/` | shared codecs (packets, events, audio-out framing, CRC-32, IMA-ADPCM, Morse) — cross-tested byte-for-byte against the C libraries |
| `backend/` | FastAPI: `POST /v1/ask` (voice and/or text, photo optional → Claude Opus 5.5 structured answer → `speech_text`, mp3 / 16 kHz ADPCM), `POST /v1/transcribe`, `GET|POST /v1/speech`, `POST /v1/morse` (optional), `GET /v1/health`; speech-to-text via OpenAI or local faster-whisper; sessions for follow-ups |
| `app/` | React Native / Expo companion: BLE + events, push-to-talk state machine (ring mic or phone mic), transcript UI, phone TTS or server mp3 → headphones, ring-speaker streaming, settings |
| `tools/ring-cli/` | Python desktop companion (bleak): `mcring talk` (push-to-talk from the keyboard or the ring button), `listen`, `say`, `events`, `config`; no-hardware `mcring ask photo.jpg --audio q.wav` |
| `hardware/` | BOMs with sources for all three stages, pin maps, schematic notes and generated schematics, power budget, Mermaid [block diagrams](hardware/block-diagram.md), parametric CadQuery enclosure model with fit check ([`hardware/cad/`](hardware/cad/README.md)) |

## Quick start (no hardware)

```bash
(cd backend && pip install -r requirements.txt)   # backend + python/mcring_core (editable); run it from backend/ so the relative -e path resolves
pip install -e 'tools/ring-cli[mic]'              # the mcring CLI; [mic] = sounddevice for the laptop microphone
export ANTHROPIC_API_KEY=sk-ant-...        # the answers
export OPENAI_API_KEY=sk-...               # speech-to-text (default provider) — or set MCRING_STT_PROVIDER=local
(cd backend && uvicorn app.main:app --port 8000 &)
mcring talk --no-ring                      # Enter → ask out loud → Enter → hear the answer
mcring ask your-photo.jpg -q "what is this?" --speak    # typed question about a photo, no mic needed
```

Full instructions: [`docs/06-getting-started.md`](docs/06-getting-started.md). Flash the ring:
[`firmware/ring-esp32s3/README.md`](firmware/ring-esp32s3/README.md) (speaker wiring included).

## Key engineering conclusions (details in `docs/03` and `docs/04`)

1. **Battery and peak current, not chip size, decide the ring.** Real rings carry 16–22 mAh at
   ~1C; an ESP32-S3 camera board peaks at 300+ mA. ESP32-S3 is the right stage-0/1 part and the
   wrong stage-2 part; nRF52840-class is the stage-2 part.
2. **No digital camera a hobbyist can buy fits inside a 3 mm band.** The best stage-2 option is
   the OmniVision OVM7692 (2.8 × 3.2 × 2.6 mm, DVP, in stock) in a ~4–5 mm pod. The famous
   0.65 mm OVM6948 is analog and needs a 6 × 6 mm bridge chip — skip it.
3. **The phone is the audio hub.** Bluetooth headphones pair to the phone, never to the ring; the
   ring only needs BLE. An on-ring speaker (10 mm driver + MAX98357A, roughly 66 dB at 1 m) is
   worth having on the oversized stage-1 ring for arm's-length use in a quiet room, and is
   physically out at Oura size.
4. **Keep images ≤ 30 KB** so the BLE leg stays under ~1 s on iPhone (~350 kbps) — QVGA JPEG or
   160 × 120 grayscale is plenty for identification; the 16 kHz ADPCM question costs 8 KB/s.
5. **Haptics are cues, not a reading channel.** One tick = listening, two = answer ready, a long
   buzz = error. The earlier haptic-Morse output survives only as an optional silent mode (below).

## Test status

| Suite | Result |
|---|---|
| `python/mcring_core` (codecs + C cross-check, incl. events / audio-out) | 36 passed |
| `backend` (LLM, STT and TTS providers mocked) | 77 passed |
| `tools/ring-cli` (BLE and HTTP mocked) | 24 passed |
| `app` jest + `tsc --noEmit` | 33 passed in 5 suites, typecheck clean |
| `firmware/ring-esp32s3` | C libraries compiled & tested on the host (Unity, 14 tests); application syntax-checked against API stubs — **not yet compiled with the ESP32 toolchain** (network-restricted build sandbox); run `pio run` locally. I2S speaker output is unverified on hardware |
| `firmware/ring-nrf52840` | reviewed, uncompiled skeleton |

## Optional silent mode (Morse)

mcring started as a haptic-Morse ring, and that path is still in the tree: the ITU Morse encoder
(`python/mcring_core`, `lib/mcring_morse`, `app/src/lib/morse.ts`), the ring's pattern player and
the `MORSE_TEXT` / `MORSE_UNITS` feedback opcodes all work and remain cross-tested. Nothing uses
them by default — the backend returns `short`/`morse` only when asked (`want_morse=true`), the app
has no Morse UI, and the CLI needs `--morse`. See [`protocol/morse.md`](protocol/morse.md) if you
want a silent pattern on the finger where audio is impossible.

## Later (v2): projection

Could the ring one day project visuals onto a wall? [`docs/08-projection-v2.md`](docs/08-projection-v2.md)
is the sourced feasibility note: full raster projection is not plausible at ring size (power,
heat, eye safety), an aimed Class-1 laser pointer on the existing aux channel is, and the
decision checklist says what v1 must prove first. It is on the [roadmap](docs/05-roadmap.md) as a
v2 item, not in v1.

## License

MIT — see `LICENSE`.
