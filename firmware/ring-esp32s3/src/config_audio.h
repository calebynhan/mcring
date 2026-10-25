/*
 * Speaker / cue / voice-first additions to the board config. Included at the END of config.h so the
 * board pin map is already defined; everything here is guarded so it can be included on its own too.
 *
 * On-ring speaker (stage-1 oversized ring, optional): MAX98357A I2S class-D amp + 8 Ω 10 mm speaker.
 *   BCLK  -> PIN_I2S_BCLK      (bit clock, 32 × fs = 512 kHz at 16 kHz)
 *   LRC   -> PIN_I2S_LRCLK     (word select / frame clock = fs)
 *   DIN   -> PIN_I2S_DOUT      (serial data, ESP32 → amp)
 *   SD    -> PIN_SPEAKER_EN or tied high (amp shutdown/channel select; see audio_out.cpp)
 *   GND / VIN (3V3 or VBAT; the MAX98357A runs 2.5–5.5 V)
 * The ring streams mono and duplicates each sample into both I2S slots, so any SD channel mode works.
 */
#ifndef MCRING_CONFIG_AUDIO_H
#define MCRING_CONFIG_AUDIO_H

#if defined(BOARD_XIAO_ESP32S3_SENSE)
  // The XIAO header has exactly 11 GPIOs (D0..D10) and all were taken, so three are reassigned:
  //   D6 = GPIO43 (UART0 TXD0) and D7 = GPIO44 (UART0 RXD0) are free because logging goes over USB-CDC
  //   (ARDUINO_USB_CDC_ON_BOOT=1). The ROM bootloader still prints its banner on GPIO43 for ~50 ms at
  //   reset; on LRCLK that is a few garbage frames while the amp has no BCLK — inaudible.
  //   D10 = GPIO9 was PIN_AUX (the air-puff actuator experiment). That experiment is parked on the dev
  //   kit: the speaker is the voice-first priority and this is the only remaining header pin.
  #define PIN_I2S_BCLK     44    // D7
  #define PIN_I2S_LRCLK    43    // D6
  #define PIN_I2S_DOUT      9    // D10 (was PIN_AUX)
  #define PIN_SPEAKER_EN   -1    // MAX98357A SD tied high / breakout pull-up: amp always enabled
                                 // (~2.4 mA idle; wire SD to a spare GPIO and set this if that matters)
  #ifdef PIN_AUX
    #undef PIN_AUX
  #endif
  #define PIN_AUX          -1    // reassigned to I2S DIN (feedback.cpp compiles the aux channel out)

#elif defined(BOARD_MCRING_V1)
  // Stage-1 board (hardware/electrical/mcring_v1.py, hardware/pinmap.md): optional MAX98357A (U10, 16-TQFN) on a
  // gated 3V3 rail (VAMP) behind a third TPS22916 load switch (U11). IO34-IO37 are plain GPIOs on the N4R2 module
  // (only the octal-PSRAM R8 parts route SPIIO4-7 to them) with no boot-time function; IO44 (RXD0) stays spare.
  // Omitting the speaker group on a board does not need a firmware change: the I2S outputs then drive nothing.
  #define PIN_I2S_BCLK     35    // U10 BCLK  (net I2S_BCLK),  32 x fs = 512 kHz at 16 kHz
  #define PIN_I2S_LRCLK    36    // U10 LRCLK (net I2S_LRCLK), fs = 16 kHz
  #define PIN_I2S_DOUT     37    // U10 DIN   (net I2S_DOUT)
  #define PIN_SPEAKER_EN   34    // U11 TPS22916 ON (net AMP_PWR_EN, 100k pull-down R20): HIGH powers the amp rail
                                 // VAMP. SD_MODE is tied to VAMP on the board (> 1.4 V = left-channel mode), so this
                                 // one pin is both the power gate and the amp enable; the amp draws nothing while LOW.
                                 // HW NOTE: while this pin is LOW the three I2S pins must idle LOW (or be inputs with
                                 // the pull-up off; not gpio_reset_pin(), which re-enables the pull-up) — a high level
                                 // back-feeds the unpowered amp through its input ESD diodes. R22-R24 (1 kΩ in series
                                 // with BCLK/LRCLK/DIN on the board) bound that to <= 2.6 mA per pin, so a pin left high
                                 // after i2s_driver_uninstall() is a battery drain, not damage; park the three pins low
                                 // in driver_stop() and drive all four low before deep sleep (hardware/electrical/README.md §7).
                                 // Board gain is 3 dB (R21 = 100k): a full-scale sample at SPEAKER_VOLUME 255 is 0.25 W into
                                 // the 8 Ω speaker, inside its 300 mW rating (R21 = 0R / 6 dB = 0.5 W is a bench option).

#else
  #define PIN_I2S_BCLK     -1
  #define PIN_I2S_LRCLK    -1
  #define PIN_I2S_DOUT     -1
  #define PIN_SPEAKER_EN   -1
#endif

// ---------------------------------------------------------------------------
// -DMCRING_XIAO_BASE — stage-0 *no-solder* variant (platformio env `xiao_esp32s3_sense_base`): the pre-soldered
// XIAO ESP32S3 Sense seated in Seeed's Expansion Board Base for XIAO (103030356). Wiring and kit:
// hardware/pcb/wiring_stage0_solderless.md, hardware/bom/stage0-devkit-solderless.csv, docs/07-build-guide.md §1.12.
// The base's own parts land on the firmware's pins — user button on D1 = GPIO2, passive buzzer on A3 = D3 = GPIO4 —
// so the two #defines below are the stock values (Seeed wiki / Zephyr shield table); they live here so that a base
// revision that moves either part is a one-line change. What really differs from the breadboard rig:
//   * haptics = Seeed Grove Haptic Motor 105020011 (DRV2605L + factory-attached ERM, one Grove plug) → ERM drive
//     profile (HAPTIC_MOTOR_LRA 0); the module's EN is tied on-module, nothing to drive;
//   * D2 = GPIO3 is the base's microSD chip-select → PIN_HAPTIC is parked so the firmware never toggles that line;
//   * the LIS3DH's INT1 reaches D8 only through an optional clip / press-fit jumper, and nothing else drives D8 (it is
//     the base's and the Sense board's microSD clock line) → taps are polled (IMU_POLL_MS) and PIN_IMU_INT is parked:
//     no ISR and no EXT1 wake on a line that may float (a floating D8 would wake the ring at random, and every EXT1
//     wake starts an ask). Tap-to-wake from deep sleep is opt-in: fit the jumper AND build with -DMCRING_IMU_INT_WIRED
//     (platformio env `xiao_esp32s3_sense_base_tapwake`). Without it the LIS3DH is powered down in deep sleep and the
//     ring wakes on the button only;
//   * the battery sits in the base's JST socket and A0 (PIN_BATTERY_ADC) is an open Grove pin → parked, so STATUS
//     reports 255 % = unknown instead of a floating-ADC reading (which could fire LOW_BATTERY). A divider wired to A0
//     is opt-in with -DMCRING_BATT_DIVIDER_WIRED.
//   * I²S speaker pins are unchanged (D6/D7 = the base's Grove-UART socket, D10 on the breakout header).
//     Everything else (camera, mic, LED, BLE) is the stock XIAO Sense map.
// ---------------------------------------------------------------------------
#if defined(MCRING_XIAO_BASE)
  #if !defined(BOARD_XIAO_ESP32S3_SENSE)
    #error "MCRING_XIAO_BASE is a variant of BOARD_XIAO_ESP32S3_SENSE (platformio env xiao_esp32s3_sense_base)"
  #endif
  #undef  BOARD_NAME
  #if defined(MCRING_IMU_INT_WIRED)
    #define BOARD_NAME      "xiao-esp32s3-sense+base+tapwake"
  #else
    #define BOARD_NAME      "xiao-esp32s3-sense+base"
  #endif
  #undef  PIN_BUTTON
  #define PIN_BUTTON         2     // base user button → D1 (GPIO2) to GND; RTC GPIO → EXT0 deep-sleep wake as before
  #undef  PIN_BUZZER
  #define PIN_BUZZER         4     // base passive buzzer → A3 = D3 (GPIO4), cuttable trace on the base
  #undef  PIN_HAPTIC
  #define PIN_HAPTIC        -1     // D2 (GPIO3) is the base's microSD CS; haptics are I²C-only (RTP + STANDBY), like mcring_v1
  #define HAPTIC_MOTOR_LRA   0     // Grove Haptic Motor = ERM → drv2605_init(false) in main.cpp
  #define IMU_POLL_MS       25     // poll the latched tap source every 25 ms (≈ 0.25 % of the I²C bus) — INT1 → D8 optional
  #if !defined(MCRING_IMU_INT_WIRED)
    #undef  PIN_IMU_INT
    #define PIN_IMU_INT     -1     // D8 may float (no jumper): no ISR, no EXT1 tap-wake; LIS3DH off in deep sleep
  #endif
  #if !defined(MCRING_BATT_DIVIDER_WIRED)
    #undef  PIN_BATTERY_ADC
    #define PIN_BATTERY_ADC -1     // A0 is an open Grove pin on this rig: battery_mv() = 0 → STATUS 255 % (unknown)
  #endif
#endif
#ifndef HAPTIC_MOTOR_LRA
  #define HAPTIC_MOTOR_LRA   1     // every other build drives the 8 mm LRA closed-loop (autocal at boot)
#endif
#ifndef IMU_POLL_MS
  #define IMU_POLL_MS        0     // 0 = interrupt-driven only (PIN_IMU_INT)
#endif

// Speaker present when all three I2S pins are configured (drives the SPEAKER_OK status flag).
#define HAS_SPEAKER  ((PIN_I2S_BCLK) >= 0 && (PIN_I2S_LRCLK) >= 0 && (PIN_I2S_DOUT) >= 0)

// ---------------------------------------------------------------------------
// Voice-first behavioural defaults (run-time overridable via SET_CONFIG keys 9..11, persisted in NVS)
// ---------------------------------------------------------------------------
#define DEFAULT_SPEAKER_VOLUME     255                               // key 9: 0..255 (255 = unity)
#define DEFAULT_CUES_MASK          (MC_CUES_HAPTIC | MC_CUES_LED)    // key 10: haptic + LED cues, no beep
#define DEFAULT_MIC_SOURCE         MC_MIC_SRC_RING                   // key 11: ring mic records on long press

// Cue timing (cues.cpp): one "tick" of haptic/LED
#define CUE_TICK_MS                60

// Audio-out stream (audio_out.cpp)
#define AUDIO_OUT_SAMPLE_RATE      16000
#define AUDIO_OUT_QUEUE_BLOCKS     48     // × 132 B = 6.3 KB; 48 × 16 ms = 768 ms of audio (spec: ≥ 32)
#define AUDIO_OUT_PREBUFFER_BLOCKS 24     // start playback after ~400 ms is queued
#define AUDIO_OUT_REBUFFER_BLOCKS  8      // after an underrun, resume once this much has accumulated
#define AUDIO_OUT_DMA_BUF_COUNT    6      // 6 × 256 frames = 96 ms of DMA (covers BLE jitter + a 15 ms transfer tick)
#define AUDIO_OUT_DMA_BUF_LEN      256    // frames (stereo 16-bit → 1 KB per buffer)

// LOW_BATTERY event thresholds (main.cpp)
#define LOW_BATTERY_PCT            15
#define LOW_BATTERY_REARM_PCT      20

#endif  // MCRING_CONFIG_AUDIO_H
