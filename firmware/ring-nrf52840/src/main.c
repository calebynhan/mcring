/* mcring stage-2 skeleton: nRF52840 / Zephyr. Same protocol and state machine as the ESP32 build. */
#include "mcring_cfg.h"
#include "mcring_proto.h"
#include "ble_svc.h"
#include "transfer.h"
#include "feedback.h"
#include "camera_hal.h"
#include "trigger.h"
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <string.h>

LOG_MODULE_REGISTER(mcring, LOG_LEVEL_INF);

static uint8_t g_state = MC_STATE_IDLE, g_err;
static bool g_status_dirty = true;
static int64_t g_last_status;

static void send_status(void) {
  mc_status_t s = { .version = MCRING_PROTO_VERSION, .state = g_state, .battery_mv = 0, .battery_pct = 255,
                    .flags = (camera_hal_available() ? MC_FLAG_CAMERA_OK : 0) | (transfer_queued() ? MC_FLAG_QUEUED : 0),
                    .uptime_s = k_uptime_get() / 1000, .last_error = g_err ? g_err : transfer_last_error(),
                    .queued = transfer_queued() };
  uint8_t b[12]; mc_encode_status(&s, b);
  ble_svc_notify_status(b, sizeof b);
  g_last_status = k_uptime_get(); g_status_dirty = false;
}

static void do_capture(uint8_t quality, bool on_ring) {
  cam_frame_t f = {0};
  g_state = MC_STATE_CAPTURING; g_status_dirty = true;
  if (camera_hal_capture(quality, &f) != 0) { g_err = MC_ERR_CAPTURE_FAILED; feedback_play_text("HH", 20, MC_CH_LED); g_state = MC_STATE_IDLE; return; }
  xfer_item_t it = { .data = f.data, .len = f.len, .type = MC_XFER_JPEG, .width = f.width, .height = f.height, .flags = on_ring };
  if (!transfer_enqueue(&it)) k_free(f.data);
  g_err = 0;
  static const uint8_t sn[] = {1,1,1,1,1,1,3,1,1};
  feedback_play_units(sn, sizeof sn, 50, MC_CH_LED);
  g_state = ble_svc_connected() ? MC_STATE_TRANSFERRING : MC_STATE_IDLE;
}

static void on_control(const uint8_t *d, size_t n) {
  switch (d[0]) {
  case MC_OP_CAPTURE: if (g_state <= MC_STATE_TRANSFERRING) do_capture(n > 1 ? d[1] : 0, false); break;
  case MC_OP_ACK_TRANSFER: transfer_on_ack(d + 1, n - 1); g_status_dirty = true; break;
  case MC_OP_PING: case MC_OP_GET_STATUS: g_status_dirty = true; break;
  case MC_OP_ABORT: transfer_abort_all(); feedback_stop(); g_state = MC_STATE_IDLE; break;
  case MC_OP_SET_CONFIG: /* TODO: persist via settings subsystem */ g_status_dirty = true; break;
  default: LOG_WRN("op 0x%02x", d[0]);
  }
}

static void on_feedback(const uint8_t *d, size_t n) {
  switch (d[0]) {
  case MC_FB_MORSE_TEXT: { if (n < 4) return; char t[256]; uint8_t l = MIN(d[3], n - 4); memcpy(t, d + 4, l); t[l] = 0; feedback_play_text(t, d[1], d[2]); break; }
  case MC_FB_PATTERN: if (n >= 4) feedback_play_units(d + 4, MIN(d[3], n - 4), d[1], d[2]); break;
  case MC_FB_STOP: feedback_stop(); break;
  case MC_FB_MORSE_UNITS: if (n >= 5) { feedback_units_begin(mc_get_u16(d + 3), d[1], d[2]); feedback_units_put(0, d + 5, n - 5); } break;
  case MC_FB_MORSE_UNITS_CONT: if (n >= 3) feedback_units_put(mc_get_u16(d + 1), d + 3, n - 3); break;
  default: break;
  }
}

static void on_conn(bool connected) { g_status_dirty = true; if (!connected) { transfer_on_disconnect(); feedback_stop(); } }

int main(void) {
  LOG_INF("mcring nRF52840 fw %s", MCRING_FW_VERSION);
  feedback_init();
  camera_hal_init();
  trigger_init();
  ble_svc_init(on_control, on_feedback, on_conn);
  while (1) {
    if (trigger_poll_capture() && g_state <= MC_STATE_TRANSFERRING) do_capture(0, true);
    transfer_tick();
    feedback_tick();
    if (g_state == MC_STATE_TRANSFERRING && !transfer_busy() && !transfer_queued()) g_state = MC_STATE_IDLE;
    if (ble_svc_connected() && (g_status_dirty || k_uptime_get() - g_last_status > 30000)) send_status();
    k_sleep(K_MSEC(2));
  }
  return 0;
}
