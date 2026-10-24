#pragma once
#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>
int  feedback_init(void);
void feedback_tick(void);
bool feedback_playing(void);
void feedback_stop(void);
void feedback_play_units(const uint8_t *units, size_t n, uint16_t unit_ms, uint8_t channels);
void feedback_play_text(const char *text, uint8_t wpm, uint8_t channels);
void feedback_units_begin(uint16_t n, uint16_t unit_ms, uint8_t channels);
void feedback_units_put(uint16_t off, const uint8_t *d, size_t len);
