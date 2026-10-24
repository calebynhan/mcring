#pragma once
#include <stdint.h>
#include <stddef.h>
#include <functional>

namespace ble {

using BytesHandler = std::function<void(const uint8_t *data, size_t len)>;
using ConnHandler  = std::function<void(bool connected)>;

void init(const char *base_name);
bool connected();
uint16_t mtu();                 // negotiated ATT MTU (23 until exchanged)
bool data_subscribed();         // phone subscribed to transfer-data notifications
bool status_subscribed();

// Notify helpers return false if not connected / not subscribed / queue full (after retries).
bool notify_status(const uint8_t *buf, size_t len);
bool notify_meta(const uint8_t *buf, size_t len);
bool notify_data(const uint8_t *buf, size_t len);

// Flow control: number of notifications we may still push before the stack back-pressures us.
int  tx_credits();
void set_tx_credits_max(int n);

// Ask the central for fast (transfer) or relaxed (idle) connection parameters.
void request_fast_params();
void request_slow_params();

void on_control(BytesHandler h);
void on_feedback(BytesHandler h);
void on_connection(ConnHandler h);

void tick();  // call from loop(): handles advertising restart, credit timeouts
}
