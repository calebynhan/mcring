#pragma once
#include <stdint.h>
#include <stddef.h>

// PDM microphone -> 16 kHz mono PCM -> IMA-ADPCM (132-byte blocks of 256 samples).
bool audio_init();
bool audio_available();
bool audio_start_recording(uint8_t max_seconds);   // allocates buffer, starts I2S
void audio_tick();                                  // pump I2S into the buffer (call often)
bool audio_recording();
// Stop and hand over the encoded buffer (caller frees). Returns false if nothing recorded.
bool audio_finish(uint8_t **adpcm_out, size_t *adpcm_len, uint32_t *n_samples);
void audio_abort();
