#pragma once
#include <stdint.h>
#include <stddef.h>

struct Capture {
  uint8_t *data = nullptr;   // JPEG bytes (heap/PSRAM; free with capture_free)
  size_t   len = 0;
  uint16_t width = 0;
  uint16_t height = 0;
};

// Powers the sensor, grabs one JPEG at the requested quality/frame size, powers it back down.
// quality 0 / frame_size 0 use the persisted defaults. Returns false and sets *err on failure.
bool camera_capture(uint8_t quality, uint8_t frame_size, Capture *out, uint8_t *err);
void capture_free(Capture *c);
bool camera_available();      // sensor detected at boot probe
void camera_probe();          // one-time init/deinit to detect the sensor and warm settings
