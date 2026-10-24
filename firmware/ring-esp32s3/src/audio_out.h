#pragma once
#include <stdint.h>
#include <stddef.h>
#include <functional>

// On-ring speaker: phone streams 16 kHz mono mcring-ADPCM over the AUDIO_OUT characteristic (0008),
// the ring queues the 132-byte blocks, decodes them and plays them over I2S (MAX98357A class-D amp).
//
// Threading: audio_out_on_packet() and audio_out_stop() may run on the NimBLE host task (control /
// audio-out writes and the disconnect callback): they only touch the block queue and the command flags,
// which are protected by a spinlock critical section. Everything else — the I2S driver, the decoder,
// the state machine and the event sink — runs from loop() via audio_out_tick().
//
// Lifecycle:  AUDIO_START → Prebuffer (24 blocks ≈ 400 ms, or AUDIO_END arrives) → Playing
//             queue empty & AUDIO_END → Draining (let DMA finish) → Idle + AUDIO_DONE(0)
//             queue empty & no END     → AUDIO_UNDERRUN, silence, rebuffer 8 blocks, resume
//             AUDIO_STOP / ABORT       → Idle + AUDIO_DONE(1)
// The I2S driver (and the amp, if PIN_SPEAKER_EN is wired) is only installed while a stream plays.

enum class AudioOutState : uint8_t { Idle = 0, Prebuffer, Playing, Draining };

void audio_out_init();                                   // GPIO setup only; no driver until a stream starts
bool audio_out_available();                              // HAS_SPEAKER → STATUS flag SPEAKER_OK

// Feed one write of the AUDIO_OUT characteristic (opcode 0x20..0x23 + payload). BLE-task context.
void audio_out_on_packet(const uint8_t *data, size_t len);

void audio_out_tick();                                   // from loop(): decode + feed I2S, emit events
void audio_out_stop();                                   // request a flush (ABORT / disconnect; any task). The next
                                                         // audio_out_tick() stops the stream → AUDIO_DONE(1) if one was active
bool audio_out_active();                                 // a stream is in progress (not Idle)
AudioOutState audio_out_state();
size_t audio_out_queued();                               // blocks waiting in the queue

// Sink for AUDIO_UNDERRUN / AUDIO_DONE events; invoked from loop() context only (audio_out_tick).
void audio_out_on_event(std::function<void(uint8_t ev, uint8_t arg)> h);

// Call before deep sleep: stops playback, releases the driver, parks the I2S lines and the amp enable low.
void audio_out_sleep_prepare();
