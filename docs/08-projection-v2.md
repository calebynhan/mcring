# 8. Projection from the ring (v2 idea) — feasibility note

> Research pass from web-search snippets; direct page fetches (TI PDFs etc.) were blocked by the
> sandbox, so **[unverified]** marks a number that could only be read from a snippet or recalled
> from memory. Nothing here is in v1 scope. v1 is voice-first: ring button → question (+ photo)
> → spoken answer, haptics as confirmation cues only. This note answers one question: *could a
> later ring project visuals onto a wall, and if not, what is the nearest thing that could?*

## TL;DR

1. **Full-image projection from a ring is not plausible in this project.** The smallest
   complete image engines that exist are watch-sized (≈ 1.6–12 cc, 25–50 mm long), draw
   1.5–7 W, and still need a dim room. A 30–40 mAh ring cell holds ≈ 0.11–0.15 Wh and cannot
   source 400 mA; the ring would run a 1.5 W engine for ~3 minutes if it ran it at all, and
   would hit the 43 °C skin-contact limit first. Humane shipped the closest thing (a 34 g,
   $699 chest pin with a 720p Class-2 laser display) and it was criticised for being hard to
   read in daylight and for overheating; it was discontinued in February 2025.
2. **A laser *pointer* is plausible, cheap, and already wired.** A Ø3.3–6 mm laser module
   draws 20–30 mA, fits the stage-1 ring, and can hang off the existing aux pads (`PIN_AUX`
   IO9 → Q1 AO3400 → J2). One 2-second "point" costs ~14 µAh, a tenth of a photo. A 1 mW red
   dot is ~10,000 lux at 1 m — visible in any indoor light, which no projector at this size
   can say.
3. **Vector glyphs (arrow, circle, digit) with a 1–2 mm MEMS mirror are the stretch goal**, not
   raster images: a 1 mW beam drawn as a 25 cm arrow gives ~300 lux (red) / ~1,900 lux
   (green) on the wall, enough indoors; the same milliwatt spread over a 7 × 10 cm image is
   ~70 lux, below room light.
4. **Eye safety is the gating constraint, not optics.** A hand-worn emitter sweeps across other
   people's faces. Design to **Class 1 (≤ 0.39 mW visible CW) [unverified exact AEL]**, the
   class the EU requires for toys, and treat Class 2 (1 mW) as the ceiling even in experiments.
   Prefer a 520 nm green diode: at equal power the eye sees it ~6.6× brighter than 650 nm red,
   so a Class-1 green dot out-shines a Class-2 red one.
5. **Recommended v2 experiment:** an aimed pointer along the camera axis, firmware-interlocked
   to the button, the IMU, and a phone-side face detector. ≈ $5 of parts plus a laser power
   meter. Start it only after the v1 voice loop has been used daily for a few weeks and the
   "did the camera see what I meant?" failure rate has been measured (§5).

---

## 1. What exists at the small end

### 1.1 Humane AI Pin "Laser Ink Display" (2023–2025)

The only shipped consumer device that projected an interface from a small wearable.

| Item | Value | Source |
|---|---|---|
| Form | chest pin, 47.5 × 44.5 × 15.0/8.25 mm, **34.2 g** (+ 20.5 g battery booster), **$699** | [iFixit](https://www.ifixit.com/Device/Humane_AI_Pin), [The Decoder](https://the-decoder.com/humanes-ai-pin-is-a-curious-ai-wearable-with-a-hefty-price-tag/) |
| Display | **720p**, monochrome green, "custom single-diode" laser, **498 nm**, **Class 2**, **25 mW peak emission** (scanned; time-averaged exposure is what sets the class) | iFixit |
| Geometry | works at **20–40 cm**, FOV **18.2° × 13.3°**; ≈ **7 × 9.6 cm** image at 30 cm | iFixit, [china-gadgets](https://www.china-gadgets.de/humane-ai-pin/) |
| Module | internal name "LunarSky", described as very small in FCC photos; dimensions and power not published | [Notebookcheck](https://www.notebookcheck.com/Humane-Ai-Pin-Teardown-enthuellt-veraltete-Hardware-Easter-Eggs-und-winzigen-Akku-im-teuren-KI-Gadget.824560.0.html) |
| Battery | ~1,290 mAh @ 3.45 V (≈ 4.5 Wh) **[unverified aggregator figure]**; "2000 nits" claim **[unverified, no source]** | [wifitalents](https://wifitalents.com/humane-ai-pin-statistics/) |
| Criticism | "not bright enough to be readable in direct sunlight"; display use "triggered heat problems… needed cooldowns after a few minutes"; one review counted four overheats in 30 min | [ZDNet roundup](https://www.zdnet.com.au/article/humane-ai-pin-reviews-5-takeaways-on-a-promising-but-dangerously-flawed-wearable/), [appfind](https://appfind.beehiiv.com/p/humane-ai-pin-reality-check-the-700-wearable-that-overheats-every-30-minutes-brutally-honest-review) |
| Fate | HP bought Humane's assets Feb 2025; the Pin was excluded and switched off 28 Feb 2025 | iFixit, [Wikipedia](https://en.wikipedia.org/wiki/Humane_Inc.) |

Why it was criticised, in our terms: it projected onto the *palm* at 20–40 cm (the only surface
a wearable can guarantee), monochrome, and still ran out of thermal headroom in a 34 g body
with ~40× the battery energy a ring can carry. The palm-only geometry also killed the
"projects onto a wall" idea before launch — at 1 m the same 18° beam is a 32 cm patch and the
illuminance drops ~11×.

### 1.2 TI DLP Pico — the smallest DMD chipsets

| Chipset | DMD | Optical engine | Brightness | Price points | Source |
|---|---|---|---|---|---|
| **DLP2000** (0.2", nHD 640×360) | package ≈ 14 × 5 mm | reference engine **30 × 30 × 9 mm (8.1 cc)** [snippet of TI slide] | up to **20–30 lm**; EVM default LED 320 mA ≈ 20 lm | **DLPDLCR2000EVM $99** (54 × 76 mm board); **DLPM2000EVM engine $49**; Alibaba modules "$13–22" **[unverified buying guide]** | [LinuxGizmos](https://linuxgizmos.com/tis-99-dlp-pico-projector-board-connects-to-beaglebone-black/), [TI DLPM2000EVM](https://www.ti.com/product/DLPM2000EVM/part-details/DLPM2000EVM), [TI E2E](https://e2e.ti.com/support/dlp-products-group/dlp/f/dlp-products-forum/847558/dlpdlcr2000evm-power-consumption-and-weight), [Alibaba guide](https://electronics.alibaba.com/buyingguides/led-dlp-micro-projector-module-guide) |
| **DLP160CP** (0.16", nHD/HD) | **13.39 × 4.97 × 3.18 mm** | Gen-2 engine **32.5 × 10.6 × 4.8 mm (1.65 cc)**, side-lit — the smallest full-image engine found | chipset "up to 300 lm" (system spec, not this engine) | LightCrafter 160CP EVM 66 × 56 mm; price not found | [TI DLP160CP](https://www.ti.com/product/DLP160CP), [TI SPRPEA6](https://www.ti.com/jp/lit/ml/sprpea6/sprpea6.pdf), [TI DLPU131](https://www.ti.com/lit/ug/dlpu131a/dlpu131a.pdf) |
| **DLP230NP** (0.23", 1080p) | — | EVM 81 × 87 mm; engine size not found | up to **100 lm** | price not found | [TI DLPDLCR230NPEVM](https://www.ti.com/tool/DLPDLCR230NPEVM) |
| **DLP3010** (0.3", 720p) | — | reference engine **94 × 50 × 25 mm** (DLPA079) | 300 lm class | EVM-G2 **≈ €1,121 ex VAT** (RS NL) | [TI DLPA079](https://www.ti.com/lit/an/dlpa079/dlpa079.pdf), [RS](https://nl.rs-online.com/web/p/display-development-tools/2659764) |
| DLP230GP, Young Optics / Anhua engines | **not found in any snippet** — treat all third-party engine sizes as unknown | | | | — |

TI's own target for a "thin" module is 25 × 25 × 6 mm (DLPA078, snippet). Power: the DLP2000 EVM
is specified for a 5 V / 3 A supply; at the default 320 mA LED drive the LED alone is ≈ 1 W and
the controller + PMIC add a few hundred mW, so **≈ 1.5–2 W for ~20 lm ≈ 10–13 lm/W
[derived, not measured]**.

### 1.3 Laser-beam-scanning (LBS) engines and MEMS mirrors

| Item | Size | Power / brightness | Source |
|---|---|---|---|
| MicroVision PicoP (2008) | **42 × 20 × 7 mm, 20 g** | "as little as 3 W", 1.5 W target for embedded | [MicroVision PR](https://ir.microvision.com/news/press-releases/detail/201/microvision-completes-design-of-new-picop-laser-display) |
| MicroVision PSE-0403-101 (2017, 720p) | **36 × 53 × 6 mm, 11.6 cc** | "up to 401 lm" **[unverified metric]**; power not found | [opli](https://opli.net/opli_magazine/eo/2016/microvision-begins-shipping-samples-to-customers-of-its-small-form-factor-display-engine-dec-news) |
| Sony MP-CL1 (2015, LBS, 1920×720) | phone-sized, 0.2 kg | **32 lm**, laser output 206 mW, 5 V/1.5 A, 3,400 mAh for 2 h ⇒ **≈ 6 W average [derived]** | [Sony NZ](https://store.sony.co.nz/projector-portable/MPCL1AN.html), [ProjectorCentral](https://www.projectorcentral.com/sony-mp-cl1.htm) |
| LumiWatch (CMU, CHI 2018) — the smallest *wearable* projector actually built | engine **25.8 × 16.6 × 5.2 mm**; watch body 50 × 41 × 17 mm | **15 lm**, 1024×600, 39° × 22.5°; **2.7 W max**; 740 mAh ⇒ **~1 h continuous** | [TechXplore](https://techxplore.com/news/2018-04-arm-smartwatch-touchscreen.html), [eeNews](https://www.eenewseurope.com/en/smart-watch-expands-touch-display-to-the-skin/) |
| Hamamatsu S13989-01H 2-axis MEMS mirror | **Ø1.23 mm** mirror, electromagnetic | ±20° fast / ±12° slow optical | [Hamamatsu](https://www.hamamatsu.com/content/dam/hamamatsu-photonics/sites/documents/99_SALES_LIBRARY/ssd/s13989-01h_koth1009e.pdf) |
| Mirrorcle 2-axis MEMS mirrors | **0.8 / 1.2 / 1.6 / 2.0 / 2.4 mm** in stock; 1.2 mm scan module gives 40° × 40° FOV | actuators **< 1 mW**; electrostatic ⇒ needs a ~100+ V bias driver **[unverified]**; quasi-static (vector) or Lissajous modes; dev kits quote-based (expect $k) | [Mirrorcle](https://www.mirrorcletech.com/wp/products/mems-mirrors/), [FindLight](https://findlight.net/optical-systems/adaptive-optics/deformable-mirrors/mirrorcle-technologies-mems-mirrors) |
| ST LBS (STAR0/STAR1, LaSAR alliance) | AR-glasses engines; sizes not public | thin-film piezo mirror, "15 % less power than STAR0" | [ST newsroom](https://newsroom.st.com/media-center/press-item.html/t4297.html), [edge-ai-vision](https://www.edge-ai-vision.com/2022/10/stmicroelectronics-demonstration-of-laser-beam-scanning-for-ar-glasses-and-beyond/) |

Two facts matter for a ring: the *mirror* can be 1 mm, but every complete raster engine is still
≥ 1.6 cc because it needs three laser diodes, beam combining, a fold and a driver board; and
even the best (LumiWatch, 15 lm at 2.7 W ≈ 5.5 lm/W) is less efficient than LED-DLP.

### 1.4 Finger- and ring-worn projectors: prototypes, patents, vaporware

* **Patents only, no built finger projectors found.** US 9,477,146 "Projection ring" (projector on a
  telescopic arm), US 10,372,160 "Ring shaped wearable device having projector", US 2016/0261834
  "Wearable projection equipment" (two rotating projectors). None reports a working unit.
  ([Google Patents](https://patents.google.com/patent/US9477146),
  [US10372160](https://patents.google.com/patent/US10372160),
  [Justia](https://patents.justia.com/patent/20160261834))
* **Cicret bracelet (2014)** — the viral "project your phone onto your arm" video. Snopes: no
  working prototype existed; a co-founder later called the video "a mockup not representative of
  any functional prototype". ([Snopes](https://www.snopes.com/fact-check/do-you-want-to-know-a-cicret/))
* **Ritot projection watch (2014)** — ~$1.4 M from 7,828 Indiegogo backers, no prototype before
  launch, not shipping two years later, campaign later "under review"; refunds started then
  stalled. ([Indiegogo](https://indiegogo.com/projects/ritot-the-first-projection-watch),
  [Wareable](https://www.wareable.com/wearable-tech/worse-for-wear-the-worst-wearable-crowdfunding-campaigns-865),
  [ABC7](https://abc7chicago.com/post/crowdfunding-highs-and-lows-of-adventure-capital-/908651/))
* **Real research wearables used pocket/shoulder projectors**: SixthSense (MIT, pendant with a
  pocket projector, < $350 of parts) and OmniTouch (CMU/MSR 2011, shoulder-worn laser pico
  projector + depth camera, ~15 lm ShowWX-class). ([MIT Media Lab](https://www.media.mit.edu/publications/sixthsense-a-wearable-gestural-interface-2/),
  [CMU](https://www.cmu.edu/news/stories/archives/2011/october/oct17_omnitouch.html))
* **Rings with lasers do exist — as pointers.** Genius Ring Presenter, Delton P48, Kokuyoseki
  (32 mm ring, 12 g with battery), assorted "finger ring clicker" products, typically < 5 mW
  Class 3R red. ([Ubergizmo](https://www.ubergizmo.com/2012/01/genius-ring-presenter/),
  [Best Buy](https://www.bestbuy.com/product/delton-p48-2-4ghz-wireless-presentation-finger-laser-pointer-dlp48-black/J38PCKS9V6/sku/10148158))
* **Fixed-glyph laser projection has shipped**: the Celluon laser keyboard draws a 241 × 106 mm
  keyboard with one red diode and a diffractive optical element (DOE) from a lighter-sized
  box. ([Wikipedia](https://en.wikipedia.org/wiki/Projection_keyboard))

---

## 2. Physics for a ring

### 2.1 Brightness: lumens → lux on the wall

1 lux = 1 lm/m². Spread over a **10 × 10 cm patch (0.01 m²)**, **1 lm ⇒ 100 lux**; over
Humane's 7 × 9.6 cm palm patch, 1 lm ⇒ ~150 lux. The AV rule of thumb is
*lumens = area × ambient lux on the surface × desired contrast*, with 10:1 "good" and ~3:1 the
floor of legibility ([Troikatronix forum quoting AV Magazine](https://community.troikatronix.com/post/34245)).
Offices are lit to ~300–500 lux on the desk **[standard values, not re-verified]**; a vertical
wall sees perhaps a third to a half of that.

| Scene (lux on the wall) | 10 cm image, 3:1 | 10 cm image, 10:1 |
|---|---|---|
| dim living room, 50 lux | 1.5 lm | 5 lm |
| office wall, 150 lux | 4.5 lm | 15 lm |
| shade outdoors, 2,000 lux | 60 lm | 200 lm |
| sunlight, 50,000+ lux | hopeless | hopeless |

So even the *idea* of a 1-lumen ring projector only works in a dim room, and nothing at 1 lm is
sold; the smallest engines are 15–30 lm because that is the minimum useful indoors.

**A pointer is a different regime.** Monochromatic flux = 683 lm/W × V(λ) × power, with
V(650 nm) ≈ 0.107 and V(520 nm) ≈ 0.71 ([Wikipedia](https://en.wikipedia.org/wiki/Luminous_efficiency_function)):

| Beam | Flux | 3 mm dot at 1 m (7 mm²) | 8 mm dot at 5 m (50 mm²) | 25 cm × 1 mm drawn arrow (250 mm²) | 7 × 9.6 cm raster |
|---|---|---|---|---|---|
| 1 mW red (Class 2) | 0.073 lm | **10,300 lux** | 1,460 lux | 290 lux | 11 lux |
| 0.39 mW red (Class 1) | 0.028 lm | 4,000 lux | 570 lux | 110 lux | 4 lux |
| 1 mW green (Class 2) | 0.485 lm | **68,600 lux** | 9,700 lux | **1,940 lux** | 72 lux |
| 0.39 mW green (Class 1) | 0.189 lm | 26,700 lux | 3,800 lux | **760 lux** | 28 lux |

Read across: a Class-1 green **dot** beats daylight shade; a Class-1 green **glyph** is readable
on an office wall; a Class-2 **raster** image is invisible in the same room. That is the whole
story of why Humane needed 25 mW peak and a palm at 30 cm.

### 2.2 Power vs. a 30–40 mAh cell

* Energy: 30 mAh × 3.7 V = **0.111 Wh = 400 J** (40 mAh: 530 J); usable ~80 %.
* Full-image engine at the LumiWatch/DLP2000 level, **1.5–2.7 W**: 320 J ÷ 1.5 W ≈ **3.6 min**,
  ÷ 2.7 W ≈ **2 min** — *if* the cell could deliver it. 1.5 W / 3.7 V = **405 mA ≈ 13 C** on a
  30 mAh cell rated ~1 C (10 C on 40 mAh). It cannot; the rail browns out, as the 300 mA camera
  peaks already threaten (`hardware/power-budget.txt`). A 100 mAh cell gets ~12 min at 4 C.
* Laser pointer module, red 1 mW class: **20–30 mA at 3 V ≈ 75–90 mW** (Olimex 5 mW module 25 mA;
  Photonic Products 0.9 mW module 30 mA typ) ([Olimex](https://olimex.com/Products/Components/LEDs/LASER-650nm),
  [Photonic Products](https://www.webwire.com/ViewPressRel.asp?aId=5283)). A **2 s point = 25 mA × 2 s ≈ 14 µAh**,
  ~9 % of the 154 µAh a photo costs; **~1,000 points per charge** on top of normal use; 1.2 h
  if left on continuously.
* Green direct diode (e.g. Osram PLT5 520, 10 mW at 60 mA) throttled to < 1 mW sits near its
  lasing threshold and drifts with temperature ⇒ needs automatic power control; expect
  **40–60 mA ≈ 150–250 mW [estimate]**. ([DigiKey listing via search](https://www.digikey.com/en/products/filter/laser-diodes-modules/95))
* MEMS vector projector: mirror actuation < 1 mW (Mirrorcle), but HV bias generation, a DAC
  pair and the laser bring it to **~150–300 mW [estimate]** — 20–40 min continuous on 30 mAh,
  acceptable in 2–5 s bursts.

### 2.3 Thermal

A printed 30 mm ring has ~10–15 cm² of exposed surface; natural convection ≈ 10 W/m²·K gives
~0.015 W/K, so **1.5 W would settle ~100 K above ambient** — i.e. never settles; it is burst-only.
Heat capacity (≈ 5 g resin + cell + board ≈ 8–10 J/K) means a 30 s burst at 1.5 W adds ~5 K
*averaged*, far more at the engine. Skin-contact wearables are held to **≈ 43 °C** for prolonged
contact (IEC 60601-1 / ISO 13732-1 class limits **[from memory]**), leaving roughly a minute of
projector time from a 25 °C start. Humane throttled at 34 g; a 5 g ring is worse. The pointer
dissipates ~80 mW and is a non-issue (`docs/04` thermal note already allows 0.5 W for a second).

### 2.4 Size

Stage-1 ring: ~30 mm OD × 12 mm wide, 24 mm board cavity, camera pod (`hardware/cad/`).

| Candidate | Envelope | Fits stage 1? | Fits Oura-size (8 × 3 mm band)? |
|---|---|---|---|
| DLP160CP engine | 32.5 × 10.6 × 4.8 mm | **No** (longer than the ring OD) | No |
| LumiWatch LBS engine | 25.8 × 16.6 × 5.2 mm | No (would be the whole ring + more) | No |
| MEMS mirror (Ø1.2 mm) + 1 laser diode + fold + driver | ~8 × 8 × 6 mm pod **[estimate]** | Marginal, as a signet pod | No |
| Laser dot module Ø3.3 × 7 mm (LC-LMD) or Ø4 × 10 mm (generic) | 0.06–0.13 cc | **Yes**, beside the camera | Borderline (a 4 mm pod is already the plan for the camera) |
| Laser + DOE glyph head | Ø6–12 mm × 20–38 mm as sold | No as sold; DOE itself is a few mm | No |

([Laser Components LC-LMD](https://lasercomponents.com/us/photonics-portal/news/the-smallest-oem-laser-modules-the-lc-lmd-series),
[eBay 4 mm module](https://www.ebay.com/p/20031539964))

### 2.5 Eye safety on a hand-worn emitter

* IEC 60825-1 visible-CW accessible emission limits: **Class 1 ≤ 0.39 mW [unverified; from memory of
  the standard]**, **Class 2 ≤ 1 mW**, **Class 3R ≤ 5 mW**. Class 2 is "safe" only because the
  aversion/blink response limits exposure to ~0.25 s; 1 mW appears unable to injure for up to ~5 s,
  and Class 3R is "quite safe for momentary accidental exposure" but exceeds the MPE up to 5×.
  ([Schulmeister 2010](https://www.seibersdorf-laboratories.at/fileadmin/user_upload/docs/le/las/publ/2010_mla_the_risk_of_retinal_injury_from_class_2r_and_visible_class_3r_lasers_including_medical_laser_aiming_beams_schulmeister.pdf),
  [Schulmeister 2011](https://www.seibersdorf-laboratories.at/fileadmin/user_upload/docs/le/las/publ/2011_ilsc_widely_varying_risk_from_class_3r_laser_products_in_light_of_the_revision_of_iec_60825-1_schulmeister.pdf),
  [Weill Cornell EHS](https://ehs.weill.cornell.edu/faq/how-are-classes-lasers-defined))
* **Toys must be Class 1** in the EU (EN 62115 Annex E) and the FDA says the same, precisely because
  the 0.25 s aversion assumption fails when the exposed person is not the operator.
  ([Frontiers / AOT letter](https://www.frontiersin.org/journals/advanced-optical-technologies/articles/10.1515/aot-2020-0072/full),
  [laserpointersafety.com](https://laserpointersafety.com/news/news/other-news_files/tag-class003a-1.php))
* A ring is the toy case, not the presenter case: the operator cannot see where a dot lands
  while gesturing, a hand at chest height sweeps across the faces of seated adults and standing
  children at 1–3 m, and bystanders have not consented. **Rule for this project: Class 1 as
  built and measured; Class 2 only on a bench.** Cheap modules are routinely mislabelled (NIST
  2013 found most tested green pointers over their rated power **[unverified; widely reported]**),
  so a laser power meter is mandatory, not optional.
* Scanned displays get their class from time-averaged exposure (Humane: 25 mW peak, Class 2). A
  stuck mirror turns that into a 25 mW static beam; do not go there on a hand.

---

## 3. What is plausible in a ring-sized v2, ranked

| Rank | Option | Verdict | Why |
|---|---|---|---|
| **(a)** | **Laser pointer**, Ø3.3–6 mm module, 20–30 mA, Class 1 (green preferred) | **Do this** | Fits, wired already (aux channel), 14 µAh per use, visible in any indoor light, products exist as ring presenters. Lets Claude *point*: "the one on the left", highlight an item on a shelf or a word on a page, mark a spot on the floor, show a companion what you mean. |
| **(b1)** | Laser + **DOE fixed glyph** (arrow, circle, crosshair) | Maybe, bench first | DOE heads exist as €98–176 Ø10–12 mm modules ([Picotronic cross](https://www.picotronic.de/picopage/en/product/detail/id/360048), [viewfinder](https://picotronic.de/picopage/en/product/detail/id/357837), [grid](https://www.picotronic.de/picopage/en/product/detail/id/362594)); a bare DOE is a few mm but custom patterns are NRE-heavy. One glyph per DOE; an arrow that cannot rotate is weaker than a dot plus speech. |
| **(b2)** | Laser + **1–2 mm 2-axis MEMS** "vector projector" drawing arrows/digits/a few letters | Research-grade stretch | Brightness works at Class 1 green (§2.1: ~760 lux glyph). Blockers: HV electrostatic drive or an electromagnetic mirror's package, ~8 × 8 × 6 mm pod, laser class with a stuck mirror, $k dev kits, no cheap supply chain. Companion-pendant material, not ring material. |
| **(c)** | **LED "status glow"** onto the hand/wall | Free, not projection | The WS2812 is already in the design; a 505–520 nm LED behind a lens is inherently eye-safe but makes a 30 cm blob at 1 m — a cue, not a pointer. |
| **(d)** | **Full raster image projection** | **Not in this project** | ≥ 1.6 cc, 1.5–7 W, dim rooms only, 13 C on the cell, 43 °C skin limit, Class 2+ scanning on a hand. If ever wanted: a clip/pendant with a 500+ mAh cell and a DLP160CP or LBS engine, paired to the same phone app. Revisit if a ≤ 1 cc, ≤ 0.3 W, Class-1 engine appears (watch ST LBS and TI's 0.16" line yearly). |

---

## 4. Proposed v2 experiment: an aimed Class-1 pointer on the aux channel

**Goal.** Measure whether a dot that marks the camera axis makes answers better (framing) and
whether Claude pointing at things is something anyone uses twice.

### 4.1 Hardware (stage-1 board, no re-spin)

* **Load**: laser dot module with built-in driver/APC, 3–5 V input. Candidates: Laser
  Components LC-LMD Ø3.3 × 7 mm, < 0.9 mW option (OEM quote; est. $15–40 **[unverified]**);
  generic Ø4 × 10 mm or Ø6 × 13 mm 650 nm modules, $1–3 on AliExpress / €0.50 at Olimex (sold as
  3–5 mW ⇒ **must** be attenuated or current-limited to ≤ 0.39 mW and measured); for green, a
  FLEXPOINT MINI 520 nm 1 mW (Ø8 × 15 mm, bench only) ([Laser Components](https://www.lasercomponents.com/se/product/flexpoint-mini/)).
* **Wiring**: J2 pad 1 (VBAT) → module V+; module V− → J2 pad 2 (AUX_DRAIN) → Q1 AO3400 drain;
  gate = `PIN_AUX` (IO9) with the existing 100 kΩ pull-down, so the pointer is **off at reset,
  during boot and in deep sleep**. Add 10–47 Ω in series if the module is 3 V-rated (VBAT is
  3.0–4.2 V) and a 1 µF across the module.
* **Aiming**: mount parallel to the camera axis, 5–8 mm off-axis in the camera pod; parallax is
  then a fixed 5–8 mm offset at every distance, irrelevant beyond 30 cm. A dab of UV resin
  after sighting it on a target at 1 m is the alignment procedure.
* **Measurement**: a laser power meter (hobby thermopile ~$30–100, Thorlabs PM16 class ~$300)
  used once per module and after any current change; log the reading in `docs/benchmarks.md`.
* **BOM delta**: ≈ **$2–5** (module + resistor) using the parts already on the board; the meter is
  the real cost.

### 4.2 Firmware

* Reuse the aux output path: the pattern player can already drive `PIN_AUX`, so "blink the
  pointer twice" is a pattern, not new code. Add a `pointer` mode behind a compile-time flag
  (`MCRING_POINTER`), default **off**.
* Proposed protocol delta (**v2, not in the v1 GATT spec**): CONTROL `POINTER {u8 mode, u16 max_ms}`
  (mode 0 off, 1 on-while-button, 2 pulse pattern), SET_CONFIG `POINTER_ENABLE` (default 0),
  STATUS flag `POINTER_ON`, EVENT `POINTER_BLOCKED {arg = reason}` so the app can say why it
  refused. All keep the v1 packet grammar.

### 4.3 App / backend loop

1. User holds the button: dot on, camera axis marked, photo + question go out (the dot is in the
   photo — tell Claude that the red/green dot marks the centre; or capture with the dot off for
   10 ms, trivial on the aux pin).
2. Backend asks Claude for the answer **plus a normalised bounding box or a direction** for the
   object the answer is about (structured output already exists for Morse/speech fields).
3. App converts the box to an angular offset using the lens FOV (OV2640 stock lens ≈ 66°
   horizontal **[unverified]** ⇒ ~0.2°/px at QVGA; a 60 px offset ≈ 12° ≈ 21 cm at 1 m) and says
   "up-left, about a hand's width".
4. **Closed loop ("blink when the axis crosses it")** needs orientation. The stage-1 IMU is a
   **LIS2DW12 3-axis accelerometer**: it gives pitch/roll from gravity and motion, **no yaw**. So
   either (i) a stage-1.5 spin with a 6-axis part (LSM6DSO/BMI270 class, ~0.5 mA with gyro on
   **[unverified]**) and integrate yaw for the few seconds of a sweep, or (ii) keep the IMU and
   use **visual servoing on the phone**: stream 160 × 120 grey JPEGs (~3–5 KB, 2–3 fps over BLE
   **[estimate]**), template-match the target crop from the first photo, and tick the haptic +
   blink the dot when the target is within ±5 % of frame centre. (ii) costs no silicon and is
   the better first experiment.

### 4.4 Power

Per use: ~14 µAh for a 2 s point, ~40 µAh for a 5 s sweep; a day of 30 photos + 30 points adds
~0.4–1.2 mAh to the 4.6 mAh photo budget. Streaming for a 5 s servo loop costs more than the
pointer (radio + camera ≈ 150 mA × 5 s ≈ 210 µAh); keep it opt-in.

### 4.5 Safety interlocks (all required before the dot is on in anyone's home)

| Layer | Interlock |
|---|---|
| Optical | Class 1 as measured (≤ 0.39 mW at the aperture, every module); green 520 nm preferred so Class 1 is still bright; label on the ring and in the app |
| Electrical | Q1 default-off (pull-down), series resistor sized so a shorted driver still cannot exceed Class 2; no pointer on the always-on rail |
| Firmware | on **only while the button is physically held** (v1 BUTTON_DOWN/UP events); hard cap 3 s per press and ≤ 20 % duty per minute; MCU watchdog; off on BLE disconnect, low battery, charging |
| IMU | off when the finger pitch is > ~15° above horizontal (hand raised toward faces) or during fast motion (|Δa| spikes), so a sweep across a room never carries the dot |
| Vision | app runs an on-device face detector on the capture frame; **face in frame ⇒ no dot**, and Claude's "point" directive is dropped |
| UX | app setting off by default behind a safety screen; LED cue mirrors pointer state; never auto-triggered by double-tap or touch |

Residual risk: a Class-1 dot that still reaches someone's eye is within the standard's
"safe under reasonably foreseeable use" envelope; that is the point of insisting on Class 1
rather than the 1 mW the task suggested.

---

## 5. Use cases worth validating, and when to start

### 5.1 Candidate use cases (strongest first)

1. **Framing aid** — the dot shows the user what the camera centre is on before they ask. No AI
   needed; attacks the "it answered about the wrong thing" failure directly. Measurable.
2. **"Which one?" disambiguation** — shelf, menu, control panel, medicine cabinet: Claude's
   answer names an item and the ring marks it (needs the servo loop or the user's own sweep).
3. **Pointing for someone else** — translation or explanation while a companion looks where
   the dot is; a travel/accessibility angle.
4. **Low-vision assistance** — a high-contrast green dot on "the door handle / the button" for
   users who see contrast but not detail. (Not useful for blind users; speech is.)
5. **Reading guide** — dot or short line under the current line of text for dyslexic readers
   while the phone reads along. Needs a glyph (option b) to be good.
6. **Presentation clicker** — rings already do this; the BLE link exists; nearly free but
   off-mission.
7. **Floor navigation dot** — plausible-sounding, weak in practice: a dot 1 m ahead on the
   floor from a hand that swings while walking; speech ("left at the pillar") is better.

### 5.2 Decision checklist before starting v2 pointer work

- [ ] v1 voice loop used daily by ≥ 3 people for ≥ 2 weeks; wrong-object answers logged and
      **> ~15 %** of them attributable to framing (otherwise the framing aid has no case).
- [ ] At least two testers describe a pointing use case they would use weekly, unprompted.
- [ ] Stage-1 board built; aux pads free (air-puff experiment finished or dropped).
- [ ] Laser power meter in hand; a green Class-1 module measured at ≤ 0.39 mW over 3.0–4.2 V.
- [ ] Face-detector gate prototyped in the app (latency < 200 ms on the capture frame).
- [ ] Decision taken on orientation: phone-side visual servo first; 6-axis IMU only on a
      stage-1.5 spin.
- [ ] Protocol delta (§4.2) reviewed against the frozen v1 GATT spec; packets stay compatible.
- [ ] A one-page safety note written and reviewed, covering Class 1 rationale, interlocks, and
      what the device must never do (auto-trigger, face height, continuous mode).
- [ ] Full-image projection explicitly parked: re-check annually for a ≤ 1 cc / ≤ 0.3 W /
      Class-1 engine; otherwise it belongs to a companion clip/pendant, not the ring.

### 5.3 What this note does not resolve

* Third-party DLP engine dimensions (Young Optics, Anhua, DLP230GP) — not found; TI's own
  numbers are used instead.
* Humane's projector power draw and real brightness — never published; the complaints are the
  data.
* Exact IEC 60825-1 Class 1 AEL and the 43 °C contact limit are quoted from memory.
* Whether a 10 mW-class green diode can be held stably at < 0.4 mW with a cheap APC module —
  bench question.

## Sources

Humane: [iFixit](https://www.ifixit.com/Device/Humane_AI_Pin) · [Notebookcheck teardown](https://www.notebookcheck.com/Humane-Ai-Pin-Teardown-enthuellt-veraltete-Hardware-Easter-Eggs-und-winzigen-Akku-im-teuren-KI-Gadget.824560.0.html) · [china-gadgets](https://www.china-gadgets.de/humane-ai-pin/) · [ZDNet](https://www.zdnet.com.au/article/humane-ai-pin-reviews-5-takeaways-on-a-promising-but-dangerously-flawed-wearable/) · [appfind](https://appfind.beehiiv.com/p/humane-ai-pin-reality-check-the-700-wearable-that-overheats-every-30-minutes-brutally-honest-review) · [The Decoder](https://the-decoder.com/humanes-ai-pin-is-a-curious-ai-wearable-with-a-hefty-price-tag/) · [Wikipedia](https://en.wikipedia.org/wiki/Humane_Inc.)
TI DLP: [DLP160CP](https://www.ti.com/product/DLP160CP) · [SPRPEA6](https://www.ti.com/jp/lit/ml/sprpea6/sprpea6.pdf) · [DLPU131](https://www.ti.com/lit/ug/dlpu131a/dlpu131a.pdf) · [DLPDLCR230NPEVM](https://www.ti.com/tool/DLPDLCR230NPEVM) · [DLPM2000EVM](https://www.ti.com/product/DLPM2000EVM/part-details/DLPM2000EVM) · [DLPA078](https://www.ti.com/lit/pdf/dlpa078) · [DLPA079](https://www.ti.com/lit/an/dlpa079/dlpa079.pdf) · [E2E power thread](https://e2e.ti.com/support/dlp-products-group/dlp/f/dlp-products-forum/847558/dlpdlcr2000evm-power-consumption-and-weight) · [LinuxGizmos $99 EVM](https://linuxgizmos.com/tis-99-dlp-pico-projector-board-connects-to-beaglebone-black/) · [RS DLP3010 EVM-G2](https://nl.rs-online.com/web/p/display-development-tools/2659764) · [Alibaba module guide](https://electronics.alibaba.com/buyingguides/led-dlp-micro-projector-module-guide)
LBS / MEMS: [MicroVision PicoP](https://ir.microvision.com/news/press-releases/detail/201/microvision-completes-design-of-new-picop-laser-display) · [MicroVision PSE-0403](https://opli.net/opli_magazine/eo/2016/microvision-begins-shipping-samples-to-customers-of-its-small-form-factor-display-engine-dec-news) · [Sony MP-CL1 spec](https://store.sony.co.nz/projector-portable/MPCL1AN.html) · [ProjectorCentral](https://www.projectorcentral.com/sony-mp-cl1.htm) · [LumiWatch TechXplore](https://techxplore.com/news/2018-04-arm-smartwatch-touchscreen.html) · [LumiWatch eeNews](https://www.eenewseurope.com/en/smart-watch-expands-touch-display-to-the-skin/) · [Hamamatsu S13989-01H](https://www.hamamatsu.com/content/dam/hamamatsu-photonics/sites/documents/99_SALES_LIBRARY/ssd/s13989-01h_koth1009e.pdf) · [Mirrorcle mirrors](https://www.mirrorcletech.com/wp/products/mems-mirrors/) · [Mirrorcle dev kits](https://www.mirrorcletech.com/wp/products/devkits/) · [ST LaSAR](https://newsroom.st.com/media-center/press-item.html/t4297.html) · [ST LBS demo](https://www.edge-ai-vision.com/2022/10/stmicroelectronics-demonstration-of-laser-beam-scanning-for-ar-glasses-and-beyond/)
Finger/ring projectors & vaporware: [US9477146](https://patents.google.com/patent/US9477146) · [US10372160](https://patents.google.com/patent/US10372160) · [US2016/0261834](https://patents.justia.com/patent/20160261834) · [Snopes on Cicret](https://www.snopes.com/fact-check/do-you-want-to-know-a-cicret/) · [Ritot Indiegogo](https://indiegogo.com/projects/ritot-the-first-projection-watch) · [Wareable](https://www.wareable.com/wearable-tech/worse-for-wear-the-worst-wearable-crowdfunding-campaigns-865) · [ABC7](https://abc7chicago.com/post/crowdfunding-highs-and-lows-of-adventure-capital-/908651/) · [SixthSense](https://www.media.mit.edu/publications/sixthsense-a-wearable-gestural-interface-2/) · [OmniTouch](https://www.cmu.edu/news/stories/archives/2011/october/oct17_omnitouch.html) · [Genius Ring Presenter](https://www.ubergizmo.com/2012/01/genius-ring-presenter/) · [Celluon keyboard](https://en.wikipedia.org/wiki/Projection_keyboard)
Lasers, DOE, safety: [LC-LMD Ø3.3 mm modules](https://lasercomponents.com/us/photonics-portal/news/the-smallest-oem-laser-modules-the-lc-lmd-series) · [FLEXPOINT MINI](https://www.lasercomponents.com/se/product/flexpoint-mini/) · [Olimex 650 nm module](https://olimex.com/Products/Components/LEDs/LASER-650nm) · [Photonic Products modules](https://www.webwire.com/ViewPressRel.asp?aId=5283) · [DigiKey laser modules](https://www.digikey.com/en/products/filter/laser-diodes-modules/95) · [Picotronic DOE cross](https://www.picotronic.de/picopage/en/product/detail/id/360048) · [Picotronic DOE grid](https://www.picotronic.de/picopage/en/product/detail/id/362594) · [Schulmeister 2010](https://www.seibersdorf-laboratories.at/fileadmin/user_upload/docs/le/las/publ/2010_mla_the_risk_of_retinal_injury_from_class_2r_and_visible_class_3r_lasers_including_medical_laser_aiming_beams_schulmeister.pdf) · [Schulmeister 2011](https://www.seibersdorf-laboratories.at/fileadmin/user_upload/docs/le/las/publ/2011_ilsc_widely_varying_risk_from_class_3r_laser_products_in_light_of_the_revision_of_iec_60825-1_schulmeister.pdf) · [EN 62115 toys Class 1](https://www.frontiersin.org/journals/advanced-optical-technologies/articles/10.1515/aot-2020-0072/full) · [laserpointersafety.com](https://laserpointersafety.com/news/news/other-news_files/tag-class003a-1.php) · [Weill Cornell laser classes](https://ehs.weill.cornell.edu/faq/how-are-classes-lasers-defined)
Photometry: [Luminous efficiency function](https://en.wikipedia.org/wiki/Luminous_efficiency_function) · [Troikatronix / AV Magazine lumens formula](https://community.troikatronix.com/post/34245)
