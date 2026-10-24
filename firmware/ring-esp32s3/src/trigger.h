#pragma once
#include <stdint.h>

enum class TriggerEvent : uint8_t {
  None = 0,
  Capture,          // short button press, double tap, or touch
  CaptureAndVoice,  // long button press: take a photo, then record a voice question while held
  VoiceEnd,         // button released after CaptureAndVoice
};

void trigger_init();
TriggerEvent trigger_tick();
bool trigger_button_down();
uint32_t trigger_touch_value();   // for calibration/debug
