#include "camera_mod.h"
#include "config.h"
#include "log.h"
#include "settings.h"
#include "mcring_proto.h"
#include <Arduino.h>
#include <esp_camera.h>
#include <esp_heap_caps.h>

static const char *TAG = "cam";
static bool s_available = false;

static framesize_t fs_from_code(uint8_t code) {
  switch (code) {
    case MC_FS_QQVGA: return FRAMESIZE_QQVGA;
    case MC_FS_QVGA:  return FRAMESIZE_QVGA;
    case MC_FS_VGA:   return FRAMESIZE_VGA;
    case MC_FS_SVGA:  return FRAMESIZE_SVGA;
    case MC_FS_XGA:   return FRAMESIZE_XGA;
    default:          return FRAMESIZE_QVGA;
  }
}

static void camera_power(bool on) {
#if PIN_CAM_PWR >= 0
  pinMode(PIN_CAM_PWR, OUTPUT);
  digitalWrite(PIN_CAM_PWR, on ? HIGH : LOW);
  if (on) delay(20);   // LDO + sensor power-up
#else
  (void)on;
#endif
}

static bool camera_init(uint8_t quality, uint8_t frame_size) {
  camera_config_t c = {};
  c.ledc_channel = LEDC_CHANNEL_0;
  c.ledc_timer   = LEDC_TIMER_0;
  c.pin_d0 = CAM_PIN_Y2;  c.pin_d1 = CAM_PIN_Y3;  c.pin_d2 = CAM_PIN_Y4;  c.pin_d3 = CAM_PIN_Y5;
  c.pin_d4 = CAM_PIN_Y6;  c.pin_d5 = CAM_PIN_Y7;  c.pin_d6 = CAM_PIN_Y8;  c.pin_d7 = CAM_PIN_Y9;
  c.pin_xclk  = CAM_PIN_XCLK;
  c.pin_pclk  = CAM_PIN_PCLK;
  c.pin_vsync = CAM_PIN_VSYNC;
  c.pin_href  = CAM_PIN_HREF;
  c.pin_sccb_sda = CAM_PIN_SIOD;
  c.pin_sccb_scl = CAM_PIN_SIOC;
  c.pin_pwdn  = CAM_PIN_PWDN;
  c.pin_reset = CAM_PIN_RESET;
  c.xclk_freq_hz = 20000000;
  c.pixel_format = PIXFORMAT_JPEG;
  c.frame_size   = fs_from_code(frame_size);
  c.jpeg_quality = quality;
  c.fb_count     = 1;
  c.fb_location  = psramFound() ? CAMERA_FB_IN_PSRAM : CAMERA_FB_IN_DRAM;
  c.grab_mode    = CAMERA_GRAB_LATEST;

  esp_err_t err = esp_camera_init(&c);
  if (err != ESP_OK) {
    LOGE(TAG, "esp_camera_init failed: 0x%x", err);
    return false;
  }
  sensor_t *s = esp_camera_sensor_get();
  if (s) {
    // Sensible stills defaults; OV2640/OV3660 share this API.
    s->set_brightness(s, 0);
    s->set_saturation(s, 0);
    s->set_whitebal(s, 1);
    s->set_awb_gain(s, 1);
    s->set_exposure_ctrl(s, 1);
    s->set_aec2(s, 1);
    s->set_gain_ctrl(s, 1);
    s->set_lenc(s, 1);
    if (s->id.PID == OV3660_PID) { s->set_vflip(s, 1); s->set_brightness(s, 1); s->set_saturation(s, -2); }
  }
  return true;
}

void camera_probe() {
  camera_power(true);
  s_available = camera_init(DEFAULT_JPEG_QUALITY, MC_FS_QVGA);
  if (s_available) {
    sensor_t *s = esp_camera_sensor_get();
    LOGI(TAG, "sensor PID=0x%04x detected", s ? s->id.PID : 0);
    esp_camera_deinit();
  }
  camera_power(false);
}

bool camera_available() { return s_available; }

bool camera_capture(uint8_t quality, uint8_t frame_size, Capture *out, uint8_t *err) {
  if (quality == 0) quality = settings().jpeg_quality;
  if (frame_size == 0) frame_size = settings().frame_size;
  if (quality < 1) quality = 1;
  if (quality > 63) quality = 63;

  camera_power(true);
  if (!camera_init(quality, frame_size)) {
    camera_power(false);
    if (err) *err = MC_ERR_CAMERA_INIT;
    return false;
  }

  // Let AEC/AWB settle: throw away a few frames (~100-150 ms at QVGA).
  for (int i = 0; i < 3; i++) {
    camera_fb_t *fb = esp_camera_fb_get();
    if (fb) esp_camera_fb_return(fb);
  }

  camera_fb_t *fb = esp_camera_fb_get();
  if (!fb || fb->len < 100) {
    if (fb) esp_camera_fb_return(fb);
    esp_camera_deinit();
    camera_power(false);
    if (err) *err = MC_ERR_CAPTURE_FAILED;
    return false;
  }

  // Copy out so the driver (and its DMA buffers) can be torn down immediately.
  uint8_t *buf = (uint8_t *)heap_caps_malloc(fb->len, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
  if (!buf) buf = (uint8_t *)malloc(fb->len);
  if (!buf) {
    esp_camera_fb_return(fb);
    esp_camera_deinit();
    camera_power(false);
    if (err) *err = MC_ERR_OOM;
    return false;
  }
  memcpy(buf, fb->buf, fb->len);
  out->data = buf;
  out->len = fb->len;
  out->width = fb->width;
  out->height = fb->height;
  esp_camera_fb_return(fb);
  esp_camera_deinit();
  camera_power(false);
  LOGI(TAG, "captured %ux%u JPEG, %u bytes (q=%u)", out->width, out->height, (unsigned)out->len, quality);
  if (err) *err = MC_ERR_NONE;
  return true;
}

void capture_free(Capture *c) {
  if (c && c->data) { free(c->data); c->data = nullptr; c->len = 0; }
}
