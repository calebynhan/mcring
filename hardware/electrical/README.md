# mcring v1 — stage-1 electrical design

Netlist-level design of the ring board (ESP32-S3-MINI-1U-N4R2, OV2640 24-pin FPC head, DRV2605L + 8 mm
LRA, LIS2DW12, WS2812B-2020, Omron B3U-3000P, TDK T3902, BQ25100 + TPS62840, 301012 30 mAh cell, u.FL
flex antenna). KiCad was not available where this was written, so the schematic is a small Python model
that exports what pcbnew needs plus human-readable sheets.

| File | What |
|---|---|
| `netlist_model.py` | `Part` / `Net` / `Netlist` classes; KiCad netlist export, grouped BOM CSV, Markdown net listing, ERC. `python3 netlist_model.py` runs its self-test |
| `mcring_v1.py` | the design itself (every part, pin table, net). `python3 mcring_v1.py` regenerates `out/` and checks the GPIO map against `config.h` |
| `schematic_svg.py` | renders five net-label schematic sheets (SVG + PNG) from the model |
| `out/mcring_v1.net` | KiCad netlist (version "E") for **pcbnew → File → Import Netlist** — on-board parts only |
| `out/mcring_v1_bom.csv` | BOM grouped by value + footprint with MPNs; `Mount` = `PCB` or `off-board` (cell, antenna, piezo element, band contacts) |
| `out/mcring_v1_nets.md` | every net with its nodes (off-board nodes marked `*`), every part with its pin → net table |
| `out/erc.md` | ERC result (clean; one waived single-node net, the antenna's RF lead) |
| `out/sch_power.*`, `sch_mcu.*`, `sch_camera.*`, `sch_sensors.*`, `sch_outputs.*` | schematic sheets |

Regenerate everything: `python3 mcring_v1.py && python3 schematic_svg.py` (Python ≥ 3.10, `cairosvg` for the PNGs).

## 1. What changed versus the earlier notes (deviations)

Items 10–17 are the fixes from the design review; the GPIO map in §2 and `config.h` `BOARD_MCRING_V1`
carry all of them.

1. **IO19/IO20 are native USB** (D-/D+), so `PIN_CAM_PWR` and `PIN_RGB` could not stay there.
   * `PIN_CAM_PWR` **19 → 21**: IO21 is an RTC GPIO with no boot-time function, so it can be held in deep
     sleep and never toggles during the ROM/2nd-stage bootloader. A 100 kΩ pull-down (R17) keeps the camera
     rail off while the pin floats (reset, download mode, deep sleep).
   * `PIN_RGB` **20 → 43** (TXD0): UART0 TX is free because logging is USB-CDC. The ROM prints boot messages
     on TXD0 at every reset; that reaches a WS2812 whose supply is gated off, through 1 kΩ (item 10).
   * Both edits were applied to `firmware/ring-esp32s3/src/config.h` (BOARD_MCRING_V1 only) and
     `hardware/pinmap.md`.
2. **WS2812 supply is gated** (U9, a second TPS22916, net `LED_PWR_EN`, ON = **IO33** with a 4.7 kΩ
   pull-down, `PIN_RGB_PWR 33`). An un-gated WS2812B idles at ~0.6–1 mA, i.e. 15–25 mAh/day on a 30 mAh
   cell versus the 0.6 mAh/day standby in `hardware/power-budget.txt`. **The LED stays dark until the
   firmware drives `PIN_RGB_PWR` high before `neopixelWrite()`** (§7) — the define exists, the code does
   not yet. Rail and GPIO changed in the review, see items 10 and 11.
3. **OV2640 DVDD 1.2 V LDO added** (U4, XC6206P122MR). The schematic notes only listed a 2.8 V LDO; the
   24-pin head has a DVDD pin (pin 10 in the ESP32-CAM order) and the ESP32-CAM reference feeds it 1.2 V.
   Mark U4 DNP if the purchased head regulates DVDD itself (verify on the module).
4. **Charger /CHG goes to IO3** (`PIN_CHG`, active low, 100 kΩ pull-up R19, also on `TP7`). IO3 became
   free when the DRV2605L EN pin was tied high (item 12). `battery_charging()` still returns `false`
   until it reads the pin (§7). IO3 is the JTAG_SEL strap, inert unless the eFuse is burned; it is an
   input here, so even a low level at boot (charging) is harmless.
5. **BQ25100 has no TS pin.** The DSBGA-6 BQ25100 exposes IN, OUT, /CHG, ISET, PRE_TERM, VSS; TS is on the
   BQ25101 (fixed 10 % termination). No thermistor input is wired.
6. **Charge current 25 mA** (R_ISET 9.1 kΩ with K_ISET = 230 A·Ω) for the 30 mAh 301012 cell (≈0.85 C), not
   the 35 mA / 40 mAh in the old notes. Termination 1 mA via R_PRETERM 11.5 kΩ (K_PRETERM = 11.5 A·Ω).
7. **Aux channel** is a low-side AO3400 (Q1, gate from IO9 with 100 kΩ pull-down) to a 2-pad connector
   (`J2`: VBAT + open drain). For the air-puff boost experiment, use the drain as an active-low enable or a
   load return — the notes' "PIN_AUX → boost EN" wiring is a solder-wire variant of the same pads.
8. **SCCB pull-ups and the camera RESET RC hang off the switched rail** (CAM_3V3), not 3V3, so the unpowered
   sensor is never back-fed through its ESD diodes. PWDN is tied to GND (power gating replaces it).
9. **Piezo** is driven through 100 Ω from IO4 into two 1.2 mm wire pads (`BZ1`, floorplan BZ1a/BZ1b). The
   9 × 9 × 1.9 mm Murata element is `PZ1`, off-board and **DNP/optional**: the enclosure has no pocket for
   it yet. Any 2-wire piezo element can go on the same pads.
10. **WS2812 rail is 3V3, not VBAT; data resistor 1 kΩ.** With VLED = VBAT the LED's VIH = 0.7·VDD reaches
    2.94 V at 4.2 V — above the ESP32-S3's VOH(min) of 0.8·3.3 = 2.64 V — and a LiPo spends most of its
    charge at 3.6–3.9 V, below the LED's 3.7 V minimum anyway. From 3V3 the data interface is in spec
    (VIH 2.31 V) at the cost of running the LED below its 3.7 V minimum at all times, a common and
    bench-verifiable operating point (less blue/green headroom at full brightness); if it is marginal, a
    3.3 V-rated 2020 RGB per `hardware/bom/stage1-ring.csv` fits the same pads. R7 = 1 kΩ limits the ROM
    boot chatter back-fed through DIN into the unpowered rail to ~2.7 mA (100 Ω gave 27 mA pulses).
11. **`LED_PWR_EN` moved from IO44 (RXD0) to IO33.** The ROM enables the U0RXD pull-up at reset, which
    put 0.3–0.45 V on the TPS22916 ON pin against the 4.7 kΩ pull-down — at the edge of VIL, so the LED
    rail could glitch on at every reset/download. IO33 has no boot-time role. IO33–IO37 are plain GPIOs on
    the N4R2: the in-package **quad** PSRAM uses only SPICS1 = IO26; SPIIO4–7/SPIDQS on IO33–37 are taken
    by the **octal** PSRAM of R8 parts only (ESP-IDF GPIO guide for the ESP32-S3; module datasheet footnote
    to re-check, §6). This frees five GPIOs: IO34–IO37 and IO44 are spare (firmware `-1`).
12. **DRV2605L EN is tied to 3V3** (as on the stage-0 Adafruit breakout). Per the datasheet ("Operation
    with EN control") the device only acknowledges on I²C while EN is low — no register reads or writes —
    and the firmware drives `PIN_HAPTIC` low in `feedback_init()` *before* `drv2605_init()` reads
    REG_STATUS, so an EN-on-GPIO board reports `DRV2605L not found` and never vibrates. Idle power is the
    register STANDBY bit (`drv2605_standby()`, also the power-up default): < 4 µA, registers retained.
    `PIN_HAPTIC` is `-1` on this board; the haptic channel is I²C-only.
13. **Battery divider 1 MΩ / 1 MΩ** (R8/R9) + 100 nF instead of 100k/100k: 2.1 µA permanent drain instead
    of 21 µA, which was ~80 % of the 25 µA stage-1 standby budget in `hardware/power-budget.txt`.
    `BATTERY_DIVIDER` stays 2.0. The 100 nF holds the node for the 8-sample ADC burst, so the 500 kΩ
    source impedance is irrelevant; ADC pin leakage (tens of nA) costs ≤ 25 mV — note it, see §6.
14. **R12 = 267 kΩ (E96, 1 %)**: the TPS62840 3.3 V code (VSET → GND; SLVSE12 Table 1, also TI's 3.3 V
    efficiency-plot condition). Replaces the `VSET-3V3` placeholder; the BOM is orderable.
15. **Wire pads instead of connectors/footprints that do not fit**, matching the floorplan
    (`hardware/pcb/board_params.json` → `wire_pads_bottom_mm`): `J1` = two 1.5 mm pads (the 4.25 mm JST SH
    header fits neither side of the board), `BZ1` = two 1.2 mm pads, `PAD1`/`PAD2` = one 1.5 mm pad each
    (floorplan PAD1w/PAD2w). The things wired to them are **off-board BOM lines**: `BT1` cell, `PZ1`
    piezo element, `CP1`/`CP2` inner-band ENIG contacts, `ANT1` antenna. Off-board parts stay in the BOM,
    the net listing and the ERC but are left out of `out/mcring_v1.net`, so pcbnew never asks for their
    footprints. `M1` (LRA leads to two pads) and `J2` were already pads.
16. **Charging input protection.** `D3` (PMEG2005EB Schottky, ~0.25 V at 25 mA) in series from the pad net
    `CHG_PAD` to `CHG_IN`, and `D2` is now the **bidirectional** PESD5V0S1BB. A ring seated the wrong way
    round in a 2-pin pogo cradle puts −5 V on the pad; with the old unidirectional TVS that forward-biased
    D2 (cradle current through a SOD-523) and held the BQ25100 IN at −0.7 V (abs. min −0.3 V). Now nothing
    conducts. The cradle should still be keyed (`docs/07-build-guide.md` §2.8).
17. **Antenna** `ANT1`: Molex 146153-0050, 2.4 GHz flex dipole 34.9 × 9 × 0.1 mm with a 50 mm MHF1
    (u.FL) pigtail (alt. Taoglas FXP70.07.0053A, 53 mm cable, outline to verify). It mates with the u.FL
    receptacle on the module — not a module pad, hence the waived single-node net `ANT_RF`. The mated
    plug (2.9 mm) is already `top_max_height_mm` in `board_params.json`. Placement rule in §5. The 34.9 mm
    length means it wraps along the band from the back wall; confirm the fit in the CAD.
18. **FPC1 is one part**: F32R-1A7H1-11024 (XKB, LCSC), 24-pin 0.5 mm **bottom-contact** back-flip,
    2.0 mm tall, as `hardware/bom/stage1-ring.csv` and `board_params.json` assume. The Hirose
    FH12-24S-0.5SH(55) is an "Alt MPN" field (confirm its contact side before substituting); the KiCad
    FH12 land pattern is the standard 24 + 2 mounting-pad pattern the F32R copies — check it against the
    F32R drawing.
19. `M1` LRA described correctly: INEED LRA0825BC-0167F, **240 Hz, 1.25 Vrms max** (the autocal
    registers in `docs/07-build-guide.md` §1.8 depend on it; the old "~170 Hz" was wrong).

## 2. GPIO map (BOARD_MCRING_V1)

| GPIO | Net | Function | GPIO | Net | Function |
|---|---|---|---|---|---|
| 0 | IO0 | boot strap: 10 kΩ pull-up, TP1, SW2 (DNP) | 19 | USB_DM | native USB D- → TP3 |
| 1 | BAT_SENSE | 1 M/1 M from VBAT, 100 nF (ADC1_CH0) | 20 | USB_DP | native USB D+ → TP4 |
| 2 | BUTTON | B3U-3000P to GND, 100 nF, internal pull-up, EXT0 wake | 21 | CAM_PWR_EN | U2 TPS22916 ON (100k pull-down) |
| 3 | nCHG | BQ25100 /CHG, open drain, 100k pull-up, TP7 (`PIN_CHG`, input) | 33 | LED_PWR_EN | U9 TPS22916 ON (4.7k pull-down) — `PIN_RGB_PWR`, firmware must drive it |
| 4 | BUZZER | 100 Ω → BZ1 piezo pads | 38 | CAM_VSYNC | FPC pin 7 |
| 5 | SDA | I²C, 4.7k | 39 | CAM_SIOC | FPC pin 5, 4.7k to CAM_3V3 |
| 6 | SCL | I²C, 4.7k | 40 | CAM_SIOD | FPC pin 3, 4.7k to CAM_3V3 |
| 7 | IMU_INT1 | LIS2DW12 INT1, EXT1 wake | 41 | PDM_DATA | T3902 DATA |
| 8 | TOUCH | 1 kΩ → 3×4 mm pad (T8) | 42 | PDM_CLK | T3902 CLK |
| 9 | AUX_EN | AO3400 gate, 100k pull-down | 43 (TXD0) | RGB_DATA | 1 kΩ → WS2812 DIN |
| 10 | CAM_XCLK | 20 MHz LEDC → FPC 13 | 47 | CAM_HREF | FPC pin 9 |
| 11..18 | CAM_Y8,Y7,PCLK,Y6,Y2,Y5,Y3,Y4 | 8-bit DVP (`Y2..Y9` = D0..D7 as in config.h) | 48 | CAM_Y9 | FPC pin 12 |

Spare (unconnected, firmware `-1`): **IO34, IO35, IO36, IO37, IO44 (RXD0)** — candidates for the optional
I²S speaker placeholders in `config_audio.h`; IO44 carries the ROM's reset pull-up, so prefer 34–37 for
anything that must idle low. NC: IO26 (SPICS1 of the in-package PSRAM). IO45/IO46 strapping pins left
floating (internal defaults). `PIN_HAPTIC` is `-1` (DRV2605L EN tied high). 31 of 36 exposed non-strap
GPIOs used. `python3 mcring_v1.py` fails if the model's GPIO nets drift from this table.

## 3. Power tree

```
CP1/CP2 band contacts (5 V pogo) ═wires═ PAD1/PAD2 ─ CHG_PAD ─ D2 PESD5V0S1BB (bidir.) ─ D3 Schottky ─ CHG_IN ─ BQ25100 (25 mA, 1 mA term, /CHG → IO3)
                                                                                                                   │
BT1 301012 30 mAh (PCM) ═wires═ J1 pads ─────────────────────────────────────────────────────────────── VBAT ─┬─ TPS62840 (2.2 µH, 10 µF/10 µF, R12 267k = 3.3 V) ─ 3V3 ─┬─ 100 µF + 10 µF + 100 nF at U1
                                                                                                              │                                                      ├─ DRV2605L (EN tied high), LIS2DW12, T3902, pull-ups
                                                                                                              │                                                      ├─ U2 TPS22916 (IO21) ─ CAM_3V3 ─┬─ DOVDD
                                                                                                              │                                                      │                                ├─ XC6206P282 ─ CAM_2V8 (AVDD)
                                                                                                              │                                                      │                                └─ XC6206P122 ─ CAM_1V2 (DVDD)
                                                                                                              │                                                      └─ U9 TPS22916 (IO33) ─ VLED ─ WS2812B-2020
                                                                                                              ├─ 1 M/1 M divider ─ IO1 (2.1 µA)
                                                                                                              └─ J2 aux pad (+ AO3400 low side from IO9)
```

Permanent drains on VBAT/3V3 with everything asleep: ESP32-S3 deep sleep 7–8 µA, divider 2.1 µA,
DRV2605L standby ≤ 4 µA, LIS2DW12 ~1 µA, TPS62840 60 nA, two TPS22916 ≤ 20 nA, BQ25100 battery leakage
≈ 1 µA, WS2812 0 (gated) → ≈ 12–17 µA against the 25 µA profile in `hardware/power-budget.txt`
(the earlier 100k/100k divider alone was 21 µA). R19 draws 33 µA only while charging.

## 4. Importing `out/mcring_v1.net` into KiCad

The KiCad *schematic* editor cannot import netlists; the file targets the **PCB editor**. Use the SVG sheets
and `out/mcring_v1_nets.md` as the schematic reference while laying out. Off-board parts (`ANT1`, `BT1`,
`CP1`, `CP2`, `PZ1`) are not in the netlist on purpose; their wires land on `J1`, `PAD1`, `PAD2`, `BZ1`.

1. Create a KiCad project (`mcring_v1`), open the PCB editor.
2. Add a footprint library named **`mcring`** and draw the custom footprints the netlist references
   (names in the BOM): `TPS22916_DSBGA-4_YFP`, `BQ25100_DSBGA-6_YFP`, `SW_Omron_B3U-3000P`,
   `SW_Omron_B3U-1000P`, `MIC_TDK_T3902_3.5x2.65mm`, `LRA_8mm_2pad`, `PAD_Wire_2x1.5mm_P2.0mm` (J1),
   `PAD_Wire_2x1.2mm_P2.0mm` (BZ1), `PAD_Wire_1x1.5mm` (PAD1, PAD2), `PAD_Touch_3x4mm`, `PAD_Aux_1x2`.
   Pad sizes and pitches match `hardware/pcb/board_params.json` → `wire_pads_bottom_mm`. The remaining
   footprints use KiCad 7/8 library names (`RF_Module:ESP32-S3-MINI-1U`, `Package_TO_SOT_SMD:SOT-583-8`,
   `LED_SMD:LED_WS2812B-2020_PLCC4_2.0x2.0mm`, `Connector_FFC-FPC:Hirose_FH12-24S-0.5SH_…` (land pattern
   for the F32R-1A7H1-11024 — check), `Package_LGA:LGA-12_2x2mm_P0.5mm`, `Package_SO:VSSOP-10_3x3mm_P0.5mm`,
   `Diode_SMD:D_SOD-523` ×2, passives 0402/0603/1206). If a name is missing in your KiCad version, change
   it in `mcring_v1.py` and regenerate — pad numbers must match the pin numbers in the model.
3. **File → Import Netlist…**, pick `out/mcring_v1.net`, *Match by reference*, tick *Replace footprints with
   those specified in netlist*, *Update footprint fields*, then *Load and Test Netlist* → *Update PCB*.
4. Board setup: outline from `hardware/pcb/board_params.json` (written by the floorplan step); design rules
   below; net classes: `GND/3V3/VBAT/CAM_3V3/VLED/CHG_PAD/CHG_IN/SW_NODE` 0.3 mm, everything else
   0.1–0.15 mm.
5. Re-import after any change to `mcring_v1.py` — pcbnew keeps placement and only updates connectivity.

**Bring-up power without the cell:** a current-limited 4.0 V bench supply on `TP8` (VBAT) + `TP5` (GND)
runs the whole board; 5 V for the charger goes onto the `PAD1` wire pad (`CHG_PAD`) — it is on the board,
so no extra VBUS test pad is needed. USB data stays on `TP3`/`TP4`. The BQ25100 alone (no cell) cannot
power the ESP32-S3 (its output is limited to the 25 mA charge current), so flashing always needs either
the cell or the bench supply on `TP8`.

## 5. Design rules — 2-layer, 0.6 mm FR-4, 1 oz

| Rule | Value | Why |
|---|---|---|
| Track / clearance (fine) | **0.10 / 0.10 mm** | fan-out of the 0.4 mm-pitch DSBGA (TPS22916 ×2) and 0.5 mm-pitch LGA/VSSOP/FPC |
| Track / clearance (general) | 0.15 / 0.15 mm | everything else; 0.3 mm for power nets, 0.4 mm+ for VBAT/3V3 trunks |
| Via | **0.2 mm drill / 0.45 mm pad** (0.125 mm annular) | fits between 0.5 mm pads; 0.6 mm board → aspect ratio 3:1 |
| DSBGA pads | NSMD, 0.22–0.25 mm Ø, no via-in-pad | all balls of the 2×2 and 2×3 arrays are on the perimeter → no routing between balls |
| Solder-mask expansion | 0.05 mm (0.03 mm on DSBGA) | fine-pitch parts |
| Silkscreen | none on the component side under the module | the module needs flat, bare FR-4 under the shield |
| Finish | **ENIG** | charging contacts, DSBGA/LGA co-planarity |
| Copper | 1 oz (35 µm) | thermal spreading for the 100 mW class LDO dissipation |
| Module | ESP32-S3-MINI-1U per Espressif layout guide: GND thermal pads tied to the ground plane with ≥ 9 vias; **no copper, traces or vias under the u.FL/antenna end**; antenna end points away from the camera | |
| Antenna (ANT1) | u.FL on the module → pigtail down the inside of the back wall → flex dipole along the band; **≥ 5 mm from the cell, the LRA and any metal**, never under the module or across the DVP corridor; cable ≤ 50 mm, no sharp bends at the MHF1 plug (mated height 2.9 mm = `top_max_height_mm`) | BLE only works with it fitted; the MINI-1U has no on-module antenna |
| Buck | TPS62840: CIN, L, COUT in a tight loop on the top layer; VOS sense trace from COUT; SW node minimal area | |
| Camera FPC | DVP bus length-matched loosely (±5 mm is fine at 20 MHz); XCLK/PCLK away from the antenna feed | |
| Touch pad | copper 3×4 mm on top, ground hatch around, **no copper under it** | |
| Charging input | CP1/CP2 3×2 mm ENIG flush in the inner band, ≥ 3 mm apart; wires to PAD1/PAD2; D2 (bidirectional TVS) within 2 mm of PAD1, D3 (Schottky) right after it; **polarity hazard**: a reversed ring in the cradle is survived only because of D3 — keep it, and key the cradle anyway | |
| Keep-outs | LRA, cell and antenna away from each other and from the antenna end of the module; the piezo element (PZ1) is off-board and needs its own pocket if fitted | |

Check your fab's 2-layer capability before ordering: 0.1/0.1 mm track/space and 0.2 mm drills are "advanced"
options at JLCPCB/PCBWay (standard is 0.127 mm / 0.3 mm drill). If only standard rules are available, the
0.4 mm-pitch TPS22916 can be replaced by a SOT-23-5 load switch (e.g. TPS22917DBV) with the same nets.

## 6. Assumptions to verify against the datasheets

The datasheets themselves could not be fetched from the sandbox; items marked *(web)* were confirmed
from distributor copies / Espressif documentation via web search and should be ticked once against the
PDF before ordering.

| # | Item | Where it bites |
|---|---|---|
| 1 | **ESP32-S3-MINI-1U pin table** used: 1–2 GND, 3 3V3, 4–25 IO0–IO21, 26 IO26, 27–36 IO33–IO42, 37 TXD0/IO43, 38 RXD0/IO44, 39 IO45, 40 IO46, 41 IO47, 42 IO48, 43–44 GND, 45 EN, 46–65 GND | every U1 node in the netlist; check `esp32-s3-mini-1_mini-1u_datasheet_en.pdf` Table "Pin Definitions" |
| 2 | **IO33–IO37 are free GPIOs on the N4R2** *(web: ESP-IDF GPIO guide — SPIIO4–7/SPIDQS are used "under octal configurations" only; quad PSRAM uses SPICS1 = IO26)* | IO33 = LED_PWR_EN; the module datasheet carries a footnote on IO26 — read it and confirm there is none on 27–31 |
| 3 | **FPC pin order** (ESP32-CAM / Arducam M0031): 1 NC, 2 AGND, 3 SIOD, 4 AVDD, 5 SIOC, 6 RESET, 7 VSYNC, 8 PWDN, 9 HREF, 10 DVDD, 11 DOVDD, 12 Y9, 13 XCLK, 14 Y8, 15 DGND, 16 Y7, 17 PCLK, 18 Y6, 19 Y2, 20 Y5, 21 Y3, 22 Y4, 23 Y1, 24 Y0; **F32R-1A7H1-11024 is bottom-contact** and its land pattern matches the KiCad FH12-24S-0.5SH footprint | a one-position-shifted variant exists (pin 1 AGND … pin 24 NC); buzz the purchased head before ordering boards. Also confirm whether the head needs external 1.2 V (U4) |
| 4 | **BQ25100** DSBGA ball map (A1 IN, A2 OUT, B1 /CHG, B2 PRE_TERM, C1 ISET, C2 VSS), K_ISET = 230 A·Ω, K_PRETERM = 11.5 A·Ω, no TS pin; VIN(min) with D3's ~0.25 V drop from a 4.75 V cradle (4.5 V at IN) | R10 = 9.1 kΩ → 25 mA, R11 = 11.5 kΩ → 1 mA |
| 5 | **TPS62840DLCR** pin numbers (SOT-583: 1 SW, 2 GND, 3 VIN, 4 EN, 5 STOP, 6 MODE, 7 VSET, 8 VOS); **R12 = 267 kΩ for 3.3 V** *(web: SLVSE12 Table 1 via distributor copies; 1.8 V = GND, 2.5 V = 11.5 k, 3.0 V = 52.3 k, 3.3 V = 267 k)* | Vout wrong if the table row is misread |
| 6 | **TPS22916C** ball map (A1 VIN, A2 VOUT, B1 ON, B2 GND), VIL ≥ 0.35 V so the 4.7 kΩ pull-down on IO33 holds the LED rail off, and that the "C" suffix (slower rise) is the wanted variant | U2, U9 |
| 7 | **DRV2605L** VSSOP-10 pin numbers (1 REG, 2 SCL, 3 SDA, 4 IN/TRIG, 5 EN, 6 VDD, 7 GND, 8 OUT-, 9 OUT+, 10 NC); **EN tied to VDD is allowed and shutdown blocks I²C register access** *(web: datasheet "Operation with EN control")*; standby current with EN high | U5 |
| 8 | **LIS2DW12** LGA-12 pin numbers (1 SCL, 2 CS, 3 SA0, 4 SDA, 5 RES, 6–8 GND, 9 VDD, 10 VDD_IO, 11 INT2, 12 INT1) | U6 (pins 5–8 all go to GND, so only 1–4 and 9–12 matter) |
| 9 | **T3902** pad numbering (1 VDD, 2 GND, 3 CLK, 4 DATA, 5 SELECT, 6 GND) and port hole size | MK1 |
| 10 | **WS2812B-2020** pad order (1 VDD, 2 DOUT, 3 GND, 4 DIN) and **operation at VLED = 3.3 V** (below the 3.7 V minimum; bench-check colour/brightness) — else a 3.3 V-rated 2020 RGB on the same pads | D1 |
| 11 | **PESD5V0S1BB** (bidirectional, SOD-523, no polarity) availability; **PMEG2005EB** SOD-523 pin order (1 K, 2 A) and VF at 25 mA | D2, D3 |
| 12 | **XC6206P122MR** availability (1.2 V member of the XC6206 family); else TLV70212 / NCP161 1.2 V in SOT-23 | U4 |
| 13 | LRA0825BC-0167F: 240 Hz, 1.25 Vrms max → DRV2605L RATED_V/OD_CLAMP per `docs/07-build-guide.md` §1.8 (not the 1.8 Vrms defaults in `drv2605.cpp`) | M1 |
| 14 | ESP32-S3 ADC input leakage against the 500 kΩ divider source (≤ 50 nA → ≤ 25 mV error) | R8/R9, battery_mv() |
| 15 | **ANT1** Molex 146153-0050 outline 34.9 × 9 × 0.1 mm and MHF1 plug height vs the CAD (band wrap, back-wall channel) | fit check in `hardware/cad/`; alt. Taoglas FXP70.07.0053A |
| 16 | KiCad footprint names listed in §4 exist in the installed library version | import step |

## 7. Firmware follow-ups implied by this design

`config.h` (BOARD_MCRING_V1) already carries the pins; the code does not yet use two of them:

* **`PIN_RGB_PWR` (33) is defined but never driven** — `feedback_init()` must set it as an output and drive
  it HIGH before any `neopixelWrite()` (allow ~1 ms for the TPS22916C rise before the first frame), and
  `power_deep_sleep_now()` must drive it LOW. Until then the stage-1 LED is unpowered: haptics (and the piezo,
  if fitted) are the only feedback channels.
* **`PIN_CHG` (3) is defined but `battery_charging()` returns `false`** — read it as an input (active LOW)
  so `MC_FLAG_CHARGING` becomes real; optionally an EXT1 wake on charge (IO3 is an RTC GPIO).
* `PIN_HAPTIC` is `-1` on this board (DRV2605L EN tied high): `haptic_write()` compiles to `drv2605_set()`
  only, `feedback_stop()` already parks the driver in STANDBY; a `drv2605_standby(true)` in
  `power_deep_sleep_now()` would make that explicit. Nothing else changes for the haptic path.
* The `drv2605.cpp` defaults (0x3E / 0x8C ≈ 1.8 Vrms, 235 Hz) are for the stage-0 motor; the INEED LRA
  is 1.25 Vrms / 240 Hz (`docs/07-build-guide.md` §1.8: `--vrms 1.25 --freq 240`).
* `gpio_hold_en(21)` + `gpio_deep_sleep_hold_en()` is optional — R17 already defaults the camera off; the same
  holds for IO33 and R18.
* `neopixelWrite()` works on IO43 through the RMT matrix, `digitalWrite(PIN_CAM_PWR)` on IO21, as before.
