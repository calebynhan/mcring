#pragma once
#include <stdint.h>

// Raw user-input events. main.cpp turns them into protocol Events (BUTTON_DOWN/UP, DOUBLE_TAP, TOUCH)
// and into actions (photo, "ask a question" voice session).
enum class TriggerEvent : uint8_t {
  None = 0,
  ButtonDown,    // debounced press                              → BUTTON_DOWN
  ShortPress,    // released before BUTTON_LONG_PRESS_MS        → BUTTON_UP + photo
  LongPress,     // held ≥ BUTTON_LONG_PRESS_MS (fires once)    → start "ask"
  LongRelease,   // released after a LongPress                  → BUTTON_UP + end "ask"
  DoubleTap,     // IMU double tap                              → DOUBLE_TAP (hands-free "ask")
  Touch,         // capacitive pad held ≥ 150 ms                → TOUCH + photo
};

void trigger_init();
TriggerEvent trigger_tick();
bool trigger_button_down();
uint32_t trigger_button_held_ms();   // duration of the last completed press (valid after Short/LongRelease)
uint32_t trigger_touch_value();      // for calibration/debug
