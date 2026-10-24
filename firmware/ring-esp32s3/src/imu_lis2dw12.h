#pragma once
#include <stdint.h>

// Minimal LIS2DW12 driver: double-tap detection on INT1, low-power ODR.
// Register map per ST DS12099 (verify TAP thresholds for your mechanical mount).
#define IMU_TAP_SINGLE 0x20
#define IMU_TAP_DOUBLE 0x10

bool imu_init(uint8_t i2c_addr = 0x18);   // 0x18 (SA0=0) or 0x19 (SA0=1)
bool imu_available();
uint8_t imu_read_tap_src();               // TAP_SRC register (clears on read)
void imu_set_tap_threshold(uint8_t ths_0_31);
void imu_sleep();                          // power-down (ODR = 0)
void imu_wake();
