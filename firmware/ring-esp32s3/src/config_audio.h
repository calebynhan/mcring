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
  // Placeholders: the hardware design pass assigns the speaker pins in hardware/pinmap.md and
  // config.h's BOARD_MCRING_V1 section. -1 = no speaker → STATUS flag SPEAKER_OK stays clear.
  #define PIN_I2S_BCLK     -1
  #define PIN_I2S_LRCLK    -1
  #define PIN_I2S_DOUT     -1
  #define PIN_SPEAKER_EN   -1

#else
  #define PIN_I2S_BCLK     -1
  #define PIN_I2S_LRCLK    -1
  #define PIN_I2S_DOUT     -1
  #define PIN_SPEAKER_EN   -1
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
