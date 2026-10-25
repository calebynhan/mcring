/*
 * mcring — voice-first camera ring firmware (ESP32-S3)
 *
 *   hold the button / double-tap  →  "ask": listening cue, (photo +) voice question  →  phone → Claude
 *   short press / touch           →  capture a JPEG  →  queue  →  BLE transfer to phone
 *   phone → Events (0007)         ←  BUTTON_DOWN/UP, taps, capture/record lifecycle, battery, audio-out
 *   phone → Audio out (0008)      →  ADPCM stream → on-ring speaker (optional, HAS_SPEAKER)
 *   phone → Feedback (0006)       →  cues (haptic/LED ticks); raw patterns / Morse kept as legacy
 *
 * Two mic sources (SET_CONFIG MIC_SOURCE_HINT): ring mic — the ring records while the button is held
 * and sends an ADPCM clip; phone mic — the ring only reports BUTTON_DOWN/UP and the phone records.
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
#include "cues.h"
#include "audio_mod.h"
#include "audio_out.h"
#include "power.h"

static const char *TAG = "main";

static uint8_t  g_state = MC_STATE_IDLE;
static uint8_t  g_last_err = MC_ERR_NONE;
static uint32_t g_last_status_ms = 0;
static bool     g_status_dirty = true;

static bool     g_voice_pending = false;   // ring-mic recording in progress
static uint32_t g_rec_start_ms = 0;
static bool     g_ask_active = false;      // an "ask a question" session (long press / double tap) is open
static bool     g_ask_phone_mic = false;   // ... and the phone is the one recording
static uint32_t g_ask_start_ms = 0;
static bool     g_low_batt_sent = false;

// A phone-mic ask has no ring-side recording to end it and the companions do not send RECORD_STOP when
// their own recording ends (the hands-free one auto-stops after 8 s). Expire it like the ring-mic clip
// cap so the ring does not stay "busy" (no deep sleep, no listening cue on the next press) forever.
static const uint32_t ASK_PHONE_MIC_TIMEOUT_MS = (uint32_t)VOICE_CLIP_MAX_S * 1000UL + 500;

// ---------------------------------------------------------------------------
static void emit_event(uint8_t ev, uint8_t arg) {
  bool sent = ble::notify_event(ev, arg);
  LOGD(TAG, "event %u arg %u %s", ev, arg, sent ? "" : "(not delivered)");
  (void)sent;
}

static uint8_t tenths_capped(uint32_t ms) {
  uint32_t t = (ms + 50) / 100;
  return (uint8_t)(t > 255 ? 255 : t);
}

// BUTTON_UP arg: floor(held / 100 ms), capped at 255, and always consistent with the ring's own
// short/long classification — the companions branch on `arg < 7` (photo) vs `arg >= 7` (ask), so a
// 650-699 ms press must not round up to 7 and a long press detected at 700 ms must never read 6.
static uint8_t button_up_arg(uint32_t held_ms, bool long_press) {
  const uint32_t thr = BUTTON_LONG_PRESS_MS / 100;   // 7
  uint32_t t = held_ms / 100;
  if (long_press && t < thr) t = thr;
  if (!long_press && t >= thr) t = thr - 1;
  return (uint8_t)(t > 255 ? 255 : t);
}

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
          | (battery_charging() ? MC_FLAG_CHARGING : 0)
          | (audio_out_available() ? MC_FLAG_SPEAKER_OK : 0);
  s.uptime_s = millis() / 1000;
  s.last_error = g_last_err ? g_last_err : transfer::last_error();
  s.queued = (uint8_t)transfer::queued();
  uint8_t buf[12];
  mc_encode_status(&s, buf);
  ble::notify_status(buf, sizeof buf);
  g_last_status_ms = millis();
  g_status_dirty = false;

  // LOW_BATTERY once when we drop below the threshold; re-armed once comfortably above it.
  if (s.battery_pct != 255 && !battery_charging()) {
    if (!g_low_batt_sent && s.battery_pct < LOW_BATTERY_PCT) { g_low_batt_sent = true; emit_event(MC_EV_LOW_BATTERY, s.battery_pct); }
    else if (g_low_batt_sent && s.battery_pct >= LOW_BATTERY_REARM_PCT) g_low_batt_sent = false;
  }
}

static void set_state(uint8_t st) {
  if (st != g_state) { g_state = st; g_status_dirty = true; }
}

static bool can_start_action() { return g_state == MC_STATE_IDLE || g_state == MC_STATE_TRANSFERRING || g_state == MC_STATE_FEEDBACK; }

// ---------------------------------------------------------------------------
static void do_capture(uint8_t quality, uint8_t frame_size, bool on_ring) {
  if (!camera_available()) {
    g_last_err = MC_ERR_CAMERA_INIT;
    cues_error();
    emit_event(MC_EV_CAPTURE_DONE, 0);
    g_status_dirty = true;
    return;
  }
  set_state(MC_STATE_CAPTURING);
  power_note_activity();
  emit_event(MC_EV_CAPTURE_STARTED, 0);
  Capture cap;
  uint8_t err = MC_ERR_NONE;
  if (!camera_capture(quality, frame_size, &cap, &err)) {
    g_last_err = err;
    LOGE(TAG, "capture failed (%u)", err);
    cues_error();
    emit_event(MC_EV_CAPTURE_DONE, 0);
    set_state(MC_STATE_IDLE);
    return;
  }
  transfer::Item it = { cap.data, cap.len, MC_XFER_JPEG, cap.width, cap.height, (uint8_t)(on_ring ? 1 : 0) };
  if (!transfer::enqueue(it)) {
    capture_free(&cap);
    g_last_err = MC_ERR_OOM;
    cues_error();
    emit_event(MC_EV_CAPTURE_DONE, 0);
    set_state(MC_STATE_IDLE);
    return;
  }
  g_last_err = MC_ERR_NONE;
  emit_event(MC_EV_CAPTURE_DONE, (uint8_t)transfer::queued());
  set_state(ble::connected() ? MC_STATE_TRANSFERRING : MC_STATE_IDLE);
}

// ---- ring-mic recording ------------------------------------------------------
static bool start_voice(uint8_t seconds) {
  if (!audio_available() || g_voice_pending) return false;
  if (seconds < 1) seconds = 1;
  if (seconds > VOICE_CLIP_MAX_S) seconds = VOICE_CLIP_MAX_S;
  if (!audio_start_recording(seconds)) { g_last_err = MC_ERR_MIC; cues_error(); g_status_dirty = true; return false; }
  g_voice_pending = true;
  g_rec_start_ms = millis();
  set_state(MC_STATE_RECORDING);
  emit_event(MC_EV_REC_STARTED, seconds);
  return true;
}

static void finish_voice() {
  if (!g_voice_pending) return;
  g_voice_pending = false;
  uint8_t *buf = nullptr; size_t len = 0; uint32_t n = 0;
  uint8_t tenths = 0;
  if (audio_finish(&buf, &len, &n)) {
    tenths = tenths_capped((uint32_t)((uint64_t)n * 1000 / VOICE_SAMPLE_RATE));
    if (!tenths) tenths = 1;
    transfer::Item it = { buf, len, MC_XFER_ADPCM, 0, (uint16_t)(VOICE_SAMPLE_RATE / 100), 1 };
    if (!transfer::enqueue(it)) { free(buf); tenths = 0; g_last_err = MC_ERR_OOM; }
  }
  emit_event(MC_EV_REC_STOPPED, tenths);
  set_state(MC_STATE_IDLE);
}

// ---- "ask a question": long press or double tap --------------------------------
//   ring mic  : photo → listening cue → record while held (or up to VOICE_CLIP_MAX_S). The capture
//               blocks loop() for ~150-400 ms, so the cue is played *after* it: the tick marks the
//               real start of recording (speak after the tick) instead of being stretched into a
//               buzz by the capture. Recording therefore starts ≈ 0.85-1.1 s after BUTTON_DOWN.
//   phone mic : listening cue only; the phone records between BUTTON_DOWN and BUTTON_UP (or after
//               DOUBLE_TAP) and sends CAPTURE itself if it wants a photo attached. Ends on release,
//               a second double tap, RECORD_STOP / ABORT, or ASK_PHONE_MIC_TIMEOUT_MS.
static void begin_ask() {
  if (g_ask_active || !can_start_action()) { g_status_dirty = true; return; }
  g_ask_active = true;
  g_ask_phone_mic = settings().mic_source == MC_MIC_SRC_PHONE;
  g_ask_start_ms = millis();
  power_note_activity();
  if (g_ask_phone_mic) { LOGI(TAG, "ask (phone mic)"); cues_listening(); return; }
  LOGI(TAG, "ask (ring mic)");
  do_capture(0, 0, true);                  // queued ahead of the clip; the app pairs photo + voice
  cues_listening();                        // a failed start below replaces it with the error buzz
  if (!start_voice(VOICE_CLIP_MAX_S)) g_ask_active = false;
}

static void end_ask() {
  if (!g_ask_active) return;
  g_ask_active = false;
  if (g_voice_pending) finish_voice();
}

// ---------------------------------------------------------------------------
static void handle_control(const uint8_t *d, size_t n) {
  power_note_activity();
  switch (d[0]) {
    case MC_OP_CAPTURE: {
      uint8_t q = n > 1 ? d[1] : 0, fs = n > 2 ? d[2] : 0;
      // Allowed while a phone-mic "ask" is open (the phone attaches a photo to the question).
      if (can_start_action() || (g_ask_active && g_ask_phone_mic && g_state != MC_STATE_CAPTURING)) do_capture(q, fs, false);
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
      audio_out_stop();
      if (g_voice_pending) { audio_abort(); g_voice_pending = false; emit_event(MC_EV_REC_STOPPED, 0); }
      g_ask_active = false;
      set_state(MC_STATE_IDLE);
      break;
    case MC_OP_RECORD_AUDIO:             // fixed-length clip (legacy, kept for the CLI)
      if (can_start_action()) start_voice(n > 1 ? d[1] : 3);
      else g_status_dirty = true;
      break;
    case MC_OP_RECORD_START:             // phone drives the ring mic explicitly
      if (can_start_action()) { cues_listening(); start_voice(VOICE_CLIP_MAX_S); }
      else g_status_dirty = true;
      break;
    case MC_OP_RECORD_STOP:
      if (g_voice_pending) finish_voice();
      g_ask_active = false;
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
    case MC_FB_CUE:
      if (n >= 2) cues_play(d[1]);
      break;
    case MC_FB_MORSE_TEXT: {               // legacy "silent pattern" mode
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
    case MC_FB_MORSE_UNITS: {              // legacy
      if (n < 5) return;
      uint8_t unit_ms = d[1], ch = d[2];
      uint16_t cnt = mc_get_u16(d + 3);
      feedback_units_begin(cnt, unit_ms, ch);
      feedback_units_put(0, d + 5, n - 5);
      break;
    }
    case MC_FB_MORSE_UNITS_CONT: {         // legacy
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
    cues_connected();
  } else {
    transfer::on_disconnect();
    feedback_stop();
    audio_out_stop();                       // nobody is streaming any more
  }
  power_note_activity();
}

// ---------------------------------------------------------------------------
static void handle_trigger(TriggerEvent ev) {
  switch (ev) {
    case TriggerEvent::ButtonDown:
      power_note_activity();
      emit_event(MC_EV_BUTTON_DOWN, 0);     // phone-mic mode starts recording on this
      break;
    case TriggerEvent::ShortPress:
      emit_event(MC_EV_BUTTON_UP, button_up_arg(trigger_button_held_ms(), false));
      if (can_start_action()) do_capture(0, 0, true);
      break;
    case TriggerEvent::LongPress:
      begin_ask();
      break;
    case TriggerEvent::LongRelease:
      emit_event(MC_EV_BUTTON_UP, button_up_arg(trigger_button_held_ms(), true));
      end_ask();
      break;
    case TriggerEvent::DoubleTap:
      emit_event(MC_EV_DOUBLE_TAP, 0);
      if (g_ask_active) end_ask();          // second double tap ends a hands-free question
      else begin_ask();
      break;
    case TriggerEvent::Touch:
      emit_event(MC_EV_TOUCH, 0);
      if (can_start_action()) do_capture(0, 0, true);
      break;
    default: break;
  }
}

// ---------------------------------------------------------------------------
void setup() {
  Serial.begin(115200);
  uint32_t t0 = millis();
  while (!Serial && millis() - t0 < 1500) delay(10);
  LOGI(TAG, "mcring fw %s (%s) voice-first", MCRING_FW_VERSION, BOARD_NAME);

  settings_load();
  power_init();
  feedback_init();
  cues_init();

  Wire.begin(PIN_I2C_SDA, PIN_I2C_SCL, 400000);
  imu_init();                              // LIS2DW12 or LIS3DH, whichever answers (imu_lis3dh.cpp)
  drv2605_init(HAPTIC_MOTOR_LRA);          // 1 = 8 mm LRA (default); 0 = ERM, e.g. the Grove Haptic Motor of the no-solder kit (config_audio.h)
  if (drv2605_available()) { drv2605_autocal(); drv2605_standby(true); }

  camera_probe();
  audio_init();
  audio_out_init();
  audio_out_on_event(emit_event);
  trigger_init();

  ble::on_control(handle_control);
  ble::on_feedback(handle_feedback);
  ble::on_connection(handle_connection);
  ble::init("mcring");

  // Woken by a tap → hands-free "ask" (ring mic: captured + recorded now, sent once the phone connects).
  // Woken by the button → trigger_tick() sees the button state and decides short press vs. long press.
  esp_sleep_wakeup_cause_t cause = esp_sleep_get_wakeup_cause();
  if (cause == ESP_SLEEP_WAKEUP_EXT1) {
    LOGI(TAG, "wake by tap -> ask");
    begin_ask();
  }
  cues_ok();
}

void loop() {
  ble::tick();

  // User input
  handle_trigger(trigger_tick());

  // Ring-mic recording pump; auto-stop at the clip limit
  if (g_voice_pending) {
    audio_tick();
    if (millis() - g_rec_start_ms > (uint32_t)VOICE_CLIP_MAX_S * 1000UL + 200) { finish_voice(); g_ask_active = false; }
  }

  // Phone-mic ask: the phone records, nothing on the ring ends the session. Expire it once the clip
  // cap has passed unless the button is still physically held (then LongRelease → end_ask()).
  if (g_ask_active && g_ask_phone_mic && !trigger_button_down() &&
      millis() - g_ask_start_ms > ASK_PHONE_MIC_TIMEOUT_MS) {
    LOGI(TAG, "ask (phone mic) timed out");
    g_ask_active = false;
  }

  // Transfers
  transfer::tick();
  if (g_state == MC_STATE_TRANSFERRING && !transfer::busy() && transfer::queued() == 0) set_state(MC_STATE_IDLE);
  if (g_state == MC_STATE_IDLE && transfer::busy()) set_state(MC_STATE_TRANSFERRING);

  // Output: cues/patterns and the speaker stream
  feedback_tick();
  audio_out_tick();
  bool playing = feedback_playing() || audio_out_active();
  if (playing && g_state == MC_STATE_IDLE) set_state(MC_STATE_FEEDBACK);
  if (!playing && g_state == MC_STATE_FEEDBACK) set_state(MC_STATE_IDLE);

  // Status
  if (ble::connected() && (g_status_dirty || millis() - g_last_status_ms > STATUS_PERIOD_MS)) send_status();

  // Power
  power_tick(ble::connected(), transfer::busy() || playing || g_voice_pending || g_ask_active);

  delay(1);
}
