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
| Camera power (TPS22916 ON) | 21 | RTC GPIO, no boot-time activity, hold-capable in deep sleep; 100 kΩ pull-down keeps the camera off while the pin floats. Switches CAM_3V3 (DOVDD) → 2.8 V AVDD + 1.2 V DVDD LDOs; cuts the 3 mA camera sleep current. *(was 19)* |
| RGB LED data | 43 (TXD0) | WS2812B-2020 via 100 Ω. UART0 TX is free because logging is USB-CDC; ROM boot output on TXD0 only reaches a power-gated LED. *(was 20)* |
| RGB LED power (TPS22916 ON) | 44 (RXD0) | net `LED_PWR_EN`, 4.7 kΩ pull-down — **hardware only for now**: firmware needs a `PIN_RGB_PWR 44` driven high before LED writes (an un-gated WS2812 idles at ~0.6–1 mA, 20× the whole standby budget) |
| USB D-/D+ | 19 / 20 | native USB kept for USB-CDC logging/flashing → test pads `TP_USB_DM` / `TP_USB_DP` (+ `TP_GND`); nothing else on these pins |
| Charger /CHG | — | test pad `TP_nCHG` only; no free GPIO (`battery_charging()` stays false) |

Reserved: 0 (boot, test pad + optional button), 3 (JTAG strap, fine as output after boot), 45/46 (straps, left
floating), 26-32 (flash/PSRAM), 33-37 (OPI PSRAM on R8 parts — avoid on MINI-1 N4R2 too). With the table above
all 31 exposed, non-strap, non-PSRAM GPIOs of the MINI-1U are used — see `hardware/electrical/`.

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
