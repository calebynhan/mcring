# Research report 3 — Output modalities (air puff / haptic / light / audio) and triggers

> Automated research pass from web-search snippets (direct PDF fetches were blocked by the
> sandbox). **[unverified]** marks numbers that could not be confirmed on the source page.
> Form factors: **Stage 1** = printed ring ~30 mm OD × 12 mm wide (optional "signet" plate).
> **Stage 2** = Oura-class ~8 mm band, 2.5–3 mm thick, ~20 mm ID. RingConn Gen 3, the only
> shipping ring with a vibration motor, is 2.3 mm thick and 2.5–3.5 g.

## 1. Air puff

### 1.1 Candidate pumps / blowers

| Device | Size | Weight | Drive | Flow / pressure | Power | Price / availability | Sources |
|---|---|---|---|---|---|---|---|
| **Murata MZB1001T02** microblower | 20 × 20 × 1.85 mm (+1.6 mm nozzle) | 1.4 g | 10–20 Vp-p sine at 24–27 kHz (external driver) | ≥0.70 L/min @ 0.05 kPa; static ≥1.42 kPa | ~0.18 W | ~$12.28 (Octopart); stock trend fell to zero; 2011 part | [Mouser DS](https://www.mouser.com/datasheet/2/281/MZB1001T02_SPEC_Ver2-202918.pdf), [Murata](https://www.murata.com/en-global/products/mechatronics/fluid/microblower_mzb1001t02), [DigiKey](https://digikey.cn/en/products/detail/murata-electronics/MZB1001T02/2442520) |
| **Murata MZB3004T04** (high-pressure) | 21 × 19 × 3.4 mm | — | 8–21 Vdc into Murata driver | ≥155 mL/min; static ≥50 kPa | — | DigiKey; eval driver MZBD304 | [Murata](https://www.murata.com/en-global/products/mechatronics/fluid/overview/lineup/microblower_mzb3004t04), [MZBD304](https://www.digikey.com/en/products/detail/murata-electronics/MZBD304/26262409) |
| **Lee / TTP Ventus Disc Pump** XP/BL/US | 29 mm dia; US 29 × 5.9 mm | 4.4–5 g | 20–22 kHz, 0–60 V peak; driver from 3–5 V | >400 mbar / >0.75 L/min (XP) | 0–1 W | quote only | [Lee XP](https://theleeco.com/uploads/2024/07/The-Lee-Company_PDS-197-2024-07-XP-Series-Disc-Pump.pdf), [Lee US](https://www.theleeco.com/uploads/2024/07/The-Lee-Company_PDS-200-2024-07-US-Series-Disc-Pump.pdf) |
| **Bartels mp6 / BP7** | 30 × 15 × 3.8 mm | 2 g | ~250 Vpp piezo | gas ~14 mL/min | <200 mW | quote | [Darwin](https://darwin-microfluidics.com/products/bartels-mp6-micropump) |
| **Fraunhofer EMFT** silicon micropump | 3.5 × 3.5 × 0.6 mm | — | piezo | ~0.4–0.5 mL/min | — | licensing only | [EMFT](https://www.emft.fraunhofer.de/en/research-development/micropumps/piezo-micropumps.html) |
| TDK piezo micropump | — | — | — | — | — | **not found** | — |

### 1.2 Can any produce a perceptible puff from inside a ring?

Physics estimate: 0.7–1.2 L/min = 12–20 mL/s; through a ~1 mm² nozzle that is a ~12–20 m/s jet, unmistakably perceptible on skin (breath is a few m/s). No published prototype uses a Murata microblower in a ring; closest literature is a neckband with eight microblowers ([ACM](https://dl.acm.org/doi/10.1145/3772363.3799106)). Finger-worn pneumatic rings in the literature use an external compressor.

- **mp6 / Fraunhofer-class: no** (dosing pumps, orders of magnitude too little flow).
- **Murata MZB1001T02: yes for stage 1, no for stage 2.** 20 × 20 mm → a flat signet plate aimed at the adjacent finger. Needs a 15–20 Vpp ~26 kHz drive from a 3.7 V cell. Stock thin; confirm before designing in.
- **MZB3004T04: maybe for stage 1** (3.4 mm thick, 60 kPa, ~200 mL/min).
- **Disc Pump: stage 1 only, worse than Murata** (29 mm, 1 W, 60 V, quote only).
- **Stage 2: no COTS pump fits.**

### 1.3 Puff-like alternatives
- **Pneumatic tap**: inflate a thin silicone pouch against the finger; still needs a pump; stage 1 only.
- **Thermal**: smallest Peltier Same Sky CP0734-238 (3.4 × 3.4 × 2.38 mm, 0.7 A, ~$23 @50). Hundreds-of-ms response; unsuitable for Morse timing.
- **Electrotactile**: Oura patent for electrodes in the band ([G&W](https://gadgetsandwearables.com/2026/08/22/oura-ring-electrical-haptic-feedback-patent/)); ESP32-C3 electrotactile prototype ([arXiv 2605.00240](https://arxiv.org/pdf/2605.00240)); Hackaday "Medium Machine" delivers Morse via TENS. Needs tens of volts, narrow comfort window. Not a first-stage path.

**Verdict:** air puff is a stage-1 novelty (Murata signet) and not a stage-2 option. Puff edges are also slow relative to an LRA for Morse.

## 2. Haptics

### 2.1 Actuators

| Part | Type | Size | Electrical | Output | Price / source | Sources |
|---|---|---|---|---|---|---|
| **Vybronics VG0640001D** | coin LRA | 6.0 mm dia; thickness [unverified] | 1.8 Vrms, 210 Hz | 0.9 G | €4.19 @1; 0 stock, 9-wk lead | [DigiKey](https://www.digikey.com/en/products/detail/vybronics-inc/VG0640001D/15220805) |
| **INEED LRA0825BC-0167F** | coin LRA | 8 × 2.5 mm | 0.1–1.25 Vrms, 240 Hz | — | DigiKey marketplace (449 in stock) | [INEED](https://ineedmicromotors.com/?p=3133), [DigiKey](https://azcus.digikey.com/en/products/detail/ineed-motor/LRA0825BC-0167F/21840080) |
| **Precision Microdrives C08-005** | coin LRA | 8 × 3.3 mm | 1.8 V, 235 Hz, 75 mA typ | 1.28 G typ | $5.15 @1 | [PMD](https://www.precisionmicrodrives.com/?p=12426), [DS](https://www.precisionmicrodrives.com/datasheets/C08-005%20-%20datasheet-004.pdf) |
| Jameco 8 mm coin LRA | coin LRA | 8 mm | 1.8 Vrms, 235 Hz | — | $1.75 @1 (closeout) | [Jameco](https://www.jameco.com/z/1162213-Jameco-ReliaPro-8mm-Vibrating-Motor-Coin-1-8Vrms-AC-235Hz-Wire-Leads_2310095.html) |
| Vybronics VLV101040A | square LRA | 10 × 10 mm | 2.5 VAC, 170 Hz | 2.75 G | DigiKey | [DigiKey](https://www.digikey.com/en/products/detail/vybronics-inc/VLV101040A/12323590) |
| PMD 304-015 Pico Vibe | 4 mm ERM | 4.1 × 6.8 mm | 2.5 V, 25 mA | 0.25 G (weak) | PMD | [DS](https://precisionmicrodrives.com/cdn/catalog_product/c8908dc5-85dc-4029-bd02-f7ddb691b249/304-015-datasheet.pdf) |
| **TDK PowerHap 0904H014V060** | multilayer piezo | 9 × 3.75 × 1.4 mm | 60 V max | 3.3 g on 100 g, <1 ms response | order code Z63000Z2910Z 1Z41 | [TDK](https://www.tdk-electronics.tdk.com/en/374108/tech-library/articles/products-technologies/products-technologies/mini-powerhap-actuators-for-haptic-feedback/2517756) |
| Nidec Slider / CA / TapSense | thin linear | 8 × 15 × 2 mm; 1.4 mm thick | — | — | B2B only | [Nidec](https://nidec.com/en/product/search/category/B101/M107/S100/NCJ-Thin-type) |

Not found: a 5 mm or 7 mm coin LRA; "Z4TL2B"; Boréas/CirqueTech actuator data.

### 2.2 Drivers

| Driver | Package | Price | Notes | Sources |
|---|---|---|---|---|
| **TI DRV2605L** | 10-VSSOP 3×3 mm or 9-DSBGA 1.75×1.75 mm | $1.34 @1 LCSC; Adafruit breakout $7.95 | I²C, ERM+LRA, auto-resonance, 123 effects, 2–5.2 V | [TI](https://ti.com/product/DRV2605L/part-details/DRV2605LDGST), [LCSC](https://www.lcsc.com/product-detail/C425927.html), [Adafruit](https://www.adafruit.com/products/2305) |
| **TI DRV2624** | 9-DSBGA | $1.09–$2.04 | internal waveform memory, lowest-cost closed loop | — |
| **TI DRV2603** | QFN | ~$1.00 | PWM input, auto-resonance, no I²C | — |
| **Boréas BOS1901** | WLCSP 2.1 × 2.2 mm (QFN discontinued) | $4.70 @1 | piezo driver to 190 Vpp from Li-ion; required for PowerHap | [Mouser](https://www.mouser.co.uk/boreas-bos1901-drivers) |
| Discrete N-MOSFET | — | pennies | fine for ERM; an LRA wants bidirectional drive at resonance | TI [SLOA207A](https://www.ti.com/document-viewer/lit/html/SLOA207A/GUID-7FBED20C-CF40-42A8-891F-EA69B79D95A6) |

### 2.3 What commercial rings do
- **Oura Ring 4/5: no vibration motor.** Patents filed for electrotactile and coil-pushed pad haptics.
- **Samsung Galaxy Ring: no motor** (third-party reporting).
- **RingConn Gen 3 (May 2026): first ring with a vibration motor.** 2.3 mm thick; battery 11–14 d (off) vs 10.5–13 d (on). Motor undisclosed, custom.

### 2.4 Verdict
Haptics is the only modality that works for Morse in both stages. LRA + DRV2605L/DRV2624 with active braking gives tens-of-ms edges; PowerHap gives <1 ms but needs BOS1901 and a 60 V rail. 0.9–1.3 G from a 6–8 mm LRA pressed to the finger is adequate.

## 3. Light

| Part | Size | Electrical | Price | Sources |
|---|---|---|---|---|
| **XINGLIGHT XL-1010RGBC-WS2812B** | 1.0 × 1.0 × 0.8 mm | WS2812 protocol | LCSC C5349953 | [LCSC](https://www.lcsc.com/product-detail/Light-Emitting-Diodes-LED_XINGLIGHT-XL-1010RGBC-WS2812B_C5349953.html) |
| **Worldsemi WS2812B-2020** | 2.0 × 2.0 mm | 5 V nominal, 20 mA max | $0.0887 @5 (LCSC C965555) | [LCSC DS](https://datasheet.lcsc.com/lcsc/2012110135_Worldsemi-WS2812B-2020_C965555.pdf) |
| XL-1515RGBC-2812B | 1.5 × 1.5 mm | WS2812 | LCSC C48586673 | [LCSC](https://www.lcsc.com/product-detail/C48586673.html) |

Diffusion through printed resin: move the LED back from the wall, use white/translucent resin with a locally thinned wall, add an internal cone above the LED ([Formlabs forum](https://forum.formlabs.com/t/light-diffuser-resin-or-design-problem/30918)).
**Verdict:** trivially feasible in both stages; secondary/confirmation channel only (requires looking at the ring).

## 4. Audio

### 4.1 Speakers and sounders
| Part | Size | Spec | Sources |
|---|---|---|---|
| **PUI AS01008MR-2-R** | 10 mm dia | 8 Ω, 0.3 W, 86 dB | [PUI](https://puiaudio.com/product/s/AS01008MR-2-R) |
| Same Sky CMS-15118-25-SP | 15 × 11 × 2.5 mm, 1.4 g | 94.5 dB @0.7 W/0.1 m | [ThinkRobotics](https://thinkrobotics.com/products/cms-15118-25-sp) |
| Knowles RAB-32063-000 balanced armature | 5.15 × 2.96 × 5.15 mm | 46 Ω; ear-canal coupled, inaudible in free air | [DigiKey](https://www.digikey.at/en/products/detail/knowles/RAB-32063-000/4376248) |
| **Murata PKMCS0909E4000-R1** piezo sounder | 9 × 9 × 1.9 mm | 65–72 dB @ ±1.5 Vo-p, 4 kHz, 10 cm; **Last Time Buy** | [Murata](https://www.murata.com/products/productdata/8801054228510/SPEC-PKMCS0909E4000-R1.pdf) |

### 4.2 Amplifiers
- **MAX98357A** I²S class-D, 9-WLP 1.345 × 1.435 mm — best with ESP32-S3 (no DAC on S3).
- **PAM8302A** analog-in 2.5 W, ~£0.20.
- Piezo sounder can be driven straight from two GPIOs for Morse tones.

### 4.3 Realistic loudness
10 mm speaker 86 dB @10 cm → ~66 dB at 1 m before enclosure losses; speech intelligible only with hand near ear or in a quiet room. 4 kHz piezo beep at 65–72 dB @10 cm is audible near the face. None fit an 8 × 3 mm band.

### 4.4 Bone conduction via the finger
Orii ring (2017) worked by pressing fingertip to the tragus (~30 × 20 × 12 mm body, 50 mAh). Smallest COTS transducer: Dayton Audio BCE-1, 21 × 14 × 7.8 mm. Needs the user to touch their ear, which defeats glance-free Morse. Stage-1 signet only if speech is wanted.

### 4.5 MEMS microphones
| Part | Size | Price | Sources |
|---|---|---|---|
| **TDK T3902** (PDM) | 3.5 × 2.65 × 0.98 mm | ~$1.30 | [TDK](https://invensense.tdk.com/products/t3902) |
| Infineon IM69D130 (PDM) | 4 × 3 × 1.2 mm | $2.02 | [DS](https://www.infineon.cn/content/dam/infineon/row/public/documents/24/49/infineon-im69d130-datasheet-en.pdf) |
| Knowles SPH0645LM4H (I²S) | breakout $6.95 | — | [Adafruit](https://www.adafruit.com/products/3421) |

## 5. Trigger

### 5.1 Tactile switches
| Part | Size | Actuation | Sources |
|---|---|---|---|
| **Omron B3U-3000P / -B** | 3.0 × 2.5 × 1.2 mm | side, 162 gf | [DigiKey](https://www.digikey.com/en/products/detail/omron-electronics-inc-emc-div/B3U-3000P-B/1811779) |
| E-Switch TL4110AF160Q | 2.80 × 2.46 mm | side, 160 gf | [DigiKey](https://www.digikey.com/en/products/detail/e-switch/TL4110AF160Q/8021899) |
| C&K PTS841 | 3.6 × 3.5 × 1.25 mm | side | [Mouser](https://www.mouser.in/new/ck-switches/ck-pts841-switches) |
| E-Switch TL3700 / Littelfuse KMT0 | 3 × 2.6 × 0.65 mm | top | [Littelfuse](https://www.littelfuse.com/products/switches/tactile-switches/kmt0) |

A button on a ring suffers accidental presses when gripping; put it palm-opposite and require a long press.

### 5.2 Capacitive touch
Azoteq IQS227 (<2.5 µA, ~$0.11 @3k), Microchip CAP1203 (5 µA sleep), ESP32-S3 built-in touch (18 µA at 1 % duty; Espressif notes limited EMC qualification). On a ring the neighbouring finger is always "touching" — only usable as a deliberate thumb press on the top face with a high threshold.

### 5.3 Accelerometers for tap wake
| Part | Package | Current | Price | Status |
|---|---|---|---|---|
| **ST LIS2DW12** | 2 × 2 × 0.7 mm | ~1 µA | $1.38 @1 | active — **pick** |
| ST LIS2DH12 | 2 × 2 × 1 mm | — | $1.79 | active |
| Bosch BMA400 | 2 × 2 × 0.95 mm | ~850 nA sleep | $2.22 | LCSC: NRND |
| Kionix KX122 / KX022 | 2 × 2 × 0.9 mm | — | ~$2.70 | NRND / LTB |
| ST LSM6DSO (6-axis) | 2.5 × 3 × 0.83 mm | 0.55 mA | €2.72 @5k | active (gyro unnecessary) |

Configure double-tap with a tight latency window and a quiet-period gate; expect to iterate on false positives.

## 6. Precedents
- Haptic Morse: MorseMate (ESP32 + motor) ([hackaday.io](https://hackaday.io/project/191479-morsemate)); THUMP; Medium Machine (TENS). Georgia Tech passive haptic learning taught Morse in ~4 h ([Seim et al.](https://morse.gatech.edu/assets/seimmorse.pdf)). Plan for very short answers at ~5–8 WPM.
- Finger-worn haptics: Guide Ring (KAIST), Haplets, Tactile Ring, HydroRing, HapRing.
- Camera on ring/finger: "Eyes on the Palm" (CHI 2026, ring camera streaming Wi-Fi to a wrist module); CyclopsRing (UIST 2015); EyeRing (MIT 2012); FingerReader 2.0. Every precedent offloads radio/compute to a wrist or pendant module.

## 7. Recommendations

### Stage 1
| Modality | Recommendation |
|---|---|
| **Haptic (primary)** | PMD C08-005 or INEED LRA0825BC-0167F + **DRV2605L** (Adafruit breakout for bring-up). |
| **Light** | WS2812B-2020 under a 1–1.5 mm white-resin window; XL-1010RGBC later. |
| **Air puff** | Optional experiment only: Murata MZB1001T02 as a 22 × 22 mm signet aimed at the adjacent finger. Verify stock. |
| **Audio** | Murata PKMCS0909E4000-R1 (LTB, buy now) from two GPIOs for 4 kHz beeps; or 10 mm PUI speaker + MAX98357A for near-ear TTS. Skip bone conduction. |
| **Mic** | TDK T3902 via PDM. |
| **Trigger** | LIS2DW12 double-tap INT primary; Omron B3U-3000P side switch fallback. |

### Stage 2
| Modality | Recommendation | Feasibility |
|---|---|---|
| **Haptic** | VG0640001D 6 mm LRA (confirm thickness) + DRV2624 DSBGA, or PowerHap 0904H014V060 + BOS1901 WLCSP | Feasible; thickest part after battery |
| **Light** | XL-1010RGBC-WS2812B | Trivial |
| **Air puff** | Not feasible with any purchasable pump | Drop |
| **Audio out** | Not feasible for speech | Drop / signet beeper |
| **Mic** | T3902 | Feasible |
| **Trigger** | LIS2DW12 double-tap only; optional IQS227 pad | Feasible |

### Cautions
- Haptic Morse needs slow strict timing (dot ≥ 80 ms) and a tiny vocabulary; LRA start/stop eats into 60 ms dots.
- NRND/EOL parts surfaced: BMA400, KX122, KX022, Murata PKMCS0909 (LTB), Alps SKRTLAE010, Panasonic 3.0 × 2.0 × 0.6 switches, BOS1901 QFN. Prefer LIS2DW12, DRV26xx, BOS1901 WLCSP.

### Open items
VG0640001D thickness/current; Lee XP height; XL-1010RGBC price/Vf; Eyes-on-the-Palm camera; Boréas BOS1921; ring-specific double-tap false-positive data.
