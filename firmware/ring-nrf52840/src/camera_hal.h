#pragma once
#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>

/* Camera abstraction for the nRF port. The nRF52840 has no camera peripheral, so a frame is
 * captured by (a) bit-banging the sensor's parallel bus from GPIO (proven on nRF52840 with
 * OV7670, see docs/research/02), or (b) clocking HM01B0 1-bit serial data into SPIS/I2S via
 * PPI. Both deliver a raw 8-bit grayscale frame; a tiny baseline JPEG encoder compresses it. */
typedef struct {
  uint8_t *data;     /* JPEG bytes (k_malloc'ed; caller frees) */
  size_t   len;
  uint16_t width, height;
} cam_frame_t;

int  camera_hal_init(void);
bool camera_hal_available(void);
int  camera_hal_capture(uint8_t quality, cam_frame_t *out);   /* 0 ok, <0 error */
