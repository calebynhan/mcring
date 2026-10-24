# Stage-1 schematic notes (mcring v1)

Written as a netlist-level description so it can be entered into KiCad quickly. Values are
starting points; verify against each datasheet.

## Power

* **Battery**: 1S LiPo 30–40 mAh with PCM. `BAT+` → charger `BAT`, → system via the buck.
* **Charger**: TI BQ25100 (DSBGA-6, no TS pin). `IN` from the two charging pads (5 V from the pogo
  cradle) through a bidirectional TVS (PESD5V0S1BB, D2) and a series Schottky (PMEG2005EB, D3 —
  survives a reversed ring), `ISET` 9.1 kΩ for **25 mA** (≈ 0.85 C for the 30 mAh 301012 cell;
  K_ISET = 230 A·Ω), `PRE_TERM` 11.5 kΩ for 1 mA termination, `/CHG` → **IO3** (`PIN_CHG`, open
  drain, 100 kΩ pull-up R19, also test pad TP7; `battery_charging()` must read it — firmware
  follow-up). 1 µF on IN and OUT. Netlist: `hardware/electrical/`.
* **3.3 V rail**: TPS62840 buck (60 nA IQ, 750 mA) — or TLV75533 LDO if you accept the
  dropout at 3.4 V battery. 10 µF in/out, 2.2 µH inductor (buck).
* **Camera rail**: TPS22916 load switch from 3.3 V (`ON` = `PIN_CAM_PWR` IO21, 100 kΩ pull-down)
  feeding (a) the camera DOVDD 3.3 V pin, (b) a 2.8 V LDO (XC6206P282) for the sensor AVDD and
  (c) a 1.2 V LDO (XC6206P122, DNP if the head regulates DVDD itself). SCCB pull-ups and the
  RESET RC hang off the switched rail. Camera sleep current then drops to the load-switch
  leakage (~10 nA). A second TPS22916 (`LED_PWR_EN` IO33) gates the WS2812 rail the same way.
* **Decoupling**: ESP32-S3-MINI-1U: 10 µF + 0.1 µF at 3V3; bulk **100 µF** low-ESR ceramic
  or 220 µF tantalum near the module to absorb the 300 mA capture/radio peaks on a small cell.

## MCU

* ESP32-S3-MINI-1U-N4R2. `EN` 10 kΩ pull-up + 1 µF to GND. `GPIO0` boot strap with a test
  pad. `GPIO45/46` straps left floating (internal defaults) — do **not** reuse.
* Native USB on `GPIO19/20` to test pads TP3 (D−) / TP4 (D+) with TP5 (GND) — nothing else on
  these pins; 8 test pads in all (IO0, EN, D−, D+, GND, 3V3, nCHG, VBAT), all on the top side.
* u.FL → a flexible PCB dipole or a short printed trace antenna along the band; keep the
  antenna clear of the battery and the LRA.

## Camera

* OV2640 24-pin 0.5 mm FPC (Arducam M0031 pin order) to the DVP pins in `src/config.h`.
  XCLK 20 MHz from GPIO10 (LEDC). SIOD/SIOC 4.7 kΩ pull-ups to 3.3 V.
* Alternative HM01B0 lensed module: 8-bit mode onto the same D0–D7; 1.8 V IO means a level
  consideration — the Himax module variants run 1.8/2.8 V IO; use a 1.8 V-tolerant mapping or
  the 4-bit mode. (esp32-camera has an `hm01b0` driver.)

## I²C bus (400 kHz, 4.7 kΩ pull-ups)

| Device | Addr | Extra |
|---|---|---|
| DRV2605L | 0x5A | `OUT+/OUT-` → LRA; `EN` **tied to 3V3** (`PIN_HAPTIC` = −1; the part ignores I²C while EN is low), idle via the register STANDBY bit (< 4 µA) |
| LIS2DW12 | 0x18 (SA0 = GND) | `INT1` → `PIN_IMU_INT` (RTC-capable GPIO7); 0.1 µF VDD |

## Outputs

* WS2812B-2020 data from `PIN_RGB` through 100 Ω; 0.1 µF at the LED. Window: 1.0–1.5 mm of
  white resin, LED set back ≥ 1 mm from the wall for diffusion.
* Piezo sounder between `PIN_BUZZER` and GND (or bridge-drive from two GPIOs for +6 dB).
* Aux (air-puff experiment): `PIN_AUX` → enable of a boost (e.g. TPS61040 to 15 V) + a
  half-bridge driving the Murata MZB1001T02 at ~26 kHz (LEDC can generate the carrier on a
  second pin; gate the carrier with `PIN_AUX`).
* **Audio out (optional, voice-first)**: MAX98357A I²S class-D mono amp (U10, **16-TQFN** 3 × 3 × 0.75 mm
  for hand assembly; the 9-bump WLP is the alternative) fed from 3.3 V through a **third TPS22916** (U11,
  `ON` = `PIN_SPEAKER_EN` **IO34**, net `AMP_PWR_EN`, 100 kΩ pull-down R20) so the whole group draws
  nothing asleep; 10 µF + 100 nF (C25/C26) on the gated rail `VAMP`. I²S: `BCLK` **IO35**, `LRCLK`
  **IO36**, `DIN` **IO37** (no MCLK; 512 kHz / 16 kHz), each through a **1 kΩ series resistor** (R22/R23/R24)
  at the amp: while `VAMP` is off a high level on an I²S line forward-biases the amp's input ESD diode, and
  the resistor bounds that to ≤ 2.6 mA per pin (a drain, not damage). `SD_MODE` is tied to `VAMP` →
  left-channel mode (> 1.4 V; the firmware writes the mono sample into both slots so the channel does not
  matter) and the amp comes up as the rail does — one GPIO is power gate and enable. `GAIN_SLOT` → R21
  **100 kΩ** → `VAMP` = **3 dB** (0 dBFS → 1.4 Vrms = 0.25 W into 8 Ω: a full-scale tone at unity firmware
  volume stays inside the speaker's 300 mW rating whatever the firmware does; R21 = 0 Ω → 6 dB = 0.5 W, the
  speaker's maximum and the louder bench option, still clean from 3.3 V; DNP = 9 dB clips). `OUTP/OUTN` →
  SPK1 two 1.5 mm wire pads (0.3 mm pair, filterless) → PUI **AS01008MR-2-R** Ø10 × 2.9 mm 8 Ω speaker
  (LS1, off-board) in a pocket in the signet's **right (+y) wall** with the bay as back volume
  (`hardware/pcb/board_params.json` → `speaker_mm`; left wall and band side rejected,
  `hardware/pcb/floorplan.md` §9 item 14). Firmware must still park IO35–37 low while IO34 is low (R22–R24
  make a pin left high a ≤ 2.6 mA drain, not zero). U10, U11, C25, C26, R20–R24 and LS1 are fitted or
  omitted together; `SPK1` stays. TQFN pin table, SD/gain thresholds and the digital-input abs-max rating
  are datasheet-verify items (`hardware/electrical/README.md` §6 items 17–20).

## Inputs

* Side switch Omron B3U-3000P between `PIN_BUTTON` and GND (internal pull-up, firmware
  debounce; add 100 nF if the lead is long).
* Touch: a 3 × 4 mm copper landing (TPAD1) on the top face to `PIN_TOUCH` via 1 kΩ, with a
  hatched ground ring around it and no copper under it; the electrode itself is a 4 × 5 mm copper
  foil on the lid underside, reached through a conductive-foam / spring contact on the landing
  (`hardware/pcb/floorplan.md` §2 — a pad 4 mm behind the touch surface would never trigger).
* Battery sense: **1 MΩ / 1 MΩ** divider (R8/R9) from BAT+ to `PIN_BATTERY_ADC` with 100 nF
  (BATTERY_DIVIDER = 2.0): ~2 µA permanent drain; the 100 nF supplies the 8-sample ADC burst.
  (A 100 k/100 k divider would cost 21 µA, most of the 25 µA standby budget.)

## Mechanical

* Board outline: **26.5 × 18.0 × 0.6 mm**, r 1.5 (`hardware/pcb/board_params.json`, placement in
  `hardware/pcb/floorplan.md`); the enclosure is the CadQuery model in `hardware/cad/`, generated
  from that file (signet bay with ledges, camera pod, cell and LRA pockets in the bay floor, detent
  lid, switch key). Stack above the skin: band wall 1.2 → cell pocket 3.4 → 0.35 clearance → bottom
  parts 1.15 → board 0.6 → top parts 2.9 (mated u.FL) → 0.3 → lid 1.2 = 11.1 mm; pod roof 12.7
  (`hardware/cad/fit_report.md`). The OpenSCAD concept with its 24 mm cavity was removed.
