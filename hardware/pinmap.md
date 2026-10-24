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
| RGB LED data | 43 (TXD0) | WS2812B-2020 via 1 kΩ. UART0 TX is free because logging is USB-CDC; ROM boot output on TXD0 only reaches the power-gated LED through the 1 kΩ. *(was 20)* |
| RGB LED power (TPS22916 ON) | 33 | `PIN_RGB_PWR`, net `LED_PWR_EN`, 4.7 kΩ pull-down; rail is **3V3 → VLED**. Firmware must drive it high before LED writes and low before deep sleep (an un-gated WS2812 idles at ~0.6–1 mA, 20× the whole standby budget) — feedback.cpp now does both (rgb_rail). *(was 44/RXD0, whose ROM-enabled pull-up fought the pull-down at every reset)* |
| Haptic | — (`PIN_HAPTIC -1`) | DRV2605L **EN tied to 3V3**; the driver is controlled over I²C only (RTP amplitude + register STANDBY, < 4 µA idle). With EN on a GPIO the firmware held EN low until after `drv2605_init()`, and the DRV2605L does not answer register reads in shutdown → "not found". Stage 0 is unaffected (the Adafruit breakout ties EN high). |
| Charger /CHG | 3 | `PIN_CHG`, BQ25100 open drain, active low while charging, 100 kΩ pull-up, also on test pad `TP_nCHG`. Input only (IO3 is the JTAG_SEL strap, inert unless the eFuse is burned). `battery_charging()` should read it — firmware follow-up. |
| USB D-/D+ | 19 / 20 | native USB kept for USB-CDC logging/flashing → test pads `TP_USB_DM` / `TP_USB_DP` (+ `TP_GND`); nothing else on these pins |
| Spare | 34, 35, 36, 37, 44 (RXD0) | unconnected on v1, free for an optional add-on (e.g. the MAX98357A I²S speaker placeholders in `config_audio.h`: BCLK/LRCLK/DOUT/SD). IO44 carries the ROM's reset pull-up; prefer 34–37 for anything that must idle low. |

Reserved: 0 (boot, test pad + optional button), 45/46 (straps, left floating), 26 (SPICS1 = chip select of the
in-package quad PSRAM on the N4R2 → NC). IO33–37 are **not** PSRAM pins on the N4R2: only the octal-PSRAM R8
parts route SPIIO4–7/SPIDQS to them (ESP-IDF GPIO guide for ESP32-S3; module datasheet footnote to re-check).
31 of the 36 exposed, non-strap GPIOs of the MINI-1U are used, 5 are spare — see `hardware/electrical/`.

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
