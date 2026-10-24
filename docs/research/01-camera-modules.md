# Research report 1 — Smallest buyable camera modules for a BLE camera smart ring

> Produced by an automated research pass (web search snippets; direct datasheet/PDF fetches
> were blocked by the sandbox proxy). Anything marked **[UNVERIFIED]** must be checked on the
> live page before designing around it. Target envelope used for verdicts: Oura Ring 4 class
> band, ~7.9 mm wide × ~2.88 mm thick.

## 0. Executive summary (the skeptical version)

1. **Nothing you can buy off the shelf fits inside an Oura-thickness band as a complete camera.** The only modules under ~3.5 mm in every dimension are OmniVision wafer-level "CameraCubeChip" parts (OVM6948 / OCHTA10 / OVM6946 / OVM6211 / OVM7690 / OVM7692) and bare Himax CSP sensors (HM01B0/HM0360). Even the smallest *digital-output* one, the **OVM7692 (2.8 × 3.2 × 2.5–2.6 mm)**, is as tall as the whole Oura band, so a stage-2 ring will need a local "pod" ~4–5 mm thick where the camera sits.
2. **The famous 0.65 mm OVM6948 is a trap for a BLE ring.** Its output is a proprietary 4-wire analog "AntLinx" signal (not NTSC/composite). You need OmniVision's **OV426** bridge (a 6 × 6 mm 64-ball BGA) to get 10-bit DVP, which then still needs a DVP-capable MCU. The bridge alone is bigger than a whole OVM7692 camera. Module prices are $115–$550 each with MOQ 2–10. Verdict: interesting for stage-0 play, wrong for the ring.
3. **The most hobbyist-practical digital path is the Himax HM01B0** (320×320 mono, <2 mW, configurable 1/4/8-bit output, I²C control). Lensed Himax module on DigiKey at ~$11.74, Arducam/SparkFun boards $11–$20. Its 1-bit serial mode needs only 4 signal lines (D0, PCLK, HSYNC, VSYNC) — bit-bangable with RP2040 PIO or an nRF with PPI/GPIOTE tricks. Bare CSP is "<5 mm²" but you then have to put a lens on it yourself, which hobbyists generally cannot do.
4. **OVM7692 is the best "digital + wafer-level + actually on DigiKey" candidate for stage 2**: 640×480 color, DVP parallel + MIPI serial + SCCB, single 2.8 V, ~120 mW active, 23 µA standby, DigiKey $27.50 @1 (14-week lead), LCSC ~$6.34. Downsides: 120 mW active, no breakout board exists (RS discontinued the eval kit), 0.4 mm-pitch-class 25-ball CSP soldering, and 2.5 mm z-height.
5. **All USB/UVC endoscope modules (3.3–3.9 mm OV9734, 5.5–8 mm consumer probes) require a USB host.** That means ESP32-S2/S3 (usb_stream), not a plain BLE SoC. Fine for stage 0, poor fit for a ring.
6. **Prior art that proves a BLE camera ring is buildable:** UW's **IRIS** (UIST 2024) — camera + BLE + IMU + battery in a 3D-printed ring with a 17.5 mm diameter, 2.9 mm-thick band, 16–24 h battery, camera wakes on button press and sleeps after 3 s, images compressed before BLE transfer. **Read it first** ([PDF](https://homes.cs.washington.edu/~gshyam/Papers/iris.pdf), [arXiv 2407.18141](https://arxiv.org/abs/2407.18141)).

## 1. OmniVision OV6948 / OVM6948 (CameraCubeChip) and siblings

Specs (OmniVision product brief [OVM6948-PB-v1.5](https://www.ovt.com/wp-content/uploads/2023/03/OVM6948-PB-v1.5-WEB.pdf)):
- Module 0.65 × 0.65 mm, z-height 1.158 mm; sensor die 0.575 mm sq. 200 × 200 pixels, 30 fps, 120° DFOV.
- Output: **"AntLinx Analog", 4-pin package**. Companion chip **OV426** decodes it to 10-bit DVP; 64-pin BGA 6 × 6 mm ([OVT OV426](https://www.ovt.com/products/ov426/)).
- Power: single 3.3 V, ~25 mW.
- Arrow lists OVM6948-RALA as active ([Arrow](https://www.arrow.com/en/products/ovm6948-rala/omnivision-technologies)) — price/stock **[UNVERIFIED]**.

Siblings: **OCHTA10** (400×400 in 0.65 × 0.65 mm, analog + SPI control; Camemake CM_ENDO_003 **$233.25, MOQ 10** — [camemake.eu](https://www.camemake.eu/shop/cm-endo-003-miniature-400-400-endoscope-module-with-ochta10-sensor-959)); **OVM6946** (1.10 mm sq, 400×400, analog; LCSC $60.28, 0 stock).

| Seller | What | Price | MOQ | URL |
|---|---|---|---|---|
| Alibaba | OVM6948 endoscope module with LED | $180 (1–49) → $140 (1000+) | 5 | [link](https://www.alibaba.com/product-detail/endoscopic-camera-OVM6948-module-with-led_1600376693938.html) |
| Alibaba | 1.6 mm OVM6948 module w/ LED | ~$550 | 2 | [link](https://www.alibaba.com/product-detail/ovm6948-miniature-endoscope-camera-module-1_60854713698.html) |
| AliExpress | "OVM6948 medical camera module" | ~$115–$220 | 1 | [search](https://www.aliexpress.us/w/wholesale-omnivision-ovm6948.html) |
| Camemake | OV6946 1.1 mm bare module | $143.43 | — | [link](https://www.camemake.eu/shop/cm-endo-001-ultra-compact-endoscope-module-with-omnivision-ov6946-sensor-957) |
| Camemake (DigiKey) | CM_ENDO_005 USB2/UVC decoder board for OV694x | n/a | — | [DigiKey](https://www.digikey.com.mx/en/products/detail/camemake/CM-ENDO-005/26957901) |

Hobbyist use: only via a USB/UVC decoder board (needs a USB host) or OV426 → DVP → DVP-capable MCU. No Arduino/Pi reference design found.
**Verdict:** Stage 0: fun only. Stage 1/2: **not recommended**.

## 2. Himax HM01B0 and HM0360 (ultra-low-power mono)

### HM01B0
- 320×320 mono, 3.6 µm, 1/11"; CSP "< 5 mm²" ([Himax](https://www.himax.com.tw/products/cmos-image-sensor/always-on-vision-sensors/hm01b0/)).
- Interface: configurable **1/4/8-bit** video data + frame/line sync; I²C control. In 1-bit mode a Parallax user ran it on **4 lines** ([forum](https://forums.parallax.com/discussion/178031/)). "SPI camera" in Arducam's name is marketing — RP2040 captures it with PIO.
- Power: QVGA 30 fps <2 mW, standby 200 µW. Motion-detect wake interrupt.
- Frame: 320×320×8-bit ≈ 102 kB; binned 160×120 = 19.2 kB — practical for BLE.

| Product | Size | Price | Notes | URL |
|---|---|---|---|---|
| Himax **HM01B0-MNA-00FT870** lensed module | **20.0 × 12.5 mm, 3.39 mm max height** | DigiKey $11.74 @1 | DigiKey US 0 stock / 27-wk lead; Dasenic $13.40 ~3,315 in stock | [DigiKey](https://www.digikey.com/en/products/detail/himax/HM01B0-MNA-00FT870/14109821), [Dasenic](https://dasenic.com/product/himax-hm01b0-mna-00ft870-6691302) |
| Arducam B0315 HM01B0 for Pico | board dims [UNVERIFIED] | $15.99 | in stock | [Arducam](https://www.arducam.com/product/arducam-hm01b0-qvga-spi-camera-module-for-raspberry-pi-pico-2/) |
| SparkFun SEN-15570 HM01B0 breakout | — | $10.95 | retired at several resellers | [SparkFun](https://www.sparkfun.com/himax-cmos-imaging-camera-hm01b0-monochrome.html) |
| Bare HM01B0-MWA CSP | <5 mm² | n/a | needs your own lens — not hobbyist-feasible | [DigiKey](https://www.digikey.com/en/products/detail/himax/HM01B0-MWA/14109818) |

### HM0360
- 640×480 mono, CSP < 13 mm²; 8-bit parallel **and 1-lane MIPI**; I²C. 7.8 mA VGA@60, 140 µA QVGA@2 fps, standby <140 µW.
- Himax lensed **HM0360-MWA-00FP963** DigiKey **$21.90 @1** ([DigiKey](https://azcus.digikey.com/en/products/detail/himax/HM0360-MWA-00FP963/14109819)); Arducam HM0360 for Pico $19.99 (33 × 23 mm).

**Verdict:** HM01B0 = best stage-0/stage-1 *low-power* digital candidate; the 20 × 12.5 × 3.4 mm Himax module can be glued to an oversized printed ring. Stage 2 needs the bare CSP plus a custom lens — not realistic for a hobbyist.

## 3. OV7251 / OV9281 / OVM6211 (global-shutter mono)

- **OV7251**: EOL per OmniVision; MIPI-only; smallest board 24 × 25 mm. Pi/SBC only.
- **OV9281/OV9282**: 2-lane MIPI *and* DVP; boards 25 × 24 mm, $59–79. SBC only.
- **OVM6211**: 400×400 GS, **3.2 × 3.2 mm CSP**, 85 mW active, 15 µA standby ([OVT](https://www.ovt.com/sensor/ovm6211/)). LCSC: $8.67–$67.94, **0 stock**, tray of 2000. Output interface [UNVERIFIED].

**Verdict:** OVM6211 is the right *size* for stage 2 but unobtainable in small quantity; watch list.

## 4. OV2640 / OV5640 / GC032A / GC0308 / OV7675 tiny FPC modules

| Module | Smallest footprint found | Interface | Price | Source |
|---|---|---|---|---|
| OV2640 (ESP32-CAM style) | Arducam M0031: **21 × 12.5 × 5.85 mm**, 24-pin 0.5 mm FPC | 8-bit DVP + SCCB, JPEG out | $1–$4 | [Arducam](https://www.arducam.com/arducam-ov2640-camera-module-2mp-mini-ccm-compact-camera-modules-compatible-with-arduino_m0031esp32-esp8266-development-board-with-dvp-24-pin-interface_.html), [AliExpress](https://www.aliexpress.us/item/3256805476335914.html) |
| OV7670 | Arducam 21 × 12.5 × 4.6 mm, 24-pin FPC | 8-bit DVP | ~$5 | [Arducam](https://www.arducam.com/arducam_ov7670_camera_module_vga_mini_ccm_compact_camera_modules_m0030.html) |
| **OV7675** | Sincere claims **6 × 6 mm module** [UNVERIFIED]; sensor pkg 3.85 × 2.81 mm | 8-bit DVP | quote | [cameramodule.com](https://www.cameramodule.com/fpc-camera-module/dvp-camera-module/ov7675-dvp-camera-module.html) |
| GC0308 (0.3 MP) | Supertek 34.75 × 7.8 × 3.55 mm | 8-bit DVP, 24-pin | $0.99–$3.75 | [AliExpress](https://www.aliexpress.com/w/wholesale-camera-module-gc0308.html), [M5Stack Cam0308](https://docs.m5stack.com/en/products/sku/A178) |
| GC032A | "customizable" | DVP | $1.5–$4.2, MOQ 1–5 | [HKTDC/Sinoseen](https://www.hktdc.com/event/hkelectronicsfairae/en/product/1Z03NP3IF) |
| OV5640 (5 MP) | boards ≥ 24 × 25 mm | DVP or MIPI | $8–$15 | [Waveshare](https://www.waveshare.com/product/modules/ov5640-camera-board-a.htm) |

Smallest integrated BLE+camera dev board: **Seeed XIAO ESP32S3 Sense, 21 × 17.5 × 15 mm with camera**, OV2640 on a board-to-board connector ([Pi Hut](https://thepihut.com/products/seeed-studio-xiao-esp32s3-sense)).

**Verdict:** OV2640/GC0308/GC032A FPC modules are the cheapest, best-supported DVP cameras → **ideal stage 0**, plausible **stage 1** (lens head ~8–9 mm, ~5–6 mm tall [UNVERIFIED]). Too thick for stage 2.

## 5. Endoscope/borescope "1 mm / 2 mm / 3.9 mm" modules

- 0.65–1.1 mm tips = OVM6948/OCHTA10/OVM6946 (analog); 3.3–3.9 mm = **OV9734** 720p; 5.5 mm = OV2740; 7–8 mm consumer probes = unspecified 720p/1080p.
- Essentially all retail ones are **USB-UVC**. Camemake OV9734 on DigiKey: CM_ENDO_023 3.9 mm $20.51 @10 ([DigiKey](https://www.digikey.com/en/products/detail/camemake/CM-ENDO-023/26957912)); CM_ENDO_014 3.3 mm $19.49; CM_ENDO_009 3.5 mm $15.37.
- MCU interfacing: USB host required → Espressif `usb_stream` on **ESP32-S2/S3** ([component](https://components.espressif.com/components/espressif/usb_stream/versions/1.5.0/examples/usb_camera_mic_spk)). nRF52/53 have no USB host.

**Verdict:** Stage 0 (ESP32-S3 + 3.9 mm UVC head) is a fast way to get real images from a 4 mm optic; stage 2: no.

## 6. Existing camera-ring products, prototypes, teardowns

| Project | What's known | Camera |
|---|---|---|
| **IRIS** (UW, UIST '24) | Camera + BLE + IMU + battery in 3D-printed ring; **band 17.5 mm Ø × 2.9 mm thick**; 16–24 h; camera on at button press, off after 3 s; images compressed before BLE | part number in paper [UNVERIFIED]. [PDF](https://homes.cs.washington.edu/~gshyam/Papers/iris.pdf), [ACM](https://dl.acm.org/doi/10.1145/3654777.3676327), [UW News](https://washington.edu/news/2025/01/08/smart-ring-camera-iris) |
| **Padrone Primera** (Kickstarter 2024) | Ring mouse: forward camera + IMU + BLE, 8 g | not disclosed. [New Atlas](https://newatlas.com/wearables/padrone-primera-mouse-ring/) |
| **Sony "Ring Camera"** PoC (2026) | Finger-worn sensor → phone → audio for visually impaired | n/a |
| **MIT EyeRing** (2012–13) | Ring w/ camera, thumb button, Bluetooth to phone | "small VGA camera unit", AVR, BT module. [MIT](https://www.media.mit.edu/publications/eyering-an-eye-on-a-finger/) |
| Hackaday/Hackster | No camera-ring teardown exists. Hackable non-camera rings: COLMI R02, SR08 ($22) | [Hackaday SR08](https://hackaday.com/2025/02/05/hacking-the-22e-ble-sr08-smart-ring-with-built-in-display/) |

## 7. Master comparison table

| Part / module | Sensor & res | Footprint incl. lens | Interface | Power | Price | MOQ | Verdict S0 / S1 / S2 |
|---|---|---|---|---|---|---|---|
| OVM6948 | 200×200 color | 0.65 × 0.65 × 1.16 mm | analog AntLinx → OV426 (6×6 BGA) → DVP | ~25 mW | $115–$550/module | 1–10 | fun / no / **no** |
| OCHTA10 | 400×400 | 0.65 × 0.65 × 1.2 mm | analog + SPI ctrl | n/a | $233 | 10 | same |
| HM01B0 lensed module -00FT870 | 320×320 mono | **20.0 × 12.5 × 3.39 mm** | 1/4/8-bit parallel + I²C | <2 mW | **$11.74** | 1 | **✔ / ✔ best / ✗** |
| Arducam HM01B0 for Pico | 320×320 mono | n/a | same (RP2040 PIO) | <2 mW | $15.99 | 1 | ✔ / maybe / ✗ |
| HM0360 lensed -00FP963 | 640×480 mono | ~21 × 20 × 4.9 (sibling) | 8-bit parallel or 1-lane MIPI | 7.8 mA VGA60 | $21.90 | 1 | ✔ / ✔ / ✗ |
| **OVM7692** CameraCube | 640×480 color | **2.8 × 3.2 × 2.6 mm** | 8-bit DVP + MIPI + SCCB, 2.8 V | ~120 mW, 23 µA stby | $27.50 DigiKey / ~$6 LCSC | 1 | custom PCB / ✔ / **only realistic digital S2 option** |
| OVM6211 | 400×400 GS mono | 3.2 × 3.2 mm | n/a [UNVERIFIED] | 85 mW | $8.67–$67.94 | tray | S2 ideal size, **unobtainable** |
| OV2640 24-pin FPC | 1600×1200 JPEG | 21 × 12.5 × 5.85 board; head ~8–9 mm | 8-bit DVP + SCCB | tens of mA | **$1–$4** | 1 | **✔ / ✔ / ✗** |
| GC0308 / GC032A FPC | 640×480 | 34.75 × 7.8 × 3.55 | 8-bit DVP | n/a | $1–$4 | 1–5 | ✔ / ✔ / ✗ |
| OV9734 3.3–3.9 mm endoscope | 1280×720 | Ø3.3–3.9 head + USB board | USB-UVC | n/a | $15–$21 @10 | 10 | ✔ (S3 host) / marginal / ✗ |
| Arducam Mega SPI | 3/5 MP | 30–33 × 33 × 17 mm | true SPI, JPEG out | 40–160 mA | $26–$40 | 1 | ✔ (any BLE MCU) / ✗ / ✗ |
| XIAO ESP32S3 Sense | 1600×1200 | 21 × 17.5 × 15 mm | integrated DVP, BLE 5 | n/a | ~$14–$20 | 1 | **✔ best all-in-one** / ✔ / ✗ |

## 8. Interface/MCU implications

- **DVP 8-bit parallel** (OV2640, GC0308, HM0360, OVM7692): ~13 GPIO. Native on ESP32-S3 (has BLE 5), STM32 DCMI, RP2040/RP2350 via PIO. Not native on nRF52/53/54.
- **HM01B0 1-bit mode**: 4 lines; RP2040 PIO proven; nRF via SPI-slave/PPI plausible but unproven.
- **MIPI CSI-2**: needs an SBC or MCU with CSI — not a BLE-SoC story.
- **Analog AntLinx**: OV426 bridge mandatory.
- **USB-UVC**: ESP32-S2/S3 host only.
- **True SPI with on-module JPEG** (Arducam Mega): any BLE MCU, but 30 × 33 mm.

BLE budget reality: 160×120 8-bit grayscale = 19.2 kB; 320×320 ≈ 102 kB; OV2640 QVGA JPEG typically 5–15 kB. At practical BLE 2M-PHY throughput a single still is 0.1–2 s.

## 9. Recommended path

- **Stage 0:** XIAO ESP32S3 Sense ($15–20) for the end-to-end pipeline; in parallel Arducam HM01B0 on a Pico ($16) to learn low-power 1-bit capture.
- **Stage 1:** Himax HM01B0-MNA-00FT870 lensed module or an OV2640 21-mm-FPC head glued into a ring pod; ESP32-S3 inside/alongside.
- **Stage 2:** custom flex around **OVM7692** with a DVP-capable low-power MCU + BLE, accepting a ~4–5 mm camera pod; **OVM6211** as upgrade if stock appears; **skip OVM6948**. First action: read the IRIS PDF.

## 10. Claims not verified
1. IRIS camera part number, MCU, battery mAh. 2. HM01B0 CSP outline; Arducam B0315 dims; HM0360 module dims. 3. OV2640 lens-head size. 4. OV7675 "6 × 6 mm module". 5. OVM7690 broker price; OVM6948 Arrow price. 6. OVM6211 interface/availability. 7. AliExpress ~$1 endoscope prices. 8. Raw-MIPI OV9734 variants.
