#pragma once
#include <stdint.h>

struct Settings {
  uint8_t trigger_mask;
  uint8_t jpeg_quality;
  uint8_t frame_size;
  uint16_t idle_sleep_s;
  uint8_t led_brightness;
  uint8_t haptic_strength;
  uint8_t morse_wpm;          // legacy (silent pattern mode)
  uint8_t feedback_channels;  // legacy
  uint8_t speaker_volume;     // key 9:  0..255 master gain of the on-ring speaker
  uint8_t cues_mask;          // key 10: MC_CUES_HAPTIC | MC_CUES_LED | MC_CUES_BEEP
  uint8_t mic_source;         // key 11: MC_MIC_SRC_RING / MC_MIC_SRC_PHONE
};

Settings &settings();
void settings_load();
void settings_save();
// Apply a SET_CONFIG key/value. Returns false for unknown keys / out-of-range values.
bool settings_apply(uint8_t key, int32_t value);
