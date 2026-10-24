#include "cues.h"
#include "config.h"
#include "feedback.h"
#include "mcring_proto.h"
#include "settings.h"

namespace {

// CUES_MASK → feedback channel mask. Returns 0 when every cue channel is disabled.
uint8_t channels(bool with_haptic, bool with_beep) {
  uint8_t m = settings().cues_mask, ch = 0;
  if (with_haptic && (m & MC_CUES_HAPTIC)) ch |= MC_CH_HAPTIC;
  if (m & MC_CUES_LED) ch |= MC_CH_LED;
  if (with_beep && (m & MC_CUES_BEEP)) ch |= MC_CH_BUZZER;
  return ch;
}

void play(const uint8_t *units, size_t n, uint16_t unit_ms, uint8_t ch) {
  if (!ch) return;   // feedback_play_units() would fall back to the legacy default channels
  feedback_play_units(units, n, unit_ms, ch);
}

const uint8_t P_TICK[]   = {1};          // ─
const uint8_t P_DOUBLE[] = {1, 1, 1};    // ─ ─
const uint8_t P_LONG[]   = {7};          // ███████ (7 × CUE_TICK_MS = 420 ms)
const uint8_t P_BLINK[]  = {1, 1, 1};

}  // namespace

void cues_init() {}

void cues_listening()    { play(P_TICK,   sizeof P_TICK,   CUE_TICK_MS, channels(true, true)); }
void cues_ok()           { play(P_TICK,   sizeof P_TICK,   CUE_TICK_MS, channels(true, false)); }
void cues_answer_ready() { play(P_DOUBLE, sizeof P_DOUBLE, CUE_TICK_MS, channels(true, true)); }
void cues_error()        { play(P_LONG,   sizeof P_LONG,   CUE_TICK_MS, channels(true, true)); }
void cues_connected()    { play(P_BLINK,  sizeof P_BLINK,  40,          channels(false, false)); }

void cues_play(uint8_t id) {
  switch (id) {
    case MC_CUE_LISTENING:    cues_listening(); break;
    case MC_CUE_ANSWER_READY: cues_answer_ready(); break;
    case MC_CUE_ERROR:        cues_error(); break;
    case MC_CUE_OK:           cues_ok(); break;
    default: break;
  }
}
