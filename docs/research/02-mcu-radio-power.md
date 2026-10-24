# Research report 2 — MCU + radio, BLE throughput, power and batteries

> Automated research pass from web-search snippets (datasheet/teardown fetches were blocked by
> the sandbox). Prices are dated snapshots; re-check before ordering. Nothing here is an
> invented part number; "not found" means exactly that.

## 0. Executive summary

- **The ring form factor is decided by the battery and by peak current, not by MCU footprint.** Shipping rings carry 16–22.5 mAh: Oura Gen 3 = Grepow YE160723G 3.7 V **16 mAh** ([DigiKey teardown](https://www.digikey.com/en/maker/projects/oura-ring-teardown-gen-3-and-2/2c005e01f82d429398e78f49591793cc)); Galaxy Ring = **17 / 18.5 / 22.5 mAh** by size ([Samsung](https://www.samsung.com/ca/support/mobile-devices/enhance-battery-life-and-efficiency-for-your-galaxy-ring/)). Grepow's newest curved cells reach **21–24 mAh** ([Grepow](https://www.grepow.com/wearables/9.html)). A 16–22 mAh cell rated ~1C cannot source the **300–370 mA photo-moment peaks** measured on an ESP32-S3 camera board ([Seeed via Elektor](https://elektor.com/products/seeed-studio-xiao-esp32s3-sense), [Fab Academy](https://fabacademy.org/2026/labs/benfica/students/carlos-anjos/Week-04/datasheet.html)). **Conclusion: ESP32-S3 is the right stage-0/stage-1 part; it is the wrong part for an Oura-size ring.** An nRF52-class SoC drawing ~5–15 mA peak is the only family that matches a ~1C, 16–24 mAh cell.
- **No small BLE SoC has a hardware camera interface.** nRF52840/nRF5340/nRF54L15 have none; Ambiq Apollo4 Blue Plus / Apollo510 expose MIPI **DSI (display)**, not CSI; Renesas DA1470x has no camera input found; STM32WB has no DCMI. ESP32-S3 (DVP via LCD_CAM) and Realtek RTL8735B are the only radio+camera-interface chips found, both too hungry for a ring. The ring path is therefore **nRF52840/nRF5340 + a camera you bit-bang or that outputs SPI/JPEG**, which is what three real projects did: Arduino Nano 33 BLE + OV7670 bit-bang ([Arduino](https://blog.arduino.cc/2020/06/24/machine-vision-with-low-cost-camera-modules/)), Nordic's nRF52840 + Arducam Mini OV2640 BLE image-transfer demo ([GitHub](https://github.com/jimmywong2003/nrf52-ble-image-transfer-demo)), and SparkFun Edge (Apollo3) + HM01B0 ([SparkFun](https://learn.sparkfun.com/tutorials/programming-the-sparkfun-edge-with-arduino/all)).
- **BLE budget:** plan on **~300–400 kbps to iPhone** and **~1 Mbps to Android** with 2M PHY + DLE. A 30 KB JPEG ≈ 0.7 s on iOS, ≈ 0.25 s on Android. iOS MTU is 185 (182 usable), Android up to 517.
- **Shots per charge (§3.4):** nRF52840-class ring at 20 mAh ≈ **~2,600 shots over a 7-day week (~375/day)**; ESP32-S3 at 20 mAh ≈ **~200 shots/week** and only with the camera hard power-gated and BLE not kept connected (ESP32-S3 holding a BLE connection in light sleep at ~380 µA drains 20 mAh in <2 days with zero photos).

## 1. MCU / SoC options

| SoC | Smallest package | Camera path | Radio | Active current | Sleep | Price | Ring verdict |
|---|---|---|---|---|---|---|---|
| **Nordic nRF52840** | aQFN73 7×7, QFN48 6×6, **WLCSP 3.5×3.6 mm** | none in silicon; GPIO bit-bang (proven OV7670) or SPI JPEG camera (proven Arducam Mini); HM01B0 1-bit via SPIS/I2S plausible, **unverified** | BLE 5, 2M PHY, DLE | TX 4.8 mA @0 dBm, RX 4.6 mA ([PS](https://infocenter.nordicsemi.com/pdf/nRF52840_PS_v1.8.pdf)) | OFF 0.4 µA; ON+RTC 1.5 µA | LCSC $3.83 @1, $2.33 @1k | **Best hobbyist ring choice**; SiP modules (ISP1807 8×8×1 mm) |
| **Nordic nRF5340** | aQFN94 7×7; WLCSP ~4.4×4.0 | none; 128 MHz + 512 KB RAM for bit-bang + software JPEG | BLE 5.x | n/a | n/a | $8 @1; £3.92 @500 | **Galaxy Ring uses nRF5340** ([GSMArena](https://www.gsmarena.com/samsung_galaxy_ring_is_nonrepairable_-news-64253.php)) |
| **Nordic nRF54L15** | QFN48 6×6; WLCSP (size unverified) | none | BLE 5.4 | RX 3.4 mA, TX 4.8 mA | 0.7–2.9 µA | $3.61 | Lowest power; NCS/Zephyr only; stage-2 candidate |
| **ESP32-S3FH4R2** | **QFN56 7×7 mm** with 4 MB flash + 2 MB PSRAM in package | **hardware DVP** (LCD_CAM), esp32-camera, JPEG from OV2640 | Wi-Fi + BLE 5 | XIAO Sense avg 154 mA, 304–366 mA peaks (with Wi-Fi); BLE-only figure **not found** | deep sleep 7–8 µA; light sleep 380 µA; **3 mA with camera board attached** ([cnx](https://www.cnx-software.com/?p=111849)) | $4.00 @1, $2.31 @1k | **Best stage 0/1**; poor Oura-size fit (peak current, antenna) |
| Ambiq Apollo3 Blue (Artemis 15.5×10.5×2.3) | BGA | HM01B0 bit-bang (TFLM person_detection) | BLE 5 | n/a | n/a | Edge board retired | precedent, thin ecosystem |
| Ambiq Apollo4 Blue Plus / Apollo510 | 4.7×4.7 SiP / 6.6×6.6 | **no camera/CSI**; MIPI DSI only | BLE 5.1 / none | — | — | EVB $245 | skip |
| Renesas DA1470x | — | display controller, no camera input found | BLE 5.2 | — | — | — | skip |
| Realtek RTL8735B (AMB82-Mini) | — | full camera SoC, H.264/JPEG | Wi-Fi + BLE | — | — | ~¥212 | bench only |
| STM32WB/WBA, Telink, SiLabs | — | STM32WB: no DCMI; others unverified | — | — | — | — | no evidence |

### 1.2 ESP32-S3 modules (stage 1)
| Module | Size |
|---|---|
| ESP32-S3-MINI-1 | **15.4 × 20.5 × 2.4 mm** (PCB antenna) |
| ESP32-S3-MINI-1U | **15.4 × 15.4 × 2.4 mm** (u.FL) — smallest official |
| Unexpected Maker NanoS3 | **28 × 11 × 2.4 mm**, 8 MB flash + PSRAM ([cnx](https://www.cnx-software.com/2024/04/20/unexpected-maker-nanos3-world-tiniest-esp32-s3-module/)) |
No ~10×10 mm ESP32-S3 module exists; bare QFN56 is 7×7 plus crystal and antenna.

### 1.3 Nordic modules
- **Insight SiP ISP1807**: nRF52840 SiP, **8 × 8 × 1.0 mm LGA with antenna** ([DigiKey](https://www.digikey.com/en/product-highlight/i/insight-sip/isp1807-bluetooth-module)). MOQ risk (TME MOQ 500). The most ring-compatible module found.

### 1.4 Can an nRF52840 drive a camera? Evidence
1. Arduino Nano 33 BLE + OV7670/OV7675, `Arduino_OV767X`: GPIO bit-bang of 8-bit parallel into a 150 KB buffer. Stills only.
2. nRF52840 + Arducam Mini 2MP (OV2640, SPI, hardware JPEG) → BLE → Android demo (nRF5 SDK 15.2): single-shot + streaming, 1M vs 2M PHY ([GitHub](https://github.com/jimmywong2003/nrf52-ble-image-transfer-demo)). Known issue: SPI-corrupted JPEG bytes → CRC the camera read.
3. HM01B0 on nRF52840-DK: I²C works; frame capture completion unclear ([DevZone](https://devzone.nordicsemi.com/f/nordic-q-a/95933/how-to-read-a-frame-from-hm01b0-image-sensor)). HM01B0: <4 mW QVGA 60 fps, 670 µW QQVGA. On RP2040 captured with PIO+DMA. On nRF52 the analogous trick (PCLK into SPIS/I2S slave in 1-bit mode) is **unverified R&D**.
4. Zephyr video drivers exist (OV2640, OV7670, GC2145, OV5640…) but capture back-ends are STM32/NXP, **not nRF**.
5. Arducam Mega (3/5 MP, SPI, JPEG out): 33×33×17 mm, $26/$35; SDK lists Arduino/ESP32/RP2040/STM32, plain SPI so an nRF port is straightforward.

**Ranking for the ring:** (1) nRF52840 (ISP1807 for stage 2), (2) nRF5340, (3) nRF54L15, (4) ESP32-S3 (stage 0/1 only), (5) Apollo.

## 2. BLE data-transfer realities

| Setup | Measured | Source |
|---|---|---|
| Infineon SoC → iPhone 11/X, 2M PHY, MTU 515, CI 26 ms | **311–365 kbps** | [Infineon](https://community.infineon.com/t5/ModusToolbox-Blog/BLE-Throughput-Rate-Benchmark-Test-for-Cypress-BT-SoCs/bc-p/267238) |
| Same → Pixel 3 / S10+ | **1222–1236 kbps** | same |
| Silabs BGX13 → iPad mini, 15 ms, 2M | 488 kbps; Galaxy S9 1175 kbps | [Silabs](https://docs.silabs.com/gecko-os/1/bgx/1.x/throughput) |
| nRF52 → iPhone 7, 15 ms, 2M, MTU 185 | ~400 kbps | [DevZone](https://devzone.nordicsemi.com/f/nordic-q-a/40597/) |
| nRF5340 → Android, 2M, MTU 247, DLE 251 | 1000–1050 kbps; some phones stay on 1M (<600) | [DevZone](https://devzone.nordicsemi.com/f/nordic-q-a/85258/) |
| ESP32-S3 NimBLE throughput example | 46 KB/s measured vs 63 KB/s claimed | [esp32.com](https://esp32.com/viewtopic.php?p=134134) |

Why iOS is slower: the iPhone closes each connection event early; Apple sets a **15 ms minimum CI** and may grant 30 ms. **MTU:** iOS 185 (182 payload), Android up to 517; iOS 16.0 temporarily dropped some devices to 77 — don't hard-code chunk size.

| Image | iOS realistic (350 kbps) | iOS worst (150 kbps) | Android (1000 kbps) | Android conservative (500) |
|---|---|---|---|---|
| 10 KB | 0.23 s | 0.53 s | 0.08 s | 0.16 s |
| 30 KB | 0.69 s | 1.6 s | 0.24 s | 0.48 s |
| 100 KB | 2.3 s | 5.3 s | 0.8 s | 1.6 s |

Keep images **≤ 30 KB** so the radio leg stays under ~1 s on iPhone.

### Recommended chunking / ack scheme
- Notifications (not indications) on a data characteristic, payload = MTU−3; control on a second characteristic with START{len, w, h, crc32}.
- BLE link layer already retransmits; packets are lost only on TX-queue overrun → **throttle on the stack's TX-complete callback** (`BLE_GAP_EVENT_NOTIFY_TX` on NimBLE). A per-packet application ACK halves throughput.
- Recovery: after the last packet the phone sends a bitmap/list of missing seq; ring resends only those.
- Negotiate on connect: 2M PHY, DLE 251, MTU ≥ 247, CI 15 ms; relax to a long interval at idle. Verify with a sniffer.
- Alternative: L2CAP CoC (iOS `CBL2CAPChannel`) — unverified this session.

> mcring's protocol (`/protocol/ble-gatt.md`) implements exactly this scheme.

## 3. Power

### 3.1 Battery capacities and ring cells
| Ring | Battery |
|---|---|
| Oura Gen 3 | Grepow YE160723G 3.7 V 16 mAh |
| Oura Gen 2 | Grepow; TI **BQ25120A** charger |
| Galaxy Ring | 17 / 18.5 / 22.5 mAh (nRF5340) |
| Ultrahuman Ring Air | 24 or 32 mAh (retailer specs conflict) |

Curved cells: Grepow 6.2–24 mAh, e.g. **GRP170722 = 4.2 V, 1C, 14.5 mAh, 1.7 × 6.5 × 22 mm**; curved "E-stacking" 21 mAh; also a 40 mAh curved 2508030. **1C rating** → a 15 mAh cell is specified for ~15 mA continuous. B2B samples, expect MOQ/NDA.

Hobbyist flat micro-LiPos:
| Cell | Capacity | Size | Price |
|---|---|---|---|
| 301012 | 30 mAh | 3 × 10 × 12 mm | ~$8.54 / 10 pcs (eBay) |
| 501012 | 40 mAh | 5 × 10 × 12 mm, 1.5 g | ~$10 / 4 pcs; ₹119 Robu (PCM) |
| 400909 | 25 mAh | 4 × 9 × 9 mm | listing only |
| Adafruit 1570 | 100 mAh | 31 × 11.5 × 3.8 mm | $5.95 |
10–20 mAh cells: not at retail (Eunicell on Alibaba per EEVblog). A 3 × 10 × 12 mm flat cell fits chord-wise inside a 20 mm-ID ring only if the ring is ~3 mm thick there → stage 1 should be oversized.

### 3.2 Charger ICs
| IC | Package | Charge current | Termination | Fit |
|---|---|---|---|---|
| **TI BQ25100/01** | DSBGA-6 **1.6 × 0.9 mm** | 10–250 mA | down to 1 mA | best for ring cells ([TI](https://www.ti.com/document-viewer/BQ25100/datasheet)) |
| Nordic nPM1100 | WLCSP 2.1 × 2.1 | up to 400 mA | — | stage 1, includes buck |
| Nordic nPM1300 | WLCSP 3.1 × 2.4 | up to 800 mA | — | overkill, has fuel gauge |
| Microchip MCP73831 | SOT-23-5 | 15–500 mA | ~C/13 | ≥40 mAh stage 1 |
| LTC4054 | SOT-23-5 | ≤800 mA | — | stage 1 |

### 3.3 Wireless charging
Practical Rx coil floor ~10 mm; smallest catalog coils TDK WR111180-36F5-B1 (11 mm × 1.5 mm) and Würth 760308101219 (15 mm). Real rings use custom coils in epoxy with a matched cradle. **Recommendation:** stage 1 = two pads + pogo-pin cradle; stage 2 = flex-printed coil + your own resonant transmitter.

### 3.4 Shots-per-charge math
Assumptions: **A. ESP32-S3** 1.5 s × 150 mA = 0.0625 mAh/shot, standby 20 µA (camera hard power-gated, BLE off, wake on accel INT) = 0.48 mAh/day; A′ BLE kept alive in light sleep ≈ 380 µA = 9.1 mAh/day. **B. nRF52840 + HM01B0** 1 s × 15 mA = 0.00417 mAh/shot, standby 30 µA incl. slow BLE connection = 0.72 mAh/day. Usable = 80 % of rated.

| Battery | Usable | A: shots/week | A′: BLE-connected idle alone | B: shots/week | B: standby life |
|---|---|---|---|---|---|
| 20 mAh | 16 | **202 (~29/day)** | dead in **1.8 days** | **2,630 (~375/day)** | 22 days |
| 40 mAh | 32 | **458 (~65/day)** | 3.5 days | **6,465 (~920/day)** | 44 days |
| 100 mAh | 80 | **1,226 (~175/day)** | 8.8 days | **17,980** | 111 days |

Traps: peak current (300–370 mA = 15–20C on a 1C cell) kills A at Oura size; XIAO ESP32S3 Sense deep sleep with camera board attached is **3 mA** vs 64 µA bare — the camera rail must be load-switched.

## 4. Stage-0 development boards
| Board | What | Price |
|---|---|---|
| **Seeed XIAO ESP32S3 Sense** | ESP32-S3, 8 MB PSRAM + 8 MB flash, OV2640, PDM mic, microSD; OpenGlass ran on it ([OpenGlass](https://github.com/BasedHardware/OpenGlass)) | £13.50 ex-VAT (Pi Hut); ~$14 |
| **Seeed XIAO nRF52840 Sense** | nRF52840, IMU + PDM mic, 21 × 17.5 mm | £15.29; ~$16 |
| **Arducam HM01B0 for Pico (B0315)** | mono 320×320, RP2040 PIO code | £15.40–€18.90 |
| Arducam Mini 2MP (OV2640 SPI) + nRF52840-DK | Nordic demo hardware | — |
| **Arducam Mega 3/5 MP (SPI JPEG)** | any SPI MCU; 33×33×17 mm | $25.99 / $34.99 |
| ESP32-S3-EYE | S3 + OV2640 + LCD + mic | €38.70 / $45 |
| M5Stack Timer Camera X | ESP32 + OV3660 + battery mgmt | €20.30 |
| M5Stack AtomS3R-CAM | ESP32-S3R8 + camera | $24.50 |
| LilyGO T-Camera S3 | S3 + camera + display + PIR + mic | $17.31–€21.95 |
| Freenove ESP32-S3-WROOM CAM | S3 + OV2640, 16 MB | $31.95–$44.95 |
| Nordic nRF54L15 DK | — | $38.30 |

## 5. Teardowns of real rings
| Ring | PCB | Components | Battery | Sources |
|---|---|---|---|---|
| Oura Gen 2/3 | **rigid-flex** (0.22 mm flex / 0.48 mm rigid-flex; 2.9 mm target thickness; printed microstrip antenna; capacitive wear pads) | PPG optics; BQ25120A charger; Gen 4 uses Infineon PSoC 6 | 16 mAh Grepow | [DigiKey/Stern](https://www.digikey.com/en/maker/projects/oura-ring-teardown-gen-3-and-2/2c005e01f82d429398e78f49591793cc), [Memfault](https://interrupt.memfault.com/blog/smart-ring-development-part-1) |
| Galaxy Ring | flex, epoxy-potted; battery on a press connector | **nRF5340**, tiny Qi coil, NFC, PPG | 17–22.5 mAh | [GSMArena](https://www.gsmarena.com/samsung_galaxy_ring_is_nonrepairable_-news-64253.php) |
| Ultrahuman Ring Air | flex PCB in titanium shell | PPG | 24–32 mAh | [DigiKey](https://www.digikey.com/en/maker/blogs/2024/ultrahuman-ring-air-teardown) |
| RingConn | no teardown found | — | — | — |

Takeaway: every shipping ring is a **flex or rigid-flex board ~0.2–0.5 mm thick, curved around a 16–22 mAh curved cell, potted in epoxy, with a printed antenna** and a 7×7 mm-class Nordic SoC or PSoC.

## 6. Recommendations
**Stage 0 (<$60):** XIAO ESP32S3 Sense + OpenGlass-style flow; in parallel XIAO nRF52840 Sense + Arducam HM01B0 and/or Arducam Mega 3 MP to start the nRF capture R&D. Measure current with a PPK2.
**Stage 1 (2–4 months):** nRF52840 module (ISP1807 if singles are buyable, else XIAO nRF52840 sunk into the print) or ESP32-S3-MINI-1U if the ring is big enough for 40–100 mAh; HM01B0 or SPI-JPEG camera; flat 301012/501012 cell; BQ25100 or nPM1100; load switch on camera rail; LIS2DH12-class accel for double-tap; BLE 2M/DLE/15 ms with TX-complete throttling and bitmap NACK.
**Stage 2 (hard, multi-spin):** nRF52840/nRF5340/nRF54L15 WLCSP on rigid-flex 0.22/0.48 mm, printed antenna; Grepow curved 16–24 mAh 1C cell; BQ25100/BQ25120-class charger; flex coil or pads; HM01B0-class sensor with tiny lens; grayscale QVGA JPEG ≤ 20–30 KB → ~0.7 s on iPhone. ESP32-S3 not viable here.

## 7. Not verified
ESP32-S3 BLE-only current table; nRF54L15 WLCSP size; nRF5340 current; HM01B0 serial capture on nRF52; iPhone 2M PHY model list; Oura Ring 4 / RingConn / Ultrahuman capacities; ISP1807 unit price; VDL / Jiangsu Ultra-lite as vendors; RTL8735B CSI; Seeed USD prices.
