# mcring v1 — stage-1 electrical design

Netlist-level design of the ring board (ESP32-S3-MINI-1U-N4R2, OV2640 24-pin FPC head, DRV2605L + 8 mm
LRA, LIS2DW12, WS2812B-2020, Omron B3U-3000P, TDK T3902, BQ25100 + TPS62840, 301012 30 mAh cell).
KiCad was not available where this was written, so the schematic is a small Python model that exports
what pcbnew needs plus human-readable sheets.

| File | What |
|---|---|
| `netlist_model.py` | `Part` / `Net` / `Netlist` classes; KiCad netlist export, grouped BOM CSV, Markdown net listing, ERC |
| `mcring_v1.py` | the design itself (every part, pin table, net). `python3 mcring_v1.py` regenerates `out/` |
| `schematic_svg.py` | renders five net-label schematic sheets (SVG + PNG) from the model |
| `out/mcring_v1.net` | KiCad netlist (version "E") for **pcbnew → File → Import Netlist** |
| `out/mcring_v1_bom.csv` | BOM grouped by value + footprint with MPNs |
| `out/mcring_v1_nets.md` | every net with its nodes, every part with its pin → net table |
| `out/erc.md` | ERC result (clean at the time of writing) |
| `out/sch_power.*`, `sch_mcu.*`, `sch_camera.*`, `sch_sensors.*`, `sch_outputs.*` | schematic sheets |

Regenerate everything: `python3 mcring_v1.py && python3 schematic_svg.py` (Python ≥ 3.10, `cairosvg` for the PNGs).

## 1. What changed versus the earlier notes (deviations)

1. **IO19/IO20 are native USB** (D-/D+), so `PIN_CAM_PWR` and `PIN_RGB` could not stay there.
   * `PIN_CAM_PWR` **19 → 21**: IO21 is an RTC GPIO with no boot-time function, so it can be held in deep
     sleep and never toggles during the ROM/2nd-stage bootloader. A 100 kΩ pull-down (R17) keeps the camera
     rail off while the pin floats (reset, download mode, deep sleep).
   * `PIN_RGB` **20 → 43** (TXD0): UART0 TX is free because logging is USB-CDC. The ROM prints boot messages
     on TXD0 at every reset; that garbage reaches a WS2812 whose supply is gated off, so nothing is visible.
     (The task suggested IO21 = RGB / IO43 = CAM_PWR; the swap avoids pulsing the camera rail on at every
     boot through TXD0.)
   * Both edits were applied to `firmware/ring-esp32s3/src/config.h` (BOARD_MCRING_V1 only) and
     `hardware/pinmap.md`.
2. **WS2812 supply is gated** (U9, a second TPS22916, ON = IO44/RXD0 with a 4.7 kΩ pull-down, net
   `LED_PWR_EN`). An un-gated WS2812B idles at ~0.6–1 mA, i.e. 15–25 mAh/day on a 30 mAh cell versus the
   0.6 mAh/day standby in `hardware/power-budget.txt`. The LED is fed from **VBAT** (3.0–4.2 V) through the
   switch rather than 3V3, which keeps the LED inside its 3.7–5.3 V spec for most of the discharge and keeps
   its 60 mA pulses off the buck. Firmware TODO: `PIN_RGB_PWR 44`, drive high before `neopixelWrite()`.
3. **OV2640 DVDD 1.2 V LDO added** (U4, XC6206P122MR). The schematic notes only listed a 2.8 V LDO; the
   24-pin head has a DVDD pin (pin 10 in the ESP32-CAM order) and the ESP32-CAM reference feeds it 1.2 V.
   Mark U4 DNP if the purchased head regulates DVDD itself (verify on the module).
4. **Charger /CHG goes to a test pad only** (`TP7`, 100 kΩ pull-up). Every exposed, non-strap, non-PSRAM
   GPIO of the MINI-1U is now used (31 of 31), so `battery_charging()` stays `false`.
5. **BQ25100 has no TS pin.** The DSBGA-6 BQ25100 exposes IN, OUT, /CHG, ISET, PRE_TERM, VSS; TS is on the
   BQ25101 (fixed 10 % termination). No thermistor input is wired.
6. **Charge current 25 mA** (R_ISET 9.1 kΩ with K_ISET = 230 A·Ω) for the 30 mAh 301012 cell (≈0.85 C), not
   the 35 mA / 40 mAh in the old notes. Termination 1 mA via R_PRETERM 11.5 kΩ (K_PRETERM = 11.5 A·Ω).
7. **Aux channel** is a low-side AO3400 (Q1, gate from IO9 with 100 kΩ pull-down) to a 2-pad connector
   (`J2`: VBAT + open drain). For the air-puff boost experiment, use the drain as an active-low enable or a
   load return — the notes' "PIN_AUX → boost EN" wiring is a solder-wire variant of the same pads.
8. **SCCB pull-ups and the camera RESET RC hang off the switched rail** (CAM_3V3), not 3V3, so the unpowered
   sensor is never back-fed through its ESD diodes. PWDN is tied to GND (power gating replaces it).
9. Piezo is driven through 100 Ω from IO4 (limits the GPIO current spike into the ~15 nF element).

## 2. GPIO map (BOARD_MCRING_V1, after the fix)

| GPIO | Net | Function | GPIO | Net | Function |
|---|---|---|---|---|---|
| 0 | IO0 | boot strap: 10 kΩ pull-up, TP1, SW2 (DNP) | 19 | USB_DM | native USB D- → TP3 |
| 1 | BAT_SENSE | 100k/100k from VBAT, 100 nF (ADC1_CH0) | 20 | USB_DP | native USB D+ → TP4 |
| 2 | BUTTON | B3U-3000P to GND, 100 nF, internal pull-up, EXT0 wake | 21 | CAM_PWR_EN | U2 TPS22916 ON (100k pull-down) |
| 3 | HAPTIC_EN | DRV2605L EN | 38 | CAM_VSYNC | FPC pin 7 |
| 4 | BUZZER | 100 Ω → piezo | 39 | CAM_SIOC | FPC pin 5, 4.7k to CAM_3V3 |
| 5 | SDA | I²C, 4.7k | 40 | CAM_SIOD | FPC pin 3, 4.7k to CAM_3V3 |
| 6 | SCL | I²C, 4.7k | 41 | PDM_DATA | T3902 DATA |
| 7 | IMU_INT1 | LIS2DW12 INT1, EXT1 wake | 42 | PDM_CLK | T3902 CLK |
| 8 | TOUCH | 1 kΩ → 3×4 mm pad (T8) | 43 (TXD0) | RGB_DATA | 100 Ω → WS2812 DIN |
| 9 | AUX_EN | AO3400 gate, 100k pull-down | 44 (RXD0) | LED_PWR_EN | U9 TPS22916 ON (4.7k pull-down) — firmware TODO |
| 10 | CAM_XCLK | 20 MHz LEDC → FPC 13 | 47 | CAM_HREF | FPC pin 9 |
| 11..18 | CAM_Y8,Y7,PCLK,Y6,Y2,Y5,Y3,Y4 | 8-bit DVP (`Y2..Y9` = D0..D7 as in config.h) | 48 | CAM_Y9 | FPC pin 12 |

NC: IO26, IO33–IO37 (in-package flash/PSRAM on N4R2). IO45/IO46 strapping pins left floating (internal defaults).

## 3. Power tree

```
pogo pads PAD1/PAD2 (5 V) ─ PESD5V0 ─ BQ25100 (25 mA, 1 mA term) ─ VBAT ─┬─ J1 301012 30 mAh (PCM)
                                                                       ├─ TPS62840 (2.2 µH, 10 µF/10 µF, VSET=3.3 V) ─ 3V3 ─┬─ 100 µF + 10 µF + 100 nF at U1
                                                                       │                                                   ├─ DRV2605L, LIS2DW12, T3902, pull-ups
                                                                       │                                                   └─ U2 TPS22916 (IO21) ─ CAM_3V3 ─┬─ DOVDD
                                                                       │                                                                                   ├─ XC6206P282 ─ CAM_2V8 (AVDD)
                                                                       │                                                                                   └─ XC6206P122 ─ CAM_1V2 (DVDD)
                                                                       ├─ U9 TPS22916 (IO44) ─ VLED ─ WS2812B-2020
                                                                       ├─ 100k/100k divider ─ IO1
                                                                       └─ J2 aux pad (+ AO3400 low side from IO9)
```

## 4. Importing `out/mcring_v1.net` into KiCad

The KiCad *schematic* editor cannot import netlists; the file targets the **PCB editor**. Use the SVG sheets
and `out/mcring_v1_nets.md` as the schematic reference while laying out.

1. Create a KiCad project (`mcring_v1`), open the PCB editor.
2. Add a footprint library named **`mcring`** and draw the custom footprints the netlist references
   (names in the BOM): `TPS22916_DSBGA-4_YFP`, `BQ25100_DSBGA-6_YFP`, `SW_Omron_B3U-3000P`,
   `SW_Omron_B3U-1000P`, `MIC_TDK_T3902_3.5x2.65mm`, `LRA_8mm_2pad`, `Murata_PKMCS0909_9x9mm`,
   `PAD_Charge_3.0x2.0mm`, `PAD_Touch_3x4mm`, `PAD_Aux_1x2`. The remaining footprints use KiCad 7/8 library
   names (`RF_Module:ESP32-S3-MINI-1U`, `Package_TO_SOT_SMD:SOT-583-8`,
   `LED_SMD:LED_WS2812B-2020_PLCC4_2.0x2.0mm`, `Connector_FFC-FPC:Hirose_FH12-24S-0.5SH_…`,
   `Connector_JST:JST_SH_BM02B-SRSS-TB_…`, `Package_LGA:LGA-12_2x2mm_P0.5mm`, `Package_SO:VSSOP-10_3x3mm_P0.5mm`,
   passives 0402/0603/1206). If a name is missing in your KiCad version, change it in `mcring_v1.py` and
   regenerate — pad numbers must match the pin numbers in the model.
3. **File → Import Netlist…**, pick `out/mcring_v1.net`, *Match by reference*, tick *Replace footprints with
   those specified in netlist*, *Update footprint fields*, then *Load and Test Netlist* → *Update PCB*.
4. Board setup: outline from `hardware/pcb/board_params.json` (written by the floorplan step); design rules
   below; net classes: `GND/3V3/VBAT/CAM_3V3/VLED/CHG_IN/SW_NODE` 0.3 mm, everything else 0.1–0.15 mm.
5. Re-import after any change to `mcring_v1.py` — pcbnew keeps placement and only updates connectivity.

## 5. Design rules — 2-layer, 0.6 mm FR-4, 1 oz

| Rule | Value | Why |
|---|---|---|
| Track / clearance (fine) | **0.10 / 0.10 mm** | fan-out of the 0.4 mm-pitch DSBGA (TPS22916 ×2) and 0.5 mm-pitch LGA/VSSOP/FPC |
| Track / clearance (general) | 0.15 / 0.15 mm | everything else; 0.3 mm for power nets, 0.4 mm+ for VBAT/3V3 trunks |
| Via | **0.2 mm drill / 0.45 mm pad** (0.125 mm annular) | fits between 0.5 mm pads; 0.6 mm board → aspect ratio 3:1 |
| DSBGA pads | NSMD, 0.22–0.25 mm Ø, no via-in-pad | all balls of the 2×2 and 2×3 arrays are on the perimeter → no routing between balls |
| Solder-mask expansion | 0.05 mm (0.03 mm on DSBGA) | fine-pitch parts |
| Silkscreen | none on the component side under the module | the module needs flat, bare FR-4 under the shield |
| Finish | **ENIG** | charging pads, DSBGA/LGA co-planarity |
| Copper | 1 oz (35 µm) | thermal spreading for the 100 mW class LDO dissipation |
| Module | ESP32-S3-MINI-1U per Espressif layout guide: GND thermal pads tied to the ground plane with ≥ 9 vias; **no copper, traces or vias under the u.FL/antenna end**; antenna end points away from the camera | |
| Buck | TPS62840: CIN, L, COUT in a tight loop on the top layer; VOS sense trace from COUT; SW node minimal area | |
| Camera FPC | DVP bus length-matched loosely (±5 mm is fine at 20 MHz); XCLK/PCLK away from the antenna feed | |
| Touch pad | copper 3×4 mm on top, ground hatch around, **no copper under it** | |
| Charging pads | 3×2 mm ENIG on the inner band, PESD5V0 within 2 mm of the pad | |
| Keep-outs | LRA and battery away from the antenna end; piezo 9×9 only if the bay allows (else 2 pads for a smaller element) | |

Check your fab's 2-layer capability before ordering: 0.1/0.1 mm track/space and 0.2 mm drills are "advanced"
options at JLCPCB/PCBWay (standard is 0.127 mm / 0.3 mm drill). If only standard rules are available, the
0.4 mm-pitch TPS22916 can be replaced by a SOT-23-5 load switch (e.g. TPS22917DBV) with the same nets.

## 6. Assumptions to verify against the datasheets (none could be fetched from the sandbox)

| # | Item | Where it bites |
|---|---|---|
| 1 | **ESP32-S3-MINI-1U pin table** used: 1–2 GND, 3 3V3, 4–25 IO0–IO21, 26 IO26, 27–36 IO33–IO42, 37 TXD0/IO43, 38 RXD0/IO44, 39 IO45, 40 IO46, 41 IO47, 42 IO48, 43–44 GND, 45 EN, 46–65 GND | every U1 node in the netlist; check `esp32-s3-mini-1_mini-1u_datasheet_en.pdf` Table "Pin Definitions" and that IO26/IO33–37 are indeed PSRAM-bound on N4R2 |
| 2 | **FPC pin order** (ESP32-CAM / Arducam M0031): 1 NC, 2 AGND, 3 SIOD, 4 AVDD, 5 SIOC, 6 RESET, 7 VSYNC, 8 PWDN, 9 HREF, 10 DVDD, 11 DOVDD, 12 Y9, 13 XCLK, 14 Y8, 15 DGND, 16 Y7, 17 PCLK, 18 Y6, 19 Y2, 20 Y5, 21 Y3, 22 Y4, 23 Y1, 24 Y0 | a one-position-shifted variant exists (pin 1 AGND … pin 24 NC); buzz the purchased head before ordering boards. Also confirm whether the head needs external 1.2 V (U4) |
| 3 | **BQ25100** DSBGA ball map (A1 IN, A2 OUT, B1 /CHG, B2 PRE_TERM, C1 ISET, C2 VSS), K_ISET = 230 A·Ω, K_PRETERM = 11.5 A·Ω, no TS pin | R10 = 9.1 kΩ → 25 mA, R11 = 11.5 kΩ → 1 mA |
| 4 | **TPS62840DLCR** pin numbers (SOT-583: 1 SW, 2 GND, 3 VIN, 4 EN, 5 STOP, 6 MODE, 7 VSET, 8 VOS) and the **VSET resistor for the 3.3 V code** (R12 is a placeholder value `VSET-3V3`) | Vout wrong or part dead if mis-wired |
| 5 | **TPS22916C** ball map (A1 VIN, A2 VOUT, B1 ON, B2 GND) and that the "C" suffix (slower rise) is the wanted variant | U2, U9 |
| 6 | **DRV2605L** VSSOP-10 pin numbers (1 REG, 2 SCL, 3 SDA, 4 IN/TRIG, 5 EN, 6 VDD, 7 GND, 8 OUT-, 9 OUT+, 10 NC) | U5 |
| 7 | **LIS2DW12** LGA-12 pin numbers (1 SCL, 2 CS, 3 SA0, 4 SDA, 5 RES, 6–8 GND, 9 VDD, 10 VDD_IO, 11 INT2, 12 INT1) | U6 (pins 5–8 all go to GND, so only 1–4 and 9–12 matter) |
| 8 | **T3902** pad numbering (1 VDD, 2 GND, 3 CLK, 4 DATA, 5 SELECT, 6 GND) and port hole size | MK1 |
| 9 | **WS2812B-2020** pad order (1 VDD, 2 DOUT, 3 GND, 4 DIN) and operation at VLED = VBAT (3.0–4.2 V) with 3.3 V data (VIH = 0.7·VDD = 2.94 V at 4.2 V); fall back to WS2812C-2020-V1 / move U9 VIN to 3V3 if marginal | D1 |
| 10 | **PESD5V0S1UB** SOD-523 pin order (1 K, 2 A) | D2 |
| 11 | **XC6206P122MR** availability (1.2 V member of the XC6206 family); else TLV70212 / NCP161 1.2 V in SOT-23 | U4 |
| 12 | LRA0825BC-0167F rated voltage versus DRV2605L on 3.3 V (limit RTP amplitude in firmware; measure) | M1 |
| 13 | KiCad footprint names listed in §4 exist in the installed library version | import step |

## 7. Firmware follow-ups implied by this design

* add `PIN_RGB_PWR 44` and drive it high before LED writes / low before deep sleep (or power the LED from
  CAM_3V3 and drop U9 if a GPIO is ever needed back);
* `gpio_hold_en(21)` + `gpio_deep_sleep_hold_en()` is optional — R17 already defaults the camera off;
* nothing else changes: `neopixelWrite()` works on IO43 through the RMT matrix, `digitalWrite(PIN_CAM_PWR)` on IO21.
