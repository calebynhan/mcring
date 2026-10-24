/* Same algorithm as firmware/ring-esp32s3/src/transfer.cpp, in C on Zephyr. */
#include "transfer.h"
#include "ble_svc.h"
#include "mcring_cfg.h"
#include "mcring_proto.h"
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <string.h>

LOG_MODULE_REGISTER(mc_xfer, LOG_LEVEL_INF);

enum { ST_IDLE, ST_SENDING, ST_WAIT_ACK };

static xfer_item_t q[MAX_QUEUED_CAPTURES];
static size_t qlen;
static int state = ST_IDLE;
static uint16_t xfer_id, chunk_len, n_chunks;
static uint16_t pending[2048];
static size_t pending_n, pending_pos;
static int64_t end_sent_ms;
static uint8_t rounds, last_err;
static uint8_t pkt[517];

static void pop_front(void) {
  if (!qlen) return;
  k_free(q[0].data);
  for (size_t i = 1; i < qlen; i++) q[i - 1] = q[i];
  qlen--;
}

static int send_start(void) {
  const xfer_item_t *it = &q[0];
  chunk_len = mc_chunk_len_for_mtu(ble_svc_mtu());
  n_chunks = (it->len + chunk_len - 1) / chunk_len;
  mc_xfer_start_t s = { .type = it->type, .xfer_id = xfer_id, .total_len = it->len, .chunk_len = chunk_len,
                        .n_chunks = n_chunks, .crc32 = mc_crc32(it->data, it->len), .width = it->width,
                        .height = it->height, .seq_flags = it->flags };
  uint8_t b[20]; mc_encode_xfer_start(&s, b);
  LOG_INF("START id=%u len=%u chunks=%u x %u", xfer_id, (unsigned)it->len, n_chunks, chunk_len);
  return ble_svc_notify_meta(b, sizeof b);
}

static int send_chunk(uint16_t idx) {
  const xfer_item_t *it = &q[0];
  size_t off = (size_t)idx * chunk_len;
  if (off >= it->len) return 0;
  size_t n = MIN(it->len - off, (size_t)chunk_len);
  mc_put_u16(pkt, xfer_id); mc_put_u16(pkt + 2, idx);
  memcpy(pkt + 4, it->data + off, n);
  return ble_svc_notify_data(pkt, n + 4);
}

static void send_end(void) {
  uint8_t b[3]; mc_encode_xfer_end(xfer_id, b);
  end_sent_ms = k_uptime_get();
  ble_svc_notify_meta(b, sizeof b);
}

static void start_current(void) {
  xfer_id++; rounds = 0;
  if (send_start() < 0) return;
  pending_n = MIN(n_chunks, (uint16_t)ARRAY_SIZE(pending));
  for (uint16_t i = 0; i < pending_n; i++) pending[i] = i;
  pending_pos = 0;
  state = ST_SENDING;
  ble_svc_request_fast();
}

bool transfer_enqueue(const xfer_item_t *it) {
  if (qlen >= MAX_QUEUED_CAPTURES) {
    size_t victim = state == ST_IDLE ? 0 : 1;
    if (victim >= qlen) return false;
    k_free(q[victim].data);
    for (size_t i = victim + 1; i < qlen; i++) q[i - 1] = q[i];
    qlen--;
  }
  q[qlen++] = *it;
  return true;
}
size_t transfer_queued(void) { return qlen; }
bool transfer_busy(void) { return state != ST_IDLE; }
uint8_t transfer_last_error(void) { return last_err; }

void transfer_on_ack(const uint8_t *p, size_t len) {
  if (len < 5) return;
  uint16_t id = mc_get_u16(p); uint8_t status = p[2]; uint16_t nm = mc_get_u16(p + 3);
  if (id != xfer_id || state == ST_IDLE) return;
  if (status == 0) { LOG_INF("ACK ok id=%u", id); pop_front(); state = ST_IDLE; last_err = 0; if (!qlen) ble_svc_request_slow(); return; }
  if (status == 2) { pop_front(); state = ST_IDLE; return; }
  if (len < 5u + 2u * nm) nm = (len - 5) / 2;
  pending_n = 0;
  for (uint16_t i = 0; i < nm && pending_n < ARRAY_SIZE(pending); i++) {
    uint16_t idx = mc_get_u16(p + 5 + 2 * i);
    if (idx < n_chunks) pending[pending_n++] = idx;
  }
  pending_pos = 0;
  if (++rounds >= TRANSFER_MAX_ROUNDS) { last_err = MC_ERR_TRANSFER_TIMEOUT; pop_front(); state = ST_IDLE; return; }
  state = ST_SENDING;
}

void transfer_on_disconnect(void) { state = ST_IDLE; }
void transfer_abort_all(void) { while (qlen) pop_front(); state = ST_IDLE; }

void transfer_tick(void) {
  if (!ble_svc_connected() || !ble_svc_data_subscribed()) return;
  switch (state) {
  case ST_IDLE:
    if (qlen) start_current();
    break;
  case ST_SENDING: {
    int64_t t0 = k_uptime_get();
    while (pending_pos < pending_n && k_uptime_get() - t0 < 15) {
      int rc = send_chunk(pending[pending_pos]);
      if (rc == -ENOMEM || rc == -EAGAIN) { k_sleep(K_MSEC(2)); break; }   /* TX pool full */
      if (rc < 0) { if (!ble_svc_connected()) { transfer_on_disconnect(); return; } break; }
      pending_pos++;
    }
    if (pending_pos >= pending_n) { send_end(); state = ST_WAIT_ACK; }
    break;
  }
  case ST_WAIT_ACK:
    if (k_uptime_get() - end_sent_ms > TRANSFER_ACK_TIMEOUT_MS) {
      if (++rounds >= TRANSFER_MAX_ROUNDS) { last_err = MC_ERR_TRANSFER_TIMEOUT; pop_front(); state = ST_IDLE; }
      else send_end();
    }
    break;
  }
}
