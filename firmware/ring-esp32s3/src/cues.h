#pragma once
#include <stdint.h>

// Short confirmation cues — the only haptic/LED output in the voice-first UX. Each cue is a tiny
// ON/OFF pattern played through the feedback pattern player on the channels enabled by CUES_MASK
// (bit0 haptic, bit1 LED, bit2 beep). Morse / arbitrary patterns remain available via the Feedback
// characteristic but nothing here produces them.
void cues_init();
void cues_listening();      // 1 short tick: recording (ring or phone) has started
void cues_answer_ready();   // 2 ticks: the answer is about to be spoken
void cues_error();          // long buzz
void cues_ok();             // 1 short tick: capture queued, boot
void cues_connected();      // LED-only blink on BLE connect (no haptic, so reconnects stay silent)
void cues_play(uint8_t cue_id);   // MC_CUE_* from the phone (Feedback opcode CUE)
