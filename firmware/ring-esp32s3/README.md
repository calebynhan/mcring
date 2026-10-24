# mcring firmware (ESP32-S3)

Firmware for the ring's microcontroller. Stage 0 runs unmodified on a **Seeed XIAO ESP32S3 Sense**
(OV2640 camera + PDM mic on the Sense expansion board); stage 1 targets the custom `mcring_v1`
board with the same code and a different pin map (`src/config.h`).

> Stage 2 (Oura-size) will not use an ESP32-S3 — see `docs/04-feasibility-and-risks.md`. The
> protocol and the shared C libraries in `lib/` are MCU-agnostic and carry over to the nRF52
> port in `firmware/ring-nrf52840/`.

## Build & flash

```bash
pip install platformio
cd firmware/ring-esp32s3
pio run -e xiao_esp32s3_sense -t upload      # hold B, tap R if the port is not found
pio device monitor -b 115200
pio test -e native                           # host tests for Morse / CRC / ADPCM / packets
```

If you prefer the Arduino core 3.x, replace `platform = espressif32@6.9.0` with
`platform = https://github.com/pioarduino/platform-espressif32/releases/download/stable/platform-espressif32.zip`.
The code uses only APIs that exist in both (LEDC, legacy I2S, NimBLE 2.x, esp_camera).

## Wiring for the XIAO ESP32S3 Sense (stage 0 bench rig)

| Signal | XIAO pin | Part |
|---|---|---|
| Button → GND | D1 (GPIO2) | any tactile switch (internal pull-up) |
| Haptic | D2 (GPIO3) | N-MOSFET gate for an 8 mm LRA/ERM, **or** leave for DRV2605L EN |
| Buzzer | D3 (GPIO4) | piezo sounder (optional) |
| I²C SDA / SCL | D4 / D5 (GPIO5/6) | DRV2605L breakout (0x5A) + LIS2DW12 breakout (0x18) |
| IMU INT1 | D8 (GPIO7) | LIS2DW12 INT1 |
| Touch pad | D9 (GPIO8) | a copper pad / wire (optional) |
| Aux | D10 (GPIO9) | air-puff / extra actuator driver enable (optional) |
| Battery sense | A0 (GPIO1) | 2:1 divider from BAT+ (optional; else battery shows unknown) |

The on-board user LED (GPIO21) is the light channel. Everything except the button is optional:
missing I²C devices are detected at boot and the corresponding status flags are cleared.

## Behaviour

| Action | Result |
|---|---|
| Short press / double-tap / touch | capture a JPEG (default QVGA q12, ~8–15 KB) → `<SN>` blink → queue → send over BLE |
| Long press (≥ 700 ms) | capture, then record a voice question while held (≤ 5 s), send both |
| Phone `CAPTURE` | same as short press |
| Phone `MORSE_TEXT` / `MORSE_UNITS` / `PATTERN` | play on LED / haptic / buzzer / aux |
| Disconnected & idle for `idle_sleep_s` | deep sleep (~10 µA + peripherals); wake on button (EXT0) or IMU INT (EXT1) — the wake itself triggers a capture |

Captures made while disconnected are kept in PSRAM (up to 3) and sent when a phone connects.

## Module map

```
src/main.cpp        state machine, control/feedback dispatch
src/ble_link.*      NimBLE GATT server (protocol/ble-gatt.md), MTU/PHY/conn-param negotiation, TX credits
src/transfer.*      START / chunks / END / ACK-with-missing-list retransmit, capture queue
src/camera_mod.*    esp_camera init-per-shot (power), JPEG copy-out
src/trigger.*       button debounce + long press, LIS2DW12 double tap, capacitive touch
src/feedback.*      non-blocking ON/OFF pattern player on 4 channels; MORSE_UNITS reassembly
src/drv2605.*       DRV2605L RTP mode (LRA), autocal
src/imu_lis2dw12.*  LIS2DW12 double-tap on INT1
src/audio_mod.*     PDM mic → PCM → IMA-ADPCM
src/power.*         battery ADC, idle deep sleep, EXT0/EXT1 wake
src/settings.*      NVS-persisted config (SET_CONFIG keys)
lib/mcring_proto    opcodes, packet encoders, CRC-32        (shared with python/mcring_core)
lib/mcring_morse    Morse → unit pattern encoder            (byte-identical to Python)
lib/mcring_adpcm    IMA ADPCM encoder                       (byte-identical to Python)
```

## Power notes for the dev kit

The XIAO Sense camera board is not power-gated, so deep-sleep current is ~3 mA with the
camera board attached (vs ~60 µA without). For real battery tests either unplug the Sense
board between shots or add a load switch and set `PIN_CAM_PWR` (done on `mcring_v1`).

## Known limitations / TODO

* Phone-initiated `RECORD_AUDIO` stops only at the max length (no VAD).
* No OTA yet; flash over USB.
* NimBLE `onStatus` TX-credit callback is used opportunistically; a 50 ms timeout refills
  credits if the stack never calls it, so throughput is safe but may be below optimum.
* Touch threshold is a fixed +25 % over a slow-tracking baseline; tune on the real pad.
