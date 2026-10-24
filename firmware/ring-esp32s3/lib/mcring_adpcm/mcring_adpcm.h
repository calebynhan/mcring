/*
 * IMA ADPCM (DVI4) encoder/decoder, 16-bit PCM mono -> 4-bit.
 * Block format (matches python/mcring_core/mcring_core/adpcm.py):
 *   per block of BLOCK_SAMPLES samples:
 *     int16 predictor (first sample, LE), uint8 step_index, uint8 reserved(0),
 *     then (BLOCK_SAMPLES-1) nibbles, low nibble first, padded to a byte.
 * With BLOCK_SAMPLES = 256: 4 + 128 = 132 bytes per 256 samples (≈3.9:1).
 */
#ifndef MCRING_ADPCM_H
#define MCRING_ADPCM_H

#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

#define MC_ADPCM_BLOCK_SAMPLES 256
#define MC_ADPCM_BLOCK_BYTES   (4 + (MC_ADPCM_BLOCK_SAMPLES - 1 + 1) / 2)  /* 132 */

typedef struct {
  int32_t predictor;
  int32_t step_index;
} mc_adpcm_state_t;

void    mc_adpcm_init(mc_adpcm_state_t *st);
uint8_t mc_adpcm_encode_sample(mc_adpcm_state_t *st, int16_t sample);
int16_t mc_adpcm_decode_sample(mc_adpcm_state_t *st, uint8_t nibble);

/* Encode exactly MC_ADPCM_BLOCK_SAMPLES samples into MC_ADPCM_BLOCK_BYTES bytes.
 * Each block header stores the first sample and the current step index, so every block is
 * independently decodable (good for lossy BLE transport) while the adaptive step carries
 * over between blocks (good for quality). *st is updated; use mc_adpcm_init() first. */
size_t mc_adpcm_encode_block_st(mc_adpcm_state_t *st, const int16_t *pcm, uint8_t *out);
/* Same, with a fresh state (step index 0). */
size_t mc_adpcm_encode_block(const int16_t *pcm, uint8_t *out);
size_t mc_adpcm_decode_block(const uint8_t *in, int16_t *pcm);

/* Encode n samples (n padded up to a block multiple with zeros). Returns bytes written.
 * out must hold ceil(n/256)*132 bytes. */
size_t mc_adpcm_encode(const int16_t *pcm, size_t n, uint8_t *out);
static inline size_t mc_adpcm_encoded_size(size_t n_samples) {
  return ((n_samples + MC_ADPCM_BLOCK_SAMPLES - 1) / MC_ADPCM_BLOCK_SAMPLES) * MC_ADPCM_BLOCK_BYTES;
}

#ifdef __cplusplus
}
#endif
#endif
