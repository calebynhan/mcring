/* mcring GATT service on Zephyr Bluetooth. Same UUIDs/packets as the ESP32 build. */
#include "ble_svc.h"
#include "mcring_proto.h"
#include <zephyr/kernel.h>
#include <zephyr/bluetooth/bluetooth.h>
#include <zephyr/bluetooth/conn.h>
#include <zephyr/bluetooth/gatt.h>
#include <zephyr/bluetooth/uuid.h>
#include <zephyr/logging/log.h>

LOG_MODULE_REGISTER(mc_ble, LOG_LEVEL_INF);

/* 7a3bXXXX-9c2e-4f3a-b1d4-6d6372696e67 */
#define MC_UUID(x) BT_UUID_128_ENCODE(0x7a3b0000u | (x), 0x9c2e, 0x4f3a, 0xb1d4, 0x6d6372696e67ULL)
static struct bt_uuid_128 uuid_svc   = BT_UUID_INIT_128(MC_UUID(1));
static struct bt_uuid_128 uuid_ctrl  = BT_UUID_INIT_128(MC_UUID(2));
static struct bt_uuid_128 uuid_stat  = BT_UUID_INIT_128(MC_UUID(3));
static struct bt_uuid_128 uuid_meta  = BT_UUID_INIT_128(MC_UUID(4));
static struct bt_uuid_128 uuid_data  = BT_UUID_INIT_128(MC_UUID(5));
static struct bt_uuid_128 uuid_fb    = BT_UUID_INIT_128(MC_UUID(6));

static struct bt_conn *g_conn;
static bool g_data_sub, g_stat_sub;
static uint8_t g_status_val[12];
static mc_bytes_cb_t g_on_ctrl, g_on_fb;
static mc_conn_cb_t g_on_conn;

static ssize_t on_write_ctrl(struct bt_conn *c, const struct bt_gatt_attr *a, const void *buf, uint16_t len, uint16_t off, uint8_t flags) {
  if (g_on_ctrl && len) g_on_ctrl(buf, len);
  return len;
}
static ssize_t on_write_fb(struct bt_conn *c, const struct bt_gatt_attr *a, const void *buf, uint16_t len, uint16_t off, uint8_t flags) {
  if (g_on_fb && len) g_on_fb(buf, len);
  return len;
}
static ssize_t on_read_status(struct bt_conn *c, const struct bt_gatt_attr *a, void *buf, uint16_t len, uint16_t off) {
  return bt_gatt_attr_read(c, a, buf, len, off, g_status_val, sizeof g_status_val);
}
static void ccc_data(const struct bt_gatt_attr *a, uint16_t v) { g_data_sub = v == BT_GATT_CCC_NOTIFY; }
static void ccc_stat(const struct bt_gatt_attr *a, uint16_t v) { g_stat_sub = v == BT_GATT_CCC_NOTIFY; }
static void ccc_meta(const struct bt_gatt_attr *a, uint16_t v) { ARG_UNUSED(a); ARG_UNUSED(v); }

BT_GATT_SERVICE_DEFINE(mc_svc,
  BT_GATT_PRIMARY_SERVICE(&uuid_svc),
  BT_GATT_CHARACTERISTIC(&uuid_ctrl.uuid, BT_GATT_CHRC_WRITE | BT_GATT_CHRC_WRITE_WITHOUT_RESP, BT_GATT_PERM_WRITE, NULL, on_write_ctrl, NULL),
  BT_GATT_CHARACTERISTIC(&uuid_stat.uuid, BT_GATT_CHRC_READ | BT_GATT_CHRC_NOTIFY, BT_GATT_PERM_READ, on_read_status, NULL, NULL),
  BT_GATT_CCC(ccc_stat, BT_GATT_PERM_READ | BT_GATT_PERM_WRITE),
  BT_GATT_CHARACTERISTIC(&uuid_meta.uuid, BT_GATT_CHRC_NOTIFY, BT_GATT_PERM_NONE, NULL, NULL, NULL),
  BT_GATT_CCC(ccc_meta, BT_GATT_PERM_READ | BT_GATT_PERM_WRITE),
  BT_GATT_CHARACTERISTIC(&uuid_data.uuid, BT_GATT_CHRC_NOTIFY, BT_GATT_PERM_NONE, NULL, NULL, NULL),
  BT_GATT_CCC(ccc_data, BT_GATT_PERM_READ | BT_GATT_PERM_WRITE),
  BT_GATT_CHARACTERISTIC(&uuid_fb.uuid, BT_GATT_CHRC_WRITE | BT_GATT_CHRC_WRITE_WITHOUT_RESP, BT_GATT_PERM_WRITE, NULL, on_write_fb, NULL),
);
/* attribute indices: 0 svc, 1-2 ctrl, 3-4 status, 5 ccc, 6-7 meta, 8 ccc, 9-10 data, 11 ccc, 12-13 fb */
#define ATTR_STATUS (&mc_svc.attrs[4])
#define ATTR_META   (&mc_svc.attrs[7])
#define ATTR_DATA   (&mc_svc.attrs[10])

static const struct bt_data ad[] = {
  BT_DATA_BYTES(BT_DATA_FLAGS, BT_LE_AD_GENERAL | BT_LE_AD_NO_BREDR),
  BT_DATA_BYTES(BT_DATA_UUID128_ALL, MC_UUID(1)),
};
static const struct bt_data sd[] = { BT_DATA(BT_DATA_NAME_COMPLETE, CONFIG_BT_DEVICE_NAME, sizeof(CONFIG_BT_DEVICE_NAME) - 1) };

static void start_adv(void) {
  int err = bt_le_adv_start(BT_LE_ADV_CONN, ad, ARRAY_SIZE(ad), sd, ARRAY_SIZE(sd));
  if (err) LOG_ERR("adv start failed (%d)", err);
}

static void connected(struct bt_conn *conn, uint8_t err) {
  if (err) return;
  g_conn = bt_conn_ref(conn);
  LOG_INF("connected");
  /* Fast link for transfers; 2M PHY; DLE */
  static const struct bt_le_conn_param fast = BT_LE_CONN_PARAM_INIT(12, 24, 0, 400);
  bt_conn_le_param_update(conn, &fast);
  static const struct bt_conn_le_phy_param phy = BT_CONN_LE_PHY_PARAM_INIT(BT_GAP_LE_PHY_2M, BT_GAP_LE_PHY_2M);
  bt_conn_le_phy_update(conn, &phy);
  static const struct bt_conn_le_data_len_param dl = BT_LE_DATA_LEN_PARAM_MAX;
  bt_conn_le_data_len_update(conn, &dl);
  if (g_on_conn) g_on_conn(true);
}
static void disconnected(struct bt_conn *conn, uint8_t reason) {
  LOG_INF("disconnected (0x%02x)", reason);
  if (g_conn) { bt_conn_unref(g_conn); g_conn = NULL; }
  g_data_sub = g_stat_sub = false;
  if (g_on_conn) g_on_conn(false);
  start_adv();
}
BT_CONN_CB_DEFINE(conn_cbs) = { .connected = connected, .disconnected = disconnected };

int ble_svc_init(mc_bytes_cb_t on_control, mc_bytes_cb_t on_feedback, mc_conn_cb_t on_conn) {
  g_on_ctrl = on_control; g_on_fb = on_feedback; g_on_conn = on_conn;
  int err = bt_enable(NULL);
  if (err) { LOG_ERR("bt_enable %d", err); return err; }
  /* name suffix from the address */
  bt_addr_le_t addrs[1]; size_t n = 1;
  bt_id_get(addrs, &n);
  char name[24];
  snprintk(name, sizeof name, "mcring-%02X%02X", addrs[0].a.val[1], addrs[0].a.val[0]);
  bt_set_name(name);
  start_adv();
  LOG_INF("advertising as %s", name);
  return 0;
}

bool ble_svc_connected(void) { return g_conn != NULL; }
bool ble_svc_data_subscribed(void) { return g_data_sub; }
uint16_t ble_svc_mtu(void) { return g_conn ? bt_gatt_get_mtu(g_conn) : 23; }

int ble_svc_notify_status(const uint8_t *buf, size_t len) {
  memcpy(g_status_val, buf, MIN(len, sizeof g_status_val));
  if (!g_conn || !g_stat_sub) return -ENOTCONN;
  return bt_gatt_notify(g_conn, ATTR_STATUS, buf, len);
}
int ble_svc_notify_meta(const uint8_t *buf, size_t len) {
  if (!g_conn) return -ENOTCONN;
  return bt_gatt_notify(g_conn, ATTR_META, buf, len);
}
int ble_svc_notify_data(const uint8_t *buf, size_t len) {
  if (!g_conn) return -ENOTCONN;
  return bt_gatt_notify(g_conn, ATTR_DATA, buf, len);   /* -ENOMEM when out of TX buffers → caller retries */
}
void ble_svc_request_fast(void) {
  if (!g_conn) return;
  static const struct bt_le_conn_param p = BT_LE_CONN_PARAM_INIT(12, 24, 0, 400);
  bt_conn_le_param_update(g_conn, &p);
}
void ble_svc_request_slow(void) {
  if (!g_conn) return;
  static const struct bt_le_conn_param p = BT_LE_CONN_PARAM_INIT(160, 320, 2, 600);
  bt_conn_le_param_update(g_conn, &p);
}
