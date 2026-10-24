#pragma once
#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>

typedef struct { uint8_t *data; size_t len; uint8_t type; uint16_t width, height; uint8_t flags; } xfer_item_t;

bool   transfer_enqueue(const xfer_item_t *it);   /* takes ownership of data (k_free'd when done) */
size_t transfer_queued(void);
bool   transfer_busy(void);
void   transfer_on_ack(const uint8_t *payload, size_t len);
void   transfer_on_disconnect(void);
void   transfer_abort_all(void);
void   transfer_tick(void);
uint8_t transfer_last_error(void);
