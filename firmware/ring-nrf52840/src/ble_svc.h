#pragma once
#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>

typedef void (*mc_bytes_cb_t)(const uint8_t *data, size_t len);
typedef void (*mc_conn_cb_t)(bool connected);

int  ble_svc_init(mc_bytes_cb_t on_control, mc_bytes_cb_t on_feedback, mc_conn_cb_t on_conn);
bool ble_svc_connected(void);
bool ble_svc_data_subscribed(void);
uint16_t ble_svc_mtu(void);
int  ble_svc_notify_status(const uint8_t *buf, size_t len);
int  ble_svc_notify_meta(const uint8_t *buf, size_t len);
int  ble_svc_notify_data(const uint8_t *buf, size_t len);   /* returns -EAGAIN when the TX pool is full */
void ble_svc_request_fast(void);
void ble_svc_request_slow(void);
