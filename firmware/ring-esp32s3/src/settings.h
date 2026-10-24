#pragma once
#include <stdint.h>

struct Settings {
  uint8_t trigger_mask;
  uint8_t jpeg_quality;
  uint8_t frame_size;
  uint16_t idle_sleep_s;
  uint8_t led_brightness;
  uint8_t haptic_strength;
  uint8_t morse_wpm;
  uint8_t feedback_channels;
};

Settings &settings();
void settings_load();
void settings_save();
// Apply a SET_CONFIG key/value. Returns false for unknown keys / out-of-range values.
bool settings_apply(uint8_t key, int32_t value);
