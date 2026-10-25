#include "trigger.h"
#include "config.h"
#include "log.h"
#include "settings.h"
#include "imu_lis2dw12.h"
#include "mcring_proto.h"
#include <Arduino.h>

static const char *TAG = "trig";

namespace {
// Button
bool     s_btn_last = false;
bool     s_btn_stable = false;
uint32_t s_btn_change_ms = 0;
uint32_t s_btn_down_ms = 0;
uint32_t s_btn_held_ms = 0;
bool     s_long_fired = false;

// Touch
uint32_t s_touch_base = 0;
uint32_t s_touch_last_ms = 0;
bool     s_touch_active = false;

// IMU
volatile bool s_imu_irq = false;
uint32_t s_last_tap_ms = 0;
#if IMU_POLL_MS > 0
uint32_t s_imu_poll_ms = 0;   // no-solder rig: INT1 → D8 may be left off, so the (latched) tap source is also polled (config_audio.h)
#endif

void IRAM_ATTR imu_isr() { s_imu_irq = true; }

bool read_button_raw() {
#if PIN_BUTTON >= 0
  return digitalRead(PIN_BUTTON) == LOW;
#else
  return false;
#endif
}
}  // namespace

void trigger_init() {
#if PIN_BUTTON >= 0
  pinMode(PIN_BUTTON, INPUT_PULLUP);
#endif
#if PIN_TOUCH >= 0
  // Baseline over a few reads; ESP32-S3 touch values *increase* when touched.
  uint32_t acc = 0;
  for (int i = 0; i < 8; i++) { acc += touchRead(PIN_TOUCH); delay(5); }
  s_touch_base = acc / 8;
  LOGI(TAG, "touch baseline %lu", (unsigned long)s_touch_base);
#endif
#if PIN_IMU_INT >= 0
  if (imu_available()) {
    pinMode(PIN_IMU_INT, INPUT);
    attachInterrupt(digitalPinToInterrupt(PIN_IMU_INT), imu_isr, RISING);
  }
#endif
}

bool trigger_button_down() { return s_btn_stable; }
uint32_t trigger_button_held_ms() { return s_btn_held_ms; }
uint32_t trigger_touch_value() {
#if PIN_TOUCH >= 0
  return touchRead(PIN_TOUCH);
#else
  return 0;
#endif
}

TriggerEvent trigger_tick() {
  const uint8_t mask = settings().trigger_mask;
  uint32_t now = millis();

  // ---- Button: debounce + short/long press -------------------------------------
  if (mask & MC_TRIG_BUTTON) {
    bool raw = read_button_raw();
    if (raw != s_btn_last) { s_btn_last = raw; s_btn_change_ms = now; }
    if (now - s_btn_change_ms >= BUTTON_DEBOUNCE_MS && raw != s_btn_stable) {
      s_btn_stable = raw;
      if (raw) {
        s_btn_down_ms = now;
        s_long_fired = false;
        return TriggerEvent::ButtonDown;
      } else {
        s_btn_held_ms = now - s_btn_down_ms;
        return s_long_fired ? TriggerEvent::LongRelease : TriggerEvent::ShortPress;
      }
    }
    if (s_btn_stable && !s_long_fired && now - s_btn_down_ms >= BUTTON_LONG_PRESS_MS) {
      s_long_fired = true;
      return TriggerEvent::LongPress;
    }
  }

  // ---- IMU double tap ------------------------------------------------------------
#if IMU_POLL_MS > 0
  // Without the INT1 wire the ISR never fires: read the tap source every IMU_POLL_MS instead (the LIS3DH latches
  // the click until CLICK_SRC is read, so nothing is lost; only tap-to-wake from deep sleep needs the wire).
  if (!s_imu_irq && imu_available() && now - s_imu_poll_ms >= IMU_POLL_MS) { s_imu_poll_ms = now; s_imu_irq = true; }
#endif
  if ((mask & MC_TRIG_DOUBLETAP) && s_imu_irq) {
    s_imu_irq = false;
    uint8_t src = imu_read_tap_src();
    if (src & IMU_TAP_DOUBLE) {
      if (now - s_last_tap_ms > 800) {   // ignore a burst of taps
        s_last_tap_ms = now;
        LOGI(TAG, "double tap");
        return TriggerEvent::DoubleTap;
      }
    }
  }

  // ---- Capacitive touch: deliberate press on the pad for >= 150 ms ----------------
#if PIN_TOUCH >= 0
  if (mask & MC_TRIG_TOUCH) {
    if (now - s_touch_last_ms >= 25) {
      s_touch_last_ms = now;
      uint32_t v = touchRead(PIN_TOUCH);
      bool touched = v > s_touch_base + s_touch_base / 4;   // +25 %
      static uint32_t first_ms = 0;
      if (!touched) {
        // slow baseline tracking
        s_touch_base = (s_touch_base * 31 + v) / 32;
        s_touch_active = false;
        first_ms = 0;
      } else if (!s_touch_active) {
        if (first_ms == 0) first_ms = now;
        if (now - first_ms >= 150) {
          s_touch_active = true;
          first_ms = 0;
          LOGI(TAG, "touch (%lu > %lu)", (unsigned long)v, (unsigned long)s_touch_base);
          return TriggerEvent::Touch;
        }
      }
    }
  }
#endif
  return TriggerEvent::None;
}
