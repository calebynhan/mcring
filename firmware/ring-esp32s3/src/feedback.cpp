#include "feedback.h"
#include "config.h"
#include "drv2605.h"
#include "log.h"
#include "mcring_morse.h"
#include "mcring_proto.h"
#include "settings.h"
#include <Arduino.h>

static const char *TAG = "fb";

namespace {
uint8_t  s_units[MORSE_MAX_UNITS];
size_t   s_n = 0;
size_t   s_idx = 0;
uint16_t s_unit_ms = 80;
uint8_t  s_channels = 0;
bool     s_playing = false;
uint32_t s_phase_start = 0;
bool     s_on = false;

// multi-write accumulator
uint16_t s_acc_expected = 0, s_acc_unit_ms = 80;
uint8_t  s_acc_channels = 0;
uint16_t s_acc_received = 0;
uint8_t  s_acc[MORSE_MAX_UNITS];
bool     s_acc_mask[MORSE_MAX_UNITS];

uint32_t s_rgb_off_ms = 0;

const int LEDC_CH_LED = 2;      // channel 0/1 are taken by the camera XCLK
const int LEDC_CH_BUZ = 3;

void led_write(bool on) {
#if PIN_LED >= 0
  uint8_t b = settings().led_brightness;
  uint32_t duty = on ? b : 0;
  if (LED_ACTIVE_LOW) duty = 255 - duty;
  ledcWrite(LEDC_CH_LED, duty);
#endif
#if PIN_RGB >= 0
  if (on) neopixelWrite(PIN_RGB, 0, settings().led_brightness / 2, settings().led_brightness);
  else if (s_rgb_off_ms == 0) neopixelWrite(PIN_RGB, 0, 0, 0);
#endif
  (void)on;
}

void haptic_write(bool on) {
  if (drv2605_available()) {
    drv2605_set(on ? settings().haptic_strength : 0);
  }
#if PIN_HAPTIC >= 0
  digitalWrite(PIN_HAPTIC, on ? HIGH : LOW);   // also drives a bare MOSFET/ERM if fitted
#endif
}

void buzzer_write(bool on) {
#if PIN_BUZZER >= 0
  if (on) ledcWriteTone(LEDC_CH_BUZ, 4000); else ledcWriteTone(LEDC_CH_BUZ, 0);
#endif
  (void)on;
}

void aux_write(bool on) {
#if PIN_AUX >= 0
  digitalWrite(PIN_AUX, on ? HIGH : LOW);
#endif
  (void)on;
}

void set_outputs(bool on) {
  if (s_channels & MC_CH_LED)    led_write(on);
  if (s_channels & MC_CH_HAPTIC) haptic_write(on);
  if (s_channels & MC_CH_BUZZER) buzzer_write(on);
  if (s_channels & MC_CH_AUX)    aux_write(on);
  s_on = on;
}

void all_off() {
  led_write(false); haptic_write(false); buzzer_write(false); aux_write(false);
  s_on = false;
}
}  // namespace

void feedback_init() {
#if PIN_LED >= 0
  ledcSetup(LEDC_CH_LED, 5000, 8);
  ledcAttachPin(PIN_LED, LEDC_CH_LED);
#endif
#if PIN_BUZZER >= 0
  ledcSetup(LEDC_CH_BUZ, 4000, 8);
  ledcAttachPin(PIN_BUZZER, LEDC_CH_BUZ);
#endif
#if PIN_HAPTIC >= 0
  pinMode(PIN_HAPTIC, OUTPUT);
#endif
#if PIN_AUX >= 0
  pinMode(PIN_AUX, OUTPUT);
#endif
  all_off();
}

bool feedback_playing() { return s_playing; }

void feedback_stop() {
  s_playing = false;
  s_n = s_idx = 0;
  all_off();
  if (drv2605_available()) drv2605_standby(true);
}

void feedback_play_units(const uint8_t *units, size_t n, uint16_t unit_ms, uint8_t channels) {
  if (n == 0) return;
  if (n > MORSE_MAX_UNITS) n = MORSE_MAX_UNITS;
  memcpy(s_units, units, n);
  s_n = n; s_idx = 0;
  s_unit_ms = unit_ms ? unit_ms : 80;
  s_channels = channels ? channels : settings().feedback_channels;
  if (drv2605_available()) drv2605_standby(false);
  s_playing = true;
  s_phase_start = millis();
  set_outputs(true);
  LOGI(TAG, "play %u units @ %u ms, ch=%02x (%lu ms total)", (unsigned)n, s_unit_ms, s_channels,
       (unsigned long)mc_morse_pattern_units(s_units, s_n) * s_unit_ms);
}

void feedback_play_morse_text(const char *text, uint8_t wpm, uint8_t channels) {
  if (!wpm) wpm = settings().morse_wpm;
  mc_morse_spacing_t sp;
  mc_morse_spacing_farnsworth(&sp, wpm, (uint8_t)(wpm > 10 ? wpm / 2 : 0));
  uint8_t buf[MORSE_MAX_UNITS];
  int trunc = 0;
  size_t n = mc_morse_encode(text, &sp, buf, sizeof buf, &trunc);
  if (trunc) LOGW(TAG, "morse text truncated");
  feedback_play_units(buf, n, mc_morse_unit_ms(wpm), channels);
}

void feedback_tick() {
  uint32_t now = millis();
#if PIN_RGB >= 0
  if (s_rgb_off_ms && (int32_t)(now - s_rgb_off_ms) >= 0) { s_rgb_off_ms = 0; if (!s_playing) neopixelWrite(PIN_RGB, 0, 0, 0); }
#endif
  if (!s_playing) return;
  uint32_t dur = (uint32_t)s_units[s_idx] * s_unit_ms;
  if (now - s_phase_start < dur) return;
  s_idx++;
  s_phase_start += dur;
  if (s_idx >= s_n) { feedback_stop(); return; }
  set_outputs((s_idx % 2) == 0);   // even index = ON
}

void feedback_signal_ok() {
  // <SN> ...-.  on LED + haptic tick, fast
  static const uint8_t p[] = {1,1,1,1,1,1,3,1,1};
  feedback_play_units(p, sizeof p, 50, MC_CH_LED | (drv2605_available() ? MC_CH_HAPTIC : 0));
}
void feedback_signal_error() {
  static const uint8_t p[] = {1,1,1,1,1,1,1,1,1,1,1,1,1,1,1};   // <HH> ........
  feedback_play_units(p, sizeof p, 60, MC_CH_LED);
}
void feedback_signal_connected() {
  static const uint8_t p[] = {1,2,1};
  feedback_play_units(p, sizeof p, 60, MC_CH_LED);
}

void feedback_rgb(uint8_t r, uint8_t g, uint8_t b, uint16_t ms) {
#if PIN_RGB >= 0
  neopixelWrite(PIN_RGB, r, g, b);
  s_rgb_off_ms = millis() + (ms ? ms : 200);
#else
  (void)r; (void)g; (void)b;
  // Mono LED: one flash of the requested length
  uint8_t u = (uint8_t)((ms ? ms : 200) / 50); if (!u) u = 1;
  feedback_play_units(&u, 1, 50, MC_CH_LED);
#endif
}

void feedback_units_begin(uint16_t n, uint16_t unit_ms, uint8_t channels) {
  if (n > MORSE_MAX_UNITS) n = MORSE_MAX_UNITS;
  s_acc_expected = n; s_acc_unit_ms = unit_ms; s_acc_channels = channels; s_acc_received = 0;
  memset(s_acc_mask, 0, sizeof s_acc_mask);
}

void feedback_units_put(uint16_t offset, const uint8_t *data, size_t len) {
  for (size_t i = 0; i < len; i++) {
    uint16_t k = offset + i;
    if (k >= s_acc_expected) break;
    if (!s_acc_mask[k]) { s_acc_mask[k] = true; s_acc_received++; }
    s_acc[k] = data[i] ? data[i] : 1;
  }
  if (s_acc_expected && s_acc_received >= s_acc_expected) {
    feedback_play_units(s_acc, s_acc_expected, s_acc_unit_ms, s_acc_channels);
    s_acc_expected = 0;
  }
}
