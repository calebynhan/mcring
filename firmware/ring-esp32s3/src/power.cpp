#include "power.h"
#include "config.h"
#include "log.h"
#include "settings.h"
#include "imu_lis2dw12.h"
#include "feedback.h"
#include "audio_out.h"
#include <Arduino.h>
#include <esp_sleep.h>
#include <driver/rtc_io.h>

static const char *TAG = "pwr";
static uint32_t s_last_activity = 0;

void power_init() {
#if PIN_BATTERY_ADC >= 0
  analogReadResolution(12);
  analogSetPinAttenuation(PIN_BATTERY_ADC, ADC_11db);
#endif
  s_last_activity = millis();
  esp_sleep_wakeup_cause_t cause = esp_sleep_get_wakeup_cause();
  if (cause != ESP_SLEEP_WAKEUP_UNDEFINED) LOGI(TAG, "woke from deep sleep, cause %d", (int)cause);
}

uint16_t battery_mv() {
#if PIN_BATTERY_ADC >= 0
  uint32_t acc = 0;
  for (int i = 0; i < 8; i++) acc += analogReadMilliVolts(PIN_BATTERY_ADC);
  return (uint16_t)((acc / 8) * BATTERY_DIVIDER);
#else
  return 0;
#endif
}

uint8_t battery_pct() {
  uint16_t mv = battery_mv();
  if (mv < 1000) return 255;
  if (mv >= BATTERY_FULL_MV) return 100;
  if (mv <= BATTERY_EMPTY_MV) return 0;
  // Piecewise-linear LiPo curve (coarse but monotonic)
  static const uint16_t v[] = {3300, 3500, 3600, 3700, 3800, 3900, 4000, 4150};
  static const uint8_t  p[] = {0,    5,    15,   35,   55,   75,   90,   100};
  for (int i = 1; i < 8; i++) {
    if (mv <= v[i]) return (uint8_t)(p[i - 1] + (uint32_t)(mv - v[i - 1]) * (p[i] - p[i - 1]) / (v[i] - v[i - 1]));
  }
  return 100;
}

bool battery_charging() { return false; }

void power_note_activity() { s_last_activity = millis(); }

void power_deep_sleep_now() {
  LOGI(TAG, "deep sleep");
  Serial.flush();
  feedback_stop();                       // outputs off, WS2812 rail (PIN_RGB_PWR) dropped
  audio_out_sleep_prepare();             // amp rail off, I2S lines parked low
#if defined(PIN_RGB_PWR) && PIN_RGB_PWR >= 0
  digitalWrite(PIN_RGB_PWR, LOW);        // belt and braces: the load switch must be off in sleep
#endif
#if PIN_IMU_INT >= 0
  if (imu_available()) {
    imu_wake();  // tap-to-wake costs ~1 µA; INT1 (RTC GPIO) wakes us via EXT1
    esp_sleep_enable_ext1_wakeup(1ULL << PIN_IMU_INT, ESP_EXT1_WAKEUP_ANY_HIGH);
  } else {
    imu_sleep();
  }
#else
  imu_sleep();
#endif
#if PIN_BUTTON >= 0
  rtc_gpio_pullup_en((gpio_num_t)PIN_BUTTON);
  esp_sleep_enable_ext0_wakeup((gpio_num_t)PIN_BUTTON, 0);
#endif
  esp_deep_sleep_start();
}

void power_tick(bool connected, bool busy) {
  uint16_t idle_s = settings().idle_sleep_s;
  if (idle_s == 0 || connected || busy) { if (connected || busy) s_last_activity = millis(); return; }
  if (millis() - s_last_activity > (uint32_t)idle_s * 1000UL) power_deep_sleep_now();
}
