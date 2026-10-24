#include "settings.h"
#include "config.h"
#include "mcring_proto.h"
#include "log.h"
#include <Preferences.h>

static Settings s_cfg;
static Preferences prefs;
static const char *TAG = "cfg";

Settings &settings() { return s_cfg; }

void settings_load() {
  prefs.begin("mcring", true);
  s_cfg.trigger_mask      = prefs.getUChar("trig", DEFAULT_TRIGGER_MASK);
  s_cfg.jpeg_quality      = prefs.getUChar("q", DEFAULT_JPEG_QUALITY);
  s_cfg.frame_size        = prefs.getUChar("fs", DEFAULT_FRAME_SIZE);
  s_cfg.idle_sleep_s      = prefs.getUShort("sleep", DEFAULT_IDLE_SLEEP_S);
  s_cfg.led_brightness    = prefs.getUChar("led", DEFAULT_LED_BRIGHTNESS);
  s_cfg.haptic_strength   = prefs.getUChar("hap", DEFAULT_HAPTIC_STRENGTH);
  s_cfg.morse_wpm         = prefs.getUChar("wpm", DEFAULT_MORSE_WPM);
  s_cfg.feedback_channels = prefs.getUChar("fbch", DEFAULT_FEEDBACK_CHANNELS);
  prefs.end();
  LOGI(TAG, "trig=%02x q=%u fs=%u sleep=%us led=%u hap=%u wpm=%u ch=%02x",
       s_cfg.trigger_mask, s_cfg.jpeg_quality, s_cfg.frame_size, s_cfg.idle_sleep_s,
       s_cfg.led_brightness, s_cfg.haptic_strength, s_cfg.morse_wpm, s_cfg.feedback_channels);
}

void settings_save() {
  prefs.begin("mcring", false);
  prefs.putUChar("trig", s_cfg.trigger_mask);
  prefs.putUChar("q", s_cfg.jpeg_quality);
  prefs.putUChar("fs", s_cfg.frame_size);
  prefs.putUShort("sleep", s_cfg.idle_sleep_s);
  prefs.putUChar("led", s_cfg.led_brightness);
  prefs.putUChar("hap", s_cfg.haptic_strength);
  prefs.putUChar("wpm", s_cfg.morse_wpm);
  prefs.putUChar("fbch", s_cfg.feedback_channels);
  prefs.end();
}

bool settings_apply(uint8_t key, int32_t v) {
  switch (key) {
    case MC_CFG_TRIGGER_MASK:      if (v < 0 || v > 7) return false;   s_cfg.trigger_mask = v; break;
    case MC_CFG_DEFAULT_QUALITY:   if (v < 1 || v > 63) return false;  s_cfg.jpeg_quality = v; break;
    case MC_CFG_DEFAULT_FRAMESIZE: if (v < 1 || v > 5) return false;   s_cfg.frame_size = v; break;
    case MC_CFG_IDLE_SLEEP_S:      if (v < 0 || v > 65535) return false; s_cfg.idle_sleep_s = v; break;
    case MC_CFG_LED_BRIGHTNESS:    if (v < 0 || v > 255) return false; s_cfg.led_brightness = v; break;
    case MC_CFG_HAPTIC_STRENGTH:   if (v < 0 || v > 127) return false; s_cfg.haptic_strength = v; break;
    case MC_CFG_MORSE_WPM:         if (v < 5 || v > 40) return false;  s_cfg.morse_wpm = v; break;
    case MC_CFG_FEEDBACK_CHANNELS: if (v < 0 || v > 15) return false;  s_cfg.feedback_channels = v; break;
    default: return false;
  }
  settings_save();
  return true;
}
