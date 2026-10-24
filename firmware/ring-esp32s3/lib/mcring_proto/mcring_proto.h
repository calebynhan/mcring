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
};

/* Feedback opcodes (phone -> ring) */
enum {
  MC_FB_MORSE_TEXT       = 0x10,
  MC_FB_PATTERN          = 0x11,
  MC_FB_STOP             = 0x12,
  MC_FB_RGB              = 0x13,
  MC_FB_MORSE_UNITS      = 0x14,
  MC_FB_MORSE_UNITS_CONT = 0x15,
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
  MC_CFG_MORSE_WPM         = 7,
  MC_CFG_FEEDBACK_CHANNELS = 8,
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
  MC_STATE_FEEDBACK     = 4,
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
  MC_FLAG_HAPTIC_OK = 0x10,
  MC_FLAG_QUEUED    = 0x20,
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

#define MC_XFER_CHUNK_HDR_LEN 4
#define MC_ATT_HDR_LEN        3

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
