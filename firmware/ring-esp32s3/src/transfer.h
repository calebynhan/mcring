#pragma once
#include <stdint.h>
#include <stddef.h>

// Reliable chunked transfer of a buffer over the meta/data characteristics (protocol/ble-gatt.md).
namespace transfer {

enum class State : uint8_t { Idle, Sending, WaitAck, Done, Failed };

struct Item {
  uint8_t *data;
  size_t   len;
  uint8_t  type;       // MC_XFER_JPEG / MC_XFER_ADPCM
  uint16_t width;
  uint16_t height;
  uint8_t  flags;      // seq_flags (bit0: triggered on ring)
};

// Enqueue a buffer (takes ownership; freed after successful ACK or abort). Returns false if full.
bool enqueue(const Item &item);
size_t queued();
bool busy();
State state();

void on_ack(const uint8_t *payload, size_t len);   // ACK_TRANSFER payload (after opcode)
void abort_all();
void on_disconnect();
void tick();                                        // drive the state machine from loop()
uint8_t last_error();
}
