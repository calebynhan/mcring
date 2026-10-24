# Bills of materials

Three BOMs, one per stage. Prices are snapshots from the research reports in `docs/research/`
(October 2026); re-check before ordering. All links are to the sources the research found.

| File | Stage | What it builds | Rough total |
|---|---|---|---|
| `stage0-devkit.csv` | 0 | bench rig: XIAO ESP32S3 Sense + haptic cue + IMU + button, optional MAX98357A breakout + 10 mm speaker | $40–65 |
| `stage1-ring.csv` | 1 | oversized printed signet ring (band 22.4 mm OD × 12 mm, signet 31.5 × 21 mm; `hardware/cad/`), ESP32-S3-MINI-1U on a 26.5 × 18 mm board, OV2640/HM01B0, 30 mAh flat cell | $45–80 + PCB |
| `stage2-oura-size.csv` | 2 | Oura-size: nRF52840 WLCSP/ISP1807 + OVM7692 + Grepow curved cell on rigid-flex | $200–500 per prototype |

**Buy now for stage 0** (one order from AliExpress/Seeed, one from Adafruit or DigiKey):

1. Seeed XIAO ESP32S3 Sense — the whole software loop runs on it unmodified.
2. DRV2605L breakout + an 8 mm 235 Hz coin LRA (haptic cues).
   Optional: Adafruit MAX98357A I²S amp breakout + an 8 Ω 10 mm speaker for the on-ring speaker mode.
3. LIS2DW12 breakout (a LIS3DH breakout will do for tap experiments; change the driver).
4. A tactile button, a 12 mm piezo, a 100 mAh LiPo, two 100 kΩ resistors and a 100 nF capacitor for the battery divider (10 k would cost 210 µA in sleep).

Optional stage-0 extras that de-risk stage 2: Seeed XIAO nRF52840 Sense ($16) + Arducam HM01B0
for Pico ($16) to start the low-power camera-capture work on an nRF.
