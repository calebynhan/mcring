/*
 * mcring — camera ring firmware (ESP32-S3)
 *
 *   trigger (button / double-tap / touch)  →  capture JPEG  →  queue  →  BLE transfer to phone
 *   phone → Feedback characteristic        →  Morse on LED / haptic / buzzer / aux
 *
 * Everything is cooperative: loop() ticks each module; nothing blocks for more than ~20 ms
 * except the camera capture itself (~150-400 ms).
 */
#include <Arduino.h>
#include <Wire.h>
#include <esp_sleep.h>
#include "config.h"
#include "log.h"
#include "mcring_proto.h"
#include "settings.h"
#include "camera_mod.h"
#include "ble_link.h"
#include "transfer.h"
#include "trigger.h"
#include "imu_lis2dw12.h"
#include "drv2605.h"
#include "feedback.h"
#include "audio_mod.h"
#include "power.h"

static const char *TAG = "main";

static uint8_t  g_state = MC_STATE_IDLE;
static uint8_t  g_last_err = MC_ERR_NONE;
static uint32_t g_last_status_ms = 0;
static bool     g_status_dirty = true;
static bool     g_voice_pending = false;   // recording in progress after a long press

// ---------------------------------------------------------------------------
static void send_status() {
  mc_status_t s = {};
  s.version = MCRING_PROTO_VERSION;
  s.state = g_state;
  s.battery_mv = battery_mv();
  s.battery_pct = battery_pct();
  s.flags = (camera_available() ? MC_FLAG_CAMERA_OK : 0)
          | (imu_available() ? MC_FLAG_IMU_OK : 0)
          | (audio_available() ? MC_FLAG_MIC_OK : 0)
          | (drv2605_available() ? MC_FLAG_HAPTIC_OK : 0)
          | (transfer::queued() ? MC_FLAG_QUEUED : 0)
          | (battery_charging() ? MC_FLAG_CHARGING : 0);
  s.uptime_s = millis() / 1000;
  s.last_error = g_last_err ? g_last_err : transfer::last_error();
  s.queued = (uint8_t)transfer::queued();
  uint8_t buf[12];
  mc_encode_status(&s, buf);
  ble::notify_status(buf, sizeof buf);
  g_last_status_ms = millis();
  g_status_dirty = false;
}

static void set_state(uint8_t st) {
  if (st != g_state) { g_state = st; g_status_dirty = true; }
}

// ---------------------------------------------------------------------------
static void do_capture(uint8_t quality, uint8_t frame_size, bool on_ring) {
  if (!camera_available()) {
    g_last_err = MC_ERR_CAMERA_INIT;
    feedback_signal_error();
    g_status_dirty = true;
    return;
  }
  set_state(MC_STATE_CAPTURING);
  power_note_activity();
  Capture cap;
  uint8_t err = MC_ERR_NONE;
  if (!camera_capture(quality, frame_size, &cap, &err)) {
    g_last_err = err;
    LOGE(TAG, "capture failed (%u)", err);
    feedback_signal_error();
    set_state(MC_STATE_IDLE);
    return;
  }
  transfer::Item it = { cap.data, cap.len, MC_XFER_JPEG, cap.width, cap.height, (uint8_t)(on_ring ? 1 : 0) };
  if (!transfer::enqueue(it)) {
    capture_free(&cap);
    g_last_err = MC_ERR_OOM;
    feedback_signal_error();
    set_state(MC_STATE_IDLE);
    return;
  }
  g_last_err = MC_ERR_NONE;
  feedback_signal_ok();
  set_state(ble::connected() ? MC_STATE_TRANSFERRING : MC_STATE_IDLE);
}

static void start_voice(uint8_t seconds) {
  if (!audio_available()) return;
  if (audio_start_recording(seconds)) { g_voice_pending = true; set_state(MC_STATE_RECORDING); }
}

static void finish_voice() {
  if (!g_voice_pending) return;
  g_voice_pending = false;
  uint8_t *buf = nullptr; size_t len = 0; uint32_t n = 0;
  if (audio_finish(&buf, &len, &n)) {
    transfer::Item it = { buf, len, MC_XFER_ADPCM, 0, (uint16_t)(VOICE_SAMPLE_RATE / 100), 1 };
    if (!transfer::enqueue(it)) free(buf);
  }
  set_state(MC_STATE_IDLE);
}

// ---------------------------------------------------------------------------
static void handle_control(const uint8_t *d, size_t n) {
  power_note_activity();
  switch (d[0]) {
    case MC_OP_CAPTURE: {
      uint8_t q = n > 1 ? d[1] : 0, fs = n > 2 ? d[2] : 0;
      if (g_state == MC_STATE_IDLE || g_state == MC_STATE_TRANSFERRING) do_capture(q, fs, false);
      else g_status_dirty = true;
      break;
    }
    case MC_OP_ACK_TRANSFER:
      transfer::on_ack(d + 1, n - 1);
      g_status_dirty = true;
      break;
    case MC_OP_SET_CONFIG:
      if (n >= 6) {
        bool ok = settings_apply(d[1], mc_get_i32(d + 2));
        LOGI(TAG, "set_config key=%u -> %s", d[1], ok ? "ok" : "rejected");
      }
      g_status_dirty = true;
      break;
    case MC_OP_PING:
    case MC_OP_GET_STATUS:
      g_status_dirty = true;
      break;
    case MC_OP_ABORT:
      transfer::abort_all();
      feedback_stop();
      audio_abort();
      g_voice_pending = false;
      set_state(MC_STATE_IDLE);
      break;
    case MC_OP_RECORD_AUDIO:
      if (g_state == MC_STATE_IDLE || g_state == MC_STATE_TRANSFERRING) {
        start_voice(n > 1 ? d[1] : 3);
        // phone-requested clips stop automatically at max_seconds (see loop)
      }
      break;
    case MC_OP_SLEEP:
      send_status();
      delay(50);
      power_deep_sleep_now();
      break;
    default:
      LOGW(TAG, "unknown control op 0x%02x", d[0]);
  }
}

static void handle_feedback(const uint8_t *d, size_t n) {
  power_note_activity();
  switch (d[0]) {
    case MC_FB_MORSE_TEXT: {
      if (n < 4) return;
      uint8_t wpm = d[1], ch = d[2], len = d[3];
      if (len > n - 4) len = (uint8_t)(n - 4);
      char text[256];
      memcpy(text, d + 4, len); text[len] = 0;
      LOGI(TAG, "morse text \"%s\" @%u wpm", text, wpm);
      feedback_play_morse_text(text, wpm, ch);
      break;
    }
    case MC_FB_PATTERN: {
      if (n < 4) return;
      uint8_t unit_ms = d[1], ch = d[2], cnt = d[3];
      if (cnt > n - 4) cnt = (uint8_t)(n - 4);
      feedback_play_units(d + 4, cnt, unit_ms, ch);
      break;
    }
    case MC_FB_STOP:
      feedback_stop();
      break;
    case MC_FB_RGB:
      if (n >= 6) feedback_rgb(d[1], d[2], d[3], mc_get_u16(d + 4));
      break;
    case MC_FB_MORSE_UNITS: {
      if (n < 5) return;
      uint8_t unit_ms = d[1], ch = d[2];
      uint16_t cnt = mc_get_u16(d + 3);
      feedback_units_begin(cnt, unit_ms, ch);
      feedback_units_put(0, d + 5, n - 5);
      break;
    }
    case MC_FB_MORSE_UNITS_CONT: {
      if (n < 3) return;
      feedback_units_put(mc_get_u16(d + 1), d + 3, n - 3);
      break;
    }
    default:
      LOGW(TAG, "unknown feedback op 0x%02x", d[0]);
  }
}

static void handle_connection(bool connected) {
  g_status_dirty = true;
  if (connected) {
    feedback_signal_connected();
  } else {
    transfer::on_disconnect();
    feedback_stop();
  }
  power_note_activity();
}

// ---------------------------------------------------------------------------
void setup() {
  Serial.begin(115200);
  uint32_t t0 = millis();
  while (!Serial && millis() - t0 < 1500) delay(10);
  LOGI(TAG, "mcring fw %s (%s)", MCRING_FW_VERSION, BOARD_NAME);

  settings_load();
  power_init();
  feedback_init();

  Wire.begin(PIN_I2C_SDA, PIN_I2C_SCL, 400000);
  imu_init();
  drv2605_init(true);
  if (drv2605_available()) { drv2605_autocal(); drv2605_standby(true); }

  camera_probe();
  audio_init();
  trigger_init();

  ble::on_control(handle_control);
  ble::on_feedback(handle_feedback);
  ble::on_connection(handle_connection);
  ble::init("mcring");

  // If we were woken by the button or a tap, treat it as a trigger right away.
  esp_sleep_wakeup_cause_t cause = esp_sleep_get_wakeup_cause();
  if (cause == ESP_SLEEP_WAKEUP_EXT0 || cause == ESP_SLEEP_WAKEUP_EXT1) {
    LOGI(TAG, "wake trigger -> capture");
    do_capture(0, 0, true);
  }
  feedback_signal_ok();
}

void loop() {
  ble::tick();

  // Triggers
  TriggerEvent ev = trigger_tick();
  switch (ev) {
    case TriggerEvent::Capture:
      if (g_state == MC_STATE_IDLE || g_state == MC_STATE_TRANSFERRING) do_capture(0, 0, true);
      break;
    case TriggerEvent::CaptureAndVoice:
      if (g_state == MC_STATE_IDLE || g_state == MC_STATE_TRANSFERRING) {
        do_capture(0, 0, true);
        start_voice(VOICE_CLIP_MAX_S);
      }
      break;
    case TriggerEvent::VoiceEnd:
      finish_voice();
      break;
    default: break;
  }

  // Voice recording pump; auto-stop at buffer end
  if (g_voice_pending) {
    audio_tick();
    static uint32_t rec_start = 0;
    if (g_state == MC_STATE_RECORDING && rec_start == 0) rec_start = millis();
    if (rec_start && millis() - rec_start > (uint32_t)VOICE_CLIP_MAX_S * 1000UL + 200) { finish_voice(); rec_start = 0; }
    if (!g_voice_pending) rec_start = 0;
  }

  // Transfers
  transfer::tick();
  if (g_state == MC_STATE_TRANSFERRING && !transfer::busy() && transfer::queued() == 0) set_state(MC_STATE_IDLE);
  if (g_state == MC_STATE_IDLE && transfer::busy()) set_state(MC_STATE_TRANSFERRING);

  // Output
  feedback_tick();
  if (feedback_playing() && g_state == MC_STATE_IDLE) set_state(MC_STATE_FEEDBACK);
  if (!feedback_playing() && g_state == MC_STATE_FEEDBACK) set_state(MC_STATE_IDLE);

  // Status
  if (ble::connected() && (g_status_dirty || millis() - g_last_status_ms > STATUS_PERIOD_MS)) send_status();

  // Power
  power_tick(ble::connected(), transfer::busy() || feedback_playing() || g_voice_pending);

  delay(1);
}
