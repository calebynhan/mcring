#include "imu_lis2dw12.h"
#include "log.h"
#include <Arduino.h>
#include <Wire.h>

static const char *TAG = "imu";

namespace {
uint8_t s_addr = 0x18;
bool    s_ok = false;

enum : uint8_t {
  REG_WHO_AM_I   = 0x0F,
  REG_CTRL1      = 0x20,
  REG_CTRL2      = 0x21,
  REG_CTRL3      = 0x22,
  REG_CTRL4_INT1 = 0x23,
  REG_CTRL5_INT2 = 0x24,
  REG_CTRL6      = 0x25,
  REG_TAP_THS_X  = 0x30,
  REG_TAP_THS_Y  = 0x31,
  REG_TAP_THS_Z  = 0x32,
  REG_INT_DUR    = 0x33,
  REG_WAKE_UP_THS= 0x34,
  REG_TAP_SRC    = 0x39,
  REG_CTRL7      = 0x3F,
};

bool wr(uint8_t reg, uint8_t val) {
  Wire.beginTransmission(s_addr);
  Wire.write(reg);
  Wire.write(val);
  return Wire.endTransmission() == 0;
}
int rd(uint8_t reg) {
  Wire.beginTransmission(s_addr);
  Wire.write(reg);
  if (Wire.endTransmission(false) != 0) return -1;
  if (Wire.requestFrom((int)s_addr, 1) != 1) return -1;
  return Wire.read();
}
uint8_t s_ths = 9;   // ~0.56 g at FS=2g (LSB = FS/32)
}  // namespace

bool imu_init(uint8_t addr) {
  s_addr = addr;
  int who = rd(REG_WHO_AM_I);
  if (who != 0x44) {
    // try the other address
    s_addr = (addr == 0x18) ? 0x19 : 0x18;
    who = rd(REG_WHO_AM_I);
    if (who != 0x44) { LOGW(TAG, "LIS2DW12 not found (who=0x%02x)", who); s_ok = false; return false; }
  }
  // Soft reset
  wr(REG_CTRL2, 0x44);   // BDU=1, IF_ADD_INC=1 (+ SOFT_RESET bit 6)
  delay(5);
  wr(REG_CTRL2, 0x04);   // IF_ADD_INC
  // ODR 400 Hz, high-performance mode: tap detection needs >= 400 Hz for good timing.
  wr(REG_CTRL1, 0x74);
  wr(REG_CTRL6, 0x04);   // FS=±2 g, BW_FILT=ODR/4, low-noise
  // Tap thresholds on all axes; Z register also carries axis enables (bits 7:5) and priority.
  wr(REG_TAP_THS_X, s_ths & 0x1F);
  wr(REG_TAP_THS_Y, s_ths & 0x1F);
  wr(REG_TAP_THS_Z, 0xE0 | (s_ths & 0x1F));
  // INT_DUR: LATENCY=7 (7*32 ODR = ~560 ms window for the 2nd tap), QUIET=2, SHOCK=2
  wr(REG_INT_DUR, (7 << 4) | (2 << 2) | 2);
  // Enable double-tap (bit 7), wake threshold 0
  wr(REG_WAKE_UP_THS, 0x80);
  // Route DOUBLE_TAP to INT1 (bit 3)
  wr(REG_CTRL4_INT1, 0x08);
  // Enable interrupts (bit 5), INT latched? (keep pulsed)
  wr(REG_CTRL7, 0x20);
  s_ok = true;
  LOGI(TAG, "LIS2DW12 ready at 0x%02x", s_addr);
  return true;
}

bool imu_available() { return s_ok; }

uint8_t imu_read_tap_src() {
  if (!s_ok) return 0;
  int v = rd(REG_TAP_SRC);
  return v < 0 ? 0 : (uint8_t)v;
}

void imu_set_tap_threshold(uint8_t ths) {
  s_ths = ths & 0x1F;
  if (!s_ok) return;
  wr(REG_TAP_THS_X, s_ths);
  wr(REG_TAP_THS_Y, s_ths);
  wr(REG_TAP_THS_Z, 0xE0 | s_ths);
}

void imu_sleep() { if (s_ok) wr(REG_CTRL1, 0x00); }
void imu_wake()  { if (s_ok) wr(REG_CTRL1, 0x74); }
