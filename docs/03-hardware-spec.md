# 3. Hardware specification (synthesis of the research)

Full sourced reports: `docs/research/01-camera-modules.md`, `02-mcu-radio-power.md`,
`03-actuators-triggers-audio.md`. BOM CSVs with links: `hardware/bom/`.

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
| MCU + radio + camera + mic | **Seeed XIAO ESP32S3 Sense** | OV2640 on DVP, 8 MB PSRAM, PDM mic, BLE 5; runs `firmware/ring-esp32s3` unmodified |
| Haptic | DRV2605L breakout + 8 mm 235 Hz LRA | closed-loop drive gives crisp Morse edges |
| Trigger | tactile button + LIS2DW12 breakout | button for bring-up, double-tap for the real UX |
| Light | on-board LED (and/or a WS2812) | confirmation + light Morse |
| Audio | 12 mm piezo | optional beeps |
| Power | 100 mAh LiPo on the XIAO's charger | realistic current measurements |

## 3.3 Stage 1 — oversized printed signet ring (band Ø20 ID / 22.4 OD × 12 mm; signet 31.5 × 21 mm, 11.1 mm tall)

| Block | Choice | Alternatives / notes |
|---|---|---|
| MCU/radio | **ESP32-S3-MINI-1U** (15.4 × 15.4 × 2.4), antenna/u.FL end away from the camera — decided | UM NanoS3 (28 × 11 × 2.4) was the alternative; keeps the stage-0 firmware; needs 30–40 mAh and a 100 µF+ buffer; accept ~1–4 days standby |
| Camera | **OV2640 24-pin FPC head** (~8–9 mm head, 5–6 mm tall) | **HM01B0 lensed module** 20 × 12.5 × 3.4 mm, <2 mW, mono 320×320 — the low-power path that also prepares stage 2 |
| Camera power | TPS22916 load switch + 2.8 V LDO | mandatory: un-gated camera = 3 mA sleep |
| Haptic | INEED LRA0825BC-0167F (8 × 2.5 mm) or PMD C08-005 (8 × 3.3) + DRV2605L/DRV2624 | PowerHap piezo + BOS1901 if you want <1 ms edges |
| Light | WS2812B-2020 under 1.2 mm white resin | XL-1010RGBC (1 × 1 mm) later |
| Trigger | LIS2DW12 double-tap (INT1 → deep-sleep wake) + Omron B3U-3000P side switch | touch pad optional (ESP32-S3 touch) |
| Mic | TDK T3902 PDM (bottom-port, on the board's underside) | Ø0.6 port hole through the board, Ø0.8 lid port with a tube (`hardware/cad/`) |
| Audio out | Murata PKMCS0909 9 × 9 × 1.9 piezo (LTB — buy now) | speech from a ring is not realistic; use the phone |
| Air puff | **Murata MZB1001T02** microblower as a 22 × 22 mm signet aimed at the next finger, 15–20 Vpp @ ~26 kHz driver | the only pump with a perceptible jet; stage-1 experiment only, stock is thin |
| Battery | 301012 30 mAh flat cell, PCM | in a 10.4 × 12.4 × 3.4 mm pocket in the bay floor under the board (`hardware/cad/`); the 5 mm 501012 needs a deeper pocket; band-side placement would give a 7.7 mm signet |
| Charger | TI BQ25100 (25 mA charge, 1 mA termination; /CHG → IO3 + test pad) | MCP73831 OK for ≥ 40 mAh |
| Charging | two inner-band pads + pogo cradle | coil in stage 2 |
| PCB | 2-layer 0.6 mm rigid, **26.5 × 18.0 mm** in the signet bay (`hardware/pcb/board_params.json`), FPC to the camera | rigid-flex in stage 2 |
| Enclosure | `hardware/cad/` — CadQuery model generated from `board_params.json` (shell + lid + key STLs, fit report), SLA tough white/translucent resin | the OpenSCAD concept was removed |

Expected: ~65 shots/week at 40 mAh with aggressive sleep (ESP32-S3) — see `hardware/power-budget.txt`.

## 3.4 Stage 2 — Oura-size (8 mm band, ≤ 3 mm, ~20 mm ID, plus a 4–5 mm camera pod)

| Block | Choice | Why / caveat |
|---|---|---|
| MCU/radio | **nRF52840** WLCSP (3.5 × 3.6) or **ISP1807** SiP (8 × 8 × 1.0, antenna included); nRF5340 (Galaxy Ring) or nRF54L15 as alternatives | ~5 mA radio peaks match a 1C cell; three real projects captured camera frames on nRF52840 |
| Camera | **OmniVision OVM7692** 2.8 × 3.2 × 2.6 mm, 8-bit DVP, DigiKey-stocked | only buyable *digital* camera under 3.5 mm; bit-bang 8-bit DVP at QQVGA grayscale; OVM6211 (3.2 mm GS) if stock appears; **skip OVM6948** (analog AntLinx needs a 6 × 6 mm OV426 bridge) |
| Battery | Grepow curved 16–24 mAh (e.g. GRP170722 14.5 mAh 1.7 × 6.5 × 22) | B2B samples; this is the hardest part to source |
| Charger | BQ25100 / BQ25120A | Oura Gen 2 precedent |
| Charging | flex-printed coil + own cradle (COTS coil floor ~11 mm) or pads | |
| Haptic | Vybronics VG0640001D 6 mm LRA (verify thickness) + DRV2624; or PowerHap 0904H014V060 (1.4 mm) + BOS1901 WLCSP | RingConn Gen 3 proves a motor fits in 2.3 mm |
| Light | XL-1010RGBC 1 × 1 × 0.8 mm | |
| Trigger | LIS2DW12 double-tap only (no button) | optional IQS227 touch |
| Air puff / speaker | **not feasible** at this size | haptic + phone speech only |
| PCB | rigid-flex 0.22/0.48 mm, printed microstrip antenna, WLCSP assembly house | per Memfault's smart-ring guide and Oura/Galaxy teardowns |

Expected: ~2,600 shots/week at 20 mAh standby-dominated; the 10 s haptic reply costs more
than the photo (`hardware/power-budget.txt`).

## 3.5 Output-channel verdicts

| Channel | Stage 1 | Stage 2 | Comment |
|---|---|---|---|
| Haptic (LRA) | ✔ primary | ✔ primary | Morse at char 15 / overall 8 WPM; ≤ 32 chars ≈ 10–20 s |
| Light (RGB) | ✔ | ✔ | confirmation + readable when looking |
| Beeper | ✔ (4 kHz piezo) | signet only | audible near the face |
| Speech from the ring | ✗ | ✗ | 10 mm speaker ≈ 66 dB @ 1 m; use the phone/earbuds |
| Air puff | experiment (Murata signet) | ✗ | no pump fits; electrotactile is the research alternative |
| Bone conduction | ✗ | ✗ | requires touching the ear; haptic does the job |

## 3.6 Trigger verdicts

Double-tap on a LIS2DW12 (hardware interrupt; ~1 µA in a low-power ODR, but the current firmware keeps it at 400 Hz high-performance for tap-wake, ~90 µA — `docs/07-build-guide.md` §2.4) is the primary trigger at every stage;
a side switch is the bring-up and fallback trigger at stages 0/1; capacitive touch only works
as a deliberate thumb press on the top face. Expect to tune tap thresholds against hand
impacts — the firmware exposes the threshold and uses an 800 ms burst filter.
