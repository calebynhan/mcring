# mcring firmware — nRF52840 / Zephyr (stage 2 skeleton)

The research in `docs/research/02-mcu-radio-power.md` is unambiguous: an ESP32-S3 cannot live on
a 16–24 mAh ring cell (300 mA capture peaks on a 1C cell, <2-day standby with BLE alive). An
nRF52840-class SoC can. This directory is the start of that port.

**What is here and works as a protocol peer:** the full mcring GATT service (same UUIDs and
packets as the ESP32 build), the reliable chunked transfer with retransmit, the Morse/pattern
player (LED + DRV2605 RTP), button/IMU trigger, and the shared C libraries from
`../ring-esp32s3/lib`. Flash it on a **Seeed XIAO nRF52840 Sense** and the phone app / desktop
CLI will connect and receive a (synthetic) frame.

**What is a stub:** `src/camera_hal.c`. The nRF52840 has no camera peripheral; the capture
has to be bit-banged (OV7670/OV7675 8-bit DVP, proven on this chip by `Arduino_OV767X`) or
clocked through SPIS/PPI (HM01B0 1-bit mode, unproven). It currently returns a synthetic
160×120 grayscale frame wrapped as PGM so the pipeline can be exercised. A baseline JPEG
encoder (jo_jpeg / TinyJPEG class) must be added before real captures go over BLE.

```bash
# nRF Connect SDK v2.7+ / Zephyr 3.6+
west build -b xiao_ble -p auto firmware/ring-nrf52840 && west flash
```

Not built in this repository's CI yet (needs the Zephyr SDK). Treat it as reviewed-but-uncompiled.
