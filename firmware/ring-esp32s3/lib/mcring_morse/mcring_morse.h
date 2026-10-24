/*
 * ITU Morse encoder producing alternating ON/OFF durations in "units".
 * Reference implementation: python/mcring_core/mcring_core/morse.py (must match byte-for-byte).
 */
#ifndef MCRING_MORSE_H
#define MCRING_MORSE_H

#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
  uint8_t dot;         /* default 1 */
  uint8_t dash;        /* default 3 */
  uint8_t intra_gap;   /* gap between elements of one character, default 1 */
  uint8_t char_gap;    /* gap between characters, default 3 (Farnsworth: larger) */
  uint8_t word_gap;    /* gap between words, default 7 (Farnsworth: larger) */
} mc_morse_spacing_t;

/* Standard spacing: 1/3/1/3/7. */
void mc_morse_spacing_default(mc_morse_spacing_t *s);

/* Farnsworth spacing: characters at char_wpm, overall rhythm at overall_wpm.
 * unit_ms is derived from char_wpm (1200/char_wpm). Gaps are stretched so that the
 * PARIS word takes the time it would at overall_wpm. Mirrors the Python implementation. */
void mc_morse_spacing_farnsworth(mc_morse_spacing_t *s, uint8_t char_wpm, uint8_t overall_wpm);

/* Unit length in ms for a character speed. */
static inline uint16_t mc_morse_unit_ms(uint8_t wpm) { return (uint16_t)(wpm ? (1200 / wpm) : 80); }

/* Returns the dot/dash string for an ASCII character (upper-cased), or NULL if unknown.
 * '.' = dot, '-' = dash. */
const char *mc_morse_code_for(char c);

/* Encode text into alternating ON/OFF unit durations (starting with ON, no trailing OFF).
 * Unknown characters are dropped; runs of whitespace collapse to one word gap.
 * Returns the number of units written (<= max_out). If the output would exceed max_out,
 * encoding stops at the last complete character and *truncated is set to 1 (if non-NULL). */
size_t mc_morse_encode(const char *text, const mc_morse_spacing_t *sp,
                       uint8_t *out, size_t max_out, int *truncated);

/* Total duration in units of an encoded pattern. */
uint32_t mc_morse_pattern_units(const uint8_t *units, size_t n);

#ifdef __cplusplus
}
#endif
#endif
