# Bills of materials

Three BOMs, one per stage. Prices are snapshots from the research reports in `docs/research/`
(October 2026); re-check before ordering. All links are to the sources the research found.

| File | Stage | What it builds | Rough total |
|---|---|---|---|
| `stage0-devkit.csv` | 0 | bench rig: XIAO ESP32S3 Sense + haptic cue + IMU + button, optional MAX98357A breakout + 10 mm speaker | $40–65 |
| `stage0-devkit-solderless.csv` | 0 | **the same rig with zero solder joints**: pre-soldered XIAO Sense in Seeed's Expansion Board Base (button, buzzer, JST LiPo + charger on the base) + Grove Haptic Motor (DRV2605L + ERM) + LIS3DH STEMMA QT via a Grove→QT cable; optional speaker path | $56–72 (+ $8–12 speaker) |
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

**No soldering?** Buy `stage0-devkit-solderless.csv` instead of the list above. The XIAO comes with its
headers factory-soldered (Seeed 102010635) and seats in the Expansion Board Base (103030356), whose user
button is already on D1 (`PIN_BUTTON`), whose passive buzzer is already on A3 = D3 (`PIN_BUZZER`) and whose
JST 2.0 socket takes the LiPo; the haptic driver comes as a Grove module with its motor attached (Seeed
Grove Haptic Motor, an ERM instead of the LRA — the LRA feel returns on the stage-1 board); the
accelerometer is a LIS3DH STEMMA QT board fed from the base's second Grove I²C socket through a Grove→QT
cable, and the firmware detects LIS2DW12 or LIS3DH at boot. The only wire is the LIS3DH's interrupt jumper
into the base's breakout header — and even that is optional, the `xiao_esp32s3_sense_base` build polls.
What stays non-plug-in: the MAX98357A speaker amp's header holes (its speaker terminal block *is*
pre-soldered) — press-fit pins, five joints at a makerspace, or wait for stage 1. Wiring:
`hardware/pcb/wiring_stage0_solderless.md`; steps: `docs/07-build-guide.md` §1.12; the sourcing
evidence and what could not be verified: `docs/research/04-no-solder-sourcing.md`. For stage 1 the
answer is "order it assembled": the research report's §B–C costs a JLCPCB Standard-PCBA run and the
connectors that would let the cell, LRA and speaker plug in (that floorplan change is not made yet).
