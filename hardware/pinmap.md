# Pin maps

## Stage 0 — Seeed XIAO ESP32S3 Sense (`-DBOARD_XIAO_ESP32S3_SENSE`)

| Function | GPIO | XIAO label | Notes |
|---|---|---|---|
| Camera XCLK | 10 | (Sense B2B) | 20 MHz |
| Camera SIOD / SIOC | 40 / 39 | (Sense) | SCCB |
| Camera D0..D7 | 15,17,18,16,14,12,11,48 | (Sense) | Y2..Y9 |
| Camera VSYNC / HREF / PCLK | 38 / 47 / 13 | (Sense) | |
| PDM mic CLK / DATA | 42 / 41 | (Sense) | I2S0 PDM RX |
| Battery sense | 1 | A0 / D0 | optional 2:1 divider from BAT+ |
| Button | 2 | D1 | to GND; internal pull-up; EXT0 wake |
| Haptic GPIO | 3 | D2 | MOSFET gate / DRV2605 EN |
| Buzzer | 4 | D3 | LEDC tone |
| I²C SDA / SCL | 5 / 6 | D4 / D5 | DRV2605L 0x5A, LIS2DW12 0x18 |
| IMU INT1 | 7 | D8 | EXT1 wake (any-high) |
| Touch pad | 8 | D9 | touch channel T8 |
| Aux actuator | 9 | D10 | air-puff driver enable |
| User LED | 21 | — | active low; shared with Sense SD CS (SD unused) |

## Stage 1 — mcring v1 (`-DBOARD_MCRING_V1`)

Same logical map on an ESP32-S3-MINI-1U / NanoS3, plus:

| Function | GPIO | Notes |
|---|---|---|
| Camera power (load switch EN) | 19 | TPS22916 → 2.8 V LDO + 3.3 V to camera; cuts the 3 mA camera sleep current |
| RGB LED data | 20 | WS2812B-2020 / XL-1010RGBC |
| USB D-/D+ | 19/20 are **not** usable if native USB is kept — move to 45/46 or drop USB CDC in production | choose at layout time |

Reserved: 0 (boot), 3 (JTAG strap, fine as output after boot), 45/46 (straps), 26-32 (flash/PSRAM),
33-37 (OPI PSRAM on R8 parts — avoid on MINI-1 N4R2 too).

## Stage 2 — nRF52840 (planning)

| Function | nRF pin class | Notes |
|---|---|---|
| Camera D0..D7, PCLK, HREF, VSYNC | 11 GPIO, same port | bit-bang capture (PCLK polled or PPI/GPIOTE → SPIS trick in 1-bit mode for HM01B0) |
| Camera SCCB | TWIM0 | |
| Camera XCLK | GPIOTE+TIMER or PWM0 | 6–12 MHz |
| IMU INT1 | GPIOTE (sense wake) | System OFF wake |
| Haptic driver | TWIM0 (shared) | DRV2624 |
| LED | PWM1 / bit-bang WS2812 via PWM sequence | |
| Mic PDM | PDM peripheral (native) | |
| Charger status / battery | SAADC | |
