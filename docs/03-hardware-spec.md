# 3. Hardware specification (synthesis of the research)

Full sourced reports: `docs/research/01-camera-modules.md`, `02-mcu-radio-power.md`,
`03-actuators-triggers-audio.md`. BOM CSVs with links: `hardware/bom/`.

The product is voice-first (`docs/01`): the ring records, photographs and *cues*; the **phone is
the audio hub** and speaks the answer into the user's own Bluetooth headphones. The ring never
pairs to headphones — ESP32-S3 and nRF52 have no Classic-Bluetooth A2DP/HFP and a ring cell has no
budget for streaming (`docs/04`, "Audio topology") — so the only ring-side speech output is the
**optional on-ring speaker of the oversized stage-1 ring**, fed by the phone over BLE
(`AUDIO_OUT`, `protocol/ble-gatt.md`). Stage 2 is headphones-only.

## 3.1 The two numbers that shape everything

| | Value | Source |
|---|---|---|
| Battery inside a real smart ring | **16–22.5 mAh**, ~1C (Oura Gen 3 16 mAh Grepow; Galaxy Ring 17/18.5/22.5 mAh) | research 02 §3.1 |
| ESP32-S3 camera board current at the photo moment | **300–370 mA peaks**, ~150 mA average | research 02 §0 |

A 1C 16 mAh cell is specified for ~16 mA continuous. The ESP32-S3 path is 15–20× that at
the capture peak. So: **ESP32-S3 for stage 0/1 (bigger battery, oversized ring); nRF52840-class
for stage 2.** Everything else follows from this.

## 3.2 Stage 0 — bench rig (buy today, ~$50)

| Block | Part | Why |
|---|---|---|
| MCU + radio + camera + mic | **Seeed XIAO ESP32S3 Sense** | OV2640 on DVP, 8 MB PSRAM, PDM mic (ring-mic push-to-talk), BLE 5; runs `firmware/ring-esp32s3` unmodified |
| Haptic | DRV2605L breakout + 8 mm 235 Hz LRA | closed-loop drive gives crisp confirmation ticks (*listening* 1 tick, *answer ready* 2 ticks, *error* long buzz) |
| Trigger | tactile button + LIS2DW12 breakout | button for bring-up (hold ≥ 0.7 s = ask, short press = photo), double-tap = hands-free ask |
| Light | on-board LED (and/or a WS2812) | the same cues on the LED; capture blink |
| Speaker (optional) | MAX98357A I2S breakout (Adafruit 3006 class) + 8 Ω 10 mm speaker on **D7 BCLK / D6 LRC / D10 DIN, SD → 3V3** | proves the `AUDIO_OUT` speaker path on the bench before the stage-1 board; the headphone path needs nothing on the ring |
| Beeper | 12 mm piezo | optional beep cues (`CUES_MASK` bit 2) |
| Power | 100 mAh LiPo on the XIAO's charger | realistic current measurements |
| Speech output | the laptop's or phone's audio → Bluetooth headphones | nothing on the ring: F4 is a companion feature |

## 3.3 Stage 1 — oversized printed signet ring (band Ø20 ID / 22.4 OD × 12 mm; signet 31.5 × 21 mm, 11.1 mm tall)

| Block | Choice | Alternatives / notes |
|---|---|---|
| MCU/radio | **ESP32-S3-MINI-1U** (15.4 × 15.4 × 2.4), antenna/u.FL end away from the camera — decided | UM NanoS3 (28 × 11 × 2.4) was the alternative; keeps the stage-0 firmware; needs 30–40 mAh and a 100 µF+ buffer; accept ~1–4 days standby |
| Camera | **OV2640 24-pin FPC head** (~8–9 mm head, 5–6 mm tall) | **HM01B0 lensed module** 20 × 12.5 × 3.4 mm, <2 mW, mono 320×320 — the low-power path that also prepares stage 2 |
| Camera power | TPS22916 load switch (U2, IO21) + 2.8 V LDO | mandatory: un-gated camera = 3 mA sleep |
| Haptic | INEED LRA0825BC-0167F (8 × 2.5 mm) or PMD C08-005 (8 × 3.3) + DRV2605L/DRV2624 | cues only (60 ms ticks); PowerHap piezo + BOS1901 if you want <1 ms edges |
| Light | WS2812B-2020 under 1.2 mm white resin, rail gated by U9 TPS22916 (IO33) | cues + capture blink; XL-1010RGBC (1 × 1 mm) later |
| Trigger | LIS2DW12 double-tap (INT1 → deep-sleep wake) + Omron B3U-3000P side switch | hold = ask, short press = photo, double tap = hands-free ask; touch pad optional (ESP32-S3 touch) |
| Mic | TDK T3902 PDM (bottom-port, on the board's underside) | Ø0.6 port hole through the board, Ø0.8 lid port with a tube (`hardware/cad/`); ring-mic clips ≤ 8 s, 16 kHz ADPCM |
| **Speaker (optional)** | **MAX98357A** I2S class-D amp (U10, **16-TQFN 3 × 3 mm** for hand assembly; the 9-WLP 1.35 × 1.44 mm is the smaller alternative) + **PUI AS01008MR-2-R-class 8 Ω 10 mm micro speaker** (Ø10 × ~2.5–3 mm, 0.3 W, 86 dB @ 10 cm), off-board on two wire pads; **IO35 BCLK, IO36 LRCLK, IO37 DIN, IO34 = `PIN_SPEAKER_EN`** (drives the ON pin of U11, a third TPS22916 that gates the amp's 3V3 rail `VAMP` so it draws nothing asleep; the amp's `SD_MODE` pin is tied to `VAMP`, so the amp enables as the rail rises); 3V3 rail | ~66 dB @ 1 m before enclosure losses — arm's length in a quiet room; headphones through the phone stay the default. 10 s of speech ≈ 100–150 mA (`docs/04`). GPIOs fixed in `config_audio.h` `BOARD_MCRING_V1`; IO44 stays spare. Speaker pocket + sound port: `hardware/cad/` |
| Beeper (optional) | Murata PKMCS0909 9 × 9 × 1.9 piezo (LTB — buy now) on the BZ1 pads, 100 Ω from IO4 | 4 kHz beep cues (`CUES_MASK` bit 2); no pocket in the enclosure yet |
| Air puff | **Murata MZB1001T02** microblower as a 22 × 22 mm signet aimed at the next finger, 15–20 Vpp @ ~26 kHz driver | the only pump with a perceptible jet; stage-1 experiment only on the J2 aux pads (IO9 → Q1), stock is thin. On the XIAO dev kit D10 became I2S DIN, so the experiment is parked there |
| Battery | 301012 30 mAh flat cell, PCM | in a 10.4 × 12.4 × 3.4 mm pocket in the bay floor under the board (`hardware/cad/`); the 5 mm 501012 needs a deeper pocket; band-side placement would give a 7.7 mm signet |
| Charger | TI BQ25100 (25 mA charge, 1 mA termination; /CHG → IO3 + test pad) | MCP73831 OK for ≥ 40 mAh |
| Charging | two inner-band pads + pogo cradle | coil in stage 2 |
| PCB | 2-layer 0.6 mm rigid, **26.5 × 18.0 mm** in the signet bay (`hardware/pcb/board_params.json`), FPC to the camera | rigid-flex in stage 2 |
| Enclosure | `hardware/cad/` — CadQuery model generated from `board_params.json` (shell + lid + key STLs, fit report), SLA tough white/translucent resin | the OpenSCAD concept was removed |

Expected (`hardware/power-budget.txt`): on a 40 mAh cell, ~7 days at 30 voice questions a day with the answer spoken by the phone; using the on-ring speaker for every answer roughly triples the per-question energy (10 s at ~120 mA) and cuts that to ~2–3 days.
A day of ≥ 30 questions answered in headphones fits the 30 mAh cell; each 10 s answer played on the
ring speaker costs about 2–3 photos' worth of energy on top
(`python3 docs/build-helpers/tuning_calc.py speaker`), which is why the speaker is an option, gated,
and absent from stage 2.

## 3.4 Stage 2 — Oura-size (8 mm band, ≤ 3 mm, ~20 mm ID, plus a 4–5 mm camera pod)

| Block | Choice | Why / caveat |
|---|---|---|
| MCU/radio | **nRF52840** WLCSP (3.5 × 3.6) or **ISP1807** SiP (8 × 8 × 1.0, antenna included); nRF5340 (Galaxy Ring) or nRF54L15 as alternatives | ~5 mA radio peaks match a 1C cell; three real projects captured camera frames on nRF52840 |
| Camera | **OmniVision OVM7692** 2.8 × 3.2 × 2.6 mm, 8-bit DVP, DigiKey-stocked | only buyable *digital* camera under 3.5 mm; bit-bang 8-bit DVP at QQVGA grayscale; OVM6211 (3.2 mm GS) if stock appears; **skip OVM6948** (analog AntLinx needs a 6 × 6 mm OV426 bridge) |
| Battery | Grepow curved 16–24 mAh (e.g. GRP170722 14.5 mAh 1.7 × 6.5 × 22) | B2B samples; this is the hardest part to source |
| Charger | BQ25100 / BQ25120A | Oura Gen 2 precedent |
| Charging | flex-printed coil + own cradle (COTS coil floor ~11 mm) or pads | |
| Haptic | Vybronics VG0640001D 6 mm LRA (verify thickness) + DRV2624; or PowerHap 0904H014V060 (1.4 mm) + BOS1901 WLCSP | RingConn Gen 3 proves a motor fits in 2.3 mm; cues only |
| Light | XL-1010RGBC 1 × 1 × 0.8 mm | |
| Trigger | LIS2DW12 double-tap only (no button) | optional IQS227 touch |
| Mic | PDM MEMS (T3902 class) via the nRF PDM peripheral | ring-mic path; the phone-mic path works with no mic at all |
| Air puff / speaker | **not feasible** at this size | haptic cues + speech from the phone/headphones only (`AUDIO_OUT` is not ported to the nRF52840 firmware) |
| PCB | rigid-flex 0.22/0.48 mm, printed microstrip antenna, WLCSP assembly house | per Memfault's smart-ring guide and Oura/Galaxy teardowns |

Expected (`hardware/power-budget.txt`): on a 20 mAh cell, ~5 days at 30 questions a day; the 6 s ring-mic recording, not the photo, is the largest per-question term, and standby (~0.7 mAh/day) sets the ceiling at ~3 weeks.

## 3.5 Output-channel verdicts

Speech is the primary output at every stage, and it comes out of the **phone**: on-device TTS or
the server's mp3, routed to whatever headphones are paired. Everything on the ring is a cue, except
the stage-1 speaker option.

| Channel | Stage 1 | Stage 2 | Comment |
|---|---|---|---|
| Speech via phone → Bluetooth headphones | ✔ **primary** | ✔ **primary** | the ring only needs BLE; no A2DP/HFP source on ESP32-S3/nRF52 and no power for one (`docs/04`) |
| On-ring speaker (MAX98357A + 10 mm driver) | ✔ **optional** (IO34–37, U10/U11) | ✗ | ~66 dB @ 1 m: arm's length in a quiet room; ~100–150 mA for the 10 s an answer lasts; gated to 0 mA asleep |
| Haptic (LRA) | ✔ cues | ✔ cues | *listening* 1 tick, *answer ready* 2 ticks, *error* long buzz (`CUE`, `CUES_MASK` bit 0); 60 ms ticks |
| Light (RGB) | ✔ cues | ✔ cues | same three cues on the LED (`CUES_MASK` bit 1); capture blink; readable only when looking |
| Beeper (4 kHz piezo) | ✔ optional | signet only | beep cues (`CUES_MASK` bit 2), audible near the face |
| Morse on haptic/LED | optional silent mode | optional silent mode | off by default; `want_morse` / `--morse`; char 15 / overall 8 WPM, ≤ 32 chars ≈ 10–20 s (`protocol/morse.md`) |
| Air puff | experiment (Murata signet) | ✗ | no pump fits; electrotactile is the research alternative |
| Bone conduction | ✗ | ✗ | requires touching the ear; headphones do the job |

## 3.6 Trigger verdicts

Double-tap on a LIS2DW12 (hardware interrupt; ~1 µA in a low-power ODR, but the current firmware
keeps it at 400 Hz high-performance for tap-wake, ~90 µA — `docs/07-build-guide.md` §2.4) is the
primary trigger at every stage and means **hands-free ask** (the ring, or the phone, records up to
8 s); a side switch is the bring-up and fallback trigger at stages 0/1 — hold ≥ 0.7 s to ask, short
press for a photo only; capacitive touch only works as a deliberate thumb press on the top face and
takes a photo. Because a false double tap now starts a recording rather than just a photo, tune tap
thresholds against hand impacts with more care — the firmware exposes the threshold and uses an
800 ms burst filter, and a second double tap stops the recording.
