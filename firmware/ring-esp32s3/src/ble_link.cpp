/*
 * BLE GATT server for the mcring protocol, on NimBLE-Arduino 2.x.
 * One connection, notifications for ring->phone, writes for phone->ring.
 */
#include "ble_link.h"
#include "config.h"
#include "log.h"
#include "mcring_proto.h"
#include <Arduino.h>
#include <NimBLEDevice.h>

static const char *TAG = "ble";

namespace {

NimBLEServer         *g_server = nullptr;
NimBLECharacteristic *g_ctrl = nullptr, *g_status = nullptr, *g_meta = nullptr, *g_data = nullptr, *g_fb = nullptr;
volatile bool  g_connected = false;
volatile uint16_t g_mtu = 23;
volatile uint16_t g_conn_handle = 0xFFFF;
volatile bool  g_data_sub = false, g_status_sub = false;
volatile int   g_credits = 0;
int            g_credits_max = 6;
uint32_t       g_last_tx_ms = 0;
bool           g_need_adv = true;

ble::BytesHandler g_on_ctrl, g_on_fb;
ble::ConnHandler  g_on_conn;

class ServerCB : public NimBLEServerCallbacks {
  void onConnect(NimBLEServer *s, NimBLEConnInfo &ci) override {
    g_connected = true;
    g_conn_handle = ci.getConnHandle();
    g_mtu = 23;
    g_credits = g_credits_max;
    LOGI(TAG, "connected %s", ci.getAddress().toString().c_str());
    // Ask for a quick link while the phone is likely to request a transfer soon.
    s->updateConnParams(ci.getConnHandle(), 12, 24, 0, 400);   // 15-30 ms, latency 0, 4 s timeout
#if defined(BLE_GAP_LE_PHY_2M_MASK)
    s->updatePhy(ci.getConnHandle(), BLE_GAP_LE_PHY_2M_MASK, BLE_GAP_LE_PHY_2M_MASK, 0);
#endif
    s->setDataLen(ci.getConnHandle(), 251);
    if (g_on_conn) g_on_conn(true);
  }
  void onDisconnect(NimBLEServer *, NimBLEConnInfo &, int reason) override {
    g_connected = false;
    g_data_sub = g_status_sub = false;
    g_conn_handle = 0xFFFF;
    g_need_adv = true;
    LOGI(TAG, "disconnected (reason 0x%x)", reason);
    if (g_on_conn) g_on_conn(false);
  }
  void onMTUChange(uint16_t mtu, NimBLEConnInfo &) override {
    g_mtu = mtu;
    LOGI(TAG, "MTU %u -> chunk %u", mtu, mc_chunk_len_for_mtu(mtu));
  }
};

class CtrlCB : public NimBLECharacteristicCallbacks {
  void onWrite(NimBLECharacteristic *c, NimBLEConnInfo &) override {
    NimBLEAttValue v = c->getValue();
    if (g_on_ctrl && v.size()) g_on_ctrl(v.data(), v.size());
  }
};

class FbCB : public NimBLECharacteristicCallbacks {
  void onWrite(NimBLECharacteristic *c, NimBLEConnInfo &) override {
    NimBLEAttValue v = c->getValue();
    if (g_on_fb && v.size()) g_on_fb(v.data(), v.size());
  }
};

class NotifyCB : public NimBLECharacteristicCallbacks {
  void onSubscribe(NimBLECharacteristic *c, NimBLEConnInfo &, uint16_t subValue) override {
    bool on = (subValue & 0x0001) != 0;
    if (c == g_data) g_data_sub = on;
    if (c == g_status) g_status_sub = on;
    LOGI(TAG, "subscribe %s -> %d", c->getUUID().toString().c_str(), on);
  }
  // Called when a notification has been transmitted; use it as a TX credit.
  void onStatus(NimBLECharacteristic *, int) override {
    if (g_credits < g_credits_max) g_credits = g_credits + 1;
  }
};

ServerCB  g_server_cb;
CtrlCB    g_ctrl_cb;
FbCB      g_fb_cb;
NotifyCB  g_notify_cb;

bool do_notify(NimBLECharacteristic *c, const uint8_t *buf, size_t len) {
  if (!g_connected || !c) return false;
  // Wait for a credit (bounded). Credits replenish on TX-complete; if the stack never
  // reports (older NimBLE), the timeout below replenishes them so we never deadlock.
  uint32_t t0 = millis();
  while (g_credits <= 0) {
    if (millis() - t0 > 50) { g_credits = g_credits_max; break; }
    delay(1);
  }
  for (int attempt = 0; attempt < 40; attempt++) {
    c->setValue(buf, len);
    if (c->notify()) {
      g_credits = g_credits - 1;
      g_last_tx_ms = millis();
      return true;
    }
    if (!g_connected) return false;
    delay(2);   // controller buffers full; back off briefly
  }
  LOGW(TAG, "notify dropped after retries");
  return false;
}

}  // namespace

namespace ble {

void init(const char *base_name) {
  NimBLEDevice::init("");
  NimBLEDevice::setMTU(517);
  NimBLEDevice::setPower(ESP_PWR_LVL_P6);   // +6 dBm; ring antennas are poor
  NimBLEDevice::setSecurityAuth(false, false, true);

  // Name with the last two MAC bytes so several rings can coexist.
  std::string mac = NimBLEDevice::getAddress().toString();   // "aa:bb:cc:dd:ee:ff"
  char name[24];
  snprintf(name, sizeof name, "%s-%c%c%c%c", base_name, mac[12], mac[13], mac[15], mac[16]);
  NimBLEDevice::setDeviceName(name);

  g_server = NimBLEDevice::createServer();
  g_server->setCallbacks(&g_server_cb);
  g_server->advertiseOnDisconnect(false);   // we restart advertising from tick()

  NimBLEService *svc = g_server->createService(MCRING_UUID_SERVICE);
  g_ctrl   = svc->createCharacteristic(MCRING_UUID_CONTROL,   NIMBLE_PROPERTY::WRITE | NIMBLE_PROPERTY::WRITE_NR);
  g_status = svc->createCharacteristic(MCRING_UUID_STATUS,    NIMBLE_PROPERTY::READ | NIMBLE_PROPERTY::NOTIFY);
  g_meta   = svc->createCharacteristic(MCRING_UUID_XFER_META, NIMBLE_PROPERTY::NOTIFY);
  g_data   = svc->createCharacteristic(MCRING_UUID_XFER_DATA, NIMBLE_PROPERTY::NOTIFY, 517);
  g_fb     = svc->createCharacteristic(MCRING_UUID_FEEDBACK,  NIMBLE_PROPERTY::WRITE | NIMBLE_PROPERTY::WRITE_NR, 517);
  g_ctrl->setCallbacks(&g_ctrl_cb);
  g_fb->setCallbacks(&g_fb_cb);
  g_status->setCallbacks(&g_notify_cb);
  g_meta->setCallbacks(&g_notify_cb);
  g_data->setCallbacks(&g_notify_cb);
  svc->start();

  NimBLEAdvertising *adv = NimBLEDevice::getAdvertising();
  adv->addServiceUUID(MCRING_UUID_SERVICE);
  adv->setName(name);
  adv->enableScanResponse(true);
  adv->setMinInterval(160);   // 100 ms
  adv->setMaxInterval(400);   // 250 ms
  g_need_adv = true;
  LOGI(TAG, "advertising as %s", name);
}

bool connected() { return g_connected; }
uint16_t mtu() { return g_mtu; }
bool data_subscribed() { return g_data_sub; }
bool status_subscribed() { return g_status_sub; }
int  tx_credits() { return g_credits; }
void set_tx_credits_max(int n) { g_credits_max = n < 1 ? 1 : n; }

bool notify_status(const uint8_t *buf, size_t len) {
  if (!g_status) return false;
  g_status->setValue(buf, len);          // readable even without subscription
  if (!g_connected || !g_status_sub) return false;
  return g_status->notify();
}
bool notify_meta(const uint8_t *buf, size_t len) { return do_notify(g_meta, buf, len); }
bool notify_data(const uint8_t *buf, size_t len) { return do_notify(g_data, buf, len); }

void request_fast_params() {
  if (g_server && g_connected) g_server->updateConnParams(g_conn_handle, 12, 24, 0, 400);
}
void request_slow_params() {
  if (g_server && g_connected) g_server->updateConnParams(g_conn_handle, 160, 320, 2, 600);  // 200-400 ms, latency 2
}

void on_control(BytesHandler h) { g_on_ctrl = std::move(h); }
void on_feedback(BytesHandler h) { g_on_fb = std::move(h); }
void on_connection(ConnHandler h) { g_on_conn = std::move(h); }

void tick() {
  if (g_need_adv && !g_connected) {
    NimBLEDevice::getAdvertising()->start();
    g_need_adv = false;
  }
}

}  // namespace ble
