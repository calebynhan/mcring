#include "audio_out.h"
#include "config.h"
#include "log.h"
#include "mcring_adpcm.h"
#include "mcring_proto.h"
#include "settings.h"
#include <Arduino.h>
#if HAS_SPEAKER
#include <driver/i2s.h>
#endif

static const char *TAG = "spk";

static_assert(MC_AUDIO_BLOCK_BYTES == MC_ADPCM_BLOCK_BYTES, "protocol block size must match the ADPCM codec");
static_assert(AUDIO_OUT_QUEUE_BLOCKS >= 32, "protocol requires >= 32 blocks of buffering");
static_assert(AUDIO_OUT_PREBUFFER_BLOCKS < AUDIO_OUT_QUEUE_BLOCKS, "prebuffer must fit in the queue");

namespace {

// ---- block queue (producer: BLE task, consumer: loop) -------------------------------------------
constexpr uint16_t QN = AUDIO_OUT_QUEUE_BLOCKS;
uint8_t  s_q[QN][MC_ADPCM_BLOCK_BYTES];
uint16_t s_head = 0, s_tail = 0, s_count = 0;          // guarded by s_mux
portMUX_TYPE s_mux = portMUX_INITIALIZER_UNLOCKED;

// ---- commands from the BLE task to tick() ------------------------------------------------------
enum : uint8_t { F_START = 0x01, F_END = 0x02, F_STOP = 0x04 };
uint8_t  s_flags = 0;                                   // guarded by s_mux
uint16_t s_req_rate_div100 = AUDIO_OUT_SAMPLE_RATE / 100;
uint8_t  s_req_codec = MC_AUDIO_CODEC_ADPCM;
uint8_t  s_req_volume = 255;
uint16_t s_last_seq = 0;
bool     s_have_seq = false;
uint32_t s_dropped = 0, s_gaps = 0;                     // stats, BLE task only (logged from tick)

// ---- playback state (loop task only) -----------------------------------------------------------
AudioOutState s_state = AudioOutState::Idle;
bool     s_driver = false;
bool     s_end = false;                                 // AUDIO_END seen for the current stream
bool     s_underrun = false;                            // waiting for AUDIO_OUT_REBUFFER_BLOCKS
uint32_t s_rate = AUDIO_OUT_SAMPLE_RATE;
uint8_t  s_volume = 255;
uint32_t s_drain_until = 0;
uint32_t s_blocks_played = 0;
int16_t  s_stage[MC_ADPCM_BLOCK_SAMPLES * 2];           // one decoded block, stereo-interleaved
size_t   s_stage_len = 0;                               // bytes valid in s_stage
size_t   s_stage_off = 0;                               // bytes already handed to DMA
std::function<void(uint8_t, uint8_t)> s_on_event;

void emit(uint8_t ev, uint8_t arg) { if (s_on_event) s_on_event(ev, arg); }

inline void q_reset_locked() { s_head = s_tail = s_count = 0; }

bool q_push(const uint8_t *blk) {
  bool ok = false;
  portENTER_CRITICAL(&s_mux);
  if (s_count < QN) {
    memcpy(s_q[s_head], blk, MC_ADPCM_BLOCK_BYTES);
    s_head = (uint16_t)((s_head + 1) % QN);
    s_count++;
    ok = true;
  }
  portEXIT_CRITICAL(&s_mux);
  return ok;
}

bool q_pop(uint8_t *blk) {
  bool ok = false;
  portENTER_CRITICAL(&s_mux);
  if (s_count > 0) {
    memcpy(blk, s_q[s_tail], MC_ADPCM_BLOCK_BYTES);
    s_tail = (uint16_t)((s_tail + 1) % QN);
    s_count--;
    ok = true;
  }
  portEXIT_CRITICAL(&s_mux);
  return ok;
}

uint16_t q_count() {
  portENTER_CRITICAL(&s_mux);
  uint16_t n = s_count;
  portEXIT_CRITICAL(&s_mux);
  return n;
}

uint8_t take_flags() {
  portENTER_CRITICAL(&s_mux);
  uint8_t f = s_flags;
  s_flags = 0;
  portEXIT_CRITICAL(&s_mux);
  return f;
}

uint32_t dma_ms() { return (uint32_t)AUDIO_OUT_DMA_BUF_COUNT * AUDIO_OUT_DMA_BUF_LEN * 1000UL / s_rate; }

// ---- I2S driver (installed per stream to save power) -------------------------------------------
bool driver_start() {
#if HAS_SPEAKER
  if (s_driver) return true;
  i2s_config_t cfg = {};
  cfg.mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_TX);
  cfg.sample_rate = (int)s_rate;
  cfg.bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT;
  // Mono source, but we write every sample into BOTH slots (RIGHT_LEFT): plain Philips I2S frames,
  // BCLK = 32 × fs, exactly what the MAX98357A decodes whatever its SD pin selects (L, R or (L+R)/2).
  // The legacy driver's ONLY_LEFT *TX* mono mode behaves differently on ESP32 vs ESP32-S3 (and across
  // IDF 4.4 point releases: some duplicate, some leave the other slot at zero → -6 dB on "(L+R)/2"
  // boards). Duplicating in software is the portable choice and costs 1 KB of staging RAM.
  cfg.channel_format = I2S_CHANNEL_FMT_RIGHT_LEFT;
  cfg.communication_format = I2S_COMM_FORMAT_STAND_I2S;
  cfg.intr_alloc_flags = ESP_INTR_FLAG_LEVEL1;
  cfg.dma_buf_count = AUDIO_OUT_DMA_BUF_COUNT;
  cfg.dma_buf_len = AUDIO_OUT_DMA_BUF_LEN;             // frames → 6 × 256 / 16 kHz = 96 ms of DMA
  cfg.use_apll = false;
  cfg.tx_desc_auto_clear = true;                       // a starved DMA plays silence, not the last buffer
  if (i2s_driver_install(I2S_NUM_1, &cfg, 0, nullptr) != ESP_OK) { LOGE(TAG, "i2s install failed"); return false; }
  i2s_pin_config_t pins = {};
  pins.mck_io_num = I2S_PIN_NO_CHANGE;                 // MAX98357A needs no MCLK
  pins.bck_io_num = PIN_I2S_BCLK;
  pins.ws_io_num = PIN_I2S_LRCLK;
  pins.data_out_num = PIN_I2S_DOUT;
  pins.data_in_num = I2S_PIN_NO_CHANGE;
  if (i2s_set_pin(I2S_NUM_1, &pins) != ESP_OK) { LOGE(TAG, "i2s pins failed"); i2s_driver_uninstall(I2S_NUM_1); return false; }
  i2s_zero_dma_buffer(I2S_NUM_1);
#if PIN_SPEAKER_EN >= 0
  digitalWrite(PIN_SPEAKER_EN, HIGH);                  // amp out of shutdown (MAX98357A SD high = left/stereo)
#endif
  s_driver = true;
  return true;
#else
  return false;
#endif
}

void driver_stop() {
#if HAS_SPEAKER
  if (!s_driver) return;
#if PIN_SPEAKER_EN >= 0
  digitalWrite(PIN_SPEAKER_EN, LOW);
#endif
  i2s_zero_dma_buffer(I2S_NUM_1);
  i2s_driver_uninstall(I2S_NUM_1);
  s_driver = false;
#endif
}

// Decode one block into the stereo stage buffer, applying stream × config volume.
void stage_block(const uint8_t *blk) {
  int16_t mono[MC_ADPCM_BLOCK_SAMPLES];
  mc_adpcm_decode_block(blk, mono);
  // gain 0..255 where 255 = unity: AUDIO_START.volume × SPEAKER_VOLUME / 255
  uint32_t gain = ((uint32_t)s_volume * settings().speaker_volume + 127) / 255;
  for (size_t i = 0; i < MC_ADPCM_BLOCK_SAMPLES; i++) {
    int32_t v = ((int32_t)mono[i] * (int32_t)gain) / 255;
    s_stage[2 * i] = s_stage[2 * i + 1] = (int16_t)v;
  }
  s_stage_len = sizeof s_stage;
  s_stage_off = 0;
}

// Push as much of the stage as the DMA accepts right now. True when the stage is fully queued.
bool stage_flush() {
  if (s_stage_off >= s_stage_len) return true;
#if HAS_SPEAKER
  size_t w = 0;
  i2s_write(I2S_NUM_1, (const uint8_t *)s_stage + s_stage_off, s_stage_len - s_stage_off, &w, 0);   // non-blocking
  s_stage_off += w;
#else
  s_stage_off = s_stage_len;
#endif
  return s_stage_off >= s_stage_len;
}

void reset_playback() {
  s_stage_len = s_stage_off = 0;
  s_end = false;
  s_underrun = false;
  s_blocks_played = 0;
}

void finish(uint8_t arg) {
  driver_stop();
  LOGI(TAG, "%s after %lu blocks (dropped %lu, seq gaps %lu)", arg ? "stopped" : "done",
       (unsigned long)s_blocks_played, (unsigned long)s_dropped, (unsigned long)s_gaps);
  s_state = AudioOutState::Idle;
  reset_playback();
  emit(MC_EV_AUDIO_DONE, arg);
}

void begin_stream() {
  if (s_driver) driver_stop();                         // a new START aborts the old stream silently
  reset_playback();
  uint32_t rate = (uint32_t)s_req_rate_div100 * 100UL;
  if (rate < 8000 || rate > 48000) rate = AUDIO_OUT_SAMPLE_RATE;
  s_rate = rate;
  s_volume = s_req_volume;
  if (!audio_out_available()) {
    LOGW(TAG, "AUDIO_START but no speaker on this board");
    portENTER_CRITICAL(&s_mux); q_reset_locked(); portEXIT_CRITICAL(&s_mux);
    s_state = AudioOutState::Idle;
    emit(MC_EV_AUDIO_DONE, 1);
    return;
  }
  if (s_req_codec != MC_AUDIO_CODEC_ADPCM) {
    LOGW(TAG, "unsupported codec %u", s_req_codec);
    portENTER_CRITICAL(&s_mux); q_reset_locked(); portEXIT_CRITICAL(&s_mux);
    s_state = AudioOutState::Idle;
    emit(MC_EV_AUDIO_DONE, 1);
    return;
  }
  s_state = AudioOutState::Prebuffer;
  LOGI(TAG, "stream start %lu Hz, volume %u x %u", (unsigned long)s_rate, s_volume, settings().speaker_volume);
}

}  // namespace

// ---------------------------------------------------------------------------------------------------
void audio_out_init() {
#if PIN_SPEAKER_EN >= 0
  pinMode(PIN_SPEAKER_EN, OUTPUT);
  digitalWrite(PIN_SPEAKER_EN, LOW);
#endif
  LOGI(TAG, "speaker %s", audio_out_available() ? "configured (I2S1)" : "not fitted");
}

bool audio_out_available() {
#if HAS_SPEAKER
  return true;
#else
  return false;
#endif
}

void audio_out_on_event(std::function<void(uint8_t, uint8_t)> h) { s_on_event = std::move(h); }
bool audio_out_active() { return s_state != AudioOutState::Idle; }
AudioOutState audio_out_state() { return s_state; }
size_t audio_out_queued() { return q_count(); }

// BLE-task context -------------------------------------------------------------------------------
void audio_out_on_packet(const uint8_t *d, size_t n) {
  if (!n) return;
  switch (d[0]) {
    case MC_AO_START: {
      mc_audio_start_t st;
      if (mc_decode_audio_start(d, n, &st) != 0) return;
      portENTER_CRITICAL(&s_mux);
      q_reset_locked();
      s_req_rate_div100 = st.sample_rate_div100 ? st.sample_rate_div100 : (AUDIO_OUT_SAMPLE_RATE / 100);
      s_req_codec = st.codec;
      s_req_volume = st.volume;
      s_flags = (uint8_t)((s_flags & ~(F_END | F_STOP)) | F_START);
      portEXIT_CRITICAL(&s_mux);
      s_have_seq = false;
      s_dropped = s_gaps = 0;
      break;
    }
    case MC_AO_DATA: {
      size_t nb = mc_audio_data_blocks(n);
      if (!nb) { LOGW(TAG, "AUDIO_DATA with %u bytes is not whole blocks", (unsigned)n); return; }
      uint16_t seq = mc_get_u16(d + 1);
      if (s_have_seq && seq != (uint16_t)(s_last_seq + 1)) s_gaps++;
      s_last_seq = seq;
      s_have_seq = true;
      const uint8_t *p = d + MC_AUDIO_DATA_HDR_LEN;
      for (size_t i = 0; i < nb; i++, p += MC_ADPCM_BLOCK_BYTES) {
        if (!q_push(p)) s_dropped++;                   // phone is too far ahead of real time
      }
      break;
    }
    case MC_AO_END:
      portENTER_CRITICAL(&s_mux);
      s_flags = (uint8_t)(s_flags | F_END);
      portEXIT_CRITICAL(&s_mux);
      break;
    case MC_AO_STOP:
      portENTER_CRITICAL(&s_mux);
      q_reset_locked();
      s_flags = (uint8_t)((s_flags & ~(F_START | F_END)) | F_STOP);
      portEXIT_CRITICAL(&s_mux);
      break;
    default:
      LOGW(TAG, "unknown audio-out op 0x%02x", d[0]);
  }
}

// Any task ----------------------------------------------------------------------------------------
// ABORT and the disconnect callback arrive on the NimBLE host task while loop() may be inside
// audio_out_tick() → i2s_write(). So this only records the request, exactly like an AUDIO_STOP packet;
// the driver teardown and AUDIO_DONE(1) happen in audio_out_tick() on the loop task.
void audio_out_stop() {
  portENTER_CRITICAL(&s_mux);
  q_reset_locked();
  s_flags = (uint8_t)((s_flags & ~(F_START | F_END)) | F_STOP);
  portEXIT_CRITICAL(&s_mux);
}

// loop() context ----------------------------------------------------------------------------------
void audio_out_tick() {
  uint8_t f = take_flags();
  if (f & F_STOP) {
    if (s_state != AudioOutState::Idle) finish(1);
    return;
  }
  if (f & F_START) begin_stream();
  if (f & F_END) s_end = true;
  if (s_state == AudioOutState::Idle) return;

  switch (s_state) {
    case AudioOutState::Prebuffer: {
      uint16_t have = q_count();
      uint16_t need = s_underrun ? AUDIO_OUT_REBUFFER_BLOCKS : AUDIO_OUT_PREBUFFER_BLOCKS;
      if (have >= need || (s_end && have > 0)) {
        if (!driver_start()) { s_state = AudioOutState::Idle; reset_playback(); emit(MC_EV_AUDIO_DONE, 1); return; }
        s_underrun = false;
        s_state = AudioOutState::Playing;
        // fall through into Playing below by re-entering next tick (keeps each tick short)
      } else if (s_end && have == 0) {
        if (s_blocks_played) { s_state = AudioOutState::Draining; s_drain_until = millis() + dma_ms() + 10; }
        else finish(0);                                  // empty stream
      }
      return;
    }

    case AudioOutState::Playing: {
      // The DMA holds ~96 ms; one tick tops it up with at most 8 blocks (128 ms of audio).
      for (int i = 0; i < 8; i++) {
        if (!stage_flush()) return;                      // DMA full → try again next tick
        uint8_t blk[MC_ADPCM_BLOCK_BYTES];
        if (q_pop(blk)) { stage_block(blk); s_blocks_played++; continue; }
        // Queue empty.
        if (s_end) { s_state = AudioOutState::Draining; s_drain_until = millis() + dma_ms() + 10; return; }
        if (!s_underrun) {
          s_underrun = true;
          LOGW(TAG, "underrun after %lu blocks", (unsigned long)s_blocks_played);
          emit(MC_EV_AUDIO_UNDERRUN, 0);
        }
        // Driver stays up (DMA auto-clears to silence); wait for a few blocks before resuming.
        s_state = AudioOutState::Prebuffer;
        return;
      }
      return;
    }

    case AudioOutState::Draining:
      if (!stage_flush()) return;
      if ((int32_t)(millis() - s_drain_until) >= 0) finish(0);
      return;

    case AudioOutState::Idle:
      return;
  }
}
