# 4. Feasibility, physics and risks — the honest version

## What is straightforward

* **Stage 0 end to end.** Hold → ask → BLE → phone or laptop → backend (speech-to-text, Claude,
  text-to-speech) → the answer in your Bluetooth headphones, with a tick on the ring, is a
  weekend of integration on a $14 board. Every piece exists and is used in this repo; the
  optional on-ring speaker is one breakout more.
* **The protocol and the phone/backend software** are form-factor independent; nothing has to
  be redone for stage 2.
* **The audio topology is settled: the phone is the audio hub.** Headphones pair to the phone,
  never to the ring (why: next section). The ring only needs BLE, which every candidate SoC has.
* **Cues instead of a reading channel.** Three haptic/LED cues (*listening*, *answer ready*,
  *error*) are learnt in a minute; nobody has to read anything on the finger. Haptic Morse
  survives only as an optional silent mode (`protocol/morse.md`).

## Audio topology — why the ring never pairs to headphones

| | |
|---|---|
| **No radio for it** | Bluetooth headphones speak Classic-Bluetooth A2DP (music) / HFP (calls). The ESP32-S3 is BLE-only (Classic BT was dropped after the original ESP32) and so are nRF52/nRF53/nRF54 — the ring cannot be an A2DP source at all. LE Audio would need the ring to be a unicast *source* with isochronous channels; stacks exist on nRF53, consumer headphones that accept a third-party LE Audio source barely do |
| **No power for it** | an A2DP / LE Audio source streams continuously at 30–60 mA (radio + SBC/LC3 encode); a 10 s answer would cost 100–170 µAh on the radio alone, before any speaker, and the link would have to be kept alive between answers |
| **No need for it** | the phone already owns the headphones, their pairing, their microphone and the volume rocker; it already has the internet and the API keys. Routing the answer through it is zero code (`expo-speech`, the OS voice or an mp3 player use the current audio route), and the headset mic can record the question while the ring button is held (`BUTTON_DOWN` / `BUTTON_UP` events) |
| **Consequence** | the ring is a BLE peripheral with two inputs (ring mic, or button events for the phone mic) and one optional output: the stage-1 speaker, fed by the phone as 16 kHz ADPCM over `AUDIO_OUT` (8 KB/s, a fraction of a BLE link). Stage 2 has no speaker at all |

## What is hard

| Risk | Why | Mitigation in this plan |
|---|---|---|
| **Battery vs. peak current** (stage 2) | ring cells are 16–24 mAh @ 1C; ESP32-S3 camera peaks are 300+ mA | nRF52840-class SoC for stage 2; ESP32-S3 confined to stages 0/1 with 30–100 mAh |
| **No tiny digital camera module that a hobbyist can lens** | sub-3.5 mm cameras are wafer-level parts: OVM7692 (DVP, in stock), OVM6211 (no stock), OVM6948 (analog, needs a 6 × 6 mm bridge) | stage 1 uses an off-the-shelf lensed module; stage 2 designs around OVM7692 and accepts a 4–5 mm pod |
| **No BLE SoC has a camera interface** | nRF/Ambiq/Renesas have none; only ESP32-S3 and Realtek do | bit-bang DVP on nRF52840 (proven with OV7670); HM01B0 1-bit via SPIS is R&D |
| **BLE throughput on iOS** | ~300–400 kbps, MTU 185 | keep images ≤ 30 KB (QVGA JPEG / 160×120 gray); selective retransmit; 2M PHY + DLE requested; ring-mic clips ≤ 8 s (≤ 64 KB) or use the phone mic |
| **Air puff from a ring** | no purchasable pump fits in 3 mm; the smallest with a real jet is 20 × 20 mm | stage-1 signet experiment only; electrotactile noted as the research path |
| **Curved battery sourcing** | Grepow sells B2B samples; MOQ/NDA likely | stage 1 uses flat 30–40 mAh hobby cells; start the Grepow conversation early |
| **WLCSP / rigid-flex assembly** | 0.35–0.4 mm pitch, 0.22 mm flex | assembly house; ISP1807 SiP avoids WLCSP for the radio |
| **Double-tap false positives** | a ring sees constant hand impacts, and a false double tap now starts a recording | tight latency window, quiet-period gate, long-press button as fallback; a second double tap stops the recording; log and tune |
| **Speaker playback energy** (stage-1 option) | a 10 s spoken answer on the MAX98357A + 10 mm driver draws **~100–150 mA** from 3V3 at a usable volume → 280–420 µAh, 2–3× a photo (154 µAh); an un-gated amp idles at ~2.4 mA = 58 mAh/day, twice the cell | headphones stay the default output; the amp's 3V3 rail `VAMP` is gated by a TPS22916 (U11) whose ON pin IO34 drives, and the amp's `SD_MODE` pin is tied to `VAMP` so it enables as the rail rises and draws nothing asleep; the `GAIN` pin caps the loudness and `SPEAKER_VOLUME` scales below it; `docs/build-helpers/tuning_calc.py speaker` budgets answers per charge |
| **Speaker loudness** | 10 mm driver: 86 dB @ 10 cm → ~66 dB @ 1 m in free air, a few dB less through a ported 1.2 mm shell | an arm's-length, quiet-room output; hand near the ear; it is an option on the oversized ring only and physically out at Oura size |
| **Voice latency 2–4 s** | speech-to-text (~0.5–1 s), Claude (1–3 s) and text-to-speech (0.5–1 s) run in series after the button is released, plus ~1 s of BLE clip transfer in ring-mic mode on iOS | N2 budgets 6 s to the first spoken word; phone-mic mode skips the BLE clip; prompt caching, 1–3-sentence answers; the *listening* / *answer ready* cues make the wait legible; streaming TTS and phone-side STT are on the backlog |
| **LLM cost** | vision tokens per photo | QVGA images are cheap (~1–1.5 K tokens); a voice-only question sends no image; prompt caching on the system prompt; `effort=medium` |
| **Privacy** | a camera on a hand photographs people; a microphone records them | capture and recording are explicit (hold / tap), no streaming, no wake word, LED blinks on capture, audio and images go only to the user's chosen providers (N4); keep it that way |

## Physics sanity checks

* **Optics:** a 2.8 mm camera cube has a ~1 mm aperture; depth of field is effectively
  infinite from ~15 cm; low light will be noisy. A flower in daylight is fine; a menu in a dim
  restaurant is marginal. Stage-1 OV2640 (1/4") is much better in low light.
* **Framing:** a ring on the index finger points wherever the finger points; a ~70–90° FOV
  forgives aim. Shutter lag after the trigger (camera power-up + AEC ≈ 150–250 ms) is
  short enough that a "point, hold, ask" gesture works — in ring-mic mode the photo is taken
  before the listening tick, so the user speaks after it.
* **Acoustics (speaker option):** a 10 mm 86 dB @ 10 cm driver gives ~66 dB @ 1 m in free air
  (−20 dB per decade of distance); a small port in the resin shell costs a few dB more. Speech at a
  16 kHz sample rate (8 kHz bandwidth) is fully intelligible; the 132-byte ADPCM blocks are 8 KB/s,
  ~5 % of an Android BLE link and ~70 % of an iOS one at MTU 185 — which is why the ring buffers
  ~400 ms before it starts and reports `AUDIO_UNDERRUN` rather than clicking.
* **Microphone:** a bottom-port MEMS mic behind a Ø0.8 mm port with a 1.8 mm tube is a
  Helmholtz resonator around 8–10 kHz; speech below 4 kHz is unaffected. Arm's-length speech
  reaches the ring at ~60 dB SPL, 30 dB above the T3902 noise floor.
* **Thermal:** nothing here dissipates more than ~0.5 W for a second (the class-D amp at full
  volume included); no issue.
* **RF:** a ring antenna next to a finger is detuned and lossy; expect ~3–8 m range to the
  phone, fine for a pocket. ISP1807 includes a tuned antenna; the ESP32-S3-MINI-1U wants a
  flex dipole along the band.
* **Haptics on a finger:** 0.9–1.3 G from a 6–8 mm LRA pressed against the finger is clearly
  perceptible; LRA rise/fall ≈ 20–40 ms, so the 60 ms cue tick (`CUE_TICK_MS`) is near the floor
  — keep tick and gap ≥ 60 ms, and the optional Morse at dots ≥ 80 ms (≤ 15 WPM character speed).

## Where this could still fail

1. The OVM7692 bit-bang on nRF52840 turns out too slow/flaky at 8-bit (then: HM01B0 1-bit via
   SPIS, or an nRF5340 with its faster core, or accept a 4 × 4 mm "camera co-processor").
2. No curved cell can be bought in small quantity (then: stage 1.5 — a slightly thicker ring
   around a 301012 flat cell, ~3.5 mm band).
3. The on-ring speaker is too quiet on the finger or too hungry on the cell (then: it stays an
   option on the oversized ring; the product is the headphone path, which needs nothing on the
   ring and is the only path at stage 2).
4. Round-trip latency stays above ~6 s on real networks (then: phone-side on-device
   transcription, streaming TTS from the first sentence, shorter answers — all backlog items in
   `docs/05-roadmap.md`; the protocol already lets the phone start playback before the answer is
   fully synthesised).
