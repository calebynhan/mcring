/* Pattern player: LED via GPIO (or PWM), haptic via DRV2605 RTP over I2C. */
#include "feedback.h"
#include "mcring_cfg.h"
#include "mcring_morse.h"
#include "mcring_proto.h"
#include <zephyr/kernel.h>
#include <zephyr/device.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/drivers/i2c.h>
#include <zephyr/logging/log.h>
#include <string.h>

LOG_MODULE_REGISTER(mc_fb, LOG_LEVEL_INF);

#if DT_NODE_EXISTS(DT_ALIAS(led0))
static const struct gpio_dt_spec led = GPIO_DT_SPEC_GET(DT_ALIAS(led0), gpios);
#define HAVE_LED 1
#else
#define HAVE_LED 0
#endif
#if DT_NODE_EXISTS(DT_NODELABEL(drv2605))
static const struct i2c_dt_spec drv = I2C_DT_SPEC_GET(DT_NODELABEL(drv2605));
#define HAVE_DRV 1
#else
#define HAVE_DRV 0
#endif

static uint8_t units[MORSE_MAX_UNITS]; static size_t n_units, idx;
static uint16_t unit_ms; static uint8_t channels; static bool playing; static int64_t phase_start;
static uint8_t acc[MORSE_MAX_UNITS]; static bool acc_mask[MORSE_MAX_UNITS];
static uint16_t acc_expected, acc_received, acc_unit_ms; static uint8_t acc_channels;
static bool drv_ok;

static int drv_wr(uint8_t reg, uint8_t val) {
#if HAVE_DRV
  uint8_t b[2] = { reg, val };
  return i2c_write_dt(&drv, b, 2);
#else
  ARG_UNUSED(reg); ARG_UNUSED(val); return -ENODEV;
#endif
}

static void set_outputs(bool on) {
#if HAVE_LED
  if (channels & MC_CH_LED) gpio_pin_set_dt(&led, on);
#endif
  if ((channels & MC_CH_HAPTIC) && drv_ok) drv_wr(0x02, on ? 0x64 : 0x00);   /* RTP amplitude */
}

int feedback_init(void) {
#if HAVE_LED
  gpio_pin_configure_dt(&led, GPIO_OUTPUT_INACTIVE);
#endif
#if HAVE_DRV
  if (device_is_ready(drv.bus)) {
    uint8_t st; uint8_t reg = 0x00;
    if (i2c_write_read_dt(&drv, &reg, 1, &st, 1) == 0 && ((st >> 5) & 7) == 7) {
      drv_wr(0x01, 0x00); drv_wr(0x1A, 0x80 | 0x36); drv_wr(0x16, 0x3E); drv_wr(0x17, 0x8C); drv_wr(0x03, 6); drv_wr(0x01, 0x05);
      drv_ok = true; LOG_INF("DRV2605L ready");
    }
  }
#endif
  return 0;
}

bool feedback_playing(void) { return playing; }
void feedback_stop(void) { playing = false; n_units = idx = 0; uint8_t c = channels; channels = 0xFF; set_outputs(false); channels = c; }

void feedback_play_units(const uint8_t *u, size_t n, uint16_t ums, uint8_t ch) {
  if (!n) return;
  n = MIN(n, (size_t)MORSE_MAX_UNITS);
  memcpy(units, u, n); n_units = n; idx = 0; unit_ms = ums ? ums : 80; channels = ch ? ch : (MC_CH_LED | MC_CH_HAPTIC);
  playing = true; phase_start = k_uptime_get(); set_outputs(true);
}

void feedback_play_text(const char *text, uint8_t wpm, uint8_t ch) {
  if (!wpm) wpm = 15;
  mc_morse_spacing_t sp; mc_morse_spacing_farnsworth(&sp, wpm, wpm > 10 ? wpm / 2 : 0);
  uint8_t buf[MORSE_MAX_UNITS]; int tr;
  size_t n = mc_morse_encode(text, &sp, buf, sizeof buf, &tr);
  feedback_play_units(buf, n, mc_morse_unit_ms(wpm), ch);
}

void feedback_tick(void) {
  if (!playing) return;
  int64_t now = k_uptime_get();
  int64_t dur = (int64_t)units[idx] * unit_ms;
  if (now - phase_start < dur) return;
  idx++; phase_start += dur;
  if (idx >= n_units) { feedback_stop(); return; }
  set_outputs((idx % 2) == 0);
}

void feedback_units_begin(uint16_t n, uint16_t ums, uint8_t ch) {
  acc_expected = MIN(n, MORSE_MAX_UNITS); acc_unit_ms = ums; acc_channels = ch; acc_received = 0; memset(acc_mask, 0, sizeof acc_mask);
}
void feedback_units_put(uint16_t off, const uint8_t *d, size_t len) {
  for (size_t i = 0; i < len; i++) {
    uint16_t k = off + i; if (k >= acc_expected) break;
    if (!acc_mask[k]) { acc_mask[k] = true; acc_received++; }
    acc[k] = d[i] ? d[i] : 1;
  }
  if (acc_expected && acc_received >= acc_expected) { feedback_play_units(acc, acc_expected, acc_unit_ms, acc_channels); acc_expected = 0; }
}
