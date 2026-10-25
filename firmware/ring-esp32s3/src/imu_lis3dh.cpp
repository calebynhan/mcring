/*
 * IMU: LIS3DH back-end + run-time dispatch of the imu_* API between the LIS2DW12 (stage-1 part) and the LIS3DH
 * (STEMMA QT breakout of the no-solder stage-0 kit). See imu_lis3dh.h / imu_lis2dw12.h.
 *
 * Build note. imu_lis2dw12.cpp defines the imu_* functions for the LIS2DW12 and is kept untouched; this file
 * #includes it below under lis2dw12_* names (six #defines) and then defines the real imu_* entry points, which
 * pick a back-end at boot. imu_lis2dw12.cpp must therefore NOT be compiled on its own — platformio.ini excludes
 * it (build_src_filter in [env]); compiling it anyway gives duplicate-symbol link errors, never a silent mix-up.
 * (A follow-up may rename the six definitions in imu_lis2dw12.cpp to lis2dw12_* and drop the include trick.)
 */
#include "imu_lis3dh.h"
#include "imu_lis2dw12.h"
#include "log.h"
#include <Arduino.h>
#include <Wire.h>

// ===========================================================================================================
// LIS3DH back-end
// ===========================================================================================================
namespace lis3dh {
static const char *TAG = "imu";
uint8_t s_addr = 0x18;
bool    s_ok = false;
uint8_t s_ths = 9;          // imu_* units (LIS2DW12 TAP_THS LSB = FS/32 = 62.5 mg at ±2 g): 9 ≈ 0.56 g, like the LIS2DW12 default

enum : uint8_t {
  REG_WHO_AM_I     = 0x0F,  // reads 0x33
  REG_CTRL_REG1    = 0x20,  // ODR[3:0] LPen Zen Yen Xen
  REG_CTRL_REG2    = 0x21,  // HPM[1:0] HPCF[1:0] FDS HPCLICK HP_IA2 HP_IA1
  REG_CTRL_REG3    = 0x22,  // I1_CLICK I1_IA1 I1_IA2 I1_ZYXDA I1_321DA I1_WTM I1_OVERRUN -
  REG_CTRL_REG4    = 0x23,  // BDU BLE FS[1:0] HR ST[1:0] SIM
  REG_CTRL_REG5    = 0x24,  // BOOT FIFO_EN - - LIR_INT1 D4D_INT1 LIR_INT2 D4D_INT2
  REG_CTRL_REG6    = 0x25,  // I2_CLICK I2_IA1 I2_IA2 I2_BOOT I2_ACT - INT_POLARITY -
  REG_CLICK_CFG    = 0x38,  // - - ZD ZS YD YS XD XS
  REG_CLICK_SRC    = 0x39,  // - IA DCLICK SCLICK Sign Z Y X
  REG_CLICK_THS    = 0x3A,  // LIR_Click Ths[6:0]   (1 LSB = FS/128 = 15.6 mg at ±2 g)
  REG_TIME_LIMIT   = 0x3B,  // TLI[6:0]             (1 LSB = 1/ODR = 2.5 ms at 400 Hz)
  REG_TIME_LATENCY = 0x3C,  // TLA[7:0]
  REG_TIME_WINDOW  = 0x3D,  // TW[7:0]
};

// Click engine timing at ODR 400 Hz, chosen to mirror the LIS2DW12 settings in imu_lis2dw12.cpp so the tuning
// notes in docs/07-build-guide.md §1.9 apply to both chips:
//   TIME_LIMIT   16 × 2.5 ms = 40 ms   over-threshold pulse must end within this (LIS2DW12 SHOCK = 2 → 40 ms)
//   TIME_LATENCY  8 × 2.5 ms = 20 ms   dead time after the first click           (LIS2DW12 QUIET = 2 → 20 ms)
//   TIME_WINDOW 224 × 2.5 ms = 560 ms  the second click must start inside this   (LIS2DW12 LATENCY = 7 → 560 ms)
constexpr uint8_t ODR_400HZ_XYZ   = 0x77;   // ODR = 0111 (400 Hz), normal mode (LPen = 0), X/Y/Z enabled (~185 µA)
constexpr uint8_t HP_ON_CLICK     = 0x84;   // HPM = 10 (normal), HPCF = 00 (~8 Hz at 400 Hz), HPCLICK = 1: gravity out of the click data
constexpr uint8_t I1_CLICK        = 0x80;   // CTRL_REG3: click interrupt on INT1 (active high, CTRL_REG6 INT_POLARITY = 0)
constexpr uint8_t BDU_FS2G        = 0x80;   // CTRL_REG4: block update, ±2 g, 10-bit normal mode
constexpr uint8_t CLICK_DOUBLE_XYZ= 0x2A;   // CLICK_CFG: ZD | YD | XD — double click only (a single tap must not wake the ring)
constexpr uint8_t LIR_CLICK       = 0x80;   // CLICK_THS bit 7: keep INT1 high until CLICK_SRC is read
constexpr uint8_t TIME_LIMIT_40MS = 16;
constexpr uint8_t TIME_LAT_20MS   = 8;
constexpr uint8_t TIME_WIN_560MS  = 224;

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
// WHO_AM_I is register 0x0F on both ST parts; used by the dispatcher to pick a back-end without a failed init.
int who_am_i_at(uint8_t addr) {
  Wire.beginTransmission(addr);
  Wire.write(REG_WHO_AM_I);
  if (Wire.endTransmission(false) != 0) return -1;
  if (Wire.requestFrom((int)addr, 1) != 1) return -1;
  return Wire.read();
}
uint8_t click_ths(uint8_t ths_0_31) {
  unsigned v = (unsigned)(ths_0_31 & 0x1F) * 4u;        // 62.5 mg steps → 15.6 mg steps
  return (uint8_t)(v > 0x7F ? 0x7F : v);
}
}  // namespace lis3dh

bool lis3dh_init(uint8_t addr) {
  using namespace lis3dh;
  s_ok = false;
  s_addr = addr;
  int who = rd(REG_WHO_AM_I);
  if (who != 0x33) {
    s_addr = (addr == 0x18) ? 0x19 : 0x18;              // the other SA0 strap
    who = rd(REG_WHO_AM_I);
    if (who != 0x33) return false;                       // the dispatcher logs the "no IMU" line
  }
  wr(REG_CTRL_REG5, 0x80);                               // BOOT: reload the trim parameters (the chip has no SOFT_RESET bit)
  delay(5);
  wr(REG_CTRL_REG1, ODR_400HZ_XYZ);
  wr(REG_CTRL_REG2, HP_ON_CLICK);
  wr(REG_CTRL_REG4, BDU_FS2G);
  wr(REG_CTRL_REG5, 0x00);                               // no latch on the inertial interrupts (the click latch is in CLICK_THS)
  wr(REG_CTRL_REG6, 0x00);                               // INT pins active high, nothing on INT2
  wr(REG_CLICK_CFG, CLICK_DOUBLE_XYZ);
  wr(REG_CLICK_THS, LIR_CLICK | click_ths(s_ths));
  wr(REG_TIME_LIMIT, TIME_LIMIT_40MS);
  wr(REG_TIME_LATENCY, TIME_LAT_20MS);
  wr(REG_TIME_WINDOW, TIME_WIN_560MS);
  wr(REG_CTRL_REG3, I1_CLICK);                           // route last: the engine is fully configured before INT1 can rise
  (void)rd(REG_CLICK_SRC);                               // clear a stale latch so INT1 starts low
  s_ok = true;
  LOGI(TAG, "LIS3DH ready at 0x%02x (double click -> INT1, latched; ths %u = %u mg)", s_addr, s_ths, (unsigned)s_ths * 625 / 10);
  return true;
}

bool lis3dh_available() { return lis3dh::s_ok; }

uint8_t lis3dh_read_tap_src() {
  using namespace lis3dh;
  if (!s_ok) return 0;
  int v = rd(REG_CLICK_SRC);                             // reading it releases the latched INT1
  if (v < 0) return 0;
  // LIS3DH CLICK_SRC : IA 0x40 · DCLICK 0x20 · SCLICK 0x10 · Sign 0x08 · Z 0x04 · Y 0x02 · X 0x01
  // imu_* (TAP_SRC)  : IA 0x40 · SINGLE 0x20 · DOUBLE 0x10 · Sign 0x08 · X 0x04 · Y 0x02 · Z 0x01
  uint8_t out = (uint8_t)(v & 0x4A);                     // IA, Sign and Y sit in the same place
  if (v & 0x20) out |= IMU_TAP_DOUBLE;
  if (v & 0x10) out |= IMU_TAP_SINGLE;                   // never set with CLICK_DOUBLE_XYZ; kept for completeness
  if (v & 0x04) out |= 0x01;                             // Z
  if (v & 0x01) out |= 0x04;                             // X
  return out;
}

void lis3dh_set_tap_threshold(uint8_t ths) {
  using namespace lis3dh;
  s_ths = ths & 0x1F;
  if (!s_ok) return;
  wr(REG_CLICK_THS, LIR_CLICK | click_ths(s_ths));
}

void lis3dh_sleep() {
  using namespace lis3dh;
  if (s_ok) wr(REG_CTRL_REG1, 0x00);                     // ODR = 0000: power-down (~0.5 µA)
}

void lis3dh_wake() {
  using namespace lis3dh;
  if (!s_ok) return;
  wr(REG_CTRL_REG1, ODR_400HZ_XYZ);
  (void)rd(REG_CLICK_SRC);                               // a latched INT1 would wake the ESP32 (EXT1 any-high) immediately
}

// ===========================================================================================================
// LIS2DW12 back-end: imu_lis2dw12.cpp compiled into this translation unit under lis2dw12_* names (see the
// file comment). Its anonymous-namespace helpers (wr/rd/s_addr/s_ok/s_ths) do not collide with lis3dh::.
// ===========================================================================================================
#define imu_init              lis2dw12_init
#define imu_available         lis2dw12_available
#define imu_read_tap_src      lis2dw12_read_tap_src
#define imu_set_tap_threshold lis2dw12_set_tap_threshold
#define imu_sleep             lis2dw12_sleep
#define imu_wake              lis2dw12_wake
#include "imu_lis2dw12.cpp"
#undef imu_init
#undef imu_available
#undef imu_read_tap_src
#undef imu_set_tap_threshold
#undef imu_sleep
#undef imu_wake

// ===========================================================================================================
// imu_* API: run-time dispatch
// ===========================================================================================================
namespace {
enum class Chip : uint8_t { None, Lis2dw12, Lis3dh };
Chip s_chip = Chip::None;
}  // namespace

bool imu_init(uint8_t addr) {
  s_chip = Chip::None;
  int last = -1;
  for (int pass = 0; pass < 2 && s_chip == Chip::None; pass++) {
    uint8_t a = pass == 0 ? addr : (uint8_t)(addr == 0x18 ? 0x19 : 0x18);
    int who = lis3dh::who_am_i_at(a);
    if (who < 0) continue;                               // nothing at this address
    last = who;
    if (who == 0x44 && lis2dw12_init(a))      s_chip = Chip::Lis2dw12;
    else if (who == 0x33 && lis3dh_init(a))   s_chip = Chip::Lis3dh;
  }
  if (s_chip == Chip::None) {
    LOGW(TAG, "no IMU found at 0x18/0x19 (LIS2DW12 who=0x44, LIS3DH who=0x33; read 0x%02x)", last < 0 ? 0xFF : last);
    return false;
  }
  return true;
}

bool imu_available() {
  switch (s_chip) {
    case Chip::Lis2dw12: return lis2dw12_available();
    case Chip::Lis3dh:   return lis3dh_available();
    default:             return false;
  }
}

uint8_t imu_read_tap_src() {
  switch (s_chip) {
    case Chip::Lis2dw12: return lis2dw12_read_tap_src();
    case Chip::Lis3dh:   return lis3dh_read_tap_src();
    default:             return 0;
  }
}

void imu_set_tap_threshold(uint8_t ths) {
  // Both back-ends remember the value for a later init, so forward to both when nothing is detected yet.
  if (s_chip != Chip::Lis3dh)   lis2dw12_set_tap_threshold(ths);
  if (s_chip != Chip::Lis2dw12) lis3dh_set_tap_threshold(ths);
}

void imu_sleep() {
  if (s_chip == Chip::Lis2dw12) lis2dw12_sleep();
  else if (s_chip == Chip::Lis3dh) lis3dh_sleep();
}

void imu_wake() {
  if (s_chip == Chip::Lis2dw12) lis2dw12_wake();
  else if (s_chip == Chip::Lis3dh) lis3dh_wake();
}
