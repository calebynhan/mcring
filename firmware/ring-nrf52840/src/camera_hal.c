#include "camera_hal.h"
#include "mcring_cfg.h"
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <errno.h>
#include <string.h>

LOG_MODULE_REGISTER(mc_cam, LOG_LEVEL_INF);

/* ---------------------------------------------------------------------------------------------
 * STATUS: skeleton. The capture path below returns a synthetic test frame so the whole BLE /
 * transfer / phone / LLM pipeline can be exercised on a XIAO nRF52840 Sense before the camera
 * work lands. Replace capture_raw() with one of:
 *   1. GPIO bit-bang of OV7670/OV7675 8-bit DVP (Arduino_OV767X does exactly this on the same chip).
 *   2. HM01B0 in 1-bit serial mode: PCLK → SPIS SCK, D0 → SPIS MOSI, VSYNC gating via GPIOTE/PPI.
 * and route raw grayscale through jpeg_encode_gray() (baseline DCT encoder, ~6 KB of code —
 * e.g. the public-domain "jo_jpeg" or TinyJPEG; not vendored here).
 * ------------------------------------------------------------------------------------------- */

static bool s_ok;

static int capture_raw(uint8_t *gray, uint16_t w, uint16_t h) {
  /* synthetic gradient + box so the phone can tell the frame apart from real captures */
  for (int y = 0; y < h; y++)
    for (int x = 0; x < w; x++)
      gray[y * w + x] = (x > w / 3 && x < 2 * w / 3 && y > h / 3 && y < 2 * h / 3) ? 40 : (uint8_t)((x * 255) / w);
  return 0;
}

/* Minimal "JPEG" stand-in: wrap the raw frame in a PGM header so the companion can still decode
 * it (the backend's Pillow accepts PGM). Swap for a real JPEG encoder — PGM is ~19 KB for 160x120. */
static int encode_pgm(const uint8_t *gray, uint16_t w, uint16_t h, cam_frame_t *out) {
  char hdr[32];
  int hl = snprintk(hdr, sizeof hdr, "P5\n%u %u\n255\n", w, h);
  out->len = hl + (size_t)w * h;
  out->data = k_malloc(out->len);
  if (!out->data) return -ENOMEM;
  memcpy(out->data, hdr, hl);
  memcpy(out->data + hl, gray, (size_t)w * h);
  out->width = w; out->height = h;
  return 0;
}

int camera_hal_init(void) {
  s_ok = true;   /* set from a real sensor probe (I2C WHO_AM_I) once wired */
  LOG_WRN("camera HAL is a stub: sending synthetic frames");
  return 0;
}
bool camera_hal_available(void) { return s_ok; }

int camera_hal_capture(uint8_t quality, cam_frame_t *out) {
  ARG_UNUSED(quality);
  uint8_t *gray = k_malloc((size_t)CAM_W * CAM_H);
  if (!gray) return -ENOMEM;
  int rc = capture_raw(gray, CAM_W, CAM_H);
  if (rc == 0) rc = encode_pgm(gray, CAM_W, CAM_H, out);
  k_free(gray);
  return rc;
}
