/*
 * Board pin maps and compile-time defaults.
 * Choose a board with -DBOARD_XIAO_ESP32S3_SENSE or -DBOARD_MCRING_V1 (see platformio.ini).
 */
#pragma once
#include <stdint.h>

#ifndef MCRING_FW_VERSION
#define MCRING_FW_VERSION "0.1.0-dev"
#endif

// ---------------------------------------------------------------------------
// Seeed XIAO ESP32S3 Sense — stage 0 dev kit
//   XIAO header: D0=GPIO1(A0) D1=GPIO2 D2=GPIO3 D3=GPIO4 D4=GPIO5(SDA) D5=GPIO6(SCL)
//                D6=GPIO43(TX) D7=GPIO44(RX) D8=GPIO7 D9=GPIO8 D10=GPIO9
//   On-board: user LED GPIO21 (active low). Sense board: OV2640 DVP + PDM mic (CLK 42, DATA 41).
// ---------------------------------------------------------------------------
#if defined(BOARD_XIAO_ESP32S3_SENSE)
  #define BOARD_NAME            "xiao-esp32s3-sense"
  #define HAS_CAMERA            1
  #define HAS_PDM_MIC           1

  // Camera (OV2640/OV3660 on the Sense expansion board)
  #define CAM_PIN_PWDN   -1
  #define CAM_PIN_RESET  -1
  #define CAM_PIN_XCLK   10
  #define CAM_PIN_SIOD   40
  #define CAM_PIN_SIOC   39
  #define CAM_PIN_Y9     48
  #define CAM_PIN_Y8     11
  #define CAM_PIN_Y7     12
  #define CAM_PIN_Y6     14
  #define CAM_PIN_Y5     16
  #define CAM_PIN_Y4     18
  #define CAM_PIN_Y3     17
  #define CAM_PIN_Y2     15
  #define CAM_PIN_VSYNC  38
  #define CAM_PIN_HREF   47
  #define CAM_PIN_PCLK   13
  #define PIN_CAM_PWR    -1    // no load switch on the dev kit (see hardware/pinmap.md for stage 1)

  // Mic
  #define PIN_PDM_CLK    42
  #define PIN_PDM_DATA   41

  // User I/O (external parts on the XIAO header)
  #define PIN_BATTERY_ADC 1    // A0: optional 2:1 divider from BAT+ (set BATTERY_DIVIDER=2.0f)
  #define PIN_BUTTON      2    // D1: tactile switch to GND (internal pull-up), RTC-capable → deep-sleep wake
  #define PIN_HAPTIC      3    // D2: N-MOSFET gate for an ERM/LRA, or DRV2605L EN
  #define PIN_BUZZER      4    // D3: piezo sounder (LEDC tone)
  #define PIN_I2C_SDA     5    // D4
  #define PIN_I2C_SCL     6    // D5
  #define PIN_IMU_INT     7    // D8: LIS2DW12 INT1 (RTC-capable → deep-sleep wake)
  #define PIN_TOUCH       8    // D9: capacitive pad (touch channel T8)
  #define PIN_AUX         9    // D10: aux actuator enable (air-puff driver experiment)
  #define PIN_LED        21    // on-board user LED
  #define LED_ACTIVE_LOW  1
  #define PIN_RGB        -1    // no WS2812 on the dev kit
  #define PIN_RGB_PWR    -1    // no WS2812 supply switch on the dev kit
  #define PIN_CHG        -1    // charger status not wired on the dev kit

// ---------------------------------------------------------------------------
// mcring v1 — stage 1 custom board (placeholders; finalise with hardware/pinmap.md)
// ---------------------------------------------------------------------------
#elif defined(BOARD_MCRING_V1)
  #define BOARD_NAME            "mcring-v1"
  #define HAS_CAMERA            1
  #define HAS_PDM_MIC           1

  #define CAM_PIN_PWDN   -1
  #define CAM_PIN_RESET  -1
  #define CAM_PIN_XCLK   10
  #define CAM_PIN_SIOD   40
  #define CAM_PIN_SIOC   39
  #define CAM_PIN_Y9     48
  #define CAM_PIN_Y8     11
  #define CAM_PIN_Y7     12
  #define CAM_PIN_Y6     14
  #define CAM_PIN_Y5     16
  #define CAM_PIN_Y4     18
  #define CAM_PIN_Y3     17
  #define CAM_PIN_Y2     15
  #define CAM_PIN_VSYNC  38
  #define CAM_PIN_HREF   47
  #define CAM_PIN_PCLK   13
  #define PIN_CAM_PWR    21    // TPS22916 ON for the camera rail (CAM_3V3 -> 2.8 V AVDD + 1.2 V DVDD LDOs).
                               // IO21: RTC GPIO, no boot-time activity, hold-capable in deep sleep; 100k
                               // pull-down on the board keeps the camera off while the pin floats.
                               // (was IO19 = native USB D-; IO19/IO20 are now USB test pads, see hardware/electrical)

  #define PIN_PDM_CLK    42
  #define PIN_PDM_DATA   41

  #define PIN_BATTERY_ADC 1    // 1 M / 1 M divider + 100 nF (BATTERY_DIVIDER 2.0; 2 µA permanent drain)
  #define PIN_BUTTON      2
  #define PIN_HAPTIC     -1    // DRV2605L EN is tied to 3V3 on this board: haptics are I2C-only (drv2605_set /
                               // drv2605_standby). MUST stay -1 — IO3 is the charger /CHG input (PIN_CHG) and
                               // driving it as an output would fight the BQ25100's open drain.
  #define PIN_BUZZER      4
  #define PIN_I2C_SDA     5
  #define PIN_I2C_SCL     6
  #define PIN_IMU_INT     7
  #define PIN_TOUCH       8
  #define PIN_AUX         9
  #define PIN_LED        -1
  #define LED_ACTIVE_LOW  0
  #define PIN_RGB        43    // WS2812B-2020 data via 1 k. IO43 = UART0 TXD0, free because logging is USB-CDC;
                               // ROM boot output on TXD0 only reaches the LED through 1 k while its rail is off.
                               // (was IO20 = native USB D+)
  #define PIN_RGB_PWR    33    // TPS22916 ON for the WS2812 rail (3V3 -> VLED), net LED_PWR_EN, 4.7k pull-down.
                               // HW NOTE: the LED is unpowered until firmware drives this HIGH before
                               // neopixelWrite() (and LOW before deep sleep) — see hardware/electrical/README.md §7.
                               // IO33 is a plain GPIO on the N4R2 module (only octal-PSRAM parts use IO33-37).
  #define PIN_CHG         3    // BQ25100 /CHG, open drain, active LOW while charging (100k pull-up on the board).
                               // Input only; battery_charging() should read it (firmware follow-up).

#else
  #error "Define a board: -DBOARD_XIAO_ESP32S3_SENSE or -DBOARD_MCRING_V1"
#endif

// ---------------------------------------------------------------------------
// Behavioural defaults (overridable at run time via SET_CONFIG, persisted in NVS)
// ---------------------------------------------------------------------------
#define DEFAULT_TRIGGER_MASK      (MC_TRIG_BUTTON | MC_TRIG_DOUBLETAP)
#define DEFAULT_JPEG_QUALITY      12      // 1 (best) .. 63 (worst)
#define DEFAULT_FRAME_SIZE        MC_FS_QVGA
#define DEFAULT_IDLE_SLEEP_S      120     // deep sleep after this long disconnected & idle (0 = never)
#define DEFAULT_LED_BRIGHTNESS    96
#define DEFAULT_HAPTIC_STRENGTH   100     // DRV2605 RTP amplitude 0..127
#define DEFAULT_MORSE_WPM         15
#define DEFAULT_FEEDBACK_CHANNELS (MC_CH_LED | MC_CH_HAPTIC)

#define BATTERY_DIVIDER           2.0f    // (R1+R2)/R2 of the divider on PIN_BATTERY_ADC
#define BATTERY_FULL_MV           4150
#define BATTERY_EMPTY_MV          3300

#define MAX_QUEUED_CAPTURES       3
#define TRANSFER_ACK_TIMEOUT_MS   3000
#define TRANSFER_MAX_ROUNDS       5
#define STATUS_PERIOD_MS          30000

#define BUTTON_LONG_PRESS_MS      700
#define BUTTON_DEBOUNCE_MS        30
#define VOICE_CLIP_MAX_S          8       // RECORD_START / long press cap (protocol: max 8 s)
#define VOICE_SAMPLE_RATE         16000

#define MORSE_MAX_UNITS           1024

// Speaker pins, cue/mic defaults and audio-out tuning (voice-first additions; keeps this file's board sections intact)
#include "config_audio.h"
