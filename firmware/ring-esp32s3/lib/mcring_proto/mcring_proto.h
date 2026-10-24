/*
 * mcring BLE protocol definitions — shared between firmware and host tests.
 * Wire format: little-endian, packed. See /protocol/ble-gatt.md.
 */
#ifndef MCRING_PROTO_H
#define MCRING_PROTO_H

#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

#define MCRING_PROTO_VERSION 1

/* 128-bit UUIDs (string form, as NimBLE wants them) */
#define MCRING_UUID_SERVICE   "7a3b0001-9c2e-4f3a-b1d4-6d6372696e67"
#define MCRING_UUID_CONTROL   "7a3b0002-9c2e-4f3a-b1d4-6d6372696e67"
#define MCRING_UUID_STATUS    "7a3b0003-9c2e-4f3a-b1d4-6d6372696e67"
#define MCRING_UUID_XFER_META "7a3b0004-9c2e-4f3a-b1d4-6d6372696e67"
#define MCRING_UUID_XFER_DATA "7a3b0005-9c2e-4f3a-b1d4-6d6372696e67"
#define MCRING_UUID_FEEDBACK  "7a3b0006-9c2e-4f3a-b1d4-6d6372696e67"
#define MCRING_UUID_EVENTS    "7a3b0007-9c2e-4f3a-b1d4-6d6372696e67"   /* notify, ring -> phone */
#define MCRING_UUID_AUDIO_OUT "7a3b0008-9c2e-4f3a-b1d4-6d6372696e67"   /* write-no-rsp, phone -> ring speaker */

/* Control opcodes (phone -> ring) */
enum {
  MC_OP_CAPTURE      = 0x01,
  MC_OP_ACK_TRANSFER = 0x02,
  MC_OP_SET_CONFIG   = 0x03,
  MC_OP_PING         = 0x04,
  MC_OP_ABORT        = 0x05,
  MC_OP_RECORD_AUDIO = 0x06,
  MC_OP_SLEEP        = 0x07,
  MC_OP_GET_STATUS   = 0x08,
  MC_OP_RECORD_START = 0x09,  /* begin ring-mic recording now; RECORD_STOP or max 8 s ends it */
  MC_OP_RECORD_STOP  = 0x0A,
};

/* Feedback opcodes (phone -> ring) */
enum {
  MC_FB_MORSE_TEXT       = 0x10,
  MC_FB_PATTERN          = 0x11,
  MC_FB_STOP             = 0x12,
  MC_FB_RGB              = 0x13,
  MC_FB_MORSE_UNITS      = 0x14,  /* legacy / optional "silent pattern" mode */
  MC_FB_MORSE_UNITS_CONT = 0x15,
  MC_FB_CUE              = 0x16,  /* {u8 cue}: play a built-in cue honouring CUES_MASK */
};

/* Built-in cues (MC_FB_CUE payload) */
enum {
  MC_CUE_LISTENING    = 1,  /* 1 short tick: the ring/phone is recording */
  MC_CUE_ANSWER_READY = 2,  /* 2 ticks: the answer is about to be spoken */
  MC_CUE_ERROR        = 3,  /* long buzz */
  MC_CUE_OK           = 4,  /* 1 short tick (capture ok, boot) */
};

/* CUES_MASK bits (config key 10) */
enum {
  MC_CUES_HAPTIC = 0x01,
  MC_CUES_LED    = 0x02,
  MC_CUES_BEEP   = 0x04,
};

/* MIC_SOURCE_HINT values (config key 11) */
enum {
  MC_MIC_SRC_RING  = 0,  /* ring records with its PDM mic on a long press */
  MC_MIC_SRC_PHONE = 1,  /* phone/headset records between BUTTON_DOWN and BUTTON_UP */
};

/* Audio-out opcodes (phone -> ring, characteristic 0008) */
enum {
  MC_AO_START = 0x20,  /* {u16 sample_rate_div100, u8 codec, u8 volume} */
  MC_AO_DATA  = 0x21,  /* {u16 seq, 132-byte ADPCM blocks...} */
  MC_AO_END   = 0x22,  /* drain, then AUDIO_DONE(0) */
  MC_AO_STOP  = 0x23,  /* flush now, AUDIO_DONE(1) */
};

enum { MC_AUDIO_CODEC_ADPCM = 2 };   /* mcring IMA-ADPCM, 132-byte / 256-sample blocks */
#define MC_AUDIO_BLOCK_BYTES 132     /* == MC_ADPCM_BLOCK_BYTES in lib/mcring_adpcm */

/* Events (ring -> phone, characteristic 0007) */
enum {
  MC_EV_BUTTON_DOWN     = 1,
  MC_EV_BUTTON_UP       = 2,   /* arg = held tenths of a second, capped 255 */
  MC_EV_DOUBLE_TAP      = 3,
  MC_EV_TOUCH           = 4,
  MC_EV_CAPTURE_STARTED = 5,
  MC_EV_CAPTURE_DONE    = 6,   /* arg = queued count (0 = failed) */
  MC_EV_REC_STARTED     = 7,   /* arg = max seconds */
  MC_EV_REC_STOPPED     = 8,   /* arg = recorded tenths of a second (0 = discarded) */
  MC_EV_LOW_BATTERY     = 9,   /* arg = pct */
  MC_EV_AUDIO_UNDERRUN  = 10,
  MC_EV_AUDIO_DONE      = 11,  /* arg = 0 drained, 1 stopped */
};

/* Feedback channel bitmask */
enum {
  MC_CH_LED    = 0x01,
  MC_CH_HAPTIC = 0x02,
  MC_CH_BUZZER = 0x04,
  MC_CH_AUX    = 0x08,  /* reserved: air puff / thermal */
};

/* Config keys */
enum {
  MC_CFG_TRIGGER_MASK      = 1,
  MC_CFG_DEFAULT_QUALITY   = 2,
  MC_CFG_DEFAULT_FRAMESIZE = 3,
  MC_CFG_IDLE_SLEEP_S      = 4,
  MC_CFG_LED_BRIGHTNESS    = 5,
  MC_CFG_HAPTIC_STRENGTH   = 6,
  MC_CFG_MORSE_WPM         = 7,   /* legacy */
  MC_CFG_FEEDBACK_CHANNELS = 8,   /* legacy */
  MC_CFG_SPEAKER_VOLUME    = 9,   /* 0..255 */
  MC_CFG_CUES_MASK         = 10,  /* MC_CUES_* bits */
  MC_CFG_MIC_SOURCE_HINT   = 11,  /* MC_MIC_SRC_* */
};

/* Trigger mask */
enum {
  MC_TRIG_BUTTON    = 0x01,
  MC_TRIG_DOUBLETAP = 0x02,
  MC_TRIG_TOUCH     = 0x04,
};

/* Device state */
enum {
  MC_STATE_IDLE         = 0,
  MC_STATE_CAPTURING    = 1,
  MC_STATE_TRANSFERRING = 2,
  MC_STATE_RECORDING    = 3,
  MC_STATE_FEEDBACK     = 4,  /* playing: cue / pattern / speaker audio */
  MC_STATE_ERROR        = 5,
};

/* Errors */
enum {
  MC_ERR_NONE             = 0,
  MC_ERR_CAMERA_INIT      = 1,
  MC_ERR_CAPTURE_FAILED   = 2,
  MC_ERR_TRANSFER_TIMEOUT = 3,
  MC_ERR_OOM              = 4,
  MC_ERR_MIC              = 5,
};

/* Status flags */
enum {
  MC_FLAG_CHARGING  = 0x01,
  MC_FLAG_CAMERA_OK = 0x02,
  MC_FLAG_IMU_OK    = 0x04,
  MC_FLAG_MIC_OK    = 0x08,
  MC_FLAG_HAPTIC_OK  = 0x10,
  MC_FLAG_QUEUED     = 0x20,
  MC_FLAG_SPEAKER_OK = 0x40,
};

/* Transfer types */
enum {
  MC_XFER_JPEG  = 0x01,
  MC_XFER_ADPCM = 0x02,
  MC_XFER_END   = 0xFF,
};

/* Frame size codes (CAPTURE) */
enum {
  MC_FS_DEFAULT = 0,
  MC_FS_QQVGA   = 1,  /* 160x120 */
  MC_FS_QVGA    = 2,  /* 320x240 */
  MC_FS_VGA     = 3,  /* 640x480 */
  MC_FS_SVGA    = 4,  /* 800x600 */
  MC_FS_XGA     = 5,  /* 1024x768 */
};

#if defined(__GNUC__)
#define MC_PACKED __attribute__((packed))
#else
#define MC_PACKED
#endif

typedef struct MC_PACKED {
  uint8_t  version;
  uint8_t  state;
  uint16_t battery_mv;
  uint8_t  battery_pct;
  uint8_t  flags;
  uint32_t uptime_s;
  uint8_t  last_error;
  uint8_t  queued;
} mc_status_t;                 /* 12 bytes */

typedef struct MC_PACKED {
  uint8_t  type;
  uint16_t xfer_id;
  uint32_t total_len;
  uint16_t chunk_len;
  uint16_t n_chunks;
  uint32_t crc32;
  uint16_t width;
  uint16_t height;
  uint8_t  seq_flags;
} mc_xfer_start_t;             /* 20 bytes */

typedef struct MC_PACKED {
  uint8_t  type;               /* MC_XFER_END */
  uint16_t xfer_id;
} mc_xfer_end_t;               /* 3 bytes */

typedef struct MC_PACKED {
  uint16_t xfer_id;
  uint16_t idx;
  /* payload follows */
} mc_xfer_chunk_hdr_t;         /* 4 bytes */

typedef struct MC_PACKED {
  uint8_t  event;              /* MC_EV_* */
  uint8_t  arg;
  uint32_t t_ms;               /* ring uptime when the event happened */
} mc_event_t;                  /* 6 bytes */

typedef struct MC_PACKED {
  uint16_t sample_rate_div100; /* 160 = 16 kHz */
  uint8_t  codec;              /* MC_AUDIO_CODEC_ADPCM */
  uint8_t  volume;             /* 0..255 */
} mc_audio_start_t;            /* 4 bytes after the opcode */

#define MC_XFER_CHUNK_HDR_LEN 4
#define MC_ATT_HDR_LEN        3
#define MC_EVENT_LEN          6
#define MC_AUDIO_START_LEN    5   /* opcode + mc_audio_start_t */
#define MC_AUDIO_DATA_HDR_LEN 3   /* opcode + u16 seq */

/* IEEE 802.3 CRC-32 (same polynomial as zlib.crc32). */
uint32_t mc_crc32(const uint8_t *data, size_t len);
uint32_t mc_crc32_update(uint32_t crc, const uint8_t *data, size_t len);

/* Helpers for little-endian (de)serialisation, independent of host endianness. */
static inline void mc_put_u16(uint8_t *p, uint16_t v) { p[0] = (uint8_t)v; p[1] = (uint8_t)(v >> 8); }
static inline void mc_put_u32(uint8_t *p, uint32_t v) { p[0] = (uint8_t)v; p[1] = (uint8_t)(v >> 8); p[2] = (uint8_t)(v >> 16); p[3] = (uint8_t)(v >> 24); }
static inline uint16_t mc_get_u16(const uint8_t *p) { return (uint16_t)(p[0] | (p[1] << 8)); }
static inline uint32_t mc_get_u32(const uint8_t *p) { return (uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24); }
static inline int32_t  mc_get_i32(const uint8_t *p) { return (int32_t)mc_get_u32(p); }

/* Serialise structs explicitly (avoids relying on packed layout + host endianness). */
size_t mc_encode_status(const mc_status_t *s, uint8_t *out /* >=12 */);
size_t mc_encode_xfer_start(const mc_xfer_start_t *s, uint8_t *out /* >=20 */);
size_t mc_encode_xfer_end(uint16_t xfer_id, uint8_t *out /* >=3 */);
size_t mc_encode_event(uint8_t event, uint8_t arg, uint32_t t_ms, uint8_t *out /* >=6 */);
/* Returns 0 on success, -1 if the buffer is too short. */
int    mc_decode_event(const uint8_t *in, size_t len, mc_event_t *out);

/* Audio-out packets (phone side encodes, ring side decodes; both here for host tests). */
size_t mc_encode_audio_start(uint16_t sample_rate_hz, uint8_t codec, uint8_t volume, uint8_t *out /* >=5 */);
int    mc_decode_audio_start(const uint8_t *in, size_t len, mc_audio_start_t *out);   /* in[0] == MC_AO_START */
size_t mc_encode_audio_data_hdr(uint16_t seq, uint8_t *out /* >=3 */);                  /* blocks follow */
/* Number of whole blocks in an AUDIO_DATA packet (0 if malformed / not whole blocks). */
static inline size_t mc_audio_data_blocks(size_t pkt_len) {
  if (pkt_len < MC_AUDIO_DATA_HDR_LEN) return 0;
  size_t body = pkt_len - MC_AUDIO_DATA_HDR_LEN;
  return (body % MC_AUDIO_BLOCK_BYTES) ? 0 : body / MC_AUDIO_BLOCK_BYTES;
}
/* Whole blocks that fit in one write of max_write bytes (>= 1). */
static inline size_t mc_audio_blocks_per_write(size_t max_write) {
  size_t n = max_write > MC_AUDIO_DATA_HDR_LEN ? (max_write - MC_AUDIO_DATA_HDR_LEN) / MC_AUDIO_BLOCK_BYTES : 0;
  return n ? n : 1;
}

/* Compute the chunk payload size for a negotiated ATT MTU. */
static inline uint16_t mc_chunk_len_for_mtu(uint16_t mtu) {
  int n = (int)mtu - MC_ATT_HDR_LEN - MC_XFER_CHUNK_HDR_LEN;
  if (n < 16) n = 16;
  if (n > 510) n = 510;
  return (uint16_t)n;
}

#ifdef __cplusplus
}
#endif
#endif /* MCRING_PROTO_H */
