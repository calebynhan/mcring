#include "mcring_adpcm.h"
#include <string.h>

static const int8_t INDEX_TABLE[16] = { -1, -1, -1, -1, 2, 4, 6, 8, -1, -1, -1, -1, 2, 4, 6, 8 };

static const int16_t STEP_TABLE[89] = {
      7,     8,     9,    10,    11,    12,    13,    14,    16,    17,
     19,    21,    23,    25,    28,    31,    34,    37,    41,    45,
     50,    55,    60,    66,    73,    80,    88,    97,   107,   118,
    130,   143,   157,   173,   190,   209,   230,   253,   279,   307,
    337,   371,   408,   449,   494,   544,   598,   658,   724,   796,
    876,   963,  1060,  1166,  1282,  1411,  1552,  1707,  1878,  2066,
   2272,  2499,  2749,  3024,  3327,  3660,  4026,  4428,  4871,  5358,
   5894,  6484,  7132,  7845,  8630,  9493, 10442, 11487, 12635, 13899,
  15289, 16818, 18500, 20350, 22385, 24623, 27086, 29794, 32767
};

static inline int32_t clamp16(int32_t v) { return v > 32767 ? 32767 : (v < -32768 ? -32768 : v); }
static inline int32_t clamp_idx(int32_t v) { return v < 0 ? 0 : (v > 88 ? 88 : v); }

void mc_adpcm_init(mc_adpcm_state_t *st) { st->predictor = 0; st->step_index = 0; }

uint8_t mc_adpcm_encode_sample(mc_adpcm_state_t *st, int16_t sample) {
  int32_t step = STEP_TABLE[st->step_index];
  int32_t diff = (int32_t)sample - st->predictor;
  uint8_t code = 0;
  if (diff < 0) { code = 8; diff = -diff; }
  int32_t vpdiff = step >> 3;
  if (diff >= step) { code |= 4; diff -= step; vpdiff += step; }
  step >>= 1;
  if (diff >= step) { code |= 2; diff -= step; vpdiff += step; }
  step >>= 1;
  if (diff >= step) { code |= 1; vpdiff += step; }
  st->predictor = clamp16((code & 8) ? st->predictor - vpdiff : st->predictor + vpdiff);
  st->step_index = clamp_idx(st->step_index + INDEX_TABLE[code]);
  return code;
}

int16_t mc_adpcm_decode_sample(mc_adpcm_state_t *st, uint8_t code) {
  int32_t step = STEP_TABLE[st->step_index];
  int32_t vpdiff = step >> 3;
  if (code & 4) vpdiff += step;
  if (code & 2) vpdiff += step >> 1;
  if (code & 1) vpdiff += step >> 2;
  st->predictor = clamp16((code & 8) ? st->predictor - vpdiff : st->predictor + vpdiff);
  st->step_index = clamp_idx(st->step_index + INDEX_TABLE[code & 15]);
  return (int16_t)st->predictor;
}

size_t mc_adpcm_encode_block_st(mc_adpcm_state_t *st, const int16_t *pcm, uint8_t *out) {
  /* Each block header carries the state needed to decode it standalone: the first sample
   * as predictor and the step index carried over from the previous block (so the adaptive
   * step does not have to ramp up again every 16 ms). */
  st->predictor = pcm[0];
  st->step_index = clamp_idx(st->step_index);
  out[0] = (uint8_t)(pcm[0] & 0xFF);
  out[1] = (uint8_t)(((uint16_t)pcm[0]) >> 8);
  out[2] = (uint8_t)st->step_index;
  out[3] = 0;
  size_t o = 4;
  uint8_t acc = 0; int half = 0;
  for (size_t i = 1; i < MC_ADPCM_BLOCK_SAMPLES; i++) {
    uint8_t c = mc_adpcm_encode_sample(st, pcm[i]);
    if (!half) { acc = c; half = 1; }
    else { out[o++] = (uint8_t)(acc | (c << 4)); half = 0; }
  }
  if (half) out[o++] = acc;
  return o;  /* == MC_ADPCM_BLOCK_BYTES */
}

size_t mc_adpcm_encode_block(const int16_t *pcm, uint8_t *out) {
  mc_adpcm_state_t st;
  mc_adpcm_init(&st);
  return mc_adpcm_encode_block_st(&st, pcm, out);
}

size_t mc_adpcm_decode_block(const uint8_t *in, int16_t *pcm) {
  mc_adpcm_state_t st;
  st.predictor = (int16_t)(in[0] | (in[1] << 8));
  st.step_index = clamp_idx(in[2]);
  pcm[0] = (int16_t)st.predictor;
  size_t i = 1, o = 4;
  while (i < MC_ADPCM_BLOCK_SAMPLES) {
    uint8_t b = in[o++];
    pcm[i++] = mc_adpcm_decode_sample(&st, b & 0x0F);
    if (i < MC_ADPCM_BLOCK_SAMPLES) pcm[i++] = mc_adpcm_decode_sample(&st, b >> 4);
  }
  return MC_ADPCM_BLOCK_SAMPLES;
}

size_t mc_adpcm_encode(const int16_t *pcm, size_t n, uint8_t *out) {
  size_t written = 0;
  int16_t tmp[MC_ADPCM_BLOCK_SAMPLES];
  mc_adpcm_state_t st;
  mc_adpcm_init(&st);
  for (size_t off = 0; off < n; off += MC_ADPCM_BLOCK_SAMPLES) {
    size_t take = n - off < MC_ADPCM_BLOCK_SAMPLES ? n - off : MC_ADPCM_BLOCK_SAMPLES;
    if (take == MC_ADPCM_BLOCK_SAMPLES) {
      written += mc_adpcm_encode_block_st(&st, pcm + off, out + written);
    } else {
      memset(tmp, 0, sizeof(tmp));
      memcpy(tmp, pcm + off, take * sizeof(int16_t));
      written += mc_adpcm_encode_block_st(&st, tmp, out + written);
    }
  }
  return written;
}
