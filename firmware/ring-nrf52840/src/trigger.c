#include "trigger.h"
#include <zephyr/kernel.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/logging/log.h>

LOG_MODULE_REGISTER(mc_trig, LOG_LEVEL_INF);

#if DT_NODE_EXISTS(DT_ALIAS(mcring_button))
static const struct gpio_dt_spec btn = GPIO_DT_SPEC_GET(DT_ALIAS(mcring_button), gpios);
#elif DT_NODE_EXISTS(DT_ALIAS(sw0))
static const struct gpio_dt_spec btn = GPIO_DT_SPEC_GET(DT_ALIAS(sw0), gpios);
#else
#error "no button alias (mcring-button or sw0) in the board / overlay"
#endif
#if DT_NODE_EXISTS(DT_ALIAS(mcring_imu_int))
static const struct gpio_dt_spec imu = GPIO_DT_SPEC_GET(DT_ALIAS(mcring_imu_int), gpios);
#define HAVE_IMU 1
#else
#define HAVE_IMU 0
#endif

static struct gpio_callback btn_cb, imu_cb;
static K_SEM_DEFINE(trig_sem, 0, 4);

static void on_btn(const struct device *d, struct gpio_callback *cb, uint32_t pins) { k_sem_give(&trig_sem); }
static void on_imu(const struct device *d, struct gpio_callback *cb, uint32_t pins) { k_sem_give(&trig_sem); }

int trigger_init(void) {
  if (!device_is_ready(btn.port)) return -ENODEV;
  gpio_pin_configure_dt(&btn, GPIO_INPUT);
  gpio_pin_interrupt_configure_dt(&btn, GPIO_INT_EDGE_TO_ACTIVE);
  gpio_init_callback(&btn_cb, on_btn, BIT(btn.pin));
  gpio_add_callback(btn.port, &btn_cb);
#if HAVE_IMU
  if (device_is_ready(imu.port)) {
    gpio_pin_configure_dt(&imu, GPIO_INPUT);
    gpio_pin_interrupt_configure_dt(&imu, GPIO_INT_EDGE_TO_ACTIVE);
    gpio_init_callback(&imu_cb, on_imu, BIT(imu.pin));
    gpio_add_callback(imu.port, &imu_cb);
    /* LIS2DW12 double-tap configuration is done by the Zephyr st,lis2dw12 driver via its
     * sensor API (SENSOR_TRIG_DOUBLE_TAP) — wire it here when the sensor node is enabled. */
  }
#endif
  return 0;
}

bool trigger_poll_capture(void) {
  if (k_sem_take(&trig_sem, K_NO_WAIT) != 0) return false;
  static int64_t last;
  int64_t now = k_uptime_get();
  if (now - last < 300) return false;   /* debounce / tap burst */
  last = now;
  return true;
}
