# 4. Feasibility, physics and risks — the honest version

## What is straightforward

* **Stage 0 end to end.** Camera → BLE → phone → Claude → speech + Morse on a haptic motor is
  a weekend of integration on a $14 board. Every piece exists and is used in this repo.
* **The protocol and the phone/backend software** are form-factor independent; nothing has to
  be redone for stage 2.
* **Haptic Morse** is proven usable (Georgia Tech passive-haptic-learning studies; several
  maker projects) if answers are short and slow: 5–8 effective WPM, ≤ 6 words.

## What is hard

| Risk | Why | Mitigation in this plan |
|---|---|---|
| **Battery vs. peak current** (stage 2) | ring cells are 16–24 mAh @ 1C; ESP32-S3 camera peaks are 300+ mA | nRF52840-class SoC for stage 2; ESP32-S3 confined to stages 0/1 with 30–100 mAh |
| **No tiny digital camera module that a hobbyist can lens** | sub-3.5 mm cameras are wafer-level parts: OVM7692 (DVP, in stock), OVM6211 (no stock), OVM6948 (analog, needs a 6 × 6 mm bridge) | stage 1 uses an off-the-shelf lensed module; stage 2 designs around OVM7692 and accepts a 4–5 mm pod |
| **No BLE SoC has a camera interface** | nRF/Ambiq/Renesas have none; only ESP32-S3 and Realtek do | bit-bang DVP on nRF52840 (proven with OV7670); HM01B0 1-bit via SPIS is R&D |
| **BLE throughput on iOS** | ~300–400 kbps, MTU 185 | keep images ≤ 30 KB (QVGA JPEG / 160×120 gray); selective retransmit; 2M PHY + DLE requested |
| **Air puff from a ring** | no purchasable pump fits in 3 mm; the smallest with a real jet is 20 × 20 mm | stage-1 signet experiment only; electrotactile noted as the research path |
| **Curved battery sourcing** | Grepow sells B2B samples; MOQ/NDA likely | stage 1 uses flat 30–40 mAh hobby cells; start the Grepow conversation early |
| **WLCSP / rigid-flex assembly** | 0.35–0.4 mm pitch, 0.22 mm flex | assembly house; ISP1807 SiP avoids WLCSP for the radio |
| **Double-tap false positives** | a ring sees constant hand impacts | tight latency window, quiet-period gate, long-press button as fallback; log and tune |
| **Morse reply drains more than the photo** | 10 s of LRA at ~40 mA avg ≈ 110 µAh | shorter `short` answers, lower haptic strength, LED-only mode, piezo haptics (PowerHap) |
| **LLM latency/cost** | 2–6 s per answer; vision tokens | QVGA images are cheap (~1–1.5 K tokens); prompt caching on the system prompt; `effort=medium` |
| **Privacy** | a camera on a hand photographs people | capture is explicit (trigger), no streaming, LED blinks on capture, images go only to the user's chosen provider; keep it that way |

## Physics sanity checks

* **Optics:** a 2.8 mm camera cube has a ~1 mm aperture; depth of field is effectively
  infinite from ~15 cm; low light will be noisy. A flower in daylight is fine; a menu in a dim
  restaurant is marginal. Stage-1 OV2640 (1/4") is much better in low light.
* **Framing:** a ring on the index finger points wherever the finger points; a ~70–90° FOV
  forgives aim. Shutter lag after the trigger (camera power-up + AEC ≈ 150–250 ms) is
  short enough that a "point, tap, hold still a beat" gesture works.
* **Thermal:** nothing here dissipates more than ~0.5 W for a second; no issue.
* **RF:** a ring antenna next to a finger is detuned and lossy; expect ~3–8 m range to the
  phone, fine for a pocket. ISP1807 includes a tuned antenna; the ESP32-S3-MINI-1U wants a
  flex dipole along the band.
* **Haptics on a finger:** 0.9–1.3 G from a 6–8 mm LRA pressed against the finger is clearly
  perceptible; LRA rise/fall ≈ 20–40 ms, so keep dots ≥ 80 ms (≤ 15 WPM character speed).

## Where this could still fail

1. The OVM7692 bit-bang on nRF52840 turns out too slow/flaky at 8-bit (then: HM01B0 1-bit via
   SPIS, or an nRF5340 with its faster core, or accept a 4 × 4 mm "camera co-processor").
2. No curved cell can be bought in small quantity (then: stage 1.5 — a slightly thicker ring
   around a 301012 flat cell, ~3.5 mm band).
3. Haptic Morse is too slow for users to bother with (then: lean on speech, keep Morse for
   yes/no/digits and confirmation ticks — the protocol already supports both).
