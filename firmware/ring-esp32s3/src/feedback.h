#pragma once
#include <stdint.h>
#include <stddef.h>

// Non-blocking Morse / pattern player across LED, haptic, buzzer, aux channels.
void feedback_init();
void feedback_tick();
bool feedback_playing();
void feedback_stop();

// Play alternating ON/OFF durations (units) at unit_ms per unit on the given channel mask.
void feedback_play_units(const uint8_t *units, size_t n, uint16_t unit_ms, uint8_t channels);
// Encode text on the ring and play it (standard spacing at wpm).
void feedback_play_morse_text(const char *text, uint8_t wpm, uint8_t channels);
// Convenience signals
void feedback_signal_ok();        // <SN> on LED (+ short haptic tick)
void feedback_signal_error();     // <HH> on LED
void feedback_signal_connected();
void feedback_rgb(uint8_t r, uint8_t g, uint8_t b, uint16_t ms);

// Accumulator for MORSE_UNITS / MORSE_UNITS_CONT multi-write payloads.
void feedback_units_begin(uint16_t n, uint16_t unit_ms, uint8_t channels);
void feedback_units_put(uint16_t offset, const uint8_t *data, size_t len);
