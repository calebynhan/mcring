#pragma once
#include <stdint.h>

// TI DRV2605L haptic driver, used in RTP (real-time playback) mode for Morse on/off control.
bool drv2605_init(bool lra, uint8_t i2c_addr = 0x5A);
bool drv2605_available();
void drv2605_set(uint8_t amplitude_0_127);   // 0 = off
void drv2605_standby(bool on);
bool drv2605_autocal();                      // run auto-calibration (LRA); blocks ~1 s
