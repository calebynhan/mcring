# 11. Touch ring: an R1-class controller ring at a fraction of the price

The question: the [Even Realities R1](https://www.evenrealities.com/smart-ring) is a $249 smart
ring whose job is to be a touchpad for the Even G2 glasses, plus health tracking. What would it
take to do everything it does with cheaper parts and materials, and how much of that do we
already have in this repository?

Short answer:

- **The R1 is roughly $20–35 of parts (my estimate) plus licensed health algorithms, sold for
  $249.** Its parts are known in unusual detail because the community has reverse-engineered its
  firmware (§2). Almost all of the $249 pays for brand, software, certification and margin, not
  silicon.
- **The touchpad is cheap. The expensive choices are the ceramic shell, NFC wireless charging and
  licensed health algorithms.** Replace those with a dielectric resin/PC touch arc on a steel band,
  two gold charging contacts, and open algorithms for only the health metrics that are both cheap
  and accurate. That brings the BOM to an estimated **$10–16 for a controller-only ring, or
  $12–20 with health** at 1k units (§5). By the usual 3–5× hardware markup, that is a
  $50–100 product.
- **Health only where it's cheap and accurate:** night-time resting heart rate, RMSSD heart-rate
  variability, a skin-temperature trend and an approximate step count. They need one PPG sensor
  plus parts the ring already carries. Skip SpO2, stress, readiness and calorie scores (§6).
- **The one R1 feature we can't reproduce cheaply is native G2 control.** The G2 only talks to a
  ring that the Even app has paired, so a clone ring would have to impersonate the R1 in front of
  the Even app. That is research, not a plan (§7.3). If your goal is controlling a G2, the R1 is
  the cheapest way to get it. For anything else (phone, laptop, slides, music, and the mcring
  Claude voice ask) our ring does more than the R1 does.
- **It slots straight into this repo.** It is stage 2 without the camera and mic, plus a touch
  slider. The ring-to-phone `EVENTS` channel and the phone/headset-mic push-to-talk path already
  exist (`protocol/ble-gatt.md`). A long press on the touch surface can be reported as the
  existing `BUTTON_DOWN`/`BUTTON_UP`, so the current companions would work unchanged (§7.2).

Confidence tags used below: **Official** (Even's own pages, as quoted by retailers or search
snippets; evenrealities.com itself was not reachable from the research sandbox), **RE** (community
firmware reverse engineering, read directly), **FCC** (filings, as summarised by RE), **Review**
(press), **Est.** (my estimate, not sourced, to be replaced with quotes).

## 1. What the R1 does

| Function | Detail | Tag |
|---|---|---|
| Price | $249, on top of the G2 glasses | Review ([Engadget](https://www.engadget.com/2288658/even-realities-g2-smart-glasses-review/)) |
| Touch control of G2 | Tap = confirm, double tap = back/dismiss, swipe = move through lists, long press = menu, tap-then-hold = a separate menu gesture (firmware ≥ 2.2.9) | Official ([blog](https://www.evenrealities.com/blogs/even-insider/the-grammar-of-a-ring), [support](https://support.evenrealities.com/hc/en-us/articles/13772400722063-How-to-Control)); RE ([decoder](https://github.com/Imba6/even-r1-remote/blob/98217063f84b5dfa39afd10e0d6ee490b680bbf6/even_r1/protocol.py)) |
| Health | Heart rate, HRV, SpO2, skin temperature, steps, calories, distance, sleep; works offline and syncs later; shown in the app and on the G2 display | Official (via [PB Tech](https://www.pbtech.com/pacific/product/MVRERL0014/Even-Realities-R1-Interaction-Ring-Size-10-Touch-C), [Eurooptica](https://www.eurooptica.com/products/even-r1)) |
| Battery | 3–4 days; full charge 20–90 min | Official (support specs, quoted by RE) |
| Charging | NFC (13.56 MHz) wireless charging on a magnetic-alignment dock | Official + FCC |
| Build | Zirconia ceramic exterior, PVD-coated stainless-steel interior, epoxy sensor window; sizes 6–15; IP68 | Official |
| Radio | BLE; the G2 connects to the ring as central; one phone connection at a time; Nordic Secure DFU for updates | RE |
| Haptics | **None.** The firmware's full GPIO and bus map has no motor or haptic driver | RE (inferred from [pinout](https://github.com/kalanihelekunihi/evenRealities-openCFW/blob/55c7582ed30d8770813e9d4b0f448996143e29ca/r1/docs/hardware-pinout.md)) |

What reviewers didn't like: Engadget found taps were read as swipes and swipes as taps often
enough that the reviewer stopped using the menus, and [MobileSyrup](https://mobilesyrup.com/2026/10/19/even-realities-g2s-are-my-new-daily-smartglasses-the-r1-ring-is-clutch)
called it "a little finicky". The R1's weak spot is gesture reliability, not features. That is
where a cheaper ring can also be a better one (§7.1).

## 2. What's inside the R1

From [evenRealities-openCFW](https://github.com/kalanihelekunihi/evenRealities-openCFW/blob/55c7582ed30d8770813e9d4b0f448996143e29ca/docs/hardware/r1-ring.md),
which recovered the bus map from the stock 2.2.6 firmware and cross-checked it against the FCC
filing (2BFKR-R1):

| Block | Part | Notes |
|---|---|---|
| SoC | **Nordic nRF52840** (Bravechip BCL603M module family, hardware string `603MV1.9.3`) | nRF5 SDK 17.1 + FreeRTOS. The GATT base UUID matches Bravechip's "ChipletRing" SDK, so the R1 is built on an ODM smart-ring platform |
| Touch | **Azoteq IQS7211E** trackpad controller, run as a 1-D slider | Long-press threshold 1000 ms |
| Optical | **Goodix GH3x2x** PPG front end: green + IR (HR/HRV), red (SpO2), wear detection | Goodix algorithm libraries, binary-only |
| Temperature | 2 × GXCAS GXT310 digital sensors | Official page says "NTC" |
| Motion | LIS2DW12, BMA456W or QMA6100 (firmware probes all three; which one is fitted is unknown) | |
| Charging | **ST25DVxxKC** NFC tag with energy harvesting + 13.56 MHz coil; YHMICROS **YHM2710** charger/PMIC | The dock is an NFC reader |
| Battery | 3.8 V **21 mAh** (JL136235) or **16 mAh** (JL136228), presumably by ring size | From the FCC report |
| Antenna | FPC antenna, −2.46 dBi; BLE TX power −6 dBm | From the FCC report |
| Health algorithms | **GoMore SDK** (sleep, energy, stress) | Licensed |

## 3. Where the $249 goes (estimate)

No teardown cost analysis was found. These are my estimates at roughly 1k–10k units, using the
same price basis as §5:

| Block | Est. cost |
|---|---|
| nRF52840 | 2.33 (LCSC at 1k, from `docs/research/02`) |
| IQS7211E | ~0.52 (DigiKey CA$0.71 at 1k) |
| Goodix PPG front end + LEDs + photodiode | 1.5–3 (Est.; Goodix quotes under NDA) |
| 2 × temperature sensor, accelerometer, NFC tag, PMIC | 1.2–2.5 (Est.) |
| Curved 16–21 mAh cell | 2–3 (Est.) |
| Flex PCB + assembly | 3–5 (Est.) |
| Zirconia ceramic shell + PVD steel liner + epoxy | 5–12 (Est.) |
| NFC charging dock (reader IC, MCU, magnets, USB-C) | 4–7 (Est.) |
| GoMore / Goodix algorithm licences | unknown |
| **Total** | **≈ $20–35 + licences** |

That is about 10–15 % of the retail price. The rest pays for brand, software, certification,
returns and margin. That's normal for consumer hardware, and it is the room a cheaper product
works in.

## 4. Block-by-block: R1 choice → our cheaper choice

| Function | R1 | Ours | Saves | Trade-off |
|---|---|---|---|---|
| SoC | nRF52840 module | **nRF52840** (same chip; already this repo's stage-2 part, with a Zephyr skeleton in `firmware/ring-nrf52840`) | ~0 (an nRF52832/nRF54L-class part would save about $0.5–1, Est.) | none; keeps one code base |
| Touch | IQS7211E slider | **IQS7211E** (same, about $0.52) + accelerometer tap confirmation | 0 | sourcing: DigiKey showed 0 stock and a 16-week lead time, so qualify a second source early (§9) |
| Shell | Zirconia ceramic + PVD steel | **316L steel inner band + polycarbonate or epoxy touch arc + epoxy potting**; SLA resin for prototypes | $4–10 (Est.) | resin and PC scratch; a hard-coat helps (§4.1) |
| Charging | NFC energy harvesting + reader dock | **2 gold contacts + magnetic pogo dock** (as on stage 1) | $4–7 (Est.) | exposed contacts need gold plating, a TVS and reverse-polarity protection; IP68 comes from potting |
| PMIC | YHM2710 | **TI BQ25100** (1 mA termination, already chosen in `stage2-oura-size.csv`) | ~0 | |
| Health | Goodix AFE + GoMore + 2 temperature sensors | **optional**: one PPG front end + one NTC, open algorithms, fewer metrics (§6) | $2–5 + licences | fewer, honest metrics |
| Haptics | none | optional LRA tick on the oversized ring; skip at Oura size | n/a (adds cost) | |
| Firmware updates | Nordic Secure DFU | MCUboot / Nordic DFU (free) | 0 | |
| Sizes | 10 sizes (6–15), 2 cells | one flex and one cell; **3 band sizes** at launch, with printed per-size shells for prototypes | inventory | |

### 4.1 Materials: why the shell can't simply be metal

Capacitive touch needs a **dielectric** over the electrodes. A metal ring (Oura's titanium, the
Colmi's steel) can't carry a touch surface, which is why the R1 uses ceramic. Ceramic is the
premium dielectric: scratch-proof and RF-transparent. Cheaper dielectrics, from prototype to
product:

1. **SLA tough resin** (prototype): print per size, which the stage-1 CadQuery model already
   does. 0.6–1.0 mm over the electrodes. A few dollars per ring.
2. **Overmolded or cast epoxy** (Oura-style fill) or **injection-molded PC / PA12** with a UV
   hard-coat: cents per part, but a tool per size family.
3. **Hybrid (recommended for product): a 316L stainless inner band** (comfort, strength, cheap
   to stamp or turn) with a **dielectric arc over the top 120°** where the slider lives. Put the
   electrodes on the flex's outer copper layer and a driven shield/ground on the inner layer, so
   the steel band and the finger underneath don't swamp the signal. Leave a clear epoxy window
   in the band for the PPG if it is fitted.

### 4.2 Charging: contacts instead of NFC

The R1's NFC charging is elegant: the ring is fully sealed and needs only a tag chip and a coil.
But it needs an NFC reader, an MCU and magnets in the dock. Two gold-plated contacts in the inner
band and a magnetic pogo cradle cost cents on the ring and about $1–2 for the dock. This is what
cheap rings such as the Colmi R02 do, and what `hardware/bom/stage1-ring.csv` already specifies.
Charge time is set by the cell's ~1C limit either way, so it stays comparable to the R1's 20–90 min.

## 5. BOM for our ring

Full line items with sources: [`hardware/bom/touch-ring.csv`](../hardware/bom/touch-ring.csv).

| Block | Part | 1 pc | 1k (Est.) |
|---|---|---|---|
| BLE SoC | nRF52840 (QFN48 or WLCSP) | 3.83 | 2.33 |
| Crystal, passives, TVS | 32 MHz crystal, ~20 passives, TVS on the contacts | ~1 | ~0.30 |
| Touch | IQS7211E | ~1.05 | ~0.52 |
| Accelerometer | LIS2DW12 (QMA6100 as a cheaper second source) | 1.38 | 0.3–0.7 |
| Charger | BQ25100 | 1.0 | ~0.5 |
| Cell | 16–22 mAh curved LiPo | sample | 1.5–3 |
| Flex PCB + SMT | 2-layer flex, printed antenna, slider electrodes | 100–300 per batch | 2–4 |
| Charging contacts | 2 gold pads + spring inserts | — | 0.1–0.3 |
| Shell | 316L band + PC/epoxy arc + potting (SLA resin for prototypes) | 2–15 | 1.5–4 |
| Dock | Pogo pins + magnet + USB-C board | 5–10 | 1–2 |
| **Controller-only total** | | | **≈ $10–16** |
| *Health add-on* | PPG front end + LEDs + photodiode, NTC, epoxy window | | *+ $1.5–3.5* |
| **With health** | | | **≈ $12–20** |

Rule of thumb (not a sourced figure): retail is about 3–5× BOM once certification, returns,
support and margin are paid for. That puts this ring at **$50–100** against the R1's $249. The
floor is set by commodity rings: a Colmi R02 with PPG, accelerometer, battery and dock retails
for about $20–35 ([HN](https://news.ycombinator.com/item?id=41833200),
[Notebookcheck](https://www.notebookcheck.com/Colmi-Dieser-smarte-Ring-ist-guenstig-und-in-Deutschland-erhaeltlich.855496.0.html)).
At volume, an ODM ring platform with our touch flex added may beat a fully custom build; that
needs quotes (§9).

### 5.1 Battery life (estimate, to be measured)

Assumed average current, controller only: nRF52840 with RTC 1.5 µA, a BLE connection held at a
~100 ms interval with slave latency ~10–20 µA, IQS7211E in its low-power scan mode ≤ 40 µA
(**check the datasheet; this is the largest unknown**), and accelerometer ~1 µA. That totals
about 55–65 µA, or about 11–14 days on 16–22 mAh. Halving that for margin still gives **about
1 week**, double the R1. Adding night-long PPG and daytime spot checks costs roughly another
100–300 µA (Est.), which brings it back to the R1's 3–5 days. Measure all of this with a PPK2
before quoting it to anyone.

## 6. Health: only what is cheap and accurate

The health sensors are cheap (one PPG front end plus a few LEDs, about $2–3). What isn't cheap is
**accurate algorithms and validation**: the R1 licenses GoMore's and Goodix's. The rule here:
ship a metric only if the hardware is nearly free **and** there is published evidence that a
finger PPG can measure it well.

| Metric | Extra cost | Evidence | Verdict |
|---|---|---|---|
| Night-time resting HR | the PPG front end | Finger-ring HR at night matches chest ECG with low bias ([Oura vs ECG, 35 adults](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8808342/); [Dial 2025](https://physoc.onlinelibrary.wiley.com/doi/10.14814/phy2.70527): Oura Gen 4 CCC 0.96) | **Include** in the health variant |
| HRV as RMSSD, night | same sensor | Same studies: RMSSD accurate per 5-minute window and per night; **frequency-domain HRV (LF/HF) is not** | **Include RMSSD only** |
| Skin-temperature trend | NTC thermistor, about $0.02 | A relative night-to-night change is what rings report; it is not body temperature | **Include**, labelled as a trend |
| Steps | $0, because the accelerometer is already there for tap confirmation | Finger motion is noisy. No validation found for cheap rings | Include, labelled approximate. **Drop calories and distance** |
| Sleep | $0 (motion + HR) | Staging requires validated algorithms (the R1 licenses GoMore's) | Time asleep only, no stages |
| Wear detection | $0 (touch baseline or PPG) | n/a | Include |
| SpO2 | red LED channel + a controlled-hypoxia calibration study | Achievable at rest only after calibration: the Evie ring reached 2.5–2.8 % RMSE in a sponsored study ([JMIR 2024](https://formative.jmir.org/2024/1/e54256)). That study is the expensive part | **Skip** |
| Stress / energy / readiness scores | licence | Proprietary composites, no ground truth | **Skip** |

Two caveats:

1. **The validated numbers are Oura's algorithms, not ours.** A finger PPG can be accurate; our
   firmware isn't yet. The health variant ships only after we have checked it ourselves against a
   chest strap (Polar H10 class) or an ECG-validated device, over at least 10 nights.
2. **A $20 Colmi R02 is the quickest test of "is cheap health good enough?"** It has a VCare
   VC30F PPG, an STK8321 accelerometer and a 17 mAh cell
   ([ATC_RF03_Ring](https://github.com/atc1441/ATC_RF03_Ring/tree/7b2e78e0e9f42b7cec95dd1e733670f533089bbb)),
   and pairs with [Gadgetbridge](https://gadgetbridge.org/gadgets/rings/yawell/) without the
   vendor app. Wear it next to a chest strap for a week before spending anything on PPG design.
   Gadgetbridge warns that some R02/R03/R06 units ship with different hardware it doesn't
   support.

Design rule: lay out the PPG footprint and sensor window on every flex but leave them **not
populated** in the controller-only build. One board then gives two products, and the health
decision can wait for the Colmi data.

## 7. Making the gestures do something

### 7.1 Gestures that work better than the R1's

Keep the R1's vocabulary (tap, double tap, swipe forward/back, long press, tap-then-hold). It is
what a 1-D strip can do. Then fix the reliability complaint with parts we already carry:

- **Accelerometer confirmation.** A real tap puts a short impulse on the accelerometer; a swipe
  doesn't. Report a tap only when the touch event and an impulse coincide (window about ±30 ms,
  to be tuned), and a swipe only when the slider travel passes a threshold with no impulse. This
  costs no extra hardware.
- **Per-user tuning** in the app: swipe distance, tap timeout, long-press time (the R1 fixes
  this at 1000 ms).
- **A haptic tick on recognition** on the oversized ring, which has room for an LRA. The R1 has
  no motor at all.
- **Logging before guessing.** The firmware streams raw slider position and impulse flags in a
  debug mode. Tune on recorded trials, the way the community R1 capture tool does. Target: at
  least 95 % correct over 100 trials of each gesture before a wearable build.

### 7.2 Three ways out of the ring

1. **BLE HID (no app needed).** The ring is also a standard Bluetooth keyboard / consumer-control
   / mouse-wheel device, so swipes become arrow keys, page up/down or scroll, and taps become
   play/pause or Enter, on any phone, tablet or laptop. The nRF Connect SDK HID samples cover it.
   This is the "R1 without the G2" use the community built
   [for Windows](https://github.com/Imba6/even-r1-remote), but here it is native.
2. **mcring `EVENTS` (our app and CLI).** The same GATT connection carries the existing `EVENTS`
   characteristic (0007). **Report a touch long press as `BUTTON_DOWN` / `BUTTON_UP`**, so it
   behaves exactly like the stage-0/1 button. With `MIC_SOURCE_HINT = 1` the phone records from
   your headset mic between the two events and Claude answers in your ear. That works with the
   existing companions unchanged. Proposed new event IDs (not implemented yet): `12 TAP`,
   `13 SWIPE` (arg 0 = forward, 1 = back), `14 TAP_HOLD`. Existing `3 DOUBLE_TAP` keeps its
   meaning. This is the voice ask the R1 doesn't have.
3. **Even G2 glasses**: see 7.3.

### 7.3 Even G2 compatibility (research only)

What is known (RE): the G2 is the BLE **central** and connects to a ring whose MAC address the
Even phone app hands it during pairing. It then discovers the R1's `BAE8…` service and subscribes
to its notifications. R1 gestures arrive as 11-byte frames `00 09 61 00 <code> <u16> <u32 tick>`
(codes 0 hold, 1 tap, 2 double, 4/5 swipe, 8 release, 9 tap-then-hold); see the
[decoder](https://github.com/Imba6/even-r1-remote/blob/98217063f84b5dfa39afd10e0d6ee490b680bbf6/even_r1/protocol.py)
and the [G2-side ring client](https://github.com/kalanihelekunihi/evenRealities-openCFW/blob/55c7582ed30d8770813e9d4b0f448996143e29ca/g2/docs/reference/protocols.md).

What blocks a clone: the **Even app's pairing flow**. The app talks to the ring in its phone
role (`pairAuth` and friends, only partly documented) before it ever tells the G2 the ring's
MAC. Impersonating the R1 there is unproven, would break with any Even firmware or app update,
and is reverse engineering for interoperability, so get advice before shipping anything that
does it.

A legitimate partial route: the [Even Hub SDK](https://hub.evenrealities.com/docs/getting-started/overview)
runs third-party G2 apps as web apps inside the Even app. **Our own** G2 app could receive our
ring's gestures through our backend (ring → mcring app → backend → G2 web app) and display
mcring/Claude answers on the glasses. This drives our app's screens, not the G2 system menus.
Unverified; it depends on what the Hub WebView allows.

## 8. Build path

| Phase | What | Cost | Answers |
|---|---|---|---|
| **A. Health reality check** (1 week) | Colmi R02 + Gadgetbridge, worn next to a chest strap or an ECG-validated device you already have | ~$20–35 | Is cheap-ring HR/HRV good enough to bother with? Decides whether the PPG gets populated |
| **B. Bench controller** (2–3 weeks) | XIAO nRF52840 Sense (about £16, [Pi Hut](https://thepihut.com/products/seeed-xiao-ble-nrf52840-sense); on-board IMU for tap confirmation) + an Azoteq IQS7211E evaluation kit (the sister IQS7211A kit is $49, [Future](https://futureelectronics.com/p/development-tools--dev-tools-sensors/iqs7211aev02a-s-azoteq-5187564)); firmware: HID + `EVENTS` + gesture logging | ~$70–100 | Gesture accuracy target (≥ 95 %), HID on iOS/Android/desktop, a voice ask through the existing app |
| **C. Oversized wearable** (1 month) | Same parts on a small board riding on a resin band (reuse the stage-1 CAD and pogo charging) | ~$60–120 per ring at 5 units | On-finger touch through 0.8 mm resin, real battery life, a week of daily use |
| **D. Oura-size flex** (multi-spin) | Stage-2 flex without the camera and mic: slider electrodes on the outer layer, shield inside, optional PPG window | ~$200–500 per prototype (as in `stage2-oura-size.csv`) | Fit, IP68 by potting, final BOM and quotes |

Phases A and B don't depend on each other and can run in parallel.

## 9. Risks and open questions

- **IQS7211E supply.** Qualify a second touch option during phase B: another Azoteq slider part,
  or a few discrete electrodes on a multi-channel cap-touch IC with firmware interpolation.
- **Curved cells** come with MOQs and NDAs (Grepow). A flat 301012-class cell is fine for phases
  B and C.
- **IP68 and radio certification**: potting gets the ring watertight, but claiming "IP68" means
  a lab test, and a ring with its own antenna needs its own FCC/CE testing. Get quotes before
  quoting a retail price.
- **Health claims stay wellness-only**: no SpO2, no medical language.
- **Ring sizing**: one flex has to fit the smallest band. Confirm the slider electrodes still sit
  under the touch arc across the 3 band sizes.
- **ODM route**: the R1 itself is built on an ODM platform (Bravechip). Ask an ODM for a quote
  on their ring module plus our touch flex before committing to a custom board for volume.
