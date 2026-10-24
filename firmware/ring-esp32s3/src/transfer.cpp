#include "transfer.h"
#include "ble_link.h"
#include "config.h"
#include "log.h"
#include "mcring_proto.h"
#include <Arduino.h>
#include <vector>

static const char *TAG = "xfer";

namespace {

transfer::Item g_queue[MAX_QUEUED_CAPTURES];
size_t   g_qlen = 0;

transfer::State g_state = transfer::State::Idle;
uint16_t g_xfer_id = 0;
uint16_t g_chunk_len = 0;
uint16_t g_n_chunks = 0;
uint32_t g_crc = 0;
std::vector<uint16_t> g_pending;   // chunk indices still to send this round
size_t   g_pending_pos = 0;
uint32_t g_end_sent_ms = 0;
uint8_t  g_rounds = 0;
uint8_t  g_last_err = MC_ERR_NONE;
uint8_t  g_pkt[517];

void pop_front() {
  if (g_qlen == 0) return;
  free(g_queue[0].data);
  for (size_t i = 1; i < g_qlen; i++) g_queue[i - 1] = g_queue[i];
  g_qlen--;
}

bool send_start() {
  const transfer::Item &it = g_queue[0];
  g_chunk_len = mc_chunk_len_for_mtu(ble::mtu());
  g_n_chunks = (uint16_t)((it.len + g_chunk_len - 1) / g_chunk_len);
  g_crc = mc_crc32(it.data, it.len);
  mc_xfer_start_t s = {};
  s.type = it.type; s.xfer_id = g_xfer_id; s.total_len = (uint32_t)it.len;
  s.chunk_len = g_chunk_len; s.n_chunks = g_n_chunks; s.crc32 = g_crc;
  s.width = it.width; s.height = it.height; s.seq_flags = it.flags;
  uint8_t buf[20];
  mc_encode_xfer_start(&s, buf);
  LOGI(TAG, "START id=%u type=%u len=%u chunks=%u x %u", g_xfer_id, it.type, (unsigned)it.len, g_n_chunks, g_chunk_len);
  return ble::notify_meta(buf, sizeof buf);
}

bool send_chunk(uint16_t idx) {
  const transfer::Item &it = g_queue[0];
  size_t off = (size_t)idx * g_chunk_len;
  if (off >= it.len) return true;
  size_t n = it.len - off;
  if (n > g_chunk_len) n = g_chunk_len;
  mc_put_u16(g_pkt, g_xfer_id);
  mc_put_u16(g_pkt + 2, idx);
  memcpy(g_pkt + 4, it.data + off, n);
  return ble::notify_data(g_pkt, n + 4);
}

bool send_end() {
  uint8_t buf[3];
  mc_encode_xfer_end(g_xfer_id, buf);
  g_end_sent_ms = millis();
  return ble::notify_meta(buf, sizeof buf);
}

void begin_round_all() {
  g_pending.clear();
  g_pending.reserve(g_n_chunks);
  for (uint16_t i = 0; i < g_n_chunks; i++) g_pending.push_back(i);
  g_pending_pos = 0;
}

void start_current() {
  g_xfer_id++;
  g_rounds = 0;
  if (!send_start()) { LOGW(TAG, "START notify failed"); return; }
  begin_round_all();
  g_state = transfer::State::Sending;
  ble::request_fast_params();
}

}  // namespace

namespace transfer {

bool enqueue(const Item &item) {
  if (g_qlen >= MAX_QUEUED_CAPTURES) {
    // Drop the oldest *unsent* item to make room (keep the one in flight if any).
    size_t victim = (g_state == State::Idle) ? 0 : 1;
    if (victim >= g_qlen) return false;
    free(g_queue[victim].data);
    for (size_t i = victim + 1; i < g_qlen; i++) g_queue[i - 1] = g_queue[i];
    g_qlen--;
    LOGW(TAG, "queue full, dropped an older capture");
  }
  g_queue[g_qlen++] = item;
  return true;
}

size_t queued() { return g_qlen; }
bool busy() { return g_state == State::Sending || g_state == State::WaitAck; }
State state() { return g_state; }
uint8_t last_error() { return g_last_err; }

void on_ack(const uint8_t *p, size_t len) {
  if (len < 5) return;
  uint16_t id = mc_get_u16(p);
  uint8_t status = p[2];
  uint16_t n_missing = mc_get_u16(p + 3);
  if (id != g_xfer_id) { LOGW(TAG, "ACK for stale id %u (current %u)", id, g_xfer_id); return; }
  if (g_state != State::WaitAck && g_state != State::Sending) return;

  if (status == 0) {
    LOGI(TAG, "ACK complete id=%u (%u rounds)", id, g_rounds + 1);
    pop_front();
    g_state = State::Idle;
    g_last_err = MC_ERR_NONE;
    if (g_qlen == 0) ble::request_slow_params();
    return;
  }
  if (status == 2) { LOGW(TAG, "phone aborted id=%u", id); pop_front(); g_state = State::Idle; return; }

  // status 1: resend the listed chunks
  if (len < 5u + 2u * n_missing) n_missing = (uint16_t)((len - 5) / 2);
  g_pending.clear();
  for (uint16_t i = 0; i < n_missing; i++) {
    uint16_t idx = mc_get_u16(p + 5 + 2 * i);
    if (idx < g_n_chunks) g_pending.push_back(idx);
  }
  g_pending_pos = 0;
  g_rounds++;
  if (g_rounds >= TRANSFER_MAX_ROUNDS) {
    LOGE(TAG, "too many retransmit rounds, giving up id=%u", id);
    g_last_err = MC_ERR_TRANSFER_TIMEOUT;
    pop_front();
    g_state = State::Idle;
    return;
  }
  LOGI(TAG, "resend %u chunks (round %u)", (unsigned)g_pending.size(), g_rounds + 1);
  g_state = State::Sending;
}

void abort_all() {
  while (g_qlen) pop_front();
  g_pending.clear();
  g_state = State::Idle;
}

void on_disconnect() {
  // Keep the buffers; restart from START on reconnect.
  g_pending.clear();
  g_state = State::Idle;
}

void tick() {
  if (!ble::connected() || !ble::data_subscribed()) return;

  switch (g_state) {
    case State::Idle:
    case State::Done:
    case State::Failed:
      if (g_qlen > 0) start_current();
      break;

    case State::Sending: {
      // Send chunks for up to ~15 ms per loop iteration so other tasks keep running.
      uint32_t t0 = millis();
      while (g_pending_pos < g_pending.size() && millis() - t0 < 15) {
        if (!send_chunk(g_pending[g_pending_pos])) {
          if (!ble::connected()) { on_disconnect(); return; }
          break;   // back-pressure; try again next tick
        }
        g_pending_pos++;
      }
      if (g_pending_pos >= g_pending.size()) {
        send_end();
        g_state = State::WaitAck;
      }
      break;
    }

    case State::WaitAck:
      if (millis() - g_end_sent_ms > TRANSFER_ACK_TIMEOUT_MS) {
        g_rounds++;
        if (g_rounds >= TRANSFER_MAX_ROUNDS) {
          LOGE(TAG, "no ACK, giving up id=%u", g_xfer_id);
          g_last_err = MC_ERR_TRANSFER_TIMEOUT;
          pop_front();
          g_state = State::Idle;
        } else {
          LOGW(TAG, "no ACK, resending END (round %u)", g_rounds + 1);
          send_end();
        }
      }
      break;
  }
}

}  // namespace transfer
