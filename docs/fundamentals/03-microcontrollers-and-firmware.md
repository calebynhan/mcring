# 3. Microcontrollers and firmware

This chapter is the hardware-facing half of `firmware/ring-esp32s3/`. Read it with `src/main.cpp`, `src/config.h` and whichever `src/*.cpp` module you are curious about open next to it. Sections 3.1–3.4 are the primitives every driver in `src/` uses (the chip, pins, buses, DMA); 3.5–3.6 are power and persistence; 3.7–3.8 are the toolchain and how to see inside a running ring; 3.9–3.11 are how the code is shaped and the C it is written in. Bluetooth has its own chapter (4).

Each section ends with "Check yourself"; the answers use the real numbers from `config.h`, `config_audio.h` and `protocol/ble-gatt.md`.

## 3.1 What a microcontroller is

**Why it matters in mcring.** The ring is an ESP32-S3 (stage 0/1) and will be an nRF52840 (stage 2); `docs/03-hardware-spec.md` §3.1 says the choice is decided by current, not by compute. `platformio.ini` picks the module (`seeed_xiao_esp32s3`, `qio_opi` memory, 8 MB flash) and `config.h` is nothing but a map of which pin does what. `camera_mod.cpp` and `audio_mod.cpp` ask for buffers in PSRAM (`MALLOC_CAP_SPIRAM`) because a QVGA JPEG and an 8 s voice clip do not fit comfortably in internal RAM.

**The concepts.** A microcontroller (MCU) is a CPU, RAM, flash and a set of peripherals (GPIO, timers, serial buses, ADC, radio) on one die, with no operating system required. The CPU talks to peripherals through memory-mapped registers: writing a word to an address flips pins or starts a transfer. The ESP32-S3 has two Xtensa LX7 cores at up to 240 MHz, 512 KB of internal SRAM, a 2.4 GHz radio (Wi-Fi + BLE 5), and on the XIAO module 8 MB of flash plus 8 MB of PSRAM behind an octal SPI bus. PSRAM is slower than internal RAM and sits behind the cache; the I2S DMA buffers live in internal RAM, big payloads (frames, clips) go to PSRAM, and `camera_capture` copies the JPEG into its own PSRAM buffer so the driver and its buffers can be torn down right away. The nRF52840 is one Cortex-M4F at 64 MHz, 256 KB RAM, 1 MB flash, a BLE radio and no camera interface at all; its radio peaks around 5 mA where the ESP32-S3 camera board peaks at 300+ mA (`docs/04`). Code runs from flash through a cache; anything that must run while the cache is off (interrupt handlers during a flash write, see 3.11) is placed in IRAM with `IRAM_ATTR`. Before `setup()` runs, a ROM bootloader loads a second-stage bootloader, which loads the app from the partition table (`default_8MB.csv`) and initialises `.data`/`.bss`; Memfault's "Zero to main()" walks through exactly that.

**Learn it.**

| Resource | Type | Time | Why this one |
|---|---|---|---|
| [Ben Eater: Build a 6502 computer](https://eater.net/6502) | video series | 10+ h | address/data buses, clocks, memory-mapped I/O and hardware interrupts built on a breadboard; after this, a datasheet register map reads like wiring |
| [Making Embedded Systems, 2nd ed. (Elecia White)](https://www.oreilly.com/library/view/-/9781098151539) | book | 15 h | the one book on shaping firmware: hardware/software boundary, state machines, debugging, doing maths without floats; companion code on [GitHub](https://github.com/eleciawhite/making-embedded-systems) |
| [ESP32-S3 Series Datasheet (PDF)](https://www.espressif.com/sites/default/files/documentation/esp32-s3_datasheet_en.pdf) | datasheet | 1 h skim | pin functions, RTC-capable GPIOs, strapping pins, sleep currents: the facts `config.h` and `hardware/pinmap.md` encode |
| [ESP32-S3 Technical Reference Manual (PDF)](https://www.espressif.com/sites/default/files/documentation/esp32-s3_technical_reference_manual_en.pdf) | manual | reference | the registers behind GPIO, LEDC, I2S, LCD_CAM, RTC; open the chapter when a driver's behaviour puzzles you |
| [nRF52840 Product Specification v1.8 (PDF)](https://infocenter.nordicsemi.com/pdf/nRF52840_PS_v1.8.pdf) | datasheet | 1 h skim | the stage-2 part: EasyDMA, PDM and SAADC peripherals, System OFF wake; compare its current table with the ESP32-S3's |
| [From Zero to main(): Bare metal C (Memfault Interrupt)](https://interrupt.memfault.com/blog/zero-to-main-1) | article series | 1 h | what happens before `setup()`: reset vector, `.data`/`.bss`, linker script; demystifies backtraces and `static` initialisation |

**Check yourself.**

1. An 8 s ring-mic clip is recorded as 16-bit PCM at 16 kHz before encoding. How many bytes does `audio_start_recording(8)` allocate, and why does it try `MALLOC_CAP_SPIRAM` first?
2. `camera_mod.cpp` copies the JPEG out of the driver's frame buffer and calls `esp_camera_deinit()` immediately. Name two things that buys.
3. Why does the stage-2 plan accept a slower 64 MHz Cortex-M4 for a camera ring?

<details><summary>Answers</summary>

1. 16,000 samples/s × 8 s = 128,000 samples × 2 bytes = 256,000 bytes (rounded up to a multiple of 256 samples, so exactly 256,000). That is half of all internal SRAM, so it goes to the 8 MB PSRAM; the `malloc` fallback is for boards without it.
2. The driver's DMA buffers (internal RAM) are freed, so up to `MAX_QUEUED_CAPTURES = 3` JPEGs can sit in PSRAM while the driver is gone, and the camera rail can be switched off (`PIN_CAM_PWR`) between shots, which is where the 3 mA-vs-60 µA sleep difference in the firmware README comes from.
3. Because the battery decides: a 16–22 mAh 1C cell delivers ~16–22 mA continuously; the nRF52840's ~5 mA radio peaks fit, the ESP32-S3's 300+ mA capture peaks do not. The ring only captures, compresses (on the sensor for OV2640) and ships bytes; it never needs 240 MHz.

</details>

## 3.2 GPIO, interrupts, timers and PWM

**Why it matters in mcring.** `trigger.cpp` reads the button on GPIO2 with the internal pull-up, debounces it over 30 ms and times the 700 ms long press; the LIS2DW12's INT1 on GPIO7 fires `imu_isr`, an interrupt that only sets a flag. `feedback.cpp` drives the LED and the piezo with LEDC PWM (channel 2 at 5 kHz, channel 3 as a 4 kHz tone) because channels 0/1 are taken by the camera's 20 MHz XCLK. `trigger.cpp` also polls the capacitive pad on GPIO8 with `touchRead()`, where ESP32-S3 values rise when touched.

**The concepts.** A GPIO is one pin configured as input (optionally with a pull-up/pull-down so it never floats) or output (push-pull or open-drain). A mechanical button bounces for a few ms, so firmware waits until the reading has been stable for `BUTTON_DEBOUNCE_MS` before believing it. An interrupt is the hardware calling a function of yours on an edge or level; the interrupt service routine (ISR) runs at any moment between two of your instructions, so it must be short, must not block, allocate or log, and must live in IRAM (`IRAM_ATTR`). The usual pattern, used for the IMU, is ISR sets a `volatile` flag, `loop()` reads it. Timers count clock ticks; `millis()` is a free-running 32-bit ms counter that wraps after 49.7 days, which is why every timeout in the code is written `now - t0 >= X` (unsigned subtraction wraps correctly) and the RGB-off deadline is compared as `(int32_t)(now - deadline) >= 0`. PWM switches a pin on and off at a fixed frequency and varies the duty cycle; an LED averages it to brightness, a piezo hears the frequency. The ESP32-S3's LEDC block has 4 timers and 8 channels; a timer sets frequency and resolution (bits), a channel binds a pin to a timer and holds the duty. Resolution and frequency trade off: `max_freq = source_clock / 2^bits`, so 8 bits at 80 MHz allows up to 312.5 kHz, while a 20 MHz XCLK leaves only 2 bits of duty. Capacitive touch is a charge/discharge counter per pad; a finger adds capacitance, and on the S3 that makes the count go up.

**Learn it.**

| Resource | Type | Time | Why this one |
|---|---|---|---|
| [ESP-IDF: GPIO & RTC GPIO (ESP32-S3, v4.4)](https://docs.espressif.com/projects/esp-idf/en/v4.4/esp32s3/api-reference/peripherals/gpio.html) | docs | 30 min | which pins are RTC-capable (wake sources), pull-ups, `gpio_isr_handler_add`; the v4.4 branch is what Arduino-ESP32 2.0.x wraps |
| [Arduino-ESP32: LED Control (LEDC) API](https://docs.espressif.com/projects/arduino-esp32/en/latest/api/ledc.html) | docs | 20 min | the `ledc*` calls `feedback.cpp` uses; note the 3.x API renames (`ledcAttach`) |
| [ESP-IDF: LED Control (LEDC) (ESP32-S3)](https://docs.espressif.com/projects/esp-idf/en/release-v5.1/esp32s3/api-reference/peripherals/ledc.html) | docs | 30 min | timers vs channels, duty-resolution maths, hardware fades; explains why the camera and the LED share a block |
| [ESP-IDF: Touch Sensor (ESP32-S3)](https://docs.espressif.com/projects/esp-idf/en/v4.4.7/esp32s3/api-reference/peripherals/touch_pad.html) | docs | 20 min | the "value increases when touched" note that `trigger.cpp` relies on; denoise channel, thresholds |
| [SparkFun: Pulse Width Modulation](https://learn.sparkfun.com/tutorials/pulse-width-modulation) | article | 15 min | duty cycle and frequency explained with LEDs and servos; the vocabulary the LEDC docs assume |
| [Wokwi ESP32 simulator](https://wokwi.com) | interactive | 30 min | run Arduino-ESP32 sketches (buttons, PWM, interrupts, deep sleep) in the browser; try a debounce or an ISR-flag pattern before touching the ring |

**Check yourself.**

1. `feedback_init()` sets the LED channel to 5 kHz at 8 bits. What is the largest duty value, and what does `LED_ACTIVE_LOW` do to it on the XIAO?
2. The button is read as `digitalRead(PIN_BUTTON) == LOW`. Why is pressed LOW, and what would happen without `INPUT_PULLUP`?
3. Why is `imu_isr` only three words long (`s_imu_irq = true`) instead of reading `TAP_SRC` over I2C right there?
4. A `ShortPress` is reported with `BUTTON_UP.arg = held_ms / 100`. A 650 ms press and a 699 ms press both report what, and why does `button_up_arg()` clamp?

<details><summary>Answers</summary>

1. 2^8 − 1 = 255. The on-board LED is wired to 3V3 through the pin, so `duty = 255 - brightness`: 255 means off, 0 means fully on.
2. The switch connects the pin to GND; the pull-up holds it at 3V3 when open. Without a pull-up the open pin floats and reads random noise, so "presses" would appear by themselves.
3. I2C transactions take hundreds of µs and use `Wire`, which is not ISR-safe (it waits, may take a mutex). An ISR must not block; it flags, and `trigger_tick()` does the I2C read in `loop()`.
4. Both report 6 (650/100 = 6, 699/100 = 6). The clamp exists so a rounding or timing edge can never produce `arg = 7` for a press the ring itself classified as short, because the companions branch on `arg < 7`.

</details>

## 3.3 I2C and SPI: register-style peripherals

**Why it matters in mcring.** The DRV2605L haptic driver (`drv2605.cpp`, address 0x5A) and the LIS2DW12 accelerometer (`imu_lis2dw12.cpp`, 0x18 or 0x19) are both configured and read over one I2C bus at 400 kHz on GPIO5/6. Every feature of those chips (RTP amplitude, double-tap thresholds, `WHO_AM_I`) is a register you write or read. SPI is not on the ring's connector but is everywhere inside it: `qio_opi` in `platformio.ini` means quad-SPI flash and octal-SPI PSRAM, and the stage-2 nRF plan routes the camera through SPI/PPI tricks.

**The concepts.** I2C is two open-drain wires, SDA (data) and SCL (clock), shared by many devices; pull-up resistors hold them high and any device can pull low. The controller issues a START, a 7-bit address plus a read/write bit, then bytes, each acknowledged by the receiver, then a STOP. A register read is "write the register number, repeated START, read N bytes": that is literally the `rd()` helper in both drivers (`Wire.endTransmission(false)` is the repeated START). Addresses are 7-bit, so 0x18 vs 0x19 is the LIS2DW12's SA0 pin. Speeds are 100 kHz (standard) and 400 kHz (fast); longer wires and more devices need smaller pull-ups. SPI is four wires: clock, controller-out (MOSI/COPI), controller-in (MISO/CIPO) and one chip-select per device; it is full-duplex, has no addressing or ACK, runs at tens of MHz, and has four clock modes (CPOL/CPHA) that must match the device. Quad/octal SPI widens data to 4 or 8 lines, which is how an 8 MB PSRAM keeps up with a 240 MHz core. A datasheet's register map is the API: `CTRL1 = 0x74` in `imu_init()` is "ODR 400 Hz, high-performance", and you can only understand it with the LIS2DW12 datasheet open.

**Learn it.**

| Resource | Type | Time | Why this one |
|---|---|---|---|
| [SparkFun: I2C](https://learn.sparkfun.com/tutorials/i2c/all) | article | 30 min | start/stop, address frame, ACK, clock stretching, pull-ups; then read `rd()`/`wr()` in `drv2605.cpp` |
| [SparkFun: Serial Peripheral Interface (SPI)](https://learn.sparkfun.com/tutorials/serial-peripheral-interface-spi) | article | 20 min | chip select, modes, why SPI is fast but pin-hungry; explains `qio`/`opi` |
| [TI DRV2605L product page and datasheet](https://www.ti.com/product/DRV2605L) | datasheet | 1 h | the registers `drv2605.cpp` writes: MODE, RTP, FEEDBACK, RATED_V, autocal; closed-loop LRA drive and why the 60 ms tick works |
| [ST LIS2DW12 product page and datasheet](https://www.st.com/content/st_com/en/products/mems-and-sensors/accelerometers/lis2dw12.html) | datasheet | 1 h | tap-recognition engine: `TAP_THS_*`, `INT_DUR` (latency/quiet/shock), `TAP_SRC`; the tuning knobs in `docs/07` §1.9 |
| [Wokwi ESP32 simulator](https://wokwi.com) | interactive | 30 min | simulate an I2C sensor and watch the `Wire` transactions in the logic-analyser view |

**Check yourself.**

1. `imu_init()` tries 0x18, then 0x19. What hardware difference do the two addresses encode, and why can the firmware not simply know?
2. `Wire.begin(PIN_I2C_SDA, PIN_I2C_SCL, 400000)`: what breaks if the pull-ups are missing, and what does the boot log show?
3. The DRV2605L's `REG_FEEDBACK` is written as `0x80 | 0x36` for an LRA. Decode the top bit from the comment in `drv2605.cpp`.

<details><summary>Answers</summary>

1. The SA0/SDO pin of the LIS2DW12 selects the low address bit; breakouts tie it either way. The firmware reads `WHO_AM_I` (must be 0x44) at both and keeps whichever answers.
2. Both lines stay low or float; `endTransmission()` returns non-zero, so `drv2605_init`/`imu_init` log "not found", the status flags `imu_ok`/`haptic_ok` stay clear and the ring runs without cues or double tap.
3. Bit 7 is `N_ERM_LRA`: 1 selects LRA mode (resonant drive with back-EMF sensing), 0 selects ERM. The lower bits set brake factor and loop gain.

</details>

## 3.4 I2S, PDM, DVP and DMA: streaming peripherals

**Why it matters in mcring.** Three streams cross the ring. `audio_mod.cpp` installs I2S0 in PDM-RX mode (CLK 42, DATA 41) to pull 16 kHz PCM from the MEMS mic. `audio_out.cpp` installs I2S1 in TX mode (BCLK 44, LRCLK 43, DOUT 9 on the XIAO) to feed the MAX98357A amplifier with 16-bit stereo frames. `camera_mod.cpp` configures the OV2640's 8-bit parallel DVP bus (Y2..Y9, PCLK, VSYNC, HREF) with a 20 MHz XCLK from LEDC and SCCB on 40/39. All three move data by DMA, which is why `loop()` can keep ticking BLE while audio plays.

**The concepts.** I2S is a three-wire serial audio bus: a bit clock, a word-select (left/right) clock and a data line. One stereo frame of 16-bit samples is 32 bits, so `BCLK = 32 × fs` = 512 kHz at 16 kHz, and LRCLK = fs. The amplifier is a DAC plus class-D stage; it decodes whatever slot its SD pin selects, so the ring writes the same sample into both slots (`I2S_CHANNEL_FMT_RIGHT_LEFT`) and stays mode-independent. PDM is one wire of 1-bit pulses at a few MHz whose density encodes the waveform; the I2S0 peripheral clocks the mic and runs the decimation filter that turns the bitstream into 16-bit PCM (`I2S_MODE_PDM`, `ONLY_LEFT`). DVP is the camera's parallel bus: eight data bits per PCLK edge, HREF marks a line, VSYNC a frame; the OV2640 compresses to JPEG on-chip, so the ESP32-S3 only has to catch bytes, which on the S3 the LCD_CAM peripheral does through GDMA. DMA (direct memory access) is a peripheral-side engine that copies between a FIFO and RAM from a chain of descriptors while the CPU does other things; the driver gives it `dma_buf_count` buffers of `dma_buf_len` frames, and your code refills (TX) or drains (RX) them in bulk. In `audio_out.cpp`: 6 buffers × 256 frames = 1,536 frames = 96 ms of audio in flight; `i2s_write(..., 0)` with a zero timeout is non-blocking and reports how much fit, and `tx_desc_auto_clear` makes a starved DMA play silence rather than repeat the last buffer. The PDM side reads 512 samples per `audio_tick()` with the same zero timeout.

**Learn it.**

| Resource | Type | Time | Why this one |
|---|---|---|---|
| [ESP-IDF: Inter-IC Sound (I2S), legacy driver (ESP32-S3, v4.4)](https://docs.espressif.com/projects/esp-idf/en/v4.4/esp32s3/api-reference/peripherals/i2s.html) | docs | 45 min | the exact driver both audio modules use: `i2s_config_t`, PDM mode, `dma_buf_count`/`dma_buf_len`, `i2s_write`/`i2s_read` timeouts |
| [Understanding PDM Digital Audio (Audio Precision, T. Kite)](https://www.ap.com/download/understanding-pdm-digital-audio-2) | article (PDF) | 1 h | oversampling, noise shaping and decimation: why a 1-bit stream at MHz becomes clean 16-bit PCM at 16 kHz |
| [NXP I2S bus specification (UM11732)](https://www.nxp.com/docs/en/user-manual/UM11732.pdf) | spec (PDF) | 30 min | the original timing diagrams: WS one BCLK early, MSB first; what "standard Philips I2S" in the code means |
| [Adafruit: MAX98357 I2S Class-D Mono Amp](https://learn.adafruit.com/adafruit-max98357-i2s-class-d-mono-amp) | guide | 30 min | SD/MODE channel select, GAIN pin, wiring; the breakout the stage-0 rig uses |
| [esp32-camera component (Espressif registry)](https://components.espressif.com/components/espressif/esp32-camera) | docs/code | 45 min | the `esp_camera_*` API, `camera_config_t` pins, frame buffers in PSRAM, JPEG quality numbers |
| [Seeed wiki: Camera usage on XIAO ESP32S3 Sense](https://wiki.seeedstudio.com/xiao_esp32s3_camera_usage/) | guide | 30 min | the board's camera pin map and a working capture sketch; note the OV2640→OV3660 change the firmware already handles |

**Check yourself.**

1. How many bytes is one DMA buffer in `audio_out.cpp` (256 frames, stereo, 16-bit), and how many ms of audio do all six hold?
2. The ring queues 24 ADPCM blocks (~400 ms) before starting I2S, then tops up at most 8 blocks per tick. If `loop()` runs every ~15 ms during a transfer, can the 96 ms DMA ever run dry from the firmware side alone?
3. Why does `audio_finish()` call `i2s_driver_uninstall()` and why does `driver_stop()` park BCLK/LRCLK/DOUT low on `mcring_v1`?
4. `CAM_PIN_XCLK` is 20 MHz from LEDC timer 0. What is the duty resolution LEDC can offer at that frequency from an 80 MHz clock?

<details><summary>Answers</summary>

1. 256 × 2 channels × 2 bytes = 1,024 bytes; 6 × 256 frames / 16,000 Hz = 96 ms.
2. No: 8 blocks = 128 ms of audio per tick exceeds the 96 ms DMA depth, so a tick every 15 ms keeps it full as long as the queue has blocks. Underruns come from the phone sending slower than 1 block/16 ms, which is the `AUDIO_UNDERRUN` event.
3. Uninstalling stops the clocks and frees the DMA buffers, cutting power between clips and streams. On the stage-1 board the amp's rail is switched off between streams; a high I2S line would back-feed the unpowered chip through its ESD diodes (bounded to ≤ 2.6 mA by the 1 kΩ series resistors), so the pins idle low.
4. 80 MHz / 20 MHz = 4 counts per period = 2 bits. That is why the camera owns timer 0 and the LED uses a different channel/timer at 5 kHz with 8 bits.

</details>

## 3.5 Power: deep sleep, wake sources, measuring current

**Why it matters in mcring.** `power.cpp` puts the ring into deep sleep after `IDLE_SLEEP_S` (default 120 s) disconnected and idle, arms the button (EXT0 on GPIO2, wake on low) and the IMU's INT1 (EXT1 on GPIO7, wake on high), then calls `esp_deep_sleep_start()`. `setup()` reads `esp_sleep_get_wakeup_cause()` and, if a tap woke the ring, begins a hands-free "ask" before the phone is even connected. `hardware/power-budget.txt` and `docs/build-helpers/tuning_calc.py` turn these modes into shots-per-charge.

**The concepts.** Deep sleep powers off the CPUs, most RAM and the radio; only the RTC domain (a tiny controller, the RTC timer, RTC GPIOs and RTC slow memory) stays on. Waking is a reset: `setup()` runs again, every variable is reinitialised, and only `RTC_DATA_ATTR` variables and the wake cause survive. Wake sources on the ESP32-S3: timer, EXT0 (one RTC GPIO, level), EXT1 (a mask of RTC GPIOs, any-high or all-low), touch pad, ULP. Only GPIO0–21 are RTC-capable, which is why the button is on 2 and INT1 on 7. Sleep current is a sum: the chip (~7–10 µA), every pull-up through a closed switch, every un-gated peripheral (the Sense camera board alone is ~3 mA, the WS2812 ~0.6–1 mA, the MAX98357A ~2.4 mA with SD tied high). Battery life is charge divided by average current: a 30 mAh cell at 60 µA average is 500 h, at 3 mA it is 10 h, which is the whole argument for the three TPS22916 load switches on `mcring_v1`. Energy per event is current × time: a 150 mA capture for 0.3 s is 12.5 µAh, a 10 s speaker answer at 100–150 mA is 280–420 µAh. Measuring this needs a meter that auto-ranges from µA to hundreds of mA in real time; a multimeter cannot, a Power Profiler Kit II can.

**Learn it.**

| Resource | Type | Time | Why this one |
|---|---|---|---|
| [ESP-IDF: Sleep Modes (ESP32-S3)](https://docs.espressif.com/projects/esp-idf/en/v5.3/esp32s3/api-reference/system/sleep_modes.html) | docs | 45 min | `esp_sleep_enable_ext0/ext1_wakeup`, pull-up hold during sleep, what survives; the API `power.cpp` calls |
| [Random Nerd Tutorials: ESP32 Deep Sleep with Arduino IDE and Wake Up Sources](https://randomnerdtutorials.com/esp32-deep-sleep-arduino-ide-wake-up-sources/) | tutorial | 45 min | timer, touch and external wake with working sketches; then compare with `power_deep_sleep_now()` |
| [ESP-IDF: Introduction to Low Power Mode (ESP32-S3)](https://docs.espressif.com/projects/esp-idf/en/latest/esp32s3/api-guides/low-power-mode/low-power-mode-soc.html) | docs | 30 min | light-sleep vs deep-sleep vs DFS, with current figures per mode |
| [ESP-IDF: Current Consumption Measurement of Modules](https://docs.espressif.com/projects/esp-idf/en/v5.2/esp32/api-guides/current-consumption-measurement-modules.html) | docs | 20 min | why a dev board never shows datasheet sleep current, and how to measure the module alone |
| [Nordic Power Profiler Kit II](https://www.nordicsemi.com/Products/Development-hardware/Power-Profiler-Kit-2) | tool | — | 200 nA–1 A, 100 ksps, source mode: the instrument the measurements table in `docs/07` §1.11 assumes |

**Check yourself.**

1. The ring wakes from a double tap, captures and records, and only then does the phone connect. Which lines of `main.cpp` make that work, and what is lost across the sleep?
2. With the Sense board attached, deep sleep is ~3 mA. How long does a 100 mAh bench cell last doing nothing? And a 30 mAh stage-1 cell at 60 µA?
3. `power_tick()` never sleeps while `connected`. What would have to change in the BLE link for a connected ring to sleep, and what does `request_slow_params()` buy instead?

<details><summary>Answers</summary>

1. `esp_sleep_get_wakeup_cause() == ESP_SLEEP_WAKEUP_EXT1` → `begin_ask()` in `setup()`. The capture and clip go into `transfer::enqueue`, which keeps them in PSRAM until a phone subscribes. Everything else (settings are reloaded from NVS, the BLE connection, events) is rebuilt from scratch; events are never queued.
2. 100 mAh / 3 mA ≈ 33 h. 30 mAh / 0.06 mA = 500 h ≈ 3 weeks (before self-discharge and the IMU's ~90 µA tap-wake mode, which `docs/07` §2.4 discusses).
3. The radio must stay on to keep a connection, and deep sleep kills it; the only way to "sleep connected" is a long connection interval with peripheral latency (200–400 ms, latency 2 in `request_slow_params()`), which lets the radio idle between events at ~tens of µA average while remaining reachable.

</details>

## 3.6 Persistent settings: NVS and Preferences

**Why it matters in mcring.** `settings.cpp` keeps the eleven `SET_CONFIG` keys (trigger mask, JPEG quality, idle sleep, speaker volume, cues mask, mic source ...) in the `mcring` namespace of NVS through the Arduino `Preferences` wrapper, so `mcring config idle_sleep_s 0` survives a reboot and deep sleep. `prj.conf` for the nRF port enables Zephyr's own NVS for the same job.

**The concepts.** Flash is erased in pages (4 KB) and written in smaller units, and each page survives roughly 10^5 erase cycles; you cannot update a byte in place. NVS (non-volatile storage) is a log-structured key-value store in a dedicated flash partition: writes append entries, pages are only erased when full, and the newest entry for a key wins, which spreads wear automatically. Keys are strings up to 15 characters inside a namespace; values are integers, strings or blobs. `Preferences` is the Arduino face of it: `begin(ns, readOnly)`, `getUChar(key, default)`, `putUShort(key, v)`, `end()`. Because every `settings_apply()` calls `settings_save()`, each accepted `SET_CONFIG` writes eleven entries; at 10^5 cycles per page that is still years of reconfiguring, but it is why you do not log telemetry into NVS. Big data (photos, clips) never belongs here; that is PSRAM for the queue and the phone for storage.

**Learn it.**

| Resource | Type | Time | Why this one |
|---|---|---|---|
| [Arduino-ESP32: Preferences](https://docs.espressif.com/projects/arduino-esp32/en/latest/tutorials/preferences.html) | docs | 30 min | the API `settings.cpp` uses, with the 15-character key limit and types |
| [ESP-IDF: Non-Volatile Storage Library (ESP32-S3)](https://docs.espressif.com/projects/esp-idf/en/v5.3/esp32s3/api-reference/storage/nvs_flash.html) | docs | 45 min | how NVS lays entries out in pages, namespaces, the `nvs` partition in `default_8MB.csv`, erase on layout change |
| [Random Nerd Tutorials: ESP32 Save Data Permanently using Preferences](https://randomnerdtutorials.com/esp32-save-data-permanently-preferences/) | tutorial | 30 min | worked examples (boot counter, credentials) and the `clear()`/`remove()` calls you will want for a factory reset |

**Check yourself.**

1. `settings_load()` opens the namespace read-only; `settings_save()` opens it read-write. Why bother with the distinction?
2. Key 4 (`IDLE_SLEEP_S`) is stored with `putUShort`. What is the largest value, and how does `settings_apply` guard it?
3. Where would you add a "number of boots" counter, and what would you *not* add to NVS?

<details><summary>Answers</summary>

1. A read-only open never creates or modifies the namespace, so a first boot with an empty partition just returns defaults without a write; it also documents intent and prevents accidental writes during load.
2. 65535 s (~18 h); `settings_apply` rejects `v < 0 || v > 65535` before it ever reaches the store.
3. A `putUInt("boots", n+1)` in `setup()` after `settings_load()` is fine (one entry per boot). Per-tick state, transfer progress or audio data would wear the partition and gain nothing, because a reboot rebuilds them anyway.

</details>

## 3.7 Toolchain: Arduino-ESP32, ESP-IDF, PlatformIO, host tests

**Why it matters in mcring.** `platformio.ini` pins `espressif32@6.9.0` (Arduino core 2.0.x on ESP-IDF 4.4) because `esp32-camera`, legacy I2S and NimBLE-Arduino 2.x are known-good there; the README shows the one-line swap to the pioarduino platform for Arduino core 3.x. The `native` environment compiles `lib/mcring_*` with Unity on your laptop (`pio test -e native`, 14 tests), and `python/mcring_core/tests/test_proto.py` compiles the same C from Python to prove byte-identical packets. The firmware has not yet been compiled with the ESP32 toolchain in CI; `pio run` on your machine is step one.

**The concepts.** ESP-IDF is Espressif's SDK: FreeRTOS, drivers, CMake, `menuconfig`, `idf.py`. Arduino-ESP32 is a layer on top that gives `setup()`/`loop()`, `Wire`, `Serial`, `Preferences` and runs `loop()` as one FreeRTOS task; you can call any ESP-IDF function from it (the code does: `esp_sleep_*`, `i2s_*`, `heap_caps_malloc`), but you take the core's precompiled sdkconfig as given. Arduino 2.0.x sits on IDF 4.4 and 3.x on IDF 5.x; the 3.x migration renamed the LEDC and I2S APIs, which is why the code restricts itself to calls that exist in both. PlatformIO wraps toolchains, boards and libraries: `[env]` holds build flags, `lib_deps` pins NimBLE-Arduino, `board_build.partitions` picks the flash layout, and `-D` flags select the board (`BOARD_XIAO_ESP32S3_SENSE`). The `native` platform builds for the host so the pure-C libraries (CRC, ADPCM, packets, Morse) can be unit-tested in milliseconds; `build_src_filter = -<*>` keeps `src/` out of that build. Unity is a tiny C test framework (`TEST_ASSERT_EQUAL`). The cross-language rule in this repo: anything that must match on ring, phone and backend lives in `lib/` as plain C99 with no Arduino dependency.

**Learn it.**

| Resource | Type | Time | Why this one |
|---|---|---|---|
| [Arduino-ESP32 documentation](https://docs.espressif.com/projects/arduino-esp32/en/latest/) | docs | reference | the API reference and tutorials for the core the firmware targets |
| [Arduino-ESP32: Migration from 2.x to 3.0](https://docs.espressif.com/projects/arduino-esp32/en/latest/migration_guides/2.x_to_3.0.html) | docs | 30 min | the exact LEDC/I2S/BLE renames; read before switching the platform line |
| [ESP-IDF Get Started (ESP32-S3)](https://docs.espressif.com/projects/esp-idf/en/v5.4/esp32s3/get-started/) | docs | 1 h | what sits under Arduino: toolchain, CMake, `idf.py menuconfig`, partition tables; needed when you outgrow the core |
| [PlatformIO: Espressif 32 platform](https://docs.platformio.org/en/stable/platforms/espressif32.html) | docs | 30 min | every `board_build.*` and `upload_*` option in `platformio.ini` |
| [pioarduino platform-espressif32](https://github.com/pioarduino/platform-espressif32) | code | 15 min | the community platform that carries Arduino core 3.x; the README's alternative `platform =` line |
| [PlatformIO: Unity test framework](https://docs.platformio.org/en/latest/advanced/unit-testing/frameworks/unity.html) | docs | 30 min | `pio test -e native`, `setUp`/`tearDown`, the `UNIT_TEST` guard |
| [Digi-Key: Increase the quality of your embedded projects using PlatformIO unit tests](https://www.digikey.com/en/maker/tutorials/2022/increase-the-quality-of-your-embedded-projects-using-platformio-unit-tests) | tutorial | 30 min | a worked native-vs-target test setup like the repo's `test/` directory |

**Check yourself.**

1. `[env:native]` sets `build_src_filter = -<*>` and `lib_compat_mode = off`. What does each line do for `pio test -e native`?
2. Why does the firmware use `ledcSetup`/`ledcAttachPin` and the legacy `driver/i2s.h` instead of the newer APIs?
3. `test_proto.py` compiles `mcring_proto.c` from Python. What class of bug does that catch that `pio test -e native` alone would not?

<details><summary>Answers</summary>

1. `-<*>` excludes everything in `src/` (which includes `<Arduino.h>` and cannot build on a laptop) so only `lib/mcring_*` and `test/` are compiled; `lib_compat_mode = off` stops PlatformIO from rejecting those libraries for not declaring the `native` platform in their `library.json`.
2. Arduino 2.0.x (IDF 4.4) does not have `ledcAttach` or `driver/i2s_std.h`; the chosen calls exist in both 2.x and 3.x, so one source builds on either platform line.
3. Cross-implementation drift: Python and TypeScript encoders producing different bytes than C (endianness, field order, a changed opcode). Unity tests only check C against itself.

</details>

## 3.8 Seeing inside: serial logging, crash backtraces, JTAG

**Why it matters in mcring.** `log.h` prints `[millis] I tag: message` over USB-CDC at 115200 (`ARDUINO_USB_CDC_ON_BOOT=1`), which is what frees UART0's GPIO43/44 for the speaker. `CORE_DEBUG_LEVEL=2` compiles `LOGD` out; `monitor_filters = esp32_exception_decoder` turns a crash's hex addresses into `transfer.cpp:123`. `docs/07` §4 is a troubleshooting matrix written entirely in terms of these log lines (`MTU 517 -> chunk 510`, `no ACK, resending END`).

**The concepts.** Logging is `printf` to a serial port; on the ESP32-S3 that port is the chip's native USB (CDC) rather than a UART, so there is no USB-serial bridge chip and the ROM bootloader still prints its banner on the UART pins at reset. Levels (E/W/I/D) let you compile noise out; a tag per module lets you grep. When the CPU hits an illegal address or a failed `assert`, the panic handler prints a "Guru Meditation Error" with the exception cause, the registers and a backtrace of return addresses; the exception decoder maps those addresses to functions and lines using the `.elf` from the last build, so always decode with the binary you flashed. A JTAG debugger lets you halt the CPU, step and inspect memory; the ESP32-S3 has one built into its USB port (GPIO19/20, the same pins as CDC), driven by OpenOCD + GDB, and `mcring_v1` exposes those pins on test pads. The cheapest instruments are often the best: `pio device monitor` with timestamps, a `LOGI` at every state change (the code does this), `Serial.flush()` before sleeping, and a logic analyser on BCLK/LRCLK when the speaker is silent.

**Learn it.**

| Resource | Type | Time | Why this one |
|---|---|---|---|
| [ESP-IDF: Logging library (ESP32-S3)](https://docs.espressif.com/projects/esp-idf/en/latest/esp32s3/api-reference/system/log.html) | docs | 20 min | levels, tags, `esp_log_level_set`; what `CORE_DEBUG_LEVEL` controls under the hood |
| [ESP-IDF: Fatal Errors (ESP32-S3)](https://docs.espressif.com/projects/esp-idf/en/v5.2/esp32s3/api-guides/fatal-errors.html) | docs | 30 min | reading a Guru Meditation message: exception causes, register dump, backtrace, panic behaviour options |
| [PlatformIO: `pio device monitor` and filters](https://docs.platformio.org/en/stable/core/userguide/device/cmd_monitor.html) | docs | 15 min | `esp32_exception_decoder`, `time`, `log2file`; the `monitor_filters` line in `platformio.ini` |
| [Rob Miles: Debug ESP32 programs in PlatformIO using the exception decoder](https://www.robmiles.com/journal/2024/7/5/debug-esp32esp8266-programs-in-platformio-using-the-exception-decoder) | article | 15 min | a short worked crash → decoded line example |
| [ESP-IDF: JTAG Debugging (ESP32-S3)](https://docs.espressif.com/projects/esp-idf/en/latest/esp32s3/api-guides/jtag-debugging/) | docs | 1 h | `openocd -f board/esp32s3-builtin.cfg`, GDB, breakpoints; the built-in USB JTAG needs no extra hardware |

**Check yourself.**

1. The boot banner appears on GPIO43 for ~50 ms. Why does `config_audio.h` say that is inaudible, and on which stage-1 pin does the same banner reach the LED?
2. `setup()` waits up to 1.5 s for `Serial`. What happens on battery with no USB host, and why is the cap needed?
3. You see `Guru Meditation Error ... (LoadProhibited)` with a backtrace into `transfer::send_chunk`. Name two likely causes from the code.

<details><summary>Answers</summary>

1. GPIO43 is LRCLK; without BCLK the amplifier cannot clock frames in, so garbage on LRCLK alone produces nothing. On `mcring_v1` GPIO43 is the WS2812 data line, reached only through 1 kΩ while the LED rail is off.
2. `!Serial` stays true, the loop exits after 1.5 s and the ring boots anyway; without the cap a ring on a battery would hang forever waiting for a terminal.
3. `g_queue[0].data` already freed (a `pop_front` racing an ACK path) or an `idx` beyond `g_n_chunks` from a corrupt ACK list; `on_ack` bounds-checks `idx < g_n_chunks` for exactly this reason.

</details>

## 3.9 Structuring firmware: the cooperative loop, state machines, ring buffers

**Why it matters in mcring.** `loop()` in `main.cpp` is one cooperative scheduler: `ble::tick()`, `trigger_tick()`, `audio_tick()`, `transfer::tick()` (≤ 15 ms of chunk sending), `feedback_tick()`, `audio_out_tick()`, status, `power_tick()`, `delay(1)`. Nothing blocks except the camera capture (150–400 ms). `g_state` (idle/capturing/transferring/recording/feedback) and `transfer::State` are explicit state machines; `audio_out.cpp` is a producer/consumer ring buffer of 48 ADPCM blocks filled by the NimBLE host task and drained by `loop()`.

**The concepts.** A cooperative loop ("superloop") calls every module once per iteration and asks each to do a bounded slice of work and return; latency is the sum of the longest slices, which is why `transfer::tick` budgets 15 ms and why a 300 ms capture is the one thing that causes `AUDIO_UNDERRUN`. The alternative is an RTOS with preemptive tasks (FreeRTOS is underneath Arduino anyway, and NimBLE runs its host on its own task), which buys responsiveness at the cost of shared-data hazards. A state machine replaces flags-of-flags with named states and explicit transitions: `Idle → Sending → WaitAck → Idle`, with timeouts (`TRANSFER_ACK_TIMEOUT_MS`) and bounded retries (`TRANSFER_MAX_ROUNDS`) as transitions too. Because the BLE task and `loop()` run on different FreeRTOS tasks (possibly different cores), anything both touch needs protection: `audio_out.cpp` wraps head/tail/count and the command flags in `portENTER_CRITICAL(&s_mux)`, an ESP-IDF spinlock that also masks interrupts on the current core for the few instructions of the push/pop, and keeps every slow operation (decode, `i2s_write`, driver install) on the loop side. A ring buffer is a fixed array with head (write) and tail (read) indices modulo its size; `count` makes full vs empty unambiguous. The design choice is what happens when full: `q_push` drops the new block and counts it (the phone is too far ahead), while prebuffering 24 blocks before starting makes jitter invisible. Callback-to-loop handoff is the same idea with a single flag byte (`F_START|F_END|F_STOP`): the callback records a request, `tick()` acts on it, so `i2s_driver_uninstall` never runs on the BLE task.

**Learn it.**

| Resource | Type | Time | Why this one |
|---|---|---|---|
| [Miro Samek: Modern Embedded Systems Programming video course](https://www.state-machine.com/video-course) | video course | 20+ h (pick the state-machine lessons) | the clearest treatment of event-driven firmware and state machines in C; lessons on hierarchical state machines map directly onto `g_state`/`transfer::State` |
| [Digi-Key: Introduction to RTOS (12-part series, FreeRTOS on ESP32)](https://www.youtube.com/playlist?list=PLEBQazB0HUyQ4hAPU1cJED6t3DU0h34bz) | video series | 4 h | tasks, queues, mutexes, ISR handoff and multicore on the very chip and Arduino core the ring uses; shows what the superloop is trading away |
| [ESP-IDF: FreeRTOS SMP changes](https://docs.espressif.com/projects/esp-idf/en/v4.3.5/esp32/api-guides/freertos-smp.html) | docs | 30 min | critical sections as spinlocks, task pinning, why `portENTER_CRITICAL` takes a mux on a dual-core chip |
| [esp32.com: portENTER_CRITICAL explanation](https://esp32.com/viewtopic.php?p=50172) | forum thread | 10 min | Espressif staff on what the mux does and why critical sections must be short |
| [Embedded Artistry: Creating a Circular Buffer in C and C++](https://embeddedartistry.com/blog/2017/4/6/circular-buffers-in-cc) | article | 45 min | head/tail/full-flag designs, API shape, C and C++ versions; compare with `q_push`/`q_pop` |
| [Embedded.fm podcast](https://embedded.fm) | podcast | ongoing | Elecia White and guests on architecture, debugging and craft; good background listening for everything in this chapter |

**Check yourself.**

1. `transfer::tick()` sends chunks for up to 15 ms per loop. At iOS chunk size (178 B payload) and roughly one notification per 15 ms connection interval, how many loop iterations does a 15 KB JPEG take, and what is the ring doing in between?
2. `audio_out_stop()` only sets `F_STOP`. Trace what happens on the next `audio_out_tick()` and explain why the teardown cannot happen in `ABORT`'s own context.
3. The audio queue holds 48 blocks and drops beyond that; the companions keep ≤ 22 unplayed blocks queued after the 24-block burst. Why the gap between 22+24 and 48?
4. Which `g_state` transitions are driven by polling results rather than events, and what would break if `set_state` were called from the BLE task?

<details><summary>Answers</summary>

1. 15,000 / 178 ≈ 85 chunks; if the stack takes about one per interval, ~85 × 15 ms ≈ 1.3 s, i.e. ~85 loop iterations each sending one chunk and then returning to tick the button, the cues, status and audio.
2. `take_flags()` sees `F_STOP`, `finish(1)` calls `driver_stop()` (uninstall, park pins, amp rail off), resets playback and emits `AUDIO_DONE(1)`. `ABORT` arrives on the NimBLE host task while `loop()` may be inside `i2s_write`; uninstalling the driver from another task mid-write is undefined, so the request is deferred to the loop task.
3. Margin for BLE burstiness: writes arrive in clumps per connection event, so a sender that is nominally 22 ahead can momentarily be 30+ ahead; 48 absorbs that without drops while 24 of prebuffer absorb the opposite (late) case.
4. `TRANSFERRING ↔ IDLE` from `transfer::busy()/queued()` and `FEEDBACK ↔ IDLE` from `feedback_playing() || audio_out_active()` are polled each loop. `g_state`/`g_status_dirty` are plain globals read and written only on the loop task; writing them from the BLE task would race (torn updates, lost `dirty` flags) without a lock.

</details>

## 3.10 Audio data: PCM, fixed-point, IMA ADPCM

**Why it matters in mcring.** `lib/mcring_adpcm` is the codec on both ends: `audio_mod.cpp` encodes the mic clip, `audio_out.cpp` decodes the phone's stream, and `python/mcring_core/adpcm.py` must produce identical bytes (`test_proto.py` checks). `audio_finish()` does DC removal and gain in integer Q8 arithmetic; `stage_block()` applies `AUDIO_START.volume × SPEAKER_VOLUME` the same way. `protocol/ble-gatt.md` fixes the block at 256 samples = 132 bytes, which sets the 8 KB/s budget on the BLE link.

**The concepts.** Audio is sampled at `fs` samples per second with `b` bits per sample; 16 kHz/16-bit mono is 32,000 bytes/s = 256 kbit/s and captures up to 8 kHz, enough for speech. ADPCM (adaptive differential PCM) sends the difference between each sample and a prediction, quantised to 4 bits with a step size that grows when differences are large and shrinks when small: IMA's 89-entry step table (7 … 32767) and the 16-entry index table (−1 … +8) in `mcring_adpcm.c` are the whole algorithm. Each nibble decodes as `predictor ± (step/8 + step/4·b2 + step/2·b1 + step·b0)`, clamped to 16 bits. The ring's block: 2-byte first sample, 1-byte step index, 1 reserved byte, then 255 nibbles packed low-nibble-first into 128 bytes = 132 bytes per 256 samples, so each block decodes on its own after a lost packet while the step index carries over for quality. Ratio 512/132 = 3.88:1; bit rate 132 B × 62.5 blocks/s = 8,250 B/s (66 kbit/s); an 8 s clip is 500 blocks = 66,000 bytes. Fixed-point means representing fractions as integers with an implied scale: `gain_q8 = 24000·256/peak` is a Q8.8 gain (256 = 1.0), applied as `(v × gain_q8) / 256`, clamped between 1× and 8×; volume uses 255 as unity so `(sample × gain) / 255` needs only 32-bit integer maths. The reasons are determinism across C/Python/TypeScript (byte-identical tests), speed on the Cortex-M4 target, and no float-rounding surprises in a codec whose encoder and decoder must stay in lock-step.

**Learn it.**

| Resource | Type | Time | Why this one |
|---|---|---|---|
| [Xiph.org: Digital Show & Tell (Monty Montgomery)](https://xiph.org/video/vid2.shtml) | video | 30 min | sampling, quantisation, bit depth and dither demonstrated on real bench gear; the best 30 minutes on why 16 kHz/16-bit is enough for speech |
| [MultimediaWiki: IMA ADPCM](https://wiki.multimedia.cx/index.php/IMA_ADPCM) | article | 20 min | the decode loop, the step/index tables and the 0..88 clamp exactly as in `mcring_adpcm.c` |
| [Dr. Dobb's: Inside IMA ADPCM](https://www.drdobbs.com/database/algorithm-alley/184410326) | article | 30 min | the encoder side with worked numbers; explains why the block header carries the first sample and step index |
| [Understanding PDM Digital Audio (Audio Precision)](https://www.ap.com/download/understanding-pdm-digital-audio-2) | article (PDF) | 1 h | from the 1-bit mic stream to PCM; read once to connect 3.4 with this section |
| [Making Embedded Systems, 2nd ed., maths chapter](https://www.oreilly.com/library/view/-/9781098151539) | book chapter | 1 h | fixed-point, scaling and overflow rules for MCUs without (or without wanting) floats |

**Check yourself.**

1. Verify 132 bytes per block from the header and nibble count.
2. A phone with MTU 185 can send one block per write. At 1 block / 16 ms, what fraction of a ~12 KB/s iOS link is the speaker stream using, and why does the ring prebuffer 24 blocks?
3. `audio_finish()` clamps the gain at 8×. A clip whose peak is 1,000 (of 32,767) gets what gain, and what peak afterwards?
4. Why is `step_index` carried across blocks but `predictor` reset to the first sample of each block?

<details><summary>Answers</summary>

1. 4 header bytes + ⌈255/2⌉ = 128 bytes of nibbles = 132.
2. 135-byte writes (3 header + 132) at 62.5/s = 8,440 B/s, about 70 % of 12 KB/s. With that little headroom a few late connection events would starve the DAC, so ~400 ms is queued first and `AUDIO_UNDERRUN` + silence is the fallback instead of clicks.
3. 24000·256/1000 = 6144 (24×) → clamped to 2048 (8×); the peak becomes ≈ 8,000, so quiet clips stay quiet rather than being amplified into noise.
4. Resetting the predictor makes each block decodable alone after a dropped packet (the header has the truth); keeping the step index avoids re-ramping the adaptive step every 16 ms, which would add audible noise at every block boundary.

</details>

## 3.11 C and C++ for firmware: packed structs, endianness, volatile, static, no heap in ISRs

**Why it matters in mcring.** `mcring_proto.h` defines `mc_status_t` and friends with `MC_PACKED` (`__attribute__((packed))`), yet `mc_encode_status()` still serialises field by field with `mc_put_u16`/`mc_put_u32` little-endian. `ble_link.cpp` declares `g_connected`, `g_mtu`, `g_credits` `volatile` because NimBLE callbacks write them from another task. Every module keeps its state in file-scope `static` variables or an anonymous namespace. `imu_isr` is `IRAM_ATTR` and touches one flag; all `malloc`/`heap_caps_malloc` calls happen in `loop()`-side code.

**The concepts.** A C struct may contain padding so that each field sits at its natural alignment; `packed` removes padding, which makes `sizeof(mc_status_t) == 12` match the wire format but can make field access slower or trap on unaligned loads on some cores, so the portable rule is: never cast a byte buffer to a struct pointer; copy bytes in and out explicitly. Endianness is byte order of multi-byte integers: little-endian stores the low byte first (ESP32, Cortex-M, x86 all do), big-endian the high byte first (network order). The mcring wire format is little-endian by specification, and `mc_put_u16(o, v) { o[0]=v; o[1]=v>>8; }` is correct on any host, which is what lets Python's `struct.pack('<H')` and TypeScript's `DataView.setUint16(..., true)` agree. `volatile` tells the compiler the value can change behind its back, so every access really loads/stores memory instead of a cached register; it does not make `g_credits = g_credits + 1` atomic (`do_notify` can lose an increment against `onStatus`, which the 50 ms refill makes harmless). `static` at file scope means private to this translation unit (the C way to make modules); inside a function it means one instance that persists across calls (`first_ms` in the touch code); `static const` tables stay in flash. An ISR must never call `malloc`, `printf`, `delay`, I2C or anything that may block or take a lock, because it interrupts whoever held that lock and because flash may be unreadable (cache disabled during an NVS write), hence `IRAM_ATTR` for the handler code. Prefer `uint32_t` deltas for time, `size_t` for sizes, explicit casts when narrowing (`(uint8_t)(t > 255 ? 255 : t)`), and fixed-size arrays over heap where lifetime is static (`s_q[48][132]`, `g_pkt[517]`); the heap is used only for payloads whose size is unknown (JPEGs, clips) and freed by the same module that allocated them.

**Learn it.**

| Resource | Type | Time | Why this one |
|---|---|---|---|
| [Beej's Guide to C Programming](https://beej.us/guide/bgc/html/) | book (free online) | 10 h | a complete modern-C course; chapters on pointers, structs, `static`, bit operations and the standard library are all the C `lib/` uses |
| [Embedded.com: Introduction to the volatile keyword (Nigel Jones)](https://www.embedded.com/?p=4023801) | article | 20 min | the classic explanation with the three cases: memory-mapped registers, ISR-shared globals, multi-task globals |
| [Barr Group: Embedded C Coding Standard (BARR-C)](https://barrgroup.com/coding-standard) | book (free PDF) | 2 h | rules that prevent the bugs above: fixed-width types, no magic numbers, ISR restrictions, `volatile` usage |
| [GCC manual: Common Type Attributes](https://gcc.gnu.org/onlinedocs/gcc-14.2.0/gcc/Common-Type-Attributes.html) | docs | 15 min | what `packed` and `aligned` actually promise; read before trusting `sizeof` on a wire struct |
| [Computerphile: Endianness Explained With an Egg](https://www.youtube.com/watch?v=NcaiHcBvDR4) | video | 10 min | the one-sitting version of byte order, with the Gulliver origin of the name |

**Check yourself.**

1. Without `MC_PACKED`, what would `sizeof(mc_status_t)` most likely be, and which field moves?
2. `mc_get_i32(d + 2)` decodes the `SET_CONFIG` value. Write the four-byte little-endian encoding of `idle_sleep_s = 300`.
3. `g_credits` is `volatile int` and modified in both `onStatus` (BLE task) and `do_notify` (loop). Is `g_credits = g_credits - 1` safe? What makes the design tolerate the answer?
4. `trigger_init()` reads the touch baseline with `delay(5)` in a loop. Could that code live in an ISR? Could `feedback_tick()`?

<details><summary>Answers</summary>

1. 16: `battery_mv` (u16) already sits at offset 2, but `uptime_s` (u32) at offset 6 would be padded to offset 8, pushing `last_error`/`queued` to 12–13 and the struct to 16 bytes.
2. Opcode 0x03, key 0x04, then 300 = 0x0000012C → bytes `2C 01 00 00`: the packet is `03 04 2C 01 00 00`.
3. No: it is a read-modify-write that can interleave with the increment on the other task, so a credit can be lost or gained. The design tolerates it because credits are a throttle, not a count: the 50 ms timeout refills them, `notify()` returning false is the real back-pressure signal, and the maximum is small (6).
4. Neither. `delay()` blocks (and yields to the scheduler), which is forbidden in an ISR; `feedback_tick()` calls I2C (`drv2605_set`) and `neopixelWrite`, both of which wait. Both belong where they are, in `setup()`/`loop()`.

</details>
