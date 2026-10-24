# Research report 4 — No-solder sourcing: a solderless stage 0 and an assembled stage 1

> Automated research pass, 2026-10-24, from web-search snippets only (every direct page fetch —
> adafruit.com, seeedstudio.com, learn.adafruit.com, zephyrproject.org — was blocked by the sandbox).
> Prices are the first-party list price in USD where a snippet showed one; reseller prices are
> labelled. **[UNVERIFIED]** marks anything a snippet did not actually state. Pin names follow
> `firmware/ring-esp32s3/src/config.h` (XIAO `D1` = GPIO2 button, `D3` = GPIO4 buzzer, `D4/D5` I²C,
> `D8` = GPIO7 IMU INT1, `D6/D7/D10` = I²S LRC/BCLK/DIN).

## 0. Answer in one paragraph

**Stage 0 can be built with zero solder joints** if two parts are swapped: buy the *pre-soldered* XIAO
ESP32S3 Sense (Seeed SKU 102010635) and seat it in Seeed's Expansion Board Base (103030356), whose
user button is already on **D1** and whose passive buzzer is already on **A3 = D3 = GPIO4** — exactly
`PIN_BUTTON` and `PIN_BUZZER`. The LiPo plugs into the base's JST-2.0 socket, the haptic driver and
accelerometer hang off the base's Grove-I²C socket through a Grove→STEMMA QT cable. The two things that
normally need a soldering iron — the LRA's two leads into the DRV2605L breakout, and the accelerometer's
INT pin — are avoided by (a) using Seeed's **Grove Haptic Motor** (DRV2605L + motor, one plug; it is an
ERM, firmware flag `drv2605_init(false)`), and (b) either an IC-hook test clip on the LIS3DH's INT hole or
compiling with `PIN_IMU_INT -1` (polling, loses tap-wake). The optional I²S speaker is the one item with
**no plug-in option**: every MAX98357A breakout needs its header soldered (see §A6).

**Stage 1 cannot be made fully solderless by the owner, but it can be made solder-free *for the
owner*:** order the 26.5 × 18 mm board from JLCPCB **Standard PCBA** (Economic PCBA cannot do 0.4 mm
BGA or double-sided placement), put 1.2 mm-pitch wire-to-board headers on the board for the cell, LRA and
speaker, and have the three off-board parts delivered **with mating pigtails** — which, because no
off-the-shelf 8 mm LRA, 10 mm speaker or 30 mAh cell ships with a connector, means either a 40 mAh
JST-SH cell (SparkFun/TinyCircuits), spring-contact actuators, or a one-time cable-shop/makerspace job
for ~6 joints. Details and a costed plan in §B and §C.

## A. Stage-0 parts

### A1. XIAO ESP32S3 Sense with pre-soldered headers

| Item | SKU | Price | Where | Verified by |
|---|---|---|---|---|
| Seeed Studio XIAO ESP32-S3 Sense (Pre-Soldered) | **102010635** | **$14.90** excl. VAT (Seeed datasheet PDF for 102010635, "PRICE $14.90 (Excl. VAT)", updated 2026-09-10); US street $19.95 (pricehistory tracker, Jul 2026); Mouser €12.81; Pakronics A$32.99 | [Seeed p-6335](https://www.seeedstudio.com/Seeed-Studio-XIAO-ESP32S3-Sense-Pre-Soldered-p-6335.html), [Seeed PDF](https://files.seeedstudio.com/Bazaar/product_pdf/102010635.pdf), [Electromaker](https://www.electromaker.io/shop/product/seeed-studio-xiao-esp32s3-sense-pre-soldered), [Kiwi](https://www.kiwi-electronics.com/en/seeed-studio-xiao-esp32s3-sense-pre-soldered-20491) | Seeed's own page lists 102010635; Kiwi and Pakronics resell it as SS-102010635 |
| Same, unsoldered (current BOM line) | 113991115 | $14–20 | Pi Hut 106594 "select header version before adding to cart" | Pi Hut page offers a header option — confirm at checkout |
| Pre-soldered XIAO ESP32S3 *without* Sense | 102010634? **[UNVERIFIED SKU]** | — | Seeed p-6334 | exists; not what we want (no camera/mic) |

So a pre-soldered Sense variant **does exist**; the hammer-header fallback is moot. For completeness:
Pimoroni "GPIO Hammer Header (Solderless) – Male", Adafruit **3662**, $2.25 (Adafruit list; 2×20 Pi
header, cut to 1×7 strips) — press-fit designed for the Pi's 1.0 mm holes; fit in the XIAO's holes
**[UNVERIFIED]**. Sources: [Adafruit 3662](https://www.adafruit.com/product/3662), [RobotShop](https://www.robotshop.com/products/pimoroni-gpio-hammer-header-solderless).
Pre-soldered-header orientation (pins down, for sockets) **[UNVERIFIED]** — check the product photo.

### A2. Seeed Expansion Board Base for XIAO (103030356)

| Fact | Value | Verified by |
|---|---|---|
| Price | **$17.95** Adafruit (resells it as #5033); Pi Hut £15.80 ex VAT; Pimoroni £12.50 (OOS); Kiwi €14.46 ex VAT | [Adafruit 5033](https://adafruit.com/product/5033), [Pi Hut](https://thepihut.com/products/seeeduino-xiao-expansion-board), [Pimoroni](https://shop.pimoroni.com/products/seeeduino-xiao-expansion-board) |
| Battery | "JST2.0mm standard lipo battery connector and battery management system", charge "Max: 460mA" | Pimoroni/Pi Hut copy of Seeed text |
| User button | **D1** — Zephyr shield table "pin 1 is the user button"; Seeed ESPHome page: "pressing the D1 button on the expansion base"; Seeed pin-mux example `buttonPin = D1` | [Zephyr shield doc](https://docs.zephyrproject.org/latest/boards/shields/seeed_xiao_expansion_board/doc/index.html), [Seeed ESPHome](https://wiki.seeedstudio.com/XIAO_ESP32S3_esphome/), [pin multiplexing](https://wiki.seeedstudio.com/xiao_esp32s3_pin_multiplexing/) |
| Buzzer | **A3** ("buzzer is default connected to the Pin A3", cuttable trace) = XIAO D3 = GPIO4 = `PIN_BUZZER` | [Seeed wiki](https://wiki.seeedstudio.com/Seeeduino-XIAO-Expansion-Board/), Zephyr table "pin 3 is the buzzer on A3" |
| microSD | CS on **D2** (Zephyr "pin 2 is MicroSD SPI CSn"); SPI on D8/D9/D10 **[UNVERIFIED]** (the XIAO's SPI pins) | Zephyr table |
| Grove sockets | I²C (D4/D5, shared with OLED 0x3C and RTC PCF8563); UART (D6/D7) | Seeed wiki; Adafruit 5033 "I2C RTC PCF8563" |
| Works with the Sense camera board attached? | Yes: Seeed's own "Miniature ChatGPT Voice Assistant" project runs the **Sense** in this base (Sense mic + base button/OLED), with a note that SD use needs a J3 change | [speech2chatgpt](https://wiki.seeedstudio.com/xiao_esp32s3_speech2chatgpt/) |
| Battery polarity | Seeed forum thread "XIAO Expansion – battery connector backwards?": connector was moved in production; wiki diagram is correct; users swapped pigtail wires | [forum](https://forum.seeedstudio.com/t/xiao-expansion-battery-connector-backwards/271029) |

Pin collisions against our map: **D2** (base SD CS) is `PIN_HAPTIC` (DRV2605L EN, optional — the Grove
Haptic Motor does not need it); **D6/D7** (base UART Grove) are our I²S LRC/BCLK — never plug a UART
Grove device in; **D8–D10** (base SD SPI, probable) are IMU INT1 / touch / I²S DIN — leave the base's
card slot empty. The Sense's own SD slot uses the same D8–D10 and is already "unused" in the firmware.
OLED (0x3C) and RTC (0x51) do not clash with DRV2605L 0x5A or LIS 0x18/0x19. Whether the base feeds the
XIAO's BAT pads or only VIN/5 V **[UNVERIFIED — read the v1.0 schematic PDF before relying on the A0
battery divider]**; the divider itself is two resistors on the base's female breakout header with
male-to-male jumpers (no solder), or set `BATTERY_DIVIDER` off.

### A3. Grove ↔ STEMMA QT / Qwiic cables

| Item | SKU | Price | Verified by |
|---|---|---|---|
| Adafruit Grove to STEMMA QT / Qwiic / JST SH, 100 mm | **4528** | **$1.95** (1–9) | [Adafruit 4528](https://www.adafruit.com/product/4528) "$1.95 … $1.56 at 100+" |
| SparkFun Qwiic Cable – Grove Adapter, 100 mm | **PRT-15109** (older PRT-14739) | **$1.95** | [SparkFun](https://www.sparkfun.com/qwiic-cable-grove-adapter-100mm.html) |
| Seeed's own Grove→Qwiic cable | not found | — | no Seeed SKU surfaced in two searches |

### A4. Haptic driver — DRV2605L breakouts

| Item | SKU | Price | Motor attachment | I²C | Verified by |
|---|---|---|---|---|---|
| Adafruit DRV2605L Haptic Motor Controller – STEMMA QT | **2305** | $7.95 (BOM) | **Two plated through-holes "Motor +" / "Motor −" — solder** (assembly page: "Controller Motor − to motor negative (black wire in STEMMA QT version)") | QT ×2, 0x5A | [Adafruit 2305](https://www.adafruit.com/products/2305), [Learn guide](https://learn.adafruit.com/adafruit-drv2605-haptic-controller-breakout.md?view=all) "As of July 11, 2022 – this board now comes in STEMMA QT format" |
| Seeed Grove – Haptic Motor (DRV2605L + ERM, one Grove plug) | **105020011** | Pi Hut £5.90; Farnell IE €13.75; Pakronics A$14.08 | **none — motor factory-attached** | Grove, 0x5A | [Pi Hut](https://thepihut.com/collections/new-products-maker/products/grove-haptic-motor), [Farnell](https://ie.farnell.com/seeed-studio/105020011/haptic-motor-module-arduino-board/dp/4007825) |
| TinyCircuits LRA Driver Wireling (DRV2605 + LRA pre-soldered, adhesive back) | AST1013 | $14.95 | none — but needs a 5-pin Wireling cable/adapter, not QT/Grove **[compat UNVERIFIED]** | 0x5A | [TinyCircuits](https://tinycircuits.com/products/lra-wireling-drv2605) |

**Verdict:** the Adafruit 2305 is QT on the bus side but *not* solderless on the motor side. For a
truly plug-in stage 0 use the Grove Haptic Motor (ERM; call `drv2605_init(false)` — `drv2605.cpp`
already has the ERM branch) or the Wireling with its LRA. The LRA-specific feel comes back at stage 1.

### A5. STEMMA QT / Qwiic accelerometers with hardware tap interrupt

| Board | SKU | Price | Addr | INT exposure | Status | Verified by |
|---|---|---|---|---|---|---|
| Adafruit LIS3DH | **2809** | **$4.95** | 0x18 (SDO low/open) / 0x19 (jumper) | INT + "I2" through-holes, 3.3 V logic | active, STEMMA QT | [Adafruit 2809](https://adafruit.com/product/2809) "$4.95 1-9"; Learn guide pinouts |
| SparkFun Micro LIS3DH (Qwiic) | **SEN-29529** | **$5.95** | 0x19 default (library) | "one accelerometer interrupt pin and a single ground pin" PTH | active | [SparkFun](https://www.sparkfun.com/sparkfun-micro-triple-axis-accelerometer-breakout-lis3dh-qwiic.html) |
| SparkFun Qwiic LIS2DH12 | SPX-15760 | last $6.95 | 0x19 | — | **retired** ("no longer for sale"); DigiKey 12-wk | [SparkFun](https://www.sparkfun.com/products/15760) |
| SparkFun Qwiic KX132 | **SEN-17871** | **$15.50** | 0x1E/0x1F | INT1 on PTH (examples); INT2 **[UNVERIFIED]** | active | [SparkFun](https://www.sparkfun.com/products/17871), [hookup](https://learn.sparkfun.com/tutorials/triple-axis-accelerometer-breakout---kx13x-qwiic-hookup-guide-/all) |
| Adafruit ADXL343 (tap) | 4097 | Jameco $7.85 (Adafruit list not seen) | 0x53 | INT1/INT2 PTH | STEMMA QT since 2022-03 | [Learn](https://learn.adafruit.com/adxl343-breakout-learning-guide.md?view=all) |
| Adafruit MSA301 | 4344 | — | — | — | **EOL** → MSA311 #5309 | [Learn](https://learn.adafruit.com/msa301-triple-axis-accelerometer.md?view=all) |
| Adafruit LIS2DH12 / LIS2DW12 breakout | — | — | — | — | **does not exist** (none surfaced) | — |

Firmware reality check: `imu_lis2dw12.cpp` only accepts WHO_AM_I 0x44 (LIS2DW12). An LIS3DH (0x33) or
KX132 needs a small driver variant — the register maps differ. `trigger.cpp`/`power.cpp` compile the
INT path out when `PIN_IMU_INT < 0`, so a no-wire build loses tap-wake until a polling fallback exists.
No QT board routes its interrupt into the 4-pin cable, so the INT wire is the one "clip" in the kit.

### A6. Speaker amplifier

| Item | SKU | Price | Solderless? | Verified by |
|---|---|---|---|---|
| Adafruit I2S 3 W Class-D Amp – MAX98357A | **3006** | $5.95 (BOM; UK £5.70, Mouser UK £4.47) | **Speaker side yes** ("As of June 13, 2024 – We added a pre-soldered terminal block"); **I²S side no** ("with a small piece of optional header. Some soldering is required to attach the header") | [Adafruit 3006](https://www.adafruit.com/products/3006), [Learn guide](https://learn.adafruit.com/adafruit-max98357-i2s-class-d-mono-amp.md?view=all) |
| Adafruit STEMMA Speaker – plug-and-play amp + 1 W 8 Ω speaker | **3885** | **$5.95** | Yes (3-pin JST-PH) — but **analog input** ("audio signal … up to 3 or 5 V p-p"); **ESP32-S3 has no DAC**, so this needs a sigma-delta/PWM output path that the firmware does not have | [Adafruit 3885](https://www.adafruit.com/product/3885) |
| Any Grove/Qwiic **I²S** amp | — | — | none found: Grove carries 2 signals, I²S needs 3 | — |

Solderless workarounds for the 3006's five header holes: IC-hook clips (§A7) or Pimoroni hammer pins
(fit **[UNVERIFIED]**). Honest recommendation: treat the speaker as the one optional item that is
either 5 joints at a makerspace, or deferred to the stage-1 board where the amp is SMT-assembled.

### A7. Solderless wire attachment

| Item | SKU | Price | Note | Verified by |
|---|---|---|---|---|
| Adafruit Small Alligator Clip to Male Jumper, 12 pc | **3255** | **$7.95** | clips onto breakout pads/LRA leads, plugs into the base's female header | [Adafruit 3255](https://www.adafruit.com/products/3255), Mouser 485-3255 $7.95 |
| SparkFun IC Hook with Pigtail | CAB-09741 **[SKU UNVERIFIED]** | ~US$6 (Solarbotics, dated); A$9.70 | fine-pitch hook for a PTH or lead | [Core](https://core-electronics.com.au/ic-hook-with-pigtail.html.plain.md) |
| DFRobot Hook Test Clip 10-pack | FIT0xxx **[UNVERIFIED]** | A$13.20 | | [Core](https://core-electronics.com.au/hook-test-clip-10-pack.html.md) |
| WAGO 221-412 lever nut (2-cond.) | 221-412 | $0.46–0.62 ea | **rated 28–12 AWG**: 30 AWG LRA/speaker leads must be doubled over **[judgement]** | [Del City](https://www.delcity.net/store/wire-connectors-quick-splices/wago-connectors/221-lever-nut-2-conductor/) |
| Breadboard screw-terminal adapters | — | — | no priced listing surfaced **[UNVERIFIED]** | — |

### A8. LRA / vibration motors with pre-attached connectors

| Item | Type | Termination | Verified by |
|---|---|---|---|
| Adafruit Vibrating Mini Motor Disc 1201 | ERM | bare leads | (BOM note) |
| Seeed Grove Vibration Motor 105020003 | ERM | Grove plug (no driver) | Pi Hut £2.20; DigiKey CN 20-wk lead |
| Vybronics coin LRA line | LRA | "Config 1 WIRE LEADS / Config 1.1 WIRE LEAD w. CONNECTOR" (connector family unnamed; OEM order) | [Vybronics LRA](https://www.vybronics.com/products/coin-vibration-motors/lra) |
| Vybronics **VC0820K001L** / VCLP0820K001L | ERM 8 × 2 mm, 3 V | **spring contacts, adhesive back** — "not designed to be soldered"; 85 / 35 mA | [Vybronics](https://www.vybronics.com/coin-vibration-motors/with-brushes/v-c0820k001l) |
| INEED / TSL 8 mm LRA | LRA | leads; "connector can be added as required" (custom); TSL: "lead wire, FPCB and spring mountable versions" | [TSL](https://tsinglinmotor.com/product/8mm-lra-linear-resonant-actuator-2/) |

No stock 8 mm **LRA** with a JST/Molex plug surfaced; connectors are an OEM option with MOQ.

### A9. 100 mAh LiPo with JST-PH 2.0

| Item | SKU | Price | Verified by |
|---|---|---|---|
| Adafruit LiPo 3.7 V 100 mAh, JST-PH, protected, no thermistor | **1570** | **$5.95** ("Product ID: 1570 … $5.95, in stock") | [Adafruit batteries](https://www.adafruit.com/batteries) |
| SparkFun 40 mAh, JST-PH | PRT-13852 | — | [SparkFun](https://www.sparkfun.com/products/13852) |
| SparkFun 40 mAh, **JST-SH** | PRT-25270 | — | [SparkFun](https://www.sparkfun.com/polymer-lithium-ion-battery-40mah-jst-sh.html) ("about half an inch square") |

The base's JST 2.0 mm socket is JST-PH pitch, so #1570 mates mechanically; **check polarity against the
base silkscreen first** (§A2 forum thread). Adafruit also cautions #1570 is 1 C max (100 mA) — the
base's 460 mA charger is too fast for this cell unless its current is set lower **[UNVERIFIED whether
the base's charge current is adjustable]**; the XIAO's own on-board charger is the safer route.

## B. Stage-1 design for assembly

### B1. PCBA capability and cost

| Fab / tier | Min BGA pitch | Fine pitch | Sides | Qty | Fees | Verified by |
|---|---|---|---|---|---|---|
| **JLCPCB Standard PCBA** | **0.35 mm** ("0.35 mm BGA pitch", 0201/01005) | 0.35 mm lead pitch | **single or double** | — | setup **$25 / $50** (1 / 2 sides), stencil **$7.86 / $15.72**, placement **$0.0016/joint** (Sep 2025 help article) | [JLCPCB prototype assembly](https://jlcpcb.com/solutions/pcb-prototype-assembly), [help: price](https://jlcpcb.com/help/article/pcb-assembly-price), [capabilities](https://jlcpcb.com/capabilities/pcb-assembly-capabilities) |
| JLCPCB Economic PCBA | 0.5 mm | 0.40 mm | **single only** | 2–50 | setup $8, stencil $1.50 | same |
| PCBWay | **0.3 mm** rigid (X-ray), 0.4 mm flex; "0.25mm fine pitch" | | single/double ("process repeated for the second side") | MOQ 5 | **quote-based** (human review 1–2 days); no public setup fee found **[UNVERIFIED]** | [PCBWay capabilities](https://www.pcbway.com/assembly-capabilities.html), [BGA page](https://www.pcbway.com/pcb_prototype/BGA_Assembly_Capabilities.html) |

Both 0.4 mm DSBGAs (BQ25100 YFP-6, TPS22916 YFP-4), the LGA-12 LIS2DW12, the QFN-16 MAX98357A, the
VSSOP-10 DRV2605L and the 15.4 mm module are inside Standard-PCBA limits; **Economic is out** on pitch
*and* on the double-sided layout (`floorplan.md`: bottom carries ~75 of 90 parts). JLCPCB support's own
answer on 0.4 mm BGA: "fine as long as the PCB design is within our capacity" (3.5 mil trace at 1 oz);
no first-hand DSBGA yield reports surfaced — ask for 1:1 stencil apertures as the build guide already
says. Extended-part feeder fee: $3/type on Economic is well attested; whether Standard charges $1.5/type
or nothing is **contradicted between sources [UNVERIFIED]** — read the live quote.

Parts in the JLCPCB/LCSC library (snapshot, stale-prone):

| Part | LCSC | Stock / price | Note |
|---|---|---|---|
| BQ25100AYFPR | **C2871910** | 96 pcs, ~$2.10 @1 | extended |
| LIS2DW12TR | **C189624** | 25k pcs, ~$0.37 @1k | extended |
| MAX98357AETE+T | C910544 (BOM) | — | |
| ESP32-S3-MINI-1U-**N8** | **C2980299** | 109 pcs, $4.00 @1 | **no PSRAM** — camera framebuffers need the N4R2's 2 MB; |
| ESP32-S3-MINI-1-N4R2 (PCB antenna, not 1U) | C3013941 | 455 pcs, $5.18 | wrong antenna variant for this enclosure |
| ESP32-S3-MINI-1U-N4R2 | **not found on LCSC** | aggregator "1540 pcs, inquiry" | → **consign** (ship from Mouser/DigiKey to JLCPCB) or JLCPCB Global Sourcing |
| TPS22916CYFPR | **not found on LCSC**; DigiKey OOS 12-wk; Arrow active | — | → consign; or re-check live, TI stock moves |
| F32R-1A7H1-11024 (FPC) | not on LCSC — it is an **Amphenol FCI** part (element14 3525632), not "XKB (LCSC)" as `mcring_v1.py`/BOM say | — | fix the manufacturer field; see B3 |

Rough 5-board Standard-PCBA cost (double-sided, ~90 placements ≈ 240 joints/board):
PCB 5× 0.6 mm 2-layer ENIG ≈ $10–30 · setup $50 · stencils $15.72 · placement 1 200 joints ≈ $2 ·
extended-part fees 25–30 types × $3 ≈ $75–90 (if charged) · parts ≈ $25–35/board incl. module ≈ $150 ·
consigned-part handling + shipping ≈ $30–50 → **≈ $330–420 for five assembled boards [estimate]**.

### B2. Low-profile wire-to-board connectors for the 5 off-board pairs

Constraints from `board_params.json`: **top_max_height 2.9 mm, bottom_max_height 1.15 mm**, FPC1 2.0 mm.
Nothing fits the bottom; only sub-2.9 mm mated heights fit the top, and the top already carries U1,
FPC1, SW1, D1, R7, C3 on 26.5 × 18 mm.

| Family | 2-pin header MPN | Orientation / mated height | Pitch / wire | Pre-made cables | Price | Verified by |
|---|---|---|---|---|---|---|
| **Molex Pico-EZmate** | **78171-0002** (vertical; body ≈ 4.2 × 4.5 × 1.45 mm) | **1.55 mm mated** (Molex table "2 ckt 1.55 mm"; older pages say 1.40) | 1.20 mm, 28–30 AWG | 36920-0201 socket↔socket 100 mm **$2.31** (DigiKey, 0 stock, 20-wk); pigtails 68801-4146 (152 mm, 28 AWG) RS £1.03 but "being discontinued"; 0688014229 (458 mm, fused 18 AWG) status conflicting | header ~$0.3–0.5 **[UNVERIFIED]** | [TTI datasheet](https://www.tti.com/content/dam/ttiinc/manufacturers/molex/doc/molex-pico-ezmate-connectors-datasheet-specifications.pdf), [DigiKey 0369200201](https://azcus.digikey.com/en/products/detail/molex/0369200201/10232988), [RS 1791536](https://uk.rs-online.com/web/p/crimped-wire/1791536) |
| Pico-EZmate right-angle | **none found** in 78171 | — | — | — | — | two searches |
| **JST ACH** | **BM02B-ACHSS-GAN-ETF** (SMT, top-entry, wires exit horizontally) | **1.4 mm high** (series) | 1.2 mm, 30–28 AWG, 2 A | housing ACHR-02V-S $0.10 (0 stock, 16-wk); **ACH-to-ACH 28 AWG jumpers ASACHSACH28W51/102/152/305 $0.54–0.94 in stock** → cut one end for a pigtail (listed against SACH-003G-P0.2; confirm mating) | — | [DigiKey ACH](https://www.digikey.com/es/product-highlight/j/jst/ach-series-connectors) |
| JST SH side-entry | **SM02B-SRSS-TB(LF)(SN)** (LCSC C160402) | **2.9 mm tall**, horizontal (= top limit, no lid clearance) | 1.0 mm, 32–28 AWG | SH pre-crimped leads everywhere (Unmanned Tech 20 pcs £3.49); SparkFun/TinyCircuits 40 mAh cells come **with SH plugs** | ~$0.2 | [DigiKey](https://www.digikey.com/en/products/detail/jst-sales-america-inc/SM02B-SRSS-TB-LF-SN/926708) (one non-LF listing marked obsolete — order the (LF)(SN) code) |
| JST SH top-entry BM02B-SRSS-TB | — | 4.25 mm | — | — | — | already rejected in `mcring_v1.py` |
| Hirose DF65 | DF65-2P-1.7V(21) **[2-pin not found; 3P/4P are]** | **1.8 mm mated** | 1.7 mm | — | 4P £0.61 @50 | [Farnell DF65-3P](https://jp.farnell.com/en-JP/hirose-hrs/df65-3p-1-7v-21/connector-header-3pos-1row-1-7mm/dp/2464752) |
| Molex PicoBlade 53261-0271 (Adafruit 3923 speaker plug) | RA SMT | height **[UNVERIFIED, likely >3 mm]** | 1.25 mm | many | — | RS listings |
| Kyocera-AVX poke-home 9296 | 2-pos | 2.5 mm high, 3.0 mm pitch | **20–26 AWG only** — too coarse for 30 AWG | n/a (crimp-free) | — | [Kyocera](https://www.kyocera-avx.com/product/9296-000-series/) |

Reading: the only 2-pin systems under 1.6 mm are **Pico-EZmate (1.55)** and **JST ACH (1.4)**; both
are crimp systems, but both have **off-the-shelf pigtails** (Pico-EZmate 36920/68801; ACH jumper cut in
half), so the owner never crimps — the cell/LRA/speaker end of those pigtails still has to be joined to
the part's own 30 AWG leads. Options for that last join, none perfect: a cable shop (e.g. Hoohaa lists
Pico-EZmate harnesses), a makerspace (6 joints, 10 minutes), or spring-contact parts (§B3).

### B3. Everything else that removes a solder step

- **Camera FPC**: `F32R-1A7H1-11024` is Amphenol FCI "0.50 mm pitch right-angle **ZIF with slider**,
  bottom contact, 2.00 mm height" — a ZIF, so no solder, but **slider-type, not back-flip**; the back-flip
  2.0 mm sibling is **F32D**. `mcring_v1.py` line 330 and the BOM call it "back-flip" and "XKB (LCSC)":
  both wrong. ([element14](https://kr.element14.com/amphenol-fci/f32r-1a7h1-11024/conn-r-a-ffc-fpc-24pos-1row-0/dp/3525632), [Amphenol overview](https://www.tti.com/content/dam/tti-commons/supplier/amphenol/doc/amphenol-ffc-fpc-connectors-product-overview-ap.pdf))
- **Antenna**: u.FL/MHF1 snaps on — no change.
- **Charging pads**: the netlist runs 30 AWG wires from PAD1w/PAD2w to ENIG pads in the band (two
  joints each end). Solder-free alternatives: (a) make the band contacts the *ends of a 2-layer FPC
  tail* soldered by the PCBA house to the wire pads (rigid-flex or a consigned FPC — adds ~$30–60 to
  the order **[estimate]**); (b) Mill-Max SMT **target discs** (1578/1593 series, Ø1.98–3.96 mm, hard
  gold, tape-and-reel) placed by the assembler — but they must sit on the *board*, i.e. move the pogo
  contact to a board edge visible through the band (floorplan change); (c) conductive adhesive: MG
  8331D-14G **$130**, 8331S-15G **$112–142**, CW2400 7 g **$88–142** — all absurdly priced for 4 joints;
  the silver **pen 842AR-P ~$46 (5 mL, 0.3–0.8 Ω/cm)** is viable for the ≤25 mA charge path only, never
  for the 8 Ω speaker. ([Mill-Max PR](https://www.mill-max.com/PR698), [MG 842AR](https://mgchemicals.com/products/circuit-board-repair/conductive-pens/silver-conductive-pen/), [DigiKey 8331D](https://azcus.digikey.com/en/products/detail/mg-chemicals/8331D-14G/13170710))
- **Spring-contact actuators**: Vybronics VC0820K001L (ERM, 8 × 2 mm, spring contacts, adhesive) exists
  today; spring-contact **LRAs** are quoted as custom by TSL/INEED; spring-contact micro-speakers exist
  only at 15 × 11 and 16 × 9 mm (PUI/Same Sky Slim-Line, 0.7 W, 8 Ω, 3.0–3.5 mm tall) — too big for the
  Ø10 pocket. ([Vybronics](https://www.vybronics.com/coin-vibration-motors/with-brushes/v-c0820k001l), [Mouser Slim-Line](https://www.mouser.in/new/pui-audio/pui-slim-line-micro-speakers))
- **Cells with plugs**: SparkFun 40 mAh JST-SH (PRT-25270) and TinyCircuits 40 mAh "micro JST SH" ($3.49,
  sold out at snapshot) mate an SM02B-SRSS-TB directly; dimensions **[UNVERIFIED — "about half an inch
  square", so ~13 × 13 mm, thicker than the 3 × 10 × 12 mm 301012 pocket]**.
- **PCBA house soldering wires**: PCBWay advertises "cable and harness assembly, electro-mechanical
  assembly" (trade press, 2023); JLCPCB only shows cables as library parts with "Wave Soldering" — no
  harness service surfaced **[UNVERIFIED]**. Worth asking PCBWay for a quote that includes the 3 pigtails.

## C. Recommendations

### C1. Solderless stage-0 kit (exact SKUs)

| # | Part | SKU | USD |
|---|---|---|---|
| 1 | XIAO ESP32S3 Sense, **pre-soldered** | Seeed 102010635 | 14.90 (Seeed) – 19.95 (US) |
| 2 | Expansion Board Base for XIAO | Seeed 103030356 / Adafruit 5033 | 17.95 |
| 3 | Grove Haptic Motor (DRV2605L + ERM) → base Grove-I²C | Seeed 105020011 | ~7.50 (£5.90) |
| 4 | LIS3DH STEMMA QT → daisy-chained from the Grove→QT cable | Adafruit 2809 | 4.95 |
| 5 | Grove → STEMMA QT cable | Adafruit 4528 (or SparkFun PRT-15109) | 1.95 |
| 6 | STEMMA QT 50 mm cable (2809 ← Grove Haptic has Grove only → use 2 × 4528 instead) | Adafruit 4528 ×2 total | +1.95 |
| 7 | LiPo 100 mAh JST-PH | Adafruit 1570 | 5.95 |
| 8 | Alligator-to-male jumper set (INT1 → base header D8; battery divider) | Adafruit 3255 | 7.95 |
| 9 | Male-male jumpers + 2 × 100 kΩ + 100 nF on the base header (battery %, optional) | any | ~2 |
| | **Total** | | **≈ $65–72**, zero solder joints |

Firmware deltas this kit implies: `drv2605_init(false)` (ERM); an LIS3DH driver variant (WHO_AM_I 0x33)
or accept polling with `PIN_IMU_INT -1`; `PIN_HAPTIC` unused (base SD-CS on D2 is harmless with no card).
Button D1 and buzzer D3 need **no** change. Speaker: defer to stage 1 or 5 joints at a makerspace.
Second-best accelerometer if the firmware stays LIS2DW12-only: none with QT exists — keep the current
AliExpress LIS2DW12 module plus 5 alligator clips.

### C2. Stage-1 connector set + PCBA plan

1. **Fab/assembly**: JLCPCB **Standard PCBA**, double-sided, 5 pcs, 1:1 DSBGA apertures; consign
   ESP32-S3-MINI-1U-N4R2 and TPS22916CYFPR (not in LCSC); everything else from LCSC. Budget ≈ $330–420.
   Get a parallel PCBWay quote and ask them to price "attach 3 supplied pigtails" (B3).
2. **Connectors (top side, ≤ 1.6 mm)**: 3 × **Molex 78171-0002 Pico-EZmate** for cell (J1), LRA (M1),
   speaker (SPK1), with 36920-0201 / 68801-4146 pigtails; fallback **JST BM02B-ACHSS-GAN-ETF** (1.4 mm)
   with ASACHSACH28W jumpers cut in half if Pico-EZmate stock stays at zero. Floorplan impact: ~5 × 2.6 mm
   each on an already full top side — `floorplan.py` must re-check against U1/FPC1/SW1 before this is
   adopted; if it does not fit, keep J1/M1/SPK1 as wire pads and let the assembler solder the pigtails
   (consigned, "wave soldering" line item — confirm with the quote).
3. **Charging pads**: keep PAD1w/PAD2w as pads; prefer option (a) FPC tail soldered by the assembler, or
   the 842AR silver pen for the two low-current band joints as the owner-side fallback.
4. **Off-board parts**: LRA and speaker stay wire-lead parts (no connectorised stock exists) — their
   leads go to the pigtail's bare end: makerspace/cable-shop job, 4 joints, or spring-contact ERM
   VC0820K001L against gold pads if LRA feel is negotiable. Cell: 40 mAh JST-SH cell *if* the pocket is
   deepened (dims unverified), else 301012 leads joined to the pigtail (2 joints).
5. **Fix now**: FPC1 manufacturer/actuator text (Amphenol FCI, slider ZIF, F32D if back-flip is really
   wanted); add LCSC C-numbers C2871910 / C189624 / C910544 to `stage1-ring.csv`.

Residual joints for the owner: **stage 0: 0** (speaker deferred); **stage 1: 0 on the board, 4–6 at
the pigtail/part junctions unless a cable shop or spring-contact parts take them.**
