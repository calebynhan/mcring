# 5. Roadmap

mcring is **voice-first**: hold the ring, ask, hear Claude in your headphones (or from the ring's
own speaker on the oversized ring). The camera is context, haptics are cues, Morse is an optional
silent mode. Projection is a v2 idea (last section).

## Stage 0 — bench proof (now → 2 weeks)

- [x] Protocol spec, shared codecs (C / Python / TS) with cross-tests
- [x] **Voice-first pivot of the protocol**: `EVENTS` (0007) and `AUDIO_OUT` (0008) characteristics, `RECORD_START/STOP`, `SET_CONFIG` 9–11, `SPEAKER_OK`, `CUE`
- [x] ESP32-S3 firmware for XIAO ESP32S3 Sense: button events, ring-mic push-to-talk (≤ 8 s), capture, transfer, cues, I2S speaker playback, deep sleep (legacy pattern player kept)
- [x] Backend: image-optional `/v1/ask` with speech-to-text (OpenAI / local whisper), read-aloud Claude answers, `/v1/transcribe`, `/v1/speech` (mp3 + 16 kHz ring ADPCM), sessions; Morse opt-in only
- [x] Desktop companion (bleak): `mcring talk` push-to-talk (keyboard or ring button, laptop or ring mic, OS/server voice, `--ring-speaker`), `say`, `events`, `config`; no-hardware `ask --audio`
- [x] Phone companion (Expo dev client): events, ring-mic / phone-mic push-to-talk, transcript UI, phone TTS or server mp3 → headphones, ring-speaker streaming, settings → `SET_CONFIG`
- [x] `docs/08-projection-v2.md` feasibility note (v2 scoping only)
- [ ] **Order the stage-0 BOM** (`hardware/bom/stage0-devkit.csv`, or the zero-solder `stage0-devkit-solderless.csv`) + a MAX98357A breakout and an 8 Ω 10 mm speaker for the `AUDIO_OUT` bench test
- [ ] Flash (`pio run -e xiao_esp32s3_sense -t upload`); first `mcring talk` turn with the ring button; record round-trip and BLE throughput in `docs/benchmarks.md`
- [ ] Pair Bluetooth headphones to the laptop/phone and confirm the answer routes there with nothing configured on the ring (F4)
- [ ] Phone-mic mode: measure `BUTTON_DOWN` → recording-started latency on iOS and Android (app foreground and background)
- [ ] Ring-mic clip quality at arm's length: transcription accuracy 4/5 (F6); tune mic gain / clip trimming
- [ ] Speaker bench: `mcring say "…" --ring-speaker` on the XIAO + MAX98357A; count `AUDIO_UNDERRUN` at MTU 185 vs 517; verify the I2S mono-duplication choice on real hardware; measure loudness at 30 cm and 1 m
- [ ] Measure current with a shunt/PPK2 during ask (capture + record + transfer) and during speaker playback; update `hardware/power_budget.py`
- [ ] Tune JPEG quality/size vs. answer quality (QVGA q12 vs VGA q15)
- [ ] Tune cue timing/strength on a real LRA (listening tick must not be mistaken for answer-ready)
- [ ] Prebuild the app on a phone; confirm iOS MTU/PHY behaviour and background audio recording limits

## Stage 1 — oversized wearable ring (1–3 months)

- [ ] Decide ESP32-S3-MINI-1U (keep firmware) vs. nRF52840 (future-proof) for the ring board
- [x] Speaker hardware: MAX98357A + 10 mm speaker on IO34–37, gated amp rail, pocket and grille in the signet's right wall (`hardware/electrical`, `hardware/cad`)
- [ ] KiCad layout from `hardware/electrical/out/mcring_v1.net` + `hardware/pcb/floorplan.md` (26.5 × 22.8 mm, plug-in Pico-EZmate connectors), then order the board **assembled** per `docs/10-ordering-assembled-boards.md` (CPL + JLC BOM from `hardware/pcb/export_cpl.py`); confirm the Pico-EZmate footprint and wire-exit side on the Molex drawing first
- [ ] Print `hardware/cad/out/mcring_stage1_*.stl` and fit-check with real parts (the model's fit check passes; real tolerances decide)
- [ ] Load-switched camera rail; verify < 30 µA sleep; speaker amp shut down (`SD`) between answers
- [ ] Double-tap threshold tuning on-finger (double tap = hands-free ask, so false positives start a recording); false-positive log
- [ ] One day of real use on 40 mAh: ≥ 30 questions with answers in headphones; separately measure how many speaker answers the cell affords
- [ ] Optional: Murata microblower signet experiment on the aux channel (parked on the dev kit, where D10 became I2S DIN)

## Stage 2 — Oura-size (3–9 months, multi-spin)

- [ ] Port `EVENTS` / `RECORD_START/STOP` / cues to `firmware/ring-nrf52840` (no `AUDIO_OUT`: stage 2 has no speaker — answers are phone/headphones only)
- [ ] Finish `firmware/ring-nrf52840/src/camera_hal.c`: OV7670/OVM7692 bit-bang + baseline JPEG encoder; benchmark capture time on XIAO nRF52840 Sense
- [ ] PDM mic → ADPCM on nRF52840 (nrfx PDM) with the same 132-byte block format
- [ ] Try HM01B0 1-bit mode through SPIS + PPI (lowest power path)
- [ ] Sample Grepow curved cells; BQ25100 charger board
- [ ] Rigid-flex layout (0.22/0.48 mm) around ISP1807 or nRF52840 WLCSP; printed antenna; OVM7692 pod; mic port
- [ ] Haptic for cues: VG0640001D vs PowerHap + BOS1901 on-finger comparison
- [ ] Potting + shell; charging cradle
- [ ] Battery-life validation against `hardware/power-budget.txt`

## Software backlog (any stage)

- [ ] Voice activity detection to end ring-mic recordings early (currently button release or 8 s)
- [ ] Phone-side on-device transcription (iOS Speech / Android SpeechRecognizer) so a deployment needs only `ANTHROPIC_API_KEY`
- [ ] Streaming answers: start TTS on the first sentence; stream `AUDIO_DATA` while the rest is synthesised
- [ ] Barge-in polish: cancel server TTS and ring playback on `BUTTON_DOWN` without a click
- [ ] Wake-word-free "continue" gesture: double tap during the follow-up offer = "yes"
- [ ] Ring speaker: server-side mp3 encoder so `speech_format=both` does not call TTS twice; loudness normalisation
- [ ] OTA firmware update over BLE
- [ ] Backend: rate limiting, per-device tokens, request logging opt-in
- [ ] Simulated ring (software peripheral emitting events and accepting `AUDIO_OUT`) for CI of the companion apps
- [ ] Silent-pattern mode (optional): "yes/no/digits" ultra-short Morse and a per-user abbreviation dictionary, if anyone asks for it

## Side track — R1-class touch ring (exploration)

Scope, costs and reasoning: [`docs/11-touch-ring-r1-class.md`](11-touch-ring-r1-class.md); BOM:
`hardware/bom/touch-ring.csv`.

- [x] Teardown-level analysis of the Even R1 (parts, gestures, G2 link) and a costed cheaper design
- [ ] Phase A: wear a Colmi R02 (Gadgetbridge) next to a chest strap for a week; decide whether the PPG is populated
- [ ] Phase B: XIAO nRF52840 Sense + IQS7211E eval kit: BLE HID + `EVENTS` (touch long press = `BUTTON_DOWN`/`BUTTON_UP`), accelerometer tap confirmation, gesture logging; ≥ 95 % correct over 100 trials per gesture
- [ ] Add `TAP` / `SWIPE` / `TAP_HOLD` events to `protocol/ble-gatt.md` and the shared codecs once phase B settles the gesture set
- [ ] Qualify a second touch-IC source (IQS7211E lead time)
- [ ] Phase C: oversized wearable from AliExpress modules per [`touch-ring-build.html`](touch-ring-build.html) (XIAO nRF52840 Sense + MPR121 in a printed pod on an adjustable ring blank); measure real battery life with a PPK2
- [ ] Phase C: CadQuery model of the 34 × 25 × 10 mm pod (USB-C slot, lid, floor hole for the health wires) next to `hardware/cad/mcring_stage1.py`

## v2 — projection from the ring (not scheduled)

The idea: Claude projects visuals through the ring onto a wall or your palm. There is no concrete
use case yet, so this is deliberately **v2**, after the voice loop has been worn daily. The
feasibility note [`docs/08-projection-v2.md`](08-projection-v2.md) sets the frame:

- **Full raster projection is not plausible at ring size** — the smallest real engines are
  watch-sized, draw 1.5–7 W, need a dim room, and a 30–40 mAh cell (≈ 0.11 Wh) would hit the
  skin-contact thermal limit in about a minute. Humane's AI Pin was the closest shipped device
  and was criticised for exactly these reasons.
- **An aimed Class-1 laser *pointer* is plausible, cheap and already wired**: a Ø3.3–6 mm module
  on the existing aux channel (`PIN_AUX` → Q1 → J2 on the stage-1 board), aimed along the camera
  axis, ~$2–5 of parts plus a laser power meter.
- **Vector glyphs** (arrow, circle, digit) via a 1–2 mm MEMS mirror are the research-grade
  stretch; full images, if ever, belong to a companion clip/pendant, not the ring.

v2 items, in order (details and interlocks in `08-projection-v2.md` §4–§5):

- [ ] Meet the decision checklist in `08-projection-v2.md` §5.2 first: v1 used daily by ≥ 3 people for ≥ 2 weeks, framing failures measured, a weekly pointing use case named by testers
- [ ] Pointer experiment on the stage-1 aux pads: Class-1 (≤ 0.39 mW, preferably 520 nm green) module, button-held-only, 3 s cap, IMU pitch/motion cut-off, phone-side face-detector gate
- [ ] Backend returns a bounding box / direction for "which one?" answers; phone-side visual servoing on low-res frames before any 6-axis IMU spin
- [ ] Protocol delta as a v2 extension (`POINTER` control, `POINTER_ENABLE` config, `POINTER_ON` status, `POINTER_BLOCKED` event) — proposals only, kept out of the v1 GATT spec until then
- [ ] Re-check annually for a ≤ 1 cc / ≤ 0.3 W / Class-1 image engine; otherwise raster projection stays parked
