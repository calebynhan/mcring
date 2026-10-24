#pragma once
#include <stdint.h>

void power_init();
uint16_t battery_mv();
uint8_t  battery_pct();      // 255 if unknown (no divider)
bool     battery_charging(); // false unless a CHG pin is wired
void power_note_activity();  // resets the idle timer
void power_tick(bool connected, bool busy);   // may enter deep sleep
void power_deep_sleep_now();
