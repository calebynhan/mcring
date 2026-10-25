#pragma once
#include <stdint.h>

// IMU API used by trigger.cpp / power.cpp / main.cpp: double-tap detection on INT1, low-power ODR.
// Two back-ends share it and imu_init() picks one at boot from WHO_AM_I (dispatch in imu_lis3dh.cpp):
//   * LIS2DW12 — stage-1 part, imu_lis2dw12.cpp, register map per ST DS12099 (WHO_AM_I 0x44)
//   * LIS3DH   — STEMMA QT / Qwiic breakout of the no-solder stage-0 kit, imu_lis3dh.cpp (WHO_AM_I 0x33)
// Both sit at I²C 0x18 (SA0/SDO low) or 0x19. Verify TAP thresholds for your mechanical mount.
// Build note: imu_lis2dw12.cpp is compiled *through* imu_lis3dh.cpp (which #includes it under lis2dw12_* names)
// and is excluded from PlatformIO's own source list (platformio.ini build_src_filter), so the imu_* symbols
// below are defined exactly once — see the file comment in imu_lis3dh.cpp.
//
// imu_read_tap_src() returns the LIS2DW12 TAP_SRC bit layout for either chip (the LIS3DH CLICK_SRC is remapped):
//   bit 6 TAP_IA · bit 5 single tap · bit 4 double tap · bit 3 sign · bit 2 X · bit 1 Y · bit 0 Z
#define IMU_TAP_SINGLE 0x20
#define IMU_TAP_DOUBLE 0x10

bool imu_init(uint8_t i2c_addr = 0x18);   // probes i2c_addr then the other SA0 strap (0x18 / 0x19)
bool imu_available();
uint8_t imu_read_tap_src();               // TAP_SRC / CLICK_SRC (clears the event — and the LIS3DH's latched INT1 — on read)
void imu_set_tap_threshold(uint8_t ths_0_31);   // 1 step = FS/32 = 62.5 mg at ±2 g (LIS3DH: scaled ×4 into its 7-bit CLICK_THS)
void imu_sleep();                          // power-down (ODR = 0)
void imu_wake();                           // tap-detection ODR again (LIS3DH: also clears a latched INT1 before EXT1 wake is armed)
