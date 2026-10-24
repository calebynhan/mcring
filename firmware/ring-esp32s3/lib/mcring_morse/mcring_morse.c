#include "mcring_morse.h"
#include <string.h>
#include <ctype.h>

void mc_morse_spacing_default(mc_morse_spacing_t *s) {
  s->dot = 1; s->dash = 3; s->intra_gap = 1; s->char_gap = 3; s->word_gap = 7;
}

/* Farnsworth per ARRL: at char speed c and overall speed s (<c), the extra delay to
 * distribute over the PARIS word is  t_extra = (60*c - 37.2*s) / (s*c)  seconds, spread over
 * 19 units of inter-character/word gaps (PARIS has 4 char gaps of 3 units and 1 word gap of 7).
 * We express gaps in integer units of the *character* speed:
 *   char_gap = round(3 * f), word_gap = round(7 * f), where f = (60*c - 37.2*s) / (19 * s) / unit
 * and unit = 1.2/c s. Equivalent integer-friendly form used here (and in Python):
 *   f = (60*c - 37.2*s) * c / (19 * s * 1.2) / 1 ... simplified: f = (50*c*c - 31*c*s) / (19*s)
 * then divided by the standard gap total... To stay simple and identical across
 * implementations we use the closed form:
 *   stretch = ((60.0*c - 37.2*s) / (19.0 * s)) * (c / 1.2) / 1.0   -> total extra units over 19 units
 *   f = 1 + stretch/19
 * Rounded to nearest integer per gap, min standard values. */
void mc_morse_spacing_farnsworth(mc_morse_spacing_t *s, uint8_t char_wpm, uint8_t overall_wpm) {
  mc_morse_spacing_default(s);
  if (char_wpm == 0 || overall_wpm == 0 || overall_wpm >= char_wpm) return;
  double c = (double)char_wpm, o = (double)overall_wpm;
  double unit_s = 1.2 / c;
  double extra_s = (60.0 * c - 37.2 * o) / (o * c);     /* ARRL formula */
  double extra_units = extra_s / unit_s;                /* spread over 19 gap units */
  double f = 1.0 + extra_units / 19.0;
  int cg = (int)(3.0 * f + 0.5);
  int wg = (int)(7.0 * f + 0.5);
  if (cg < 3) cg = 3;
  if (wg < 7) wg = 7;
  if (cg > 255) cg = 255;
  if (wg > 255) wg = 255;
  s->char_gap = (uint8_t)cg;
  s->word_gap = (uint8_t)wg;
}

typedef struct { char c; const char *code; } mc_morse_entry_t;

static const mc_morse_entry_t MC_TABLE[] = {
  {'A', ".-"},    {'B', "-..."},  {'C', "-.-."},  {'D', "-.."},   {'E', "."},
  {'F', "..-."},  {'G', "--."},   {'H', "...."},  {'I', ".."},    {'J', ".---"},
  {'K', "-.-"},   {'L', ".-.."},  {'M', "--"},    {'N', "-."},    {'O', "---"},
  {'P', ".--."},  {'Q', "--.-"},  {'R', ".-."},   {'S', "..."},   {'T', "-"},
  {'U', "..-"},   {'V', "...-"},  {'W', ".--"},   {'X', "-..-"},  {'Y', "-.--"},
  {'Z', "--.."},
  {'0', "-----"}, {'1', ".----"}, {'2', "..---"}, {'3', "...--"}, {'4', "....-"},
  {'5', "....."}, {'6', "-...."}, {'7', "--..."}, {'8', "---.."}, {'9', "----."},
  {'.', ".-.-.-"}, {',', "--..--"}, {'?', "..--.."}, {'\'', ".----."}, {'!', "-.-.--"},
  {'/', "-..-."},  {'(', "-.--."},  {')', "-.--.-"}, {'&', ".-..."},   {':', "---..."},
  {';', "-.-.-."}, {'=', "-...-"},  {'+', ".-.-."},  {'-', "-....-"},  {'_', "..--.-"},
  {'"', ".-..-."}, {'$', "...-..-"}, {'@', ".--.-."},
};

const char *mc_morse_code_for(char c) {
  c = (char)toupper((unsigned char)c);
  for (size_t i = 0; i < sizeof(MC_TABLE) / sizeof(MC_TABLE[0]); i++)
    if (MC_TABLE[i].c == c) return MC_TABLE[i].code;
  return NULL;
}

size_t mc_morse_encode(const char *text, const mc_morse_spacing_t *sp,
                       uint8_t *out, size_t max_out, int *truncated) {
  mc_morse_spacing_t def;
  if (!sp) { mc_morse_spacing_default(&def); sp = &def; }
  if (truncated) *truncated = 0;

  size_t n = 0;
  int have_char = 0;      /* at least one character emitted */
  int pending_word_gap = 0;

  for (const char *p = text; *p; p++) {
    unsigned char ch = (unsigned char)*p;
    if (isspace(ch)) { if (have_char) pending_word_gap = 1; continue; }
    const char *code = mc_morse_code_for((char)ch);
    if (!code) continue;

    /* How many units will this character need (including its leading gap)? */
    size_t need = 0;
    if (have_char) need += 1;                       /* leading gap (char or word) */
    size_t L = strlen(code);
    need += L + (L - 1);                            /* elements + intra gaps */
    if (n + need > max_out) { if (truncated) *truncated = 1; break; }

    if (have_char) out[n++] = pending_word_gap ? sp->word_gap : sp->char_gap;
    pending_word_gap = 0;
    for (size_t i = 0; i < L; i++) {
      if (i) out[n++] = sp->intra_gap;
      out[n++] = (code[i] == '-') ? sp->dash : sp->dot;
    }
    have_char = 1;
  }
  return n;
}

uint32_t mc_morse_pattern_units(const uint8_t *units, size_t n) {
  uint32_t t = 0;
  for (size_t i = 0; i < n; i++) t += units[i];
  return t;
}
