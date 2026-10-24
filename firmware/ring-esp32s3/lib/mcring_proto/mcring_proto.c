#include "mcring_proto.h"

/* Table-less, bitwise CRC-32 (IEEE, reflected, poly 0xEDB88320).
 * Fast enough for <100 KB images on a 240 MHz ESP32-S3 (~1 ms per 10 KB). */
uint32_t mc_crc32_update(uint32_t crc, const uint8_t *data, size_t len) {
  crc = ~crc;
  for (size_t i = 0; i < len; i++) {
    crc ^= data[i];
    for (int k = 0; k < 8; k++) {
      uint32_t mask = -(crc & 1u);
      crc = (crc >> 1) ^ (0xEDB88320u & mask);
    }
  }
  return ~crc;
}

uint32_t mc_crc32(const uint8_t *data, size_t len) {
  return mc_crc32_update(0, data, len);
}

size_t mc_encode_status(const mc_status_t *s, uint8_t *o) {
  o[0] = s->version;
  o[1] = s->state;
  mc_put_u16(o + 2, s->battery_mv);
  o[4] = s->battery_pct;
  o[5] = s->flags;
  mc_put_u32(o + 6, s->uptime_s);
  o[10] = s->last_error;
  o[11] = s->queued;
  return 12;
}

size_t mc_encode_xfer_start(const mc_xfer_start_t *s, uint8_t *o) {
  o[0] = s->type;
  mc_put_u16(o + 1, s->xfer_id);
  mc_put_u32(o + 3, s->total_len);
  mc_put_u16(o + 7, s->chunk_len);
  mc_put_u16(o + 9, s->n_chunks);
  mc_put_u32(o + 11, s->crc32);
  mc_put_u16(o + 15, s->width);
  mc_put_u16(o + 17, s->height);
  o[19] = s->seq_flags;
  return 20;
}

size_t mc_encode_xfer_end(uint16_t xfer_id, uint8_t *o) {
  o[0] = MC_XFER_END;
  mc_put_u16(o + 1, xfer_id);
  return 3;
}

size_t mc_encode_event(uint8_t event, uint8_t arg, uint32_t t_ms, uint8_t *o) {
  o[0] = event;
  o[1] = arg;
  mc_put_u32(o + 2, t_ms);
  return MC_EVENT_LEN;
}

int mc_decode_event(const uint8_t *in, size_t len, mc_event_t *out) {
  if (len < MC_EVENT_LEN) return -1;
  out->event = in[0];
  out->arg = in[1];
  out->t_ms = mc_get_u32(in + 2);
  return 0;
}

size_t mc_encode_audio_start(uint16_t sample_rate_hz, uint8_t codec, uint8_t volume, uint8_t *o) {
  o[0] = MC_AO_START;
  mc_put_u16(o + 1, (uint16_t)(sample_rate_hz / 100));
  o[3] = codec;
  o[4] = volume;
  return MC_AUDIO_START_LEN;
}

int mc_decode_audio_start(const uint8_t *in, size_t len, mc_audio_start_t *out) {
  if (len < MC_AUDIO_START_LEN || in[0] != MC_AO_START) return -1;
  out->sample_rate_div100 = mc_get_u16(in + 1);
  out->codec = in[3];
  out->volume = in[4];
  return 0;
}

size_t mc_encode_audio_data_hdr(uint16_t seq, uint8_t *o) {
  o[0] = MC_AO_DATA;
  mc_put_u16(o + 1, seq);
  return MC_AUDIO_DATA_HDR_LEN;
}
