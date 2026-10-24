#pragma once
#include <stdint.h>

// LIS3DH back-end of the imu_* API (imu_lis2dw12.h): the STEMMA QT / Qwiic accelerometer of the no-solder
// stage-0 kit (Adafruit 2809, SparkFun SEN-29529 — hardware/pcb/wiring_stage0_solderless.md). WHO_AM_I 0x33 at
// I²C 0x18 (SDO/SA0 low) or 0x19. Double-click detection on all three axes (CLICK_CFG), routed to INT1
// (CTRL_REG3 I1_CLICK) and *latched* until CLICK_SRC is read (CLICK_THS LIR_Click), so the event survives the
// 150-400 ms a camera capture blocks loop() for and can also be polled when INT1 is not wired (IMU_POLL_MS).
// Register map per ST DocID17530 (LIS3DH datasheet) and AN3308 (click recognition).
//
// imu_lis3dh.cpp also hosts the run-time dispatch of the imu_* API: imu_init() reads WHO_AM_I at 0x18/0x19 and
// hands the chip to the LIS2DW12 back-end (0x44, imu_lis2dw12.cpp) or to this one (0x33); every other imu_*
// call goes to whichever answered. Nothing outside imu_lis3dh.cpp needs the lis3dh_* names.
bool    lis3dh_init(uint8_t i2c_addr);
bool    lis3dh_available();
uint8_t lis3dh_read_tap_src();                        // CLICK_SRC remapped to the imu_* (LIS2DW12 TAP_SRC) bit layout; clears the INT1 latch
void    lis3dh_set_tap_threshold(uint8_t ths_0_31);   // imu_* units: 1 step = 62.5 mg at ±2 g (scaled ×4 into the 7-bit CLICK_THS)
void    lis3dh_sleep();                               // power-down (ODR = 0)
void    lis3dh_wake();                                // 400 Hz again + clear a latched INT1 so EXT1 tap-wake does not fire at once
