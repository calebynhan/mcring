# mcring firmware (ESP32-S3)

Firmware for the ring's microcontroller. Stage 0 runs unmodified on a **Seeed XIAO ESP32S3 Sense**
(OV2640 camera + PDM mic on the Sense expansion board); stage 1 targets the custom `mcring_v1`
board with the same code and a different pin map (`src/config.h` + `src/config_audio.h`).

mcring is **voice-first**: hold the button (or double-tap) → ask a question, with or without a
photo → hear the answer. The phone does speech-to-text / Claude / text-to-speech and plays the
answer through the user's own Bluetooth headphones (normal phone audio routing — the ring never
pairs to headphones). On the stage-1 oversized ring an **on-ring speaker** (MAX98357A + 10 mm
driver) can play the answer instead: the phone streams ADPCM to the ring over BLE.
Morse output is no longer part of the product; the pattern player and `MORSE_*` opcodes are kept
as an optional, off-by-default "silent pattern" capability (see `protocol/morse.md`).

> Stage 2 (Oura-size) will not use an ESP32-S3 — see `docs/04-feasibility-and-risks.md`. The
> protocol and the shared C libraries in `lib/` are MCU-agnostic and carry over to the nRF52
> port in `firmware/ring-nrf52840/`.

## Build & flash

```bash
pip install platformio
cd firmware/ring-esp32s3
pio run -e xiao_esp32s3_sense -t upload      # hold B, tap R if the port is not found
pio device monitor -b 115200
pio test -e native                           # host tests for packets / events / audio-out / CRC / ADPCM / Morse
```

If you prefer the Arduino core 3.x, replace `platform = espressif32@6.9.0` with
`platform = https://github.com/pioarduino/platform-espressif32/releases/download/stable/platform-espressif32.zip`.
The code uses only APIs that exist in both (LEDC, legacy I2S, NimBLE 2.x, esp_camera).

Without the ESP32 toolchain you can still syntax-check the firmware against minimal header
stubs (`g++ -fsyntax-only` per `src/*.cpp`, see the repo's CI notes).

## Wiring for the XIAO ESP32S3 Sense (stage 0 bench rig)

| Signal | XIAO pin | Part |
|---|---|---|
| Button → GND | D1 (GPIO2) | any tactile switch (internal pull-up) |
| Haptic | D2 (GPIO3) | N-MOSFET gate for an 8 mm LRA/ERM, **or** leave for DRV2605L EN |
| Buzzer | D3 (GPIO4) | piezo sounder (optional; "beep" cues) |
| I²C SDA / SCL | D4 / D5 (GPIO5/6) | DRV2605L breakout (0x5A) + LIS2DW12 breakout (0x18) |
| IMU INT1 | D8 (GPIO7) | LIS2DW12 INT1 |
| Touch pad | D9 (GPIO8) | a copper pad / wire (optional) |
| Battery sense | A0 (GPIO1) | 2:1 divider from BAT+ (optional; else battery shows unknown) |
| **Speaker I2S LRC** | D6 (GPIO43) | MAX98357A `LRC` |
| **Speaker I2S BCLK** | D7 (GPIO44) | MAX98357A `BCLK` |
| **Speaker I2S DIN** | D10 (GPIO9) | MAX98357A `DIN` |

The on-board user LED (GPIO21) is the light channel. Everything except the button is optional:
missing I²C devices are detected at boot and the corresponding status flags are cleared.

### No-solder wiring (XIAO in the Expansion Board Base) — `pio run -e xiao_esp32s3_sense_base`

For an owner who does not want to solder, the same firmware runs the **pre-soldered** XIAO ESP32S3
Sense (Seeed 102010635) seated in Seeed's **Expansion Board Base for XIAO** (103030356 / Adafruit
5033). Drawing and connection table: `hardware/pcb/wiring_stage0_solderless.md`; kit:
`hardware/bom/stage0-devkit-solderless.csv`; step-by-step: `docs/07-build-guide.md` §1.12.

| Signal | Where it comes from | Note |
|---|---|---|
| Button → GND | **the base's user button**, already on D1 (GPIO2) | nothing to wire |
| Buzzer | **the base's passive buzzer**, already on A3 = D3 (GPIO4) | nothing to wire |
| Haptics | **Grove – Haptic Motor** (Seeed 105020011) in Grove I²C socket #1 | DRV2605L 0x5A + factory-attached **ERM** → `HAPTIC_MOTOR_LRA 0`; EN tied on-module |
| IMU | **LIS3DH STEMMA QT** (Adafruit 2809 / SparkFun SEN-29529) via a Grove→STEMMA QT cable (Adafruit 4528) in Grove I²C socket #2 | WHO_AM_I 0x33; `imu_init()` picks the LIS2DW12 or LIS3DH back-end at boot (`src/imu_lis3dh.cpp`) |
| IMU INT1 | LIS3DH `INT` hole → male-male jumper → base breakout header **D8** (GPIO7) | press-fit / hammer-header pin / IC hook on the breakout side. **Optional**: the build polls the latched click source every 25 ms (`IMU_POLL_MS`); only tap-to-wake from deep sleep needs the wire |
| Battery | LiPo **≥ 400 mAh** JST-PH into the base's JST 2.0 socket | the base charges at ≤ 460 mA (too fast for the 100 mAh ring cell). No A0 divider → `batt` reads 255 % (unknown) |
| Speaker (optional) | MAX98357A breakout: `BCLK`/`LRC`/`VIN`/`GND` from the base's **Grove UART** socket (D7/D6/3V3/GND) through a Grove-to-jumper cable, `DIN` from breakout header D10, `SD` → `VIN` | the amp's 7 header holes are the one unsoldered thing on the kit: press-fit pins, 5 joints at a makerspace, or defer to stage 1 |

`-DMCRING_XIAO_BASE` (`src/config_audio.h`) restates `PIN_BUTTON`/`PIN_BUZZER` at the base's pins (today
identical to the stock map), parks `PIN_HAPTIC` (D2 = the base's microSD chip-select), selects the ERM
drive profile and enables tap polling; `BOARD_NAME` becomes `xiao-esp32s3-sense+base` so the boot log
says which build is running. Leave the base's microSD slot empty (SPI on D8/D9/D10) and never plug a
UART Grove *device* into the UART socket (D6/D7 are I²S). Not verified from the base's schematic: whether
its charger output reaches the XIAO's `BAT` pads or only the 5V/VIN pin — the XIAO's own `BAT` pads are
unused either way.

### Speaker (optional, `HAS_SPEAKER`)

Adafruit-style **MAX98357A** I2S class-D breakout + **8 Ω 10 mm speaker**:

| MAX98357A pin | Connect to | Note |
|---|---|---|
| `VIN` | 3V3 (or VBAT) | 2.5–5.5 V; ~2.4 mA idle, up to ~1 W into 8 Ω at 5 V |
| `GND` | GND | |
| `BCLK` | D7 (GPIO44) | 512 kHz at 16 kHz / 16-bit / 2 slots |
| `LRC` | D6 (GPIO43) | 16 kHz word clock |
| `DIN` | D10 (GPIO9) | |
| `SD` | leave open / tie high | shutdown & channel select. Open/high is fine: the ring sends the same sample on L and R, so any mode plays mono. Wire it to a spare GPIO and set `PIN_SPEAKER_EN` to cut the idle current |
| `GAIN` | open (9 dB) or GND (12 dB) | set the loudness ceiling; software volume (`SPEAKER_VOLUME` × stream volume) scales below it |
| `+ / –` | speaker | |

Pin notes (all in `src/config_audio.h`): the XIAO header has only 11 GPIOs, so the speaker
reuses **D6/D7 (UART0 TX/RX — free because logging is USB-CDC)** and **D10, which was the aux
"air-puff" output (`PIN_AUX` is now -1 on the XIAO)**. The ROM bootloader prints its banner on
GPIO43 at reset; on LRC that is a few garbage frames without BCLK — inaudible. On `mcring_v1`
the three I2S pins are `-1` placeholders until the hardware pass assigns them, so `SPEAKER_OK`
stays clear there.

The I2S driver (`I2S_NUM_1`, 16 kHz, 16-bit, standard Philips I2S) is installed only while a
stream is playing. The mono stream is duplicated into both slots in software rather than using
the driver's TX "only left" mono mode, which behaves differently across ESP32 variants and IDF
4.4 point releases (see `src/audio_out.cpp`). The PDM mic stays on `I2S_NUM_0`.

## Behaviour

| Action | Events (0007) | Result |
|---|---|---|
| Press button | `BUTTON_DOWN` | phone-mic mode: the phone starts recording |
| Short press (< 700 ms) / touch | `BUTTON_UP(held)` / `TOUCH`, `CAPTURE_STARTED`, `CAPTURE_DONE(queued)` | capture a JPEG (default QVGA q12, ~8–15 KB) → queue → send over BLE |
| **Hold ≥ 700 ms ("ask")**, ring mic (`MIC_SOURCE_HINT=0`, default) | `CAPTURE_*`, `REC_STARTED(max s)`, on release `BUTTON_UP(≥ 7)`, `REC_STOPPED(tenths)` | photo (~150–400 ms, blocking) → listening tick → record while held (≤ 8 s) → send JPEG + ADPCM. The tick marks the start of recording (≈ 0.85–1.1 s after the press): speak after it |
| **Hold ≥ 700 ms ("ask")**, phone mic (`MIC_SOURCE_HINT=1`) | `BUTTON_DOWN` … `BUTTON_UP(held ≥ 7)` | listening tick only; the phone records and sends `CAPTURE` itself if it wants a photo. The ring's ask session ends on release, a second double tap, `RECORD_STOP`/`ABORT`, or 8.5 s after a double tap |
| Double tap | `DOUBLE_TAP` | hands-free "ask": like a long press that ends by itself (ring mic: ≤ 8 s or `RECORD_STOP`; a second double tap ends it) |
| Phone `CAPTURE` | `CAPTURE_*` | same as short press (also allowed during a phone-mic "ask") |
| Phone `RECORD_START` / `RECORD_STOP` | `REC_STARTED` / `REC_STOPPED` | ring-mic recording under phone control (≤ 8 s) |
| Phone `CUE n` (Feedback 0006) | – | built-in cue: 1 listening tick, 2 answer-ready double tick, 3 error buzz, 4 ok — on the channels in `CUES_MASK` |
| Phone `AUDIO_START/DATA/END/STOP` (0008) | `AUDIO_UNDERRUN`, `AUDIO_DONE(0 drained / 1 stopped)` | buffer ≥ 24 ADPCM blocks (~400 ms) → decode → I2S speaker; `AUDIO_START` on a board without a speaker answers `AUDIO_DONE(1)` at once |
| Battery < 15 % | `LOW_BATTERY(pct)` | once; re-armed above 20 % |
| Phone `MORSE_TEXT` / `MORSE_UNITS` / `PATTERN` | – | legacy pattern player on LED / haptic / buzzer (still works, nothing sends it by default) |
| Disconnected & idle for `idle_sleep_s` | – | deep sleep (~10 µA + peripherals); wake on button (EXT0 → the trigger logic decides short/long press) or IMU tap (EXT1 → hands-free "ask", sent on reconnect) |

Captures and clips made while disconnected are kept in PSRAM (up to 3 items) and sent when a
phone connects. Events are not queued across disconnects.

Haptics are confirmation cues only: **listening** (1 tick), **answer ready** (2 ticks),
**error** (420 ms buzz). `SET_CONFIG CUES_MASK` (key 10) picks haptic / LED / beep; the app
sends `CUE 2` when the answer arrives, whichever output path plays it.

## Module map

```
src/main.cpp        state machine, control/feedback dispatch, "ask" session, event emission
src/ble_link.*      NimBLE GATT server (protocol/ble-gatt.md), MTU/PHY/conn-param negotiation, TX credits,
                    Events notify, Audio-out writes → audio_out queue (BLE task)
src/transfer.*      START / chunks / END / ACK-with-missing-list retransmit, capture queue
src/camera_mod.*    esp_camera init-per-shot (power), JPEG copy-out
src/trigger.*       button debounce + short/long press, LIS2DW12 double tap, capacitive touch
src/cues.*          listening / answer-ready / error / ok cues honouring CUES_MASK
src/feedback.*      non-blocking ON/OFF pattern player on 4 channels; MORSE_UNITS reassembly (legacy)
src/audio_out.*     ADPCM block queue → decoder → volume → I2S1 TX (MAX98357A); prebuffer, underrun, drain
src/audio_mod.*     PDM mic → PCM → IMA-ADPCM (I2S0)
src/drv2605.*       DRV2605L RTP mode (LRA, or ERM with HAPTIC_MOTOR_LRA 0), autocal
src/imu_lis2dw12.*  LIS2DW12 double-tap on INT1 (imu_* API header; the .cpp is compiled through imu_lis3dh.cpp)
src/imu_lis3dh.*    LIS3DH double-click on INT1 (latched) + run-time dispatch of the imu_* API between the two chips
src/power.*         battery ADC, idle deep sleep, EXT0/EXT1 wake
src/settings.*      NVS-persisted config (SET_CONFIG keys 1..11)
src/config.h        board pin maps + behavioural defaults;  src/config_audio.h  speaker pins, cue/mic defaults
lib/mcring_proto    opcodes, events, packet encoders/decoders, CRC-32   (shared with python/mcring_core, app/src/lib/proto.ts)
lib/mcring_adpcm    IMA ADPCM encoder + decoder                         (byte-identical to Python)
lib/mcring_morse    Morse → unit pattern encoder (legacy)               (byte-identical to Python)
```

## Power notes for the dev kit

The XIAO Sense camera board is not power-gated, so deep-sleep current is ~3 mA with the
camera board attached (vs ~60 µA without). For real battery tests either unplug the Sense
board between shots or add a load switch and set `PIN_CAM_PWR` (done on `mcring_v1`).
The MAX98357A idles at ~2.4 mA unless its `SD` pin is driven (`PIN_SPEAKER_EN`); the I2S
peripheral itself is only clocked while a stream plays.

## Known limitations / TODO

* Ring-mic recording stops at the 8 s cap or on `RECORD_STOP` / button release (no VAD).
* A camera capture blocks `loop()` for 150–400 ms; a speaker stream playing at the same time
  will underrun (silence + `AUDIO_UNDERRUN`) and resume. Avoid `CAPTURE` while streaming.
* Audio-out drops blocks (counted, logged) if the phone runs more than ~40 blocks ahead of real
  time; pace at 1 block / 16 ms after the initial burst.
* No OTA yet; flash over USB.
* NimBLE `onStatus` TX-credit callback is used opportunistically; a 50 ms timeout refills
  credits if the stack never calls it, so throughput is safe but may be below optimum.
* Touch threshold is a fixed +25 % over a slow-tracking baseline; tune on the real pad.
