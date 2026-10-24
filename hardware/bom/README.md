# Bills of materials

Three BOMs, one per stage. Prices are snapshots from the research reports in `docs/research/`
(October 2026); re-check before ordering. All links are to the sources the research found.

| File | Stage | What it builds | Rough total |
|---|---|---|---|
| `stage0-devkit.csv` | 0 | bench rig: XIAO ESP32S3 Sense + haptic + IMU + button | $40–55 |
| `stage1-ring.csv` | 1 | oversized (30 mm OD) printed ring, ESP32-S3-MINI-1U or NanoS3, OV2640/HM01B0, 30–40 mAh flat cell | $45–80 + PCB |
| `stage2-oura-size.csv` | 2 | Oura-size: nRF52840 WLCSP/ISP1807 + OVM7692 + Grepow curved cell on rigid-flex | $200–500 per prototype |

**Buy now for stage 0** (one order from AliExpress/Seeed, one from Adafruit or DigiKey):

1. Seeed XIAO ESP32S3 Sense — the whole software loop runs on it unmodified.
2. DRV2605L breakout + an 8 mm 235 Hz coin LRA.
3. LIS2DW12 breakout (a LIS3DH breakout will do for tap experiments; change the driver).
4. A tactile button, a 12 mm piezo, a 100 mAh LiPo, two 10 kΩ resistors.

Optional stage-0 extras that de-risk stage 2: Seeed XIAO nRF52840 Sense ($16) + Arducam HM01B0
for Pico ($16) to start the low-power camera-capture work on an nRF.
