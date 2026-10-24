# 7. PCB design and assembly

The stage-1 board is **26.5 × 18.0 × 0.6 mm, two layers, 87 placed parts**, and it does not exist yet as a layout: the repo stops at a Python netlist model (`hardware/electrical/mcring_v1.py` → `out/mcring_v1.net`, ERC clean in `out/erc.md`), a to-scale floorplan with placement and routing rules (`hardware/pcb/floorplan.py` → `floorplan.md`, `board_params.json`) and an order/assembly procedure (`docs/07-build-guide.md` §2.1–2.4). Turning that into a fabricated, populated, working board is the job this chapter prepares you for: KiCad layout from the netlist, a fab order with stencils, a two-pass reflow on a hot plate, and a power-first bring-up over the eight test pads. Read it with `hardware/pcb/out/floorplan_top.png`, `floorplan_bottom.png` and `hardware/electrical/README.md` §4–5 open.

Rows in the "Learn it" tables whose resource carries no link could not be link-checked when this chapter was built — search the exact title given. Links marked *(root)* point at a documentation home page and the "Why this one" column says where to go from there. `docs/fundamentals/_links_making.json` records how every link was checked.

## 7.1 Schematic → netlist → layout: what each artefact is and how KiCad consumes it

**Why it matters in mcring.** There is no KiCad schematic in the repo. `mcring_v1.py` declares every `Part` (reference, value, footprint name, MPN, pin table) and every `Net`, `netlist_model.py` exports a KiCad netlist (format version "E"), a grouped BOM, a Markdown net listing and runs an ERC — 92 parts, 313 pins, 65 nets, one waived single-node net (`ANT_RF`, whose other end is the module's u.FL receptacle). `hardware/electrical/README.md` §4 says exactly how pcbnew eats that file: *File → Import Netlist*, match by reference, replace footprints, update PCB; off-board parts (cell, antenna, speaker, piezo, band contacts) are deliberately absent and land on wire pads J1/PAD1/PAD2/BZ1/SPK1. The five `out/sch_*.svg` sheets are your schematic reference while routing.

**The concepts.** A *schematic* is a drawing for humans; a *netlist* is the same information for machines: a list of components (reference designator like `R8`, a value, a footprint identifier like `Resistor_SMD:R_0402_1005Metric`) and a list of nets, each net being the set of (reference, pin) pairs that must be copper-connected. Everything the layout tool enforces — ratsnest lines, DRC "unconnected" errors, net classes — derives from it. In KiCad the normal route is schematic editor → *Update PCB from Schematic*; the netlist import is the older, still-supported route and the one this repo uses because the schematic lives in Python. Footprint names must resolve in a library the PCB editor can see, so step 2 of §4 is making an `mcring` footprint library with the eleven custom land patterns (`TPS22916_DSBGA-4_YFP`, `MIC_TDK_T3902_3.5x2.65mm`, the wire pads …) before importing; pad numbers must equal the pin numbers in the model or the netlist will connect the wrong pins. *ERC* checks the schematic's logic (every pin on a net, every supply pin decoupled); *DRC* checks the board's geometry (clearances, widths, annular rings, unrouted nets). Re-importing after a change to `mcring_v1.py` keeps your placement and only updates connectivity — which is why the Python model stays the source of truth and you never hand-edit nets in pcbnew. The design-rule numbers in §5 (0.10/0.10 mm fine, 0.15 general, 0.3 mm power, 0.2 mm drill / 0.45 mm pad vias, NSMD DSBGA pads, ENIG) are typed once into *Board Setup → Design Rules* and as net classes (`GND/3V3/VBAT/CAM_3V3/VLED/VAMP/CHG_PAD/CHG_IN/SW_NODE/SPK_P/SPK_N` at 0.3 mm), so that DRC, not memory, polices them.

**Learn it.**

| Resource | Type | Time | Why this one |
|---|---|---|---|
| [KiCad documentation](https://docs.kicad.org/) *(root)* | docs | 3–4 h | Start with *Getting Started in KiCad* (one small board end to end), then the PCB Editor manual's *Import Netlist*, *Board Setup*, *Net classes* and *DRC* chapters — the exact dialogs `hardware/electrical/README.md` §4 steps through |
| Digi-Key "Introduction to KiCad" video series (Shawn Hymel, Digi-Key YouTube channel) | video course | 3 h | Schematic → footprint assignment → layout → Gerbers, one episode per step; the best first watch if you have never laid out a board |
| Phil's Lab, "KiCad hardware design" tutorials (YouTube channel) | video | 2–4 h | Full professional-style flows (MCU boards with switchers and USB) in KiCad; watch for how he organises net classes, decoupling and the power path before routing |
| Contextual Electronics, "Getting to Blinky" (Chris Gammell, free KiCad course) | course | 2 h | Short, deliberately simple; the fastest way to learn KiCad's editing idioms before touching a 87-part board |
| [Memfault Interrupt: A Schematic Review Checklist for Firmware Engineers](https://interrupt.memfault.com/blog/schematic-review-checklist) | article | 20 min | Run it on `out/sch_mcu.svg` before layout: boot straps, pull directions, test points, decoupling — the review that produced items 10–17 in `hardware/electrical/README.md` §1 |
| `hardware/electrical/netlist_model.py` (this repo) | code | 30 min | Read `to_kicad_netlist()` and `erc()`: 480 lines that show what a netlist *is* better than any glossary |

**Check yourself.**

1. `out/erc.md` reports 65 nets and 299 nodes but the netlist has 313 pins. Where did 14 pins go, and is that an error?
2. You rename `C23` to `C230` in `mcring_v1.py`, regenerate and re-import with *Match by reference*. What happens to the placed capacitor?
3. Why is `LS1` (the speaker) absent from `mcring_v1.net` although its two nets `SPK_P`/`SPK_N` are present, and what would go wrong if you added it with a real footprint?
4. Which of these does DRC catch and which only ERC: (a) R5's pull-up tied to `3V3` instead of `CAM_3V3`; (b) a 0.08 mm gap between two DSBGA fan-out traces; (c) a 0.2 mm drill under a 0.4 mm pad.

<details><summary>Answers</summary>

1. Pins marked NC or spare are not on any net, so they are not nodes: `out/mcring_v1_nets.md` lists D1's DOUT, FPC1 pins 1/23/24, the module's IO26/IO44 (spare)/IO45/IO46, DRV2605L pin 10, LIS2DW12 INT2 and the MAX98357A's four N.C. pins (5, 6, 12, 13) — exactly 14. ERC check 1 only requires every pin *not* marked NC/spare to be on a net, so it is clean.
2. pcbnew finds no footprint with reference `C230`, adds a new one at the origin and flags the old `C23` as no longer in the netlist (deleted if you ticked *Delete footprints with no components*). Placement is keyed by reference, so renames cost you the placement; change values and nets freely, rename rarely.
3. It is off-board (`Mount = off-board` in the BOM): its leads are soldered to the SPK1a/SPK1b wire pads, which *are* in the netlist as `SPK1`. A real speaker footprint would demand copper for a part that sits in the signet wall, fail DRC as unplaced or unrouted, and mislead the pick-and-place file.
4. (a) ERC/logic only — electrically legal, functionally wrong (the pull-up would leak into the switched camera rail); DRC sees copper, not intent. (b) DRC (clearance rule 0.10 mm). (c) DRC (annular ring (0.4 − 0.2)/2 = 0.1 mm < the 0.125 mm minimum).

</details>

## 7.2 Footprints and land patterns: 0402, SOT, QFN/TQFN, DSBGA, LGA, connectors

**Why it matters in mcring.** The bottom side holds 44 × 0402, 4 × 0603, two 0.4 mm-pitch DSBGA-4 load switches (U2, U9, plus U11 with the speaker), a DSBGA-6 charger (U7, 1.6 × 0.9 mm), a SOT-583 buck (U8), two SOT-23 LDOs, a VSSOP-10 haptic driver, an LGA-12 2 × 2 mm accelerometer, a 16-TQFN 3 × 3 mm amplifier with an exposed pad (U10) and a 2.65 × 3.5 mm bottom-port microphone whose port hole goes through the board (`floorplan.md` §3). `hardware/electrical/README.md` §5 sets NSMD 0.22–0.25 mm pads with no via-in-pad for the DSBGAs and 0.05 mm mask expansion (0.03 on DSBGA); §6 lists footprint checks still open (the FPC connector land pattern, the TQFN EP size, the Maxim T1633+4C drawing). Eleven footprints have to be drawn by hand.

**The concepts.** A *footprint* (land pattern) is the copper, solder-mask and paste geometry a package needs; it is derived from the package drawing plus process allowances, and IPC-7351 is the standard that formalises "nominal / least / most" land protrusions. Package codes mix two systems: an **0402** chip is 0.04 × 0.02 inch = **1.0 × 0.5 mm, metric 1005**; "0603" exists in both systems (1.6 × 0.8 mm imperial 0603 versus 0.6 × 0.3 mm metric 0603) — the trap `hardware/electrical/README.md` sidesteps by writing `R_0402_1005Metric`. Leaded packages (SOT-23, SOT-583, VSSOP) have gull-wing or flat leads you can see and reflow by eye; *leadless* packages (QFN/TQFN, LGA) have pads under the body and a thermal/ground **exposed pad (EP)** that needs paste too (U10's EP goes to the ground pour with 2–4 vias, `floorplan.md` §6); *wafer-level* packages (DSBGA/WLCSP, "YFP") are the bare die with solder balls at 0.4 mm pitch. For those the pad is **NSMD** (non-solder-mask-defined: copper smaller than the mask opening, so the ball wets the copper's edges and self-centres) and sized to about the ball diameter (0.22–0.25 mm for 0.25 mm balls); the four or six balls sit on the perimeter, so nothing routes between them and no via-in-pad is needed. Mask expansion is the gap between pad edge and mask edge: 0.05 mm keeps 0.5 mm-pitch pads from sharing one mask sliver, 0.03 mm on DSBGA keeps a mask dam between 0.4 mm-pitch balls. Connectors are the footprints most worth checking against the *purchased* part: the 24-pin 0.5 mm bottom-contact FPC connector's land pattern "matches the KiCad FH12-24S-0.5SH footprint — check" (§6 item 3), and the camera head itself has a one-position-shifted pin-order variant, which is why `docs/07` §2.1 says buzz the head before ordering boards. Worked numbers: a 0.4 mm pitch with 0.25 mm pads leaves 0.15 mm pad-to-pad, so the 0.10 mm fan-out trace between two balls has 0.025 mm per side — hence fine rules only where needed, and the SOT-23-5 TPS22917 fallback if the fab cannot do them. The via of §5: 0.2 mm drill in a 0.45 mm pad → annular ring (0.45 − 0.2)/2 = 0.125 mm, aspect ratio 0.6 mm / 0.2 mm = 3:1, comfortable for plating.

**Learn it.**

| Resource | Type | Time | Why this one |
|---|---|---|---|
| [TI AN-1112 (SNVA009): DSBGA Wafer Level Chip Scale Package](https://www.ti.com/lit/snva009) | app note | 45 min | The pad size, NSMD rule, stencil and reflow guidance for exactly the YFP packages of U2/U7/U9/U11 |
| [JLCPCB: IC package types explained](https://jlcpcb.com/blog/ic-package-types-guide) | article | 20 min | A picture of every package family on this board (SOT, VSSOP, QFN, LGA, WLCSP) and what each means for assembly |
| [Electronics Notes: SMD passive sizes, imperial vs metric trap](https://www.electronics-notes.com/articles/electronic_components/surface-mount-technology-smd-smt/passive-component-size-codes-overlap-trap.php) | article | 10 min | Why the netlist says `0402_1005Metric` and never just "0402" |
| [SparkFun: How to Read a Datasheet](https://www.sparkfun.com/tutorials/223) | article | 30 min | Where the package drawing and the recommended land pattern live in a datasheet, and how to read the tolerances |
| TI application report "QFN/SON PCB Attachment" (SLUA271) | app note | 30 min | Exposed-pad paste coverage, thermal vias and the stencil rules for U10's 16-TQFN; find it on ti.com by its document number |
| KiCad Library Conventions (KLC) site | reference | 30 min | The footprint naming and pad rules the stock KiCad library follows; copy them for the eleven custom `mcring` footprints so they look and behave like the rest |
| [TI TPS22916 product page / datasheet](https://www.ti.com/product/TPS22916) | datasheet | 20 min | Section "Layout" of the datasheet: the recommended DSBGA-4 land pattern you will draw as `TPS22916_DSBGA-4_YFP` |

**Check yourself.**

1. A supplier lists "0603 100 nF" capacitors. Give both sizes that could mean, in mm, and say which one the netlist's `C_0603_1608Metric` is.
2. The TPS22916 balls are on a 0.4 mm pitch. With 0.25 mm NSMD pads and 0.03 mm mask expansion, how wide is the solder-mask dam between two pads?
3. U10's exposed pad is "not internally connected" per §6 item 17. Does it still need paste and vias? Why?
4. Why is the FPC connector called "bottom contact" and what breaks if you buy the top-contact version with the same land pattern?

<details><summary>Answers</summary>

1. Imperial 0603 = 1.6 × 0.8 mm; metric 0603 = 0.6 × 0.3 mm (imperial 0201). The netlist's `1608Metric` is the 1.6 × 0.8 mm part.
2. Pad-to-pad gap 0.40 − 0.25 = 0.15 mm; each mask opening is 0.25 + 2 × 0.03 = 0.31 mm, so the dam is 0.15 − 0.06 = 0.09 mm — about the thinnest a fab will hold, which is why §5 keeps expansion at 0.03 mm there.
3. Yes: mechanically it is the biggest joint under the part and it keeps the package flat and coplanar during reflow; vias to the pour give it a heat path and a defined potential (GND) rather than floating copper. Coverage is reduced (windowed paste) so the part does not float on a bubble of solder.
4. The flex's exposed contacts face the board when the connector's contacts are on the bottom; `hardware/cad/README.md` ("Camera FPC") routes the flex to fold 180° and enter from the front with contacts facing down. A top-contact connector would need the flex twisted or inserted contacts-up, which the pod geometry does not allow.

</details>

## 7.3 Two-layer layout: ground pour, return paths, decoupling placement, the buck loop, vias

**Why it matters in mcring.** `floorplan.md` §5 gives the layer plan — top: module fan-out, FPC1, switch, LED, C3, test pads, GND pour; bottom: all small ICs and passives, the DVP corridor, I²C, the power cluster, GND pour everywhere else, stitched to the top pour with vias every ≤ 3 mm — and §6 the critical loops: C1–U8–L1–C2 "in a tight loop, SW_NODE minimal area", C13/C24 within 1 mm of the FPC pins, C26 within 1 mm of U10's VDD pins, ≥ 9 GND vias under the module's thermal pads. The 100 µF bulk capacitor C3 exists because the radio and the camera draw 300–370 mA steps that a 0.6 mm board's thin traces and a 30 mAh cell cannot follow (`docs/fundamentals/01` §1.2). The fallback if two layers do not close is a 4-layer 0.6 mm stack with the same outline.

**The concepts.** Every signal current returns to its source, and at the frequencies that matter on this board (a 20 MHz DVP bus with nanosecond edges, a buck switching at ~1.8 MHz, a 2.4 GHz radio) it returns directly *under* the trace, in the nearest copper, not by the shortest DC path. A solid ground pour under every signal gives that return current a path and keeps the loop area — hence the radiated noise and the inductance — small; a slot in the pour (a long trace cutting the bottom pour in two, a row of vias) forces the return to detour and turns the trace into an antenna. On two layers the compromise is: one layer mostly pour, the other mostly signals, and stitching vias so the two pours behave as one — the ≤ 3 mm spacing in §5 is well under λ/20 at 2.4 GHz (125 mm / 20 ≈ 6 mm). *Decoupling placement*: a capacitor's job is to supply a current step before the supply can; its usefulness is limited by the inductance of the loop pin → capacitor → ground → pin, roughly 1 nH per millimetre of trace, so "within 1 mm of the pin" is a loop-inductance statement, not a tidiness one. The droop it must cover is ΔV = I·Δt/C: the 100 µF bulk against a 300 mA step the TPS62840 takes ~20 µs to answer droops 60 mV; the 100 nF beside each IC handles the first nanoseconds the big capacitor's own inductance cannot. *The buck loop*: in a switching regulator the input capacitor, the switch node and the output capacitor carry current that changes in tens of nanoseconds; the loop CIN → IC → L → COUT → GND must be short and on one layer, and the SW node small because its area is the radiating antenna — which is why `floorplan.md` places C1, U8, L1 and C2 in a row at y = 3.3–5.6 mm. *Copper as a resistor*: 1 oz copper is 35 µm thick, so its sheet resistance is ρ/t = 1.72 × 10⁻⁸ / 35 × 10⁻⁶ ≈ 0.5 mΩ per square; a trace of length L and width w is L/w squares. The 0.4 mm VBAT trunk over 20 mm is 50 squares ≈ 25 mΩ, dropping 9 mV at the 370 mA capture peak; the same run at 0.15 mm would be 65 mΩ and 24 mV. Current capacity by IPC-2221 is about 1 A for a 0.4 mm external trace at a 10 °C rise, far above anything here. *Vias* add ~0.5–1 nH and ~1 mΩ each; use two in parallel for the module's 3V3 and for C3's ground.

**Learn it.**

| Resource | Type | Time | Why this one |
|---|---|---|---|
| Rick Hartley, "How to Achieve Proper Grounding" (Altium / AltiumLive talk, YouTube) | video | 2 h | The talk that explains return currents and why a pour under every signal matters; after it the §5 layer plan reads as obvious |
| [Eric Bogatin on Robert Feranec's channel: decoupling capacitor value and placement](https://fedevel.com/blog/what-decoupling-capacitor-value-to-use-and-where-to-place-them-eric-bogatin) | video | ~1 h | Measured: near vs far, one vs two, 1000 µF vs 1 µF; settles "within 1 mm" and "100 nF + 10 µF" with data |
| [EEVblog #859: Bypass Capacitor Tutorial](https://www.eevblog.com/2016/03/11/eevblog-859-bypass-capacitor-tutorial) | video | 33 min | Loop inductance and self-resonance on an analyser; why C26 sits at U10's pins and not "somewhere on the 3V3 net" |
| [TI TPS62840 product page / datasheet](https://www.ti.com/product/TPS62840) | datasheet | 30 min | The *Layout Guidelines* and *Layout Example* sections: the exact CIN/L/COUT/VOS arrangement `floorplan.md` §6 asks for |
| Saturn PCB Design Toolkit (free Windows calculator) | tool | 20 min | Trace width vs current, via resistance/inductance, crosstalk; check the 25 mΩ trunk figure above and the 3:1 via |
| Phil's Lab, PCB design and layout videos (YouTube channel) | video | 1–2 h | Hands-on routing of switchers, decoupling and return paths in KiCad; the "do it with me" complement to Hartley's theory |
| [Memfault Interrupt: Smart Ring Development (Part 2) — Hardware Design](https://interrupt.memfault.com/blog/smart-ring-development-part-2) | article | 30 min | What changes when this board becomes a rigid-flex at stage 2: stack-ups, flex bends, antenna, assembly |

**Check yourself.**

1. The I²S lines to U10 run through 1 kΩ series resistors (R22–R24). What loop-inductance argument says the 100 nF C26 must still be within 1 mm of pins 7/8 even though the signals are slow (512 kHz)?
2. Compute the resistance of a 0.1 mm wide, 12 mm long DVP trace in 1 oz copper, and the voltage drop at the 10 mA an OV2640 output pin can source. Does it matter?
3. The 3 mm stitching rule: what fraction of a wavelength is 3 mm at 2.4 GHz in FR-4 (εr ≈ 4.3)?
4. You must route `VBAT` across the DVP corridor on the bottom layer. Name the two ways to do it without slotting the return path for the DVP bus.

<details><summary>Answers</summary>

1. The amplifier's output stage switches ~300 kHz class-D edges with amps of peak current; the supply step it draws is fast regardless of the I²S rate. ~1 nH/mm × a few mm would be tens of millivolts of ringing at those edges and a radiator next to the PDM and I²C lines.
2. 120 squares × 0.5 mΩ = 60 mΩ; 10 mA × 60 mΩ = 0.6 mV. Irrelevant for a CMOS logic level (hundreds of mV of margin); DVP traces are sized for routability and crosstalk, not resistance.
3. In FR-4 the wavelength is 125 mm / √4.3 ≈ 60 mm; 3 mm is λ/20 — the usual rule of thumb for "the two pours act as one".
4. Cross on the *top* layer (a short jumper under the module region, returning to the bottom with two vias), or route the trunk around the corridor's end at x < 1 or x > 12.6. Never cut a 0.4 mm slot through the pour the DVP bus returns on.

</details>

## 7.4 The signals that care: DVP, PDM, I²S, USB, touch — and the antenna keep-outs

**Why it matters in mcring.** `floorplan.md` §6 is a list of exceptions to "route it anywhere": the DVP bus (Y2–Y9, PCLK, HREF, VSYNC, XCLK) in a bottom-layer corridor ≤ 15 mm, loosely matched ±5 mm, nothing else in the corridor, XCLK/PCLK away from the antenna end; PDM CLK/DATA ≤ 10 mm; USB D−/D+ as a pair on the top layer with a ≤ 10 mm stub to TP3/TP4 and nothing else on the nets; the touch line short and away from the DVP corridor; OUTP/OUTN as a 0.3 mm pair ≥ 1 mm from SDA/SCL, IMU_INT1 and the PDM lines. Deviation 10 of §9 is a lesson in itself: the earlier "no copper in the last 2 mm" rule was the PCB-antenna rule for the MINI-1; the MINI-1U has a u.FL, its GND/3V3/EN pads sit in exactly that strip, so copper is *required* there and the keep-out moved off the board: flex antenna and pigtail ≥ 5 mm from the cell, the LRA, the speaker magnet and any metal (`board_params.json` → `antenna_rule`, `hardware/cad/README.md` "Antenna").

**The concepts.** Whether a trace is "short" is decided by edge rate, not clock rate. A CMOS output with a 2 ns rise time has a knee frequency of about 0.35/t_r ≈ 175 MHz; signals travel ~145 mm/ns in FR-4 (6.9 ps/mm), so a 15 mm DVP trace delays its edge by 0.1 ns — far less than the 2 ns rise — and behaves as a lumped wire: no termination, no impedance control. The ±5 mm matching tolerance is ±35 ps of skew against a 50 ns period at 20 MHz, i.e. nothing; it is written down so nobody matches to the millimetre at the cost of a corridor cut. What *does* bite at 20 MHz with fast edges is crosstalk and noise coupling: keep aggressive lines (XCLK, PCLK, the class-D outputs, the buck SW node) apart from sensitive ones (PDM data, SDA/SCL, IMU_INT1, the touch electrode line, the ADC's BAT_SENSE) by the "3W" rule (centre spacing ≥ 3 × trace width) or a ground trace between them, and give the corridor its own return copper. USB full speed (12 Mbit/s, 90 Ω differential) is tolerant: a stub of a few millimetres on the top layer is fine, and `floorplan.md` keeps the pair alone on its nets so the test-pad stub is the whole run. The capacitive touch line is the opposite kind of sensitive: `trigger.cpp` looks for a +25 % change in a self-capacitance measurement, so every picofarad of stray coupling to a toggling DVP line is noise; hence short, away from the corridor, with the hatched guard ring and no copper under the landing. *Antenna*: at 2.4 GHz λ = 125 mm; a quarter-wave monopole is ~31 mm (the "31 mm wire on a cut pigtail" alternative in the CAD README); any metal within a few millimetres detunes a small antenna and absorbs its field, which is the 5 mm rule, and a u.FL pigtail loses a few tenths of a dB per 10 cm plus ~0.1–0.3 dB per connector, so ≤ 50 mm is cheap. The module's nine ground vias are not RF: they tie the shield can's thermal pads to the pour so the module's own ground reference is solid.

**Learn it.**

| Resource | Type | Time | Why this one |
|---|---|---|---|
| [ESP32-S3 Series Datasheet (Espressif)](https://www.espressif.com/sites/default/files/documentation/esp32-s3_datasheet_en.pdf) | datasheet | 30 min | GPIO drive strength and edge rates, the camera interface pins, the RF section; pair it with the MINI-1/MINI-1U module datasheet linked from `hardware/bom/stage1-ring.csv` |
| Espressif "ESP32-S3 Hardware Design Guidelines" (docs.espressif.com, esp-hardware-design-guidelines) | docs | 1 h | The module placement, ground-via and antenna-clearance rules §5 paraphrases; find the ESP32-S3 edition of the guidelines |
| TI "High-Speed Layout Guidelines" (SCAA082) | app note | 45 min | Edge rate vs trace length, when a trace is a transmission line, crosstalk and the 3W rule — written for faster buses but the reasoning is the DVP corridor's |
| TI "Antenna Selection Guide" (SWRA161) | app note | 45 min | Monopole/dipole/chip/PCB antennas at 2.4 GHz, ground-plane and keep-out effects, cable loss; the vocabulary for choosing the flex antenna |
| [Punch Through: Maximizing BLE Throughput on iOS and Android (Part 1)](https://punchthrough.com/maximizing-ble-throughput-on-ios-and-android/) | article | 30 min | What a marginal antenna costs you in practice: retries and interval, i.e. the "many `resend N chunks`" row of `docs/07` §4 |
| [Nordic DevAcademy: Designing Low-Power Bluetooth LE Products](https://academy.nordicsemi.com/courses/designing-low-power-bluetooth-le-products/) | course | 3 h | Includes antenna and RF layout lessons for the nRF52840 stage-2 board (printed microstrip antenna, rigid-flex) |

**Check yourself.**

1. XCLK runs at 20 MHz. If the ESP32-S3 drives it with a 1.5 ns edge, what is the knee frequency, and how long may a trace be before its one-way delay reaches a quarter of that rise time?
2. Why does `floorplan.md` allow the DVP bus to leave FPC1 on the top layer, drop to the bottom corridor and come back up at the module, instead of staying on one layer?
3. The speaker's NdFeB magnet is 5.45 mm from the antenna placeholder (`fit_report.md`). Name two reasons a magnet near a 2.4 GHz antenna is a problem although magnets do not radiate.
4. Give the ratio of the 31 mm monopole to the free-space wavelength and say what happens to its resonance when it lies along a finger.

<details><summary>Answers</summary>

1. 0.35 / 1.5 ns ≈ 233 MHz. A quarter of 1.5 ns is 375 ps; at 6.9 ps/mm that is ≈ 54 mm — so the 15 mm corridor is comfortably lumped.
2. FPC1 and the module's front-row pins are on the top, but the top is also where the switch, LED, C3 and the test pads sit at the front strip; the bottom corridor at y 8.3–13.8 is the only straight, part-free channel that keeps the eleven lines together with a return pour on the other side.
3. It is a lump of conductive steel/alloy that detunes and shadows the antenna (the "any other metal" rule), and the speaker's leads and voice coil carry class-D current that can couple into the feed. The 5 mm rule treats it as metal, not as a magnet.
4. 31 / 125 ≈ 0.25 (a quarter wave). Skin (εr ≈ 40–50, lossy) next to the wire loads it capacitively, shifting resonance down and absorbing power — `docs/04` expects 3–8 m of range rather than the module's free-space tens of metres.

</details>

## 7.5 DRC, fab capabilities, Gerbers and ordering boards with stencils

**Why it matters in mcring.** `docs/07-build-guide.md` §2.2 is the order form: 2 layers / 0.6 mm / FR-4 TG150+ / 1 oz, 0.10/0.10 mm fine rules, 0.20 mm drill / 0.45 mm pad vias, ENIG, 0.05 mm mask expansion (0.03 on DSBGA, NSMD), no silkscreen under the module, **two 0.10 mm frameless stencils**, 1:1 DSBGA apertures ("the fab may want to shrink them — say no"), 5–10 boards, two fiducials per side. §2.1 item 3 is the gate: confirm the fab offers 0.1/0.1 mm and 0.2 mm drills on 2-layer 0.6 mm, else swap the TPS22916s for TPS22917DBV (SOT-23-5) in `mcring_v1.py` and use standard rules. `hardware/electrical/README.md` §5 notes that at JLCPCB/PCBWay those numbers are "advanced" options (standard is 0.127 mm / 0.3 mm drill).

**The concepts.** *DRC* is your fab's capability table encoded as rules: minimum trace width and clearance, minimum drill and annular ring, hole-to-copper, mask sliver, courtyard overlaps, unrouted nets. Run it with the real fab numbers, not KiCad's defaults, and treat zero violations as the ticket to export. *Gerbers* (RS-274X) are one file per layer — copper top/bottom, mask top/bottom, paste top/bottom, silkscreen, board outline (Edge.Cuts) — plus an Excellon drill file; the paste layers become the stencils, which is why pad paste settings in the footprints (windowed EP, 1:1 DSBGA) matter at design time. Capability words: *thickness* 0.6 mm is thin (standard 1.6 mm), so the board flexes and heats fast but vias are easy (aspect 3:1); *ENIG* (electroless nickel immersion gold) is flat and solderable for months, needed for 0.4 mm-pitch coplanarity and for the exposed charging contacts, where HASL's uneven tin would not do; *TG150+* keeps the laminate stiff through a 245 °C SAC305 peak. *Stencils*: a laser-cut stainless foil, 0.10 mm (4 mil) for mixed 0402/QFN boards, 0.08 mm when fine-pitch dominates; frameless is enough for hand printing with a squeegee card. The number that decides whether paste releases from an aperture is the **area ratio** = aperture area / aperture wall area; ≥ 0.66 is the usual minimum. For a square aperture of side *s* in foil *t* it is *s*/(4*t*): a 1:1 0.25 mm DSBGA aperture in 0.10 mm foil gives 0.625 — marginal, which is why §2.2 insists on 1:1 (a shrunken aperture would be worse) and why 0.08 mm foil (0.78) is the better ask if the fab offers it; an 0402 pad of 0.5 × 0.6 mm gives 0.30/0.22 ≈ 1.36, no issue. *Fiducials*: 1 mm bare copper dots with a mask-free ring, two per side, so a stencil or a pick-and-place camera can register; on a 26.5 × 18 mm board they fight for space with the test pads, hence "if there is room". *Panelisation* is not worth it at 5–10 pieces of a 0.6 mm board; order singles with the fab's default rails.

**Learn it.**

| Resource | Type | Time | Why this one |
|---|---|---|---|
| [JLCPCB](https://jlcpcb.com/) *(root)* | fab | 20 min | Open *Capabilities → PCB* and *SMT stencil*: confirm 0.10/0.10 mm and 0.20 mm drill on 2-layer 0.6 mm before you believe `docs/07` §2.2 for your order date |
| [PCBWay](https://www.pcbway.com/) *(root)* | fab | 20 min | Same check on the second fab; their capability page lists the "advanced" tiers and ENIG/stencil options side by side |
| [KiCad documentation](https://docs.kicad.org/) *(root)* | docs | 1 h | PCB Editor manual → *Design rule checking* and *Fabrication outputs* (Gerbers, drill, pick-and-place, paste layers) |
| [Adafruit: SMT Manufacturing](https://learn.adafruit.com/smt-manufacturing) | article | 30 min | What a stencil, a paste layer, a fiducial and a reflow profile are for, from a small manufacturer's floor |
| [TI AN-1112 (SNVA009): DSBGA Wafer Level Chip Scale Package](https://www.ti.com/lit/snva009) | app note | 20 min | The stencil aperture and foil-thickness recommendations for the DSBGA pads — the source of the "1:1, don't shrink" instruction |
| Gerber viewer (your fab's online viewer, or KiCad's own *Gerber Viewer*) | tool | 15 min | Open every exported layer before uploading: mirrored bottom, missing paste on the EP, a stray outline all show up here |

**Check yourself.**

1. The bottom stencil must deposit paste for 72 parts including two DSBGA-4s, one DSBGA-6 and a QFN EP. Compute the area ratio of a 1:1 0.22 mm aperture in 0.10 mm and in 0.08 mm foil.
2. Why does the Kapton tape over the Ø0.6 mm mic hole (`docs/07` §2.3 step 1) have to go on from the *top* before stencilling the bottom?
3. You exported Gerbers with the bottom copper un-mirrored. Will the fab catch it? What does the viewer show?
4. Standard rules only (0.127 mm / 0.3 mm drill): list the three places on this board that fail and what §2.1 item 3 does about them.

<details><summary>Answers</summary>

1. *s*/(4*t*): 0.22/0.40 = 0.55 (poor release, expect skips) and 0.22/0.32 = 0.69 (acceptable). Ask for 0.08 mm foil for the bottom stencil, or accept touch-up with a syringe on the DSBGAs.
2. Paste squeegeed over the bottom side would enter the through-hole from the bottom; tape on the top closes the far end and is removable later without disturbing the bottom paste or parts. Taping the bottom would lift the stencil locally.
3. Gerbers carry no "side" — the fab trusts the file names and the stackup; a mirrored or un-mirrored error produces a board whose bottom pads are reversed left-right against the top. The viewer overlays layers in one coordinate system, so the module's top pads and the bottom parts that should be under them will not line up.
4. The 0.4 mm-pitch DSBGA fan-out (0.1 mm traces between balls) at U2/U9/U11, the 0.2 mm vias between 0.5 mm-pitch pads, and the 0.5 mm-pitch LGA/VSSOP/FPC escapes needing < 0.127 mm spacing. The fix swaps the DSBGA switches for SOT-23-5 parts with the same nets and regenerates the netlist; the rest can be re-routed at 0.127 mm with slightly larger vias.

</details>

## 7.6 Reflow: paste, stencilling, hot plate, hot air, two-alloy builds

**Why it matters in mcring.** `docs/07` §2.3 is a two-pass build: bottom first (stencil + hot plate), prove the power tree, then the top (the 15.4 mm module, FPC1, SW1, D1, R7, C3). Two strategies keep the bottom joints from re-melting: (A) one alloy and hot air on the top with the board preheated to ≤ 120 °C (SnBi) / ≤ 150 °C (SAC305), or (B) **two alloys** — bottom in SAC305 (liquidus 217 °C), top in SnBi58 (138 °C) on the hot plate at 165–175 °C, so the bottom never liquefies. Profiles: SnBi peak 165–175 °C for 30 s; SAC305 peak 235–245 °C; "the 0.6 mm board heats fast — do not exceed 60 s above liquidus". Hot air for the module: 300 °C, low flow, slow spiral, a gentle push once the paste melts.

**The concepts.** Solder paste is powdered alloy in flux; the flux cleans and protects the metal while the alloy melts and *wets* it. A reflow profile has four parts: **preheat** (ramp 1–3 °C/s to let volatiles escape without spattering), **soak** (flux activates, the board equalises), **reflow** (above liquidus long enough to wet every joint, typically 30–60 s, peak 20–30 °C above liquidus) and **cooling** (fast enough for a fine grain, slow enough not to crack ceramics). *Alloys*: SAC305 (Sn96.5/Ag3/Cu0.5) melts at 217 °C and is the industry lead-free standard; SnBi58 (Sn42/Bi58) melts at 138 °C, is weaker and more brittle but kind to small boards, plastic parts and your nerves; mixing them deliberately, as in strategy B, is a legitimate hierarchy — the 165–175 °C second pass is 42 °C below the SAC305 joints' liquidus. Mixing them *accidentally* (SnBi paste on a SAC-balled DSBGA) forms a mixed alloy with a lower, less predictable melting point, acceptable for a prototype and unacceptable for a product. *Why a hot plate*: a 0.6 mm board on a preheater reaches a uniform temperature from below without blowing 0402s around, and the plate's own temperature is the profile's ceiling; a USB microscope and a thermocouple on a scrap pad tell you the real board temperature, which lags the plate by tens of degrees. *Why hot air for the module*: the shield can is the biggest thermal mass on the board and its 65 pads are under the can's edge; air from above plus the preheater from below gets them to 170 °C together, and surface tension pulls the module onto its pads when the paste melts — the "gentle push" seats the edge pads. *Self-alignment* is also what saves slightly misplaced 0402s and DSBGAs; it fails when a pad is starved of paste (skips from a bad area ratio) or when one pad melts first (tombstoning on 0402s with unequal pad thermal mass). *Bottom parts on the second pass* hang by surface tension in strategy A — fine for 0402s and SOT-23s, nerve-racking under a module you are heating for a minute.

**Learn it.**

| Resource | Type | Time | Why this one |
|---|---|---|---|
| [Adafruit: SMT Manufacturing](https://learn.adafruit.com/smt-manufacturing) | article | 30 min | Stencil printing, placement and reflow as a small shop does it; the mental model for the two-pass build |
| [Adafruit Guide to Excellent Soldering: Surface Mount Components](https://learn.adafruit.com/adafruit-guide-excellent-soldering/surface-mount) | article | 30 min | Good/bad joint photos for chips, SOTs and QFNs — what you are inspecting for after each pass |
| SparkFun learn guide "Electronics Assembly" (learn.sparkfun.com) | article | 30 min | Stencil, paste, reflow and inspection stations explained with photos; search the title on the SparkFun learn site |
| [TI AN-1112 (SNVA009): DSBGA Wafer Level Chip Scale Package](https://www.ti.com/lit/snva009) | app note | 20 min | The reflow profile window and the "no underfill needed" notes for the YFP parts; what peak and time-above-liquidus the balls tolerate |
| Phil's Lab, PCB assembly / reflow / rework videos (YouTube channel) | video | 1 h | Stencil alignment by hand, hot-plate reflow of fine-pitch parts, hot-air placement of modules — the exact operations of §2.3 on camera |
| Mr SolderFix (YouTube channel) | video | 1 h | Hot-air technique, flux use and rework of QFN/BGA parts by a repair technician; watch a few before the module pass |

**Check yourself.**

1. Strategy B puts the hot plate at 170 °C for the top pass. How far below the SAC305 liquidus are the bottom joints, and why is that margin needed when the plate reads 170 °C?
2. A 0402 stands up on one pad after the bottom pass. Name the mechanism and two design or process causes on this board.
3. Why does §2.3 say to put *nothing* on the wire pads (J1, PAD1w, M1, SPK1 …) during reflow?
4. Strategy A, SnBi everywhere: the preheater must stay ≤ 120 °C during the top pass. Why that number and not 138 °C?

<details><summary>Answers</summary>

1. 217 − 170 = 47 °C. The board's real temperature lags and can overshoot the plate reading locally under the hot-air stream; the module pass also runs for a minute or more, so you want the bottom's SAC joints never to approach 217 °C even under the air.
2. Tombstoning: one pad's paste melts first, its surface tension lifts the part before the other pad wets. Causes here: a pad connected to a wide pour (one end of a decoupling cap to GND, the other to a thin trace) heating later, uneven paste from a marginal aperture, a thermal gradient across a 0.6 mm board on a plate.
3. Paste on a bare pad reflows into a bump that later has to be re-melted to take a wire; a dome of SnBi on a pad also wicks a 30 AWG wire poorly. Wires are soldered afterwards with an iron, one at a time, with strain relief.
4. 138 °C is where SnBi *melts*; the bottom joints start to soften and lose strength well before, and the hot-air stream adds heat from above. 120 °C keeps the whole bottom solid with margin while still bringing the top pads most of the way to reflow, so the air gun has only ~50 °C to add.

</details>

## 7.7 Hand soldering and rework: 0402, SOT, QFN/TQFN and what cannot be hand-soldered

**Why it matters in mcring.** After reflow comes the iron: the eleven wire pads (cell, charging pads, LRA, speaker, piezo, aux) take 30 AWG wires with "a dab of UV glue" for strain relief, the band's two 3 × 2 mm ENIG contacts are tinned by hand, and every bring-up fault in `docs/07` §4 ends in a rework — a 0402 pull-down to replace, a DSBGA to reflow, U9 that must "never be bridged". The MAX98357A was chosen in the **16-TQFN 3 × 3 mm** package over the 9-WLP specifically "for hand assembly" (`docs/03` §3.3).

**The concepts.** A joint needs three things: clean metal, flux, and enough heat for long enough to wet — not a hot tip pressed harder. Tip temperature ~320–350 °C for lead-free, a chisel or bevel tip for pads, a fine conical only for inspection-sized work; flux gel is the tool that turns a smeared bridge into two clean joints by letting the solder re-form under surface tension. *0402s*: tin one pad, slide the part in with tweezers while re-melting that pad, then solder the other; fix a tombstone by re-melting the lifted side with flux. *SOT/SOIC/VSSOP*: tack one corner pin, check alignment, solder the diagonal, then the rest; bridges on 0.5 mm pitch are wiped off by *drag soldering* with flux. *QFN/TQFN*: pre-tin the pads thinly, flux, place, and reflow the whole part with hot air (300–350 °C, low flow) because the pads are under the body; the exposed pad can be soldered through a via from the back with an iron if you leave a via unmasked. *DSBGA/WLCSP* cannot be hand-soldered: there is no access to the balls, so rework is remove-clean-repaste-reflow with hot air, and with 0.4 mm pitch you re-ball by replacing the part. *Removal*: hot air with a nozzle sized to the part, or two irons for a two-pin part; `ChipQuik`-style low-melt alloy for multi-pin parts you must save the board from. *Wires*: strip 2 mm, tin the strand, tin the pad, join with a touch, glue the wire 3–5 mm back so the joint never takes a bending load — the LRA and speaker leads move every time the ring is assembled. *ESD*: wrist strap, grounded mat and tip; the ESP32-S3 module and the LIS2DW12 are class-1 ESD parts and a dead I²C device after assembly is a classic ESD symptom. *Cleaning*: isopropyl alcohol and a brush after every flux job; no-clean flux residue is fine electrically but hides joints under the microscope and traps moisture under a conformal coat (`docs/07` §2.7).

**Learn it.**

| Resource | Type | Time | Why this one |
|---|---|---|---|
| [Adafruit Guide to Excellent Soldering: Surface Mount Components](https://learn.adafruit.com/adafruit-guide-excellent-soldering/surface-mount) | article | 30 min | 0402/SOT/QFN hand techniques with "good / too little / too much / bridged" photos |
| EEVblog "Soldering Tutorial" series (Dave Jones, YouTube: parts 1–3, part 3 is surface mount) | video | 1.5 h | Iron, tips, flux, drag soldering of fine pitch, QFN with hot air; the classic that most people learned from |
| Mr SolderFix (YouTube channel) | video | 1 h | Removal and replacement of QFN/BGA with hot air and low-melt alloy; flux discipline; exactly the rework you will do on U7/U8 |
| NASA Workmanship Standards (workmanship.nasa.gov pictorial reference) | reference | 30 min | Photos of acceptable and rejectable joints for wires, chips and leaded parts — the inspection standard for the 30 AWG wire pads |
| [EOS/ESD Association: Fundamentals Part 1 — An Introduction to ESD](https://www.esda.org/esd-overview/esd-fundamentals/part-1-an-introduction-to-esd/) | article | 20 min | Why the bench needs a strap and a mat before the module and the IMU go on, in the standards body's words |
| GreatScott! (YouTube channel) | video | 30 min | Short, practical SMD soldering and hot-air demonstrations aimed at first-time builders; pick the "how to solder SMD" videos |

**Check yourself.**

1. U9 (TPS22916, DSBGA-4) reads shorted VIN–VOUT after the bottom pass. Describe the rework, step by step, and what you cannot do with an iron.
2. Why does §2.3 solder the cell leads *last*, with the cell already in its pocket (`docs/07` §2.6 step 4)?
3. A 30 AWG wire to M1a breaks at the pad after three assemblies. Which two mistakes does that point to?
4. Flux residue under the mic (MK1) is harmless electrically. Why does the guide still want it clean there?

<details><summary>Answers</summary>

1. Hot air (small nozzle, ~320 °C, low flow) with the board on the preheater until the four balls melt, lift the part with tweezers, clean the pads with flux and a wipe, re-paste (or tin-and-flux) and place a *new* part, reflow with hot air; check adjacent-ball continuity is open. An iron cannot reach balls under the die, and the old part's balls are gone with the pads' solder.
2. A charged cell on the board during any further reflow or hot-air work is a fire risk, and its leads would be in the way of the top pass; soldering them with the cell seated also sets the lead length and avoids a second strain on the J1 pads.
3. No strain relief (glue 3–5 mm back) and/or a stiff joint: a wire soldered with the insulation flush to the pad flexes exactly at the solder, where the strands are brittle. The 15 mm length and the "dab of UV glue" exist for this.
4. The acoustic port is a Ø0.6 mm hole through the board under the mic; flux or residue can block it or leave a film that changes the mic's response, and the foam ring that seals the lid tube needs a clean, flat surface.

</details>

## 7.8 Inspection, bring-up order and the test-pad habit

**Why it matters in mcring.** `docs/07` §2.3 step 4 is the bring-up script: with the top side still empty, 4.0 V at a 100 mA current limit on TP8 (VBAT) / TP5 (GND) → TP6 `3V3` = 3.30 ± 0.05 V, `CAM_3V3` and `VLED` at 0 V, idle current < 20 µA; jumper R17's pad to TP6 → `CAM_3V3` 3.3 V, `CAM_2V8` 2.8 V, `CAM_1V2` 1.2 V; jumper R18 → `VLED` 3.3 V; then the charger with a real cell and 5 V on PAD1w: TP7 `nCHG` low, ~25 mA into the cell, ~0.25 V across D3, and nothing conducting with the polarity swapped. `floorplan.md` deviation 5 put all eight test pads (IO0, EN, D−, D+, GND, 3V3, nCHG, VBAT) on the *top* at 1.0 mm size and 1.5 mm pitch so that flashing, holding IO0, pulsing EN and bench-powering work with the board seated in the bay and the lid off; the earlier bottom-side pads would have been unreachable once the board sat on its ledges with wires soldered.

**The concepts.** *Inspect before power*: under the microscope, every DSBGA flat with no bridging at the perimeter balls, every QFN's edge fillets visible, no tombstones, no solder balls loose in the corridor; then a multimeter in continuity mode across supply rails to ground (VBAT–GND, 3V3–GND, CAM_3V3–GND) looking for shorts, and between adjacent fine-pitch pins. *Power first, in stages*: a bench supply with a current limit set just above the expected draw (100 mA here) turns a short into a sagging voltage instead of a burnt trace; measure the quiescent current and compare with the budget (< 20 µA: the TPS62840's 60 nA quiescent current, the 2.1 µA divider, and the standby currents of the DRV2605L and LIS2DW12) — a few milliamps means a rail is on (3 mA = the camera rail, per `docs/07` §4) and tells you *which* before any firmware exists. *Rails in order*: input → regulator output → gated rails → loads, each confirmed before the next is enabled, with jumper wires standing in for the MCU's enables. *Then the MCU*: flash over the native USB pads (D−/D+/GND only — never VBUS, the board runs from the cell or TP8, because the BQ25100's output is the 25 mA charge current and cannot power an ESP32-S3), enter download mode by holding IO0 low through a reset (EN pulsed low), and read the boot log's device probes (`LIS2DW12 ready at 0x18`, `DRV2605L ready`, `sensor PID=0x2640`) as the final continuity test of I²C, SCCB and the DVP bus. *Scope what moves*: `CAM_3V3` high for 0.3 s at boot and 0.2–0.5 s per capture, `VLED` pulsing for 60 ms blinks, the amp rail only during playback. *Test pads as a design habit*: every rail, every enable, every bus you may need to probe gets a 1 mm pad on the side you can reach after assembly, placed where probe hooks do not collide; the pads cost nothing on the bare board and save the board when the first fault appears. *Current measurement*: the sleep floor is 110–130 µA as the firmware stands (the IMU at 400 Hz), ≤ 30 µA after the low-power wake change — numbers a bench supply's display cannot resolve; a Power Profiler Kit II or a µCurrent in series with the cell can, and logging over an hour shows the periodic wakeups a meter averages away.

**Learn it.**

| Resource | Type | Time | Why this one |
|---|---|---|---|
| [Making Embedded Systems, 2nd ed. (Elecia White)](https://www.oreilly.com/library/view/making-embedded-systems/9781098151539/) | book | 2 h (the board bring-up chapter) | The hardware/firmware handshake: reading schematics, bring-up order, what to test before the first flash — the chapter `docs/07` §2.3–2.4 follows |
| [Memfault Interrupt: A Schematic Review Checklist for Firmware Engineers](https://interrupt.memfault.com/blog/schematic-review-checklist) | article | 20 min | The test-point, boot-strap and debug-access items are a bring-up plan in disguise; tick them against the eight pads |
| [Nordic Power Profiler Kit II](https://www.nordicsemi.com/Products/Development-hardware/Power-Profiler-Kit-2) | tool | 30 min | The source-meter the build guide names for the ≤ 130 µA sleep check; its *Get started* page shows ampere-meter vs source modes |
| [EEVblog µCurrent GOLD](https://eevblog.com/projects/ucurrent) | tool | 15 min | The cheaper way to see microamps with a normal multimeter without burden-voltage lies |
| [Adafruit Guide to Excellent Soldering: Surface Mount Components](https://learn.adafruit.com/adafruit-guide-excellent-soldering/surface-mount) | article | 15 min | Its inspection photos double as the pre-power checklist for DSBGA/QFN/0402 joints |
| [ESP-IDF: JTAG Debugging (ESP32-S3)](https://docs.espressif.com/projects/esp-idf/en/latest/esp32s3/api-guides/jtag-debugging/) | docs | 30 min | When the serial log is not enough: the S3's built-in USB-JTAG on the same D−/D+ pads, no extra probe needed |
| `docs/07-build-guide.md` §2.3 step 4, §2.4 and §4 (this repo) | procedure | 30 min | The actual bring-up script and troubleshooting matrix; read them once before the boards arrive and once with the first board on the bench |

**Check yourself.**

1. First power-up reads 3.3 V on TP6 but 3.1 mA of idle current with no module fitted. Which rail is on, which part do you suspect, and what one measurement confirms it?
2. Why does the guide forbid connecting USB VBUS to the stage-1 board, and what would actually happen if you did?
3. The TPS62840's VSET resistor (R12) is read from the wrong row of the table and 3V3 comes up at 3.0 V. Which later checks would have silently passed, and which would have failed first?
4. Design question: you add a stage-2 rigid-flex. Which four test pads would you keep if you could only have four, and why?

<details><summary>Answers</summary>

1. ~3 mA is the camera rail: `CAM_3V3` on means U2's ON pin (IO21 net) is not held low — R17 (100 kΩ pull-down) missing, misplaced or open. Measure `CAM_3V3` at C10: 3.3 V instead of 0 V confirms; a meter on U2.B1 shows a floating node.
2. 5 V would go onto whatever VBUS is tied to; on this board there is no VBUS net at all — the charger input is `CHG_PAD` through D2/D3 and the BQ25100 cannot supply the ESP32-S3's 300 mA peaks (its output is the 25 mA charge current). The board must run from the cell or a 4.0 V bench supply on TP8; USB data alone is harmless.
3. The module boots at 3.0 V (in spec), the LDOs and I²C parts run, BLE works — everything "passes". The first visible failure would be the WS2812 (already marginal at 3.3 V, `hardware/electrical/README.md` §6 item 10) looking dim or wrong-coloured, and the battery ADC calibration reading low if it assumed 3.3 V. Hence "TP6 = 3.30 ± 0.05 V" as the first line of the script.
4. GND, 3V3, EN and IO0 (or SWDIO/SWDCLK on an nRF52840): ground reference, the rail that proves the regulator, reset, and a way into the bootloader. USB data can come through a connector or pogo fixture; VBAT is available at the cell tabs.

</details>
