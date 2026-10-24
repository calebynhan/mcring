#include "drv2605.h"
#include "log.h"
#include <Arduino.h>
#include <Wire.h>

static const char *TAG = "drv";

namespace {
uint8_t s_addr = 0x5A;
bool    s_ok = false;
bool    s_lra = true;

enum : uint8_t {
  REG_STATUS = 0x00, REG_MODE = 0x01, REG_RTP = 0x02, REG_LIB = 0x03,
  REG_WAVESEQ1 = 0x04, REG_GO = 0x0C, REG_ODT = 0x0D,
  REG_RATED_V = 0x16, REG_OD_CLAMP = 0x17, REG_FEEDBACK = 0x1A,
  REG_CTRL1 = 0x1B, REG_CTRL2 = 0x1C, REG_CTRL3 = 0x1D,
};
enum : uint8_t { MODE_INT_TRIG = 0x00, MODE_RTP = 0x05, MODE_AUTOCAL = 0x07, MODE_STANDBY = 0x40 };

bool wr(uint8_t r, uint8_t v) {
  Wire.beginTransmission(s_addr); Wire.write(r); Wire.write(v);
  return Wire.endTransmission() == 0;
}
int rd(uint8_t r) {
  Wire.beginTransmission(s_addr); Wire.write(r);
  if (Wire.endTransmission(false) != 0) return -1;
  if (Wire.requestFrom((int)s_addr, 1) != 1) return -1;
  return Wire.read();
}
}  // namespace

bool drv2605_init(bool lra, uint8_t addr) {
  s_addr = addr; s_lra = lra;
  int st = rd(REG_STATUS);
  if (st < 0 || ((st >> 5) & 0x07) != 0x07) {   // DEVICE_ID[7:5] = 111 for DRV2605L
    LOGW(TAG, "DRV2605L not found (status=0x%02x)", st);
    s_ok = false;
    return false;
  }
  wr(REG_MODE, MODE_INT_TRIG);              // out of standby
  wr(REG_RTP, 0);
  wr(REG_WAVESEQ1, 0);
  wr(REG_ODT, 0);
  // Feedback control: bit7 N_ERM_LRA, FB_BRAKE_FACTOR=3 (bits 6:4 = 011), LOOP_GAIN=1 (bits 3:2 = 01)
  wr(REG_FEEDBACK, (lra ? 0x80 : 0x00) | 0x36);
  if (lra) {
    wr(REG_RATED_V, 0x3E);                  // ~1.8 Vrms for 8 mm 235 Hz LRA (tune per datasheet)
    wr(REG_OD_CLAMP, 0x8C);
    wr(REG_LIB, 6);                          // LRA library
    // CTRL3: default closed-loop LRA; RTP data signed (default)
  } else {
    wr(REG_RATED_V, 0x90);
    wr(REG_OD_CLAMP, 0xA4);
    wr(REG_LIB, 1);
  }
  wr(REG_MODE, MODE_RTP);
  s_ok = true;
  LOGI(TAG, "DRV2605L ready (%s)", lra ? "LRA" : "ERM");
  return true;
}

bool drv2605_available() { return s_ok; }

void drv2605_set(uint8_t amp) {
  if (!s_ok) return;
  if (amp > 127) amp = 127;
  wr(REG_RTP, amp);                          // signed mode: 0x00..0x7F positive drive
}

void drv2605_standby(bool on) {
  if (!s_ok) return;
  wr(REG_MODE, on ? (MODE_STANDBY | MODE_RTP) : MODE_RTP);
}

bool drv2605_autocal() {
  if (!s_ok) return false;
  wr(REG_MODE, MODE_AUTOCAL);
  wr(REG_GO, 1);
  uint32_t t0 = millis();
  while (millis() - t0 < 1500) {
    int go = rd(REG_GO);
    if (go == 0) break;
    delay(10);
  }
  int st = rd(REG_STATUS);
  bool ok = st >= 0 && !(st & 0x08);        // DIAG_RESULT bit 3: 0 = pass
  wr(REG_MODE, MODE_RTP);
  LOGI(TAG, "autocal %s (status 0x%02x)", ok ? "ok" : "FAILED", st);
  return ok;
}
