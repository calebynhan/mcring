# Stage-1 schematic notes (mcring v1)

Written as a netlist-level description so it can be entered into KiCad quickly. Values are
starting points; verify against each datasheet.

## Power

* **Battery**: 1S LiPo 30–40 mAh with PCM. `BAT+` → charger `BAT`, → system via the buck.
* **Charger**: TI BQ25100 (DSBGA-6). `IN` from the two charging pads (5 V from the pogo
  cradle), `ISET` resistor for **35 mA** (≈1C for a 40 mAh cell; R = 340 Ω·… use TI's formula,
  ≈ 10 kΩ class), `PRETERM` pin for 1 mA termination, `/CHG` → MCU GPIO (status flag
  `charging`). 1 µF on IN and BAT. TVS (PESD5V0) on the pads.
* **3.3 V rail**: TPS62840 buck (60 nA IQ, 750 mA) — or TLV75533 LDO if you accept the
  dropout at 3.4 V battery. 10 µF in/out, 2.2 µH inductor (buck).
* **Camera rail**: TPS22916 load switch from 3.3 V (`EN` = `PIN_CAM_PWR`) feeding (a) the
  camera 3.3 V/IO pin and (b) a 2.8 V LDO (XC6206P282) for the sensor AVDD. Camera sleep
  current then drops to the load-switch leakage (~10 nA).
* **Decoupling**: ESP32-S3-MINI-1U: 10 µF + 0.1 µF at 3V3; bulk **100 µF** low-ESR ceramic
  or 220 µF tantalum near the module to absorb the 300 mA capture/radio peaks on a small cell.

## MCU

* ESP32-S3-MINI-1U-N4R2. `EN` 10 kΩ pull-up + 1 µF to GND. `GPIO0` boot strap with a test
  pad. `GPIO45/46` straps left floating (internal defaults) — do **not** reuse.
* Native USB on `GPIO19/20` to a 6-pin test-pad footprint (or USB-C if the band allows);
  600 Ω common-mode choke optional.
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
| DRV2605L | 0x5A | `OUT+/OUT-` → LRA; `EN` → `PIN_HAPTIC` (or tie high and use I²C standby) |
| LIS2DW12 | 0x18 (SA0 = GND) | `INT1` → `PIN_IMU_INT` (RTC-capable GPIO7); 0.1 µF VDD |

## Outputs

* WS2812B-2020 data from `PIN_RGB` through 100 Ω; 0.1 µF at the LED. Window: 1.0–1.5 mm of
  white resin, LED set back ≥ 1 mm from the wall for diffusion.
* Piezo sounder between `PIN_BUZZER` and GND (or bridge-drive from two GPIOs for +6 dB).
* Aux (air-puff experiment): `PIN_AUX` → enable of a boost (e.g. TPS61040 to 15 V) + a
  half-bridge driving the Murata MZB1001T02 at ~26 kHz (LEDC can generate the carrier on a
  second pin; gate the carrier with `PIN_AUX`).

## Inputs

* Side switch Omron B3U-3000P between `PIN_BUTTON` and GND (internal pull-up, firmware
  debounce; add 100 nF if the lead is long).
* Touch pad: a 3 × 4 mm copper area on the top face to `PIN_TOUCH` via 1 kΩ; keep a ground
  hatch around it, none under it.
* Battery sense: 100 kΩ / 100 kΩ divider from BAT+ to `PIN_BATTERY_ADC` with 100 nF
  (BATTERY_DIVIDER = 2.0). High-value divider keeps the drain at ~20 µA; or gate it with
  a P-FET from `PIN_CAM_PWR` and read it only during captures.

## Mechanical

* Board outline: the OpenSCAD model (`enclosure/mcring_stage1.scad`) carries a 24 mm
  cavity for a flat rigid board plus a pod for the camera lens. Thinnest stack is
  battery (3 mm) → board (0.6 mm) → components (≤ 2.6 mm on the module side).
