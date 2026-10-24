#include "audio_mod.h"
#include "config.h"
#include "log.h"
#include "mcring_adpcm.h"
#include <Arduino.h>
#include <esp_heap_caps.h>
#if HAS_PDM_MIC
#include <driver/i2s.h>
#endif

static const char *TAG = "mic";

namespace {
bool     s_ok = false;
bool     s_rec = false;
int16_t *s_pcm = nullptr;
size_t   s_cap = 0;     // samples
size_t   s_len = 0;     // samples
}

bool audio_init() {
#if HAS_PDM_MIC
  s_ok = true;   // driver is installed per recording to save power
#else
  s_ok = false;
#endif
  return s_ok;
}

bool audio_available() { return s_ok; }
bool audio_recording() { return s_rec; }

bool audio_start_recording(uint8_t max_seconds) {
#if HAS_PDM_MIC
  if (!s_ok || s_rec) return false;
  if (max_seconds < 1) max_seconds = 1;
  if (max_seconds > VOICE_CLIP_MAX_S) max_seconds = VOICE_CLIP_MAX_S;
  s_cap = (size_t)VOICE_SAMPLE_RATE * max_seconds;
  s_cap = (s_cap + MC_ADPCM_BLOCK_SAMPLES - 1) / MC_ADPCM_BLOCK_SAMPLES * MC_ADPCM_BLOCK_SAMPLES;
  s_pcm = (int16_t *)heap_caps_malloc(s_cap * sizeof(int16_t), MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
  if (!s_pcm) s_pcm = (int16_t *)malloc(s_cap * sizeof(int16_t));
  if (!s_pcm) { LOGE(TAG, "oom"); return false; }
  s_len = 0;

  i2s_config_t cfg = {};
  cfg.mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX | I2S_MODE_PDM);
  cfg.sample_rate = VOICE_SAMPLE_RATE;
  cfg.bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT;
  cfg.channel_format = I2S_CHANNEL_FMT_ONLY_LEFT;
  cfg.communication_format = I2S_COMM_FORMAT_STAND_I2S;
  cfg.intr_alloc_flags = ESP_INTR_FLAG_LEVEL1;
  cfg.dma_buf_count = 6;
  cfg.dma_buf_len = 256;
  cfg.use_apll = false;
  if (i2s_driver_install(I2S_NUM_0, &cfg, 0, nullptr) != ESP_OK) { LOGE(TAG, "i2s install failed"); free(s_pcm); s_pcm = nullptr; return false; }
  i2s_pin_config_t pins = {};
  pins.bck_io_num = I2S_PIN_NO_CHANGE;
  pins.ws_io_num = PIN_PDM_CLK;
  pins.data_out_num = I2S_PIN_NO_CHANGE;
  pins.data_in_num = PIN_PDM_DATA;
  i2s_set_pin(I2S_NUM_0, &pins);
  i2s_zero_dma_buffer(I2S_NUM_0);
  s_rec = true;
  LOGI(TAG, "recording up to %u s", max_seconds);
  return true;
#else
  (void)max_seconds;
  return false;
#endif
}

void audio_tick() {
#if HAS_PDM_MIC
  if (!s_rec) return;
  size_t room = s_cap - s_len;
  if (room == 0) return;
  size_t want = room > 512 ? 512 : room;
  size_t got = 0;
  i2s_read(I2S_NUM_0, s_pcm + s_len, want * sizeof(int16_t), &got, 0);
  s_len += got / sizeof(int16_t);
#endif
}

bool audio_finish(uint8_t **out, size_t *out_len, uint32_t *n_samples) {
#if HAS_PDM_MIC
  if (!s_rec) return false;
  // Drain for a few ms to catch the tail
  for (int i = 0; i < 4 && s_len < s_cap; i++) { audio_tick(); delay(5); }
  i2s_driver_uninstall(I2S_NUM_0);
  s_rec = false;
  if (s_len < MC_ADPCM_BLOCK_SAMPLES) { free(s_pcm); s_pcm = nullptr; return false; }

  // Simple DC removal + gain (PDM mics on the Sense board are quiet).
  int32_t mean = 0;
  for (size_t i = 0; i < s_len; i++) mean += s_pcm[i];
  mean /= (int32_t)s_len;
  int32_t peak = 1;
  for (size_t i = 0; i < s_len; i++) { int32_t v = s_pcm[i] - mean; if (v < 0) v = -v; if (v > peak) peak = v; }
  int32_t gain_q8 = peak > 0 ? (int32_t)((24000L * 256) / peak) : 256;
  if (gain_q8 > 8 * 256) gain_q8 = 8 * 256;
  if (gain_q8 < 256) gain_q8 = 256;
  for (size_t i = 0; i < s_len; i++) {
    int32_t v = ((int32_t)s_pcm[i] - mean) * gain_q8 / 256;
    s_pcm[i] = (int16_t)(v > 32767 ? 32767 : (v < -32768 ? -32768 : v));
  }

  size_t enc_len = mc_adpcm_encoded_size(s_len);
  uint8_t *enc = (uint8_t *)heap_caps_malloc(enc_len, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
  if (!enc) enc = (uint8_t *)malloc(enc_len);
  if (!enc) { free(s_pcm); s_pcm = nullptr; return false; }
  size_t w = mc_adpcm_encode(s_pcm, s_len, enc);
  free(s_pcm); s_pcm = nullptr;
  *out = enc; *out_len = w; *n_samples = (uint32_t)s_len;
  LOGI(TAG, "%u samples -> %u ADPCM bytes", (unsigned)s_len, (unsigned)w);
  return true;
#else
  (void)out; (void)out_len; (void)n_samples;
  return false;
#endif
}

void audio_abort() {
#if HAS_PDM_MIC
  if (s_rec) { i2s_driver_uninstall(I2S_NUM_0); s_rec = false; }
  if (s_pcm) { free(s_pcm); s_pcm = nullptr; }
#endif
}
