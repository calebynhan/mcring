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
| I²S DIN → speaker amp (optional) | 9 | D10 | MAX98357A breakout DIN. **Was `PIN_AUX`** (air-puff driver enable): the XIAO header has exactly 11 GPIOs and the speaker is the voice-first priority, so `config_audio.h` reassigns D10 and undefines `PIN_AUX` (−1) on the dev kit |
| I²S LRCLK → speaker amp (optional) | 43 | D6 / TX | MAX98357A LRC. UART0 TXD0 is free because logging is USB-CDC; the ROM banner on GPIO43 for ~50 ms at reset is a few garbage frames without BCLK — inaudible |
| I²S BCLK → speaker amp (optional) | 44 | D7 / RX | MAX98357A BCLK (512 kHz at 16 kHz). UART0 RXD0, same argument |
| Speaker amp SD / VIN | — | 3V3 | breakout `SD` → 3V3 (left-channel mode; or leave on the breakout's default pull-up = (L+R)/2 — the firmware duplicates mono into both slots), `VIN` → 3V3, `GAIN` open (9 dB); `PIN_SPEAKER_EN` = −1 on the dev kit (amp always on, ~2.4 mA) — `hardware/pcb/wiring_stage0.md` |
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
| Speaker amp power (TPS22916 ON) | 34 | `PIN_SPEAKER_EN`, net `AMP_PWR_EN`, 100 kΩ pull-down R20 (the camera-gate pattern); third TPS22916 (U11) switches **3V3 → VAMP** for the optional MAX98357A (U10). `SD_MODE` is tied to VAMP on the board (> 1.4 V = left-channel mode), so one GPIO is both power gate and amp enable and the amp draws nothing while it is low. `audio_out.cpp` already drives it high/low around a stream; while it is low IO35–37 must idle low (ESD back-feed into the unpowered amp; R22–R24 1 kΩ bound it to ≤ 2.6 mA per pin, so a pin left high is a battery drain, not damage) — firmware follow-up: park them after `i2s_driver_uninstall()` and before deep sleep |
| I²S BCLK (speaker, optional) | 35 | `PIN_I2S_BCLK`, net `I2S_BCLK` → R22 1 kΩ → U10 pin 16 (net `AMP_BCLK`); 32 × fs = 512 kHz at 16 kHz; no MCLK needed |
| I²S LRCLK (speaker, optional) | 36 | `PIN_I2S_LRCLK`, net `I2S_LRCLK` → R23 1 kΩ → U10 pin 14 (`AMP_LRCLK`); fs = 16 kHz |
| I²S DOUT (speaker, optional) | 37 | `PIN_I2S_DOUT`, net `I2S_DOUT` → R24 1 kΩ → U10 pin 1 DIN (`AMP_DIN`); mono samples duplicated into both slots, so the amp's channel mode is irrelevant |
| Spare | 44 (RXD0) | unconnected on v1. It carries the ROM's reset pull-up, which is why the speaker took 34–37 instead. |

Reserved: 0 (boot, test pad + optional button), 45/46 (straps, left floating), 26 (SPICS1 = chip select of the
in-package quad PSRAM on the N4R2 → NC). IO33–37 are **not** PSRAM pins on the N4R2: only the octal-PSRAM R8
parts route SPIIO4–7/SPIDQS to them (ESP-IDF GPIO guide for ESP32-S3; module datasheet footnote to re-check).
35 of the 36 exposed, non-strap GPIOs of the MINI-1U are used, 1 is spare — see `hardware/electrical/`. The
speaker group (U10, U11, their passives R20–R24 / C25–C26, the PUI AS01008MR-2-R in the signet's right wall) is
optional: leave it off the board and `HAS_SPEAKER` still compiles to 1 — the I²S pins then drive nothing. Board
gain is 3 dB (R21 = 100 kΩ): a full-scale sample at `SPEAKER_VOLUME` 255 is 0.25 W into the 8 Ω speaker, inside
its 300 mW rating; R21 = 0 Ω (6 dB, 0.5 W = the speaker's maximum) is the louder bench option.

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
