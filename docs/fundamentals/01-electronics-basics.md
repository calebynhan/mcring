# 1. Electronics basics

The stage-1 board (`hardware/schematic-notes.md`, `hardware/electrical/README.md`) is 87 placed parts, and almost every one of them is justified by a sentence of basic electronics: a divider that
costs 2 µA, a pull-down that holds a camera rail off while the ESP32-S3 floats, a 1 kΩ that turns an ESD-diode short into a 2.6 mA nuisance. This file teaches the fundamentals behind those
sentences, on mcring's own numbers. Read it next to `hardware/electrical/out/sch_power.svg` and `hardware/pinmap.md`; run the numbers yourself in `docs/build-helpers/tuning_calc.py` where a
calculator exists.



## 1.1 Voltage, current, power and Ohm's law

**Why it matters in mcring.** Every row of `hardware/power-budget.txt` is a current multiplied by a time. The battery divider in `hardware/schematic-notes.md` is 1 MΩ / 1 MΩ *because* 4.2 V
across 2 MΩ is 2.1 µA, while 100 k / 100 k would be 21 µA, most of the 25 µA standby budget (`hardware/electrical/README.md` item 13). The WS2812 data resistor R7 became 1 kΩ instead of 100 Ω
because 3.3 V through 100 Ω is a 27 mA pulse into an unpowered LED (item 10). The speaker's "0.25 W into 8 Ω" (item 20) is P = V²/R with V =
1.41 Vrms.

**The concepts.** Voltage is the push (potential difference between two points), current is the flow of charge through a part, resistance is how hard the part resists that flow. Ohm's law ties
them: V = I·R, so I = V/R and R = V/I. Power is P = V·I, and with Ohm's law also P = I²·R = V²/R. Energy is power × time; a battery's "capacity" in mAh is current × time, so a 30 mAh cell can
deliver 30 mA for one hour or 1 mA for 30 hours (ideally). Kirchhoff's two rules do the bookkeeping: currents into a node sum to zero, voltages around any loop sum to zero. Resistors in series
add; in parallel they combine as 1/R = 1/R1 + 1/R2 (two equal resistors halve). The divider is the most used circuit in the repo: Vout = Vin · R2 / (R1 + R2), and its current is Vin / (R1 + R2).
Worked on mcring: the 1 M / 1 M divider at 4.2 V gives
2.1 V to the ADC and draws 4.2 / 2 000 000 = 2.1 µA; over a day that is 2.1 µA × 24 h = 50 µAh, 0.05 mAh. The I²C pull-ups
(4.7 kΩ to 3.3 V) pass 3.3 / 4700 = 0.70 mA per line, but only while the line is held low. The 30 mAh cell at a nominal
3.7 V stores 30 mAh × 3.7 V = 111 mWh = 111 mWh × 3.6 J/mWh ≈ 400 J. A full-scale tone into the 8 Ω speaker at the 3 dB
gain setting is 1.41 Vrms, so P = 1.41² / 8 = 0.25 W and I = 1.41 / 8 = 0.18 A rms (peaks higher), which is why C3 (100 µF) sits on the 3V3 rail.

**Learn it.**

| Resource | Type | Time | Why this one |
|---|---|---|---|
| [SparkFun: Voltage, Current, Resistance, and Ohm's Law](https://learn.sparkfun.com/tutorials/voltage-current-resistance-and-ohms-law) | article | 30 min | The cleanest zero-prerequisite explanation, with the water analogy and a hands-on experiment |
| [Khan Academy EE: circuit analysis overview](https://en.khanacademy.org/science/electrical-engineering/ee-circuit-analysis-topic/ee-dc-circuit-analysis/a/ee-circuit-analysis-overview) | course | 2–4 h | Ohm's law, Kirchhoff, node and mesh methods with worked problems; the free structured path |
| [All About Circuits, Lessons in Electric Circuits Vol. I (DC)](https://www.allaboutcircuits.com/textbook/direct-current/) | book (free) | chapter 2 in 1–2 h | A real textbook: chapter 2 is Ohm's law and power, chapter 5 series/parallel; the reference to come back to |
| [Falstad circuit simulator](https://falstad.com/circuit/) | interactive | 30 min | Draw the 1 M / 1 M divider, watch the current dots slow down as you raise R; the fastest way to build intuition |
| [MIT OCW 6.002, Lecture 1: Lumped abstraction](https://ocw.mit.edu/courses/electrical-engineering-and-computer-science/6-002-circuits-and-electronics-spring-2007/video-lectures/lecture-1/) | video | 50 min | Agarwal explains *why* V, I and R are allowed to be lumped quantities at all; watch once the basics feel easy |
| [The Art of Electronics, 3rd ed. (official site)](https://artofelectronics.net/) | book | reference | Horowitz & Hill chapter 1 is the standard "foundations" chapter; the site carries the errata |

**Check yourself.**

1. The stage-0 build guide warns that a 10 k / 10 k divider "drains 210 µA, ten times the sleep budget". Verify it at 4.2 V.
2. The electrical README's "6 dB bench option" puts 2.0 Vrms across the 8 Ω speaker. What power and rms current is that?
3. R7 was 100 Ω before the review. With 3.3 V on the ESP32-S3 pin and roughly 0.6 V dropped across the LED's input diode, what current flowed into the unpowered LED?
4. How much energy, in joules, does a 16 mAh Oura-size cell hold at 3.7 V nominal? Compare with the 30 mAh stage-1 cell.

<details><summary>Answers</summary>

1. I = 4.2 V / 20 kΩ = 210 µA. Per day: 210 µA × 24 h = 5.04 mAh, a sixth of the 30 mAh cell every day.
2. P = 2.0² / 8 = 0.5 W; I = 2.0 / 8 = 0.25 A rms. That is the speaker's 500 mW *maximum*, hence the 3 dB default.
3. (3.3 − 0.6) / 100 Ω = 27 mA, the "27 mA pulses" in README item 10. With 1 kΩ it is 2.7 mA.
4. 16 mAh × 3.7 V = 59 mWh ≈ 213 J. 30 mAh → 111 mWh ≈ 400 J. About 2 % and 4 % of the ~10 kJ in a AA alkaline cell.

</details>

## 1.2 Resistors and capacitors in practice: pull-ups, decoupling, RC filters, the battery divider

**Why it matters in mcring.** `hardware/schematic-notes.md` is full of these parts: 4.7 kΩ I²C pull-ups, a 10 kΩ pull-up with 1 µF on the ESP32-S3 `EN` pin, a 100 kΩ pull-up on the BQ25100
open-drain `/CHG`, 100 kΩ and 4.7 kΩ pull-downs on the TPS22916 `ON` pins, 10 µF + 0.1 µF decoupling at the module plus a 100 µF bulk capacitor, and the 1 M / 1 M + 100 nF battery divider. The
electrical README's item 11 is a pull-up-versus-pull-down fight: the ROM enabled a pull-up on IO44 at reset and put 0.3–0.45 V on a 4.7 kΩ pull-down, at the edge of the load switch's VIL, so the
LED rail could glitch on at every reset. The fix was a different pin, not a different resistor.

**The concepts.** A CMOS input that is connected to nothing *floats*: it picks up whatever charge is nearby and reads high or low at random, and it can oscillate and waste current. A pull-up
(resistor to the supply) or pull-down (to ground) gives it a default; the resistor, not a wire, so that a switch, an open-drain output or the MCU can still pull it the other way. Smaller R =
stronger pull: faster edges and more immunity to leakage, at the cost of current while the line is driven against it. Typical choices:
4.7–10 kΩ for I²C (TI's SLVA689 gives the bounds: low enough to meet the rise time with the bus capacitance, high enough that the driver can still sink the current), 10–100 kΩ
for enables and status lines, 100 kΩ where the only job is to hold a floating pin off. When two pulls fight, you get a divider: the ESP32-S3's internal pull-up is roughly 45 kΩ, so against R18 =
4.7 kΩ the node sits at 3.3 × 4.7 / (45 + 4.7) ≈ 0.31 V, which is the 0.3–0.45 V the README measured against a VIL of about 0.35 V. Open-drain outputs (`/CHG`, SDA/SCL, the WS2812's absent
push-pull) can only pull low; the pull-up makes the high. A capacitor stores charge: Q = C·V, and the current through it is I = C · dV/dt. Three jobs follow. *Decoupling*: a chip's supply current
jumps in nanoseconds (the radio keys on, the camera's DVP bus toggles), and the battery and traces are too slow and too inductive to follow, so a local capacitor supplies the step and the supply
refills it; the droop is ΔV = I·Δt / C. For a 300 mA step that the TPS62840 takes 20 µs to respond to, a 100 µF bulk capacitor droops 0.3 × 20e-6 / 100e-6 = 60 mV; a 10 µF would droop 600 mV and
reset the chip. The 0.1 µF next to each pin handles the fast edges the 100 µF's own inductance cannot, which is why they come in pairs. Ceramic capacitors lose capacitance under DC bias: a 100 µF
ceramic at 3.3 V can be 40–70 µF, so read the bias curve (Phil's Lab #152 shows how to measure it). *RC filters* and delays: a resistor charging a capacitor has a time constant τ = R·C; the
voltage reaches 63 % in one τ and ~99 % in 5τ, and the cutoff frequency is f = 1 / (2π·R·C). The `EN` network, 10 kΩ × 1 µF = 10 ms, holds the ESP32-S3 in reset until the 3V3 rail is stable. The
button's 100 nF with the ~45 kΩ internal pull-up gives τ ≈ 4.5 ms of hardware debounce under the 30 ms software debounce in `config.h`. *The battery divider* (R8/R9 1 MΩ + C23 100 nF) is both:
its source impedance is R1 ∥ R2 = 500 kΩ, so τ = 50 ms and the node follows the (slow) battery fine, and the 100 nF is a local reservoir for the eight `analogReadMilliVolts()` samples in
`firmware/ring-esp32s3/src/power.cpp`, which would otherwise be pulled down by the ADC's sampling capacitor through 500 kΩ. The price of a 500 kΩ source is sensitivity to leakage: 50 nA of ADC
input leakage × 500 kΩ = 25 mV of error (README item 14), acceptable against a 3300–4150 mV window.

**Learn it.**

| Resource | Type | Time | Why this one |
|---|---|---|---|
| [SparkFun: Pull-up Resistors](https://learn.sparkfun.com/tutorials/pull-up-resistors) | article | 20 min | Floating pins, the button case, how to pick 10 kΩ; the exact logic behind every pull in the schematic notes |
| [TI SLVA689: I²C Bus Pull-up Resistor Calculation](https://www.ti.com/lit/SLVA689) | article | 30 min | The min/max bounds for the 4.7 kΩ on SDA/SCL, derived from VOL, sink current and the 30 %/70 % rise-time rule |
| [SparkFun: Capacitors](https://learn.sparkfun.com/tutorials/capacitors) | article | 30 min | Capacitance, charging, series/parallel, applications (local storage, filtering) at the right level |
| [EEVblog #859: Bypass Capacitor Tutorial](https://www.eevblog.com/2016/03/11/eevblog-859-bypass-capacitor-tutorial) | video | 33 min | Why decoupling exists, why you parallel values, why package matters, checked on an impedance analyser |
| [Eric Bogatin on Robert Feranec's channel: What decoupling capacitor value to use and where to place them](https://fedevel.com/blog/what-decoupling-capacitor-value-to-use-and-where-to-place-them-eric-bogatin) | video | ~1 h | Measured demonstrations of 1000 µF vs 1 µF, near vs far, one vs two; settles the "why 100 nF" question |
| [Phil's Lab #152: Ceramic Capacitor DC Bias Effects & Measurement](https://www.youtube.com/watch?v=Tfatk7wmnhs) | video | ~15 min | The 100 µF bulk ceramic on 3V3 is not 100 µF at 3.3 V; here is how much it loses and how to measure it |
| [Memfault Interrupt: A Schematic Review Checklist for Firmware Engineers](https://interrupt.memfault.com/blog/schematic-review-checklist) | article | 20 min | Pull-ups, decoupling, boot straps and test points from the firmware side; a checklist to run on `sch_mcu.svg` |

**Check yourself.**

1. Redo README item 11: the ROM pull-up is ~45 kΩ and R18 is 4.7 kΩ. What node voltage results, and what would 100 kΩ (as on R17) have given?
2. The TPS62840 responds to a load step in roughly 10–30 µs. For a 300 mA step and 20 µs, what droop do 10 µF, 47 µF and 100 µF give?
3. The `EN` network is 10 kΩ with 1 µF. What is τ, and why is it there at all?
4. R17 (100 kΩ pull-down on IO21, the camera load switch) is missing on an assembled board. What happens in deep sleep, and what number in `hardware/power-budget.txt` tells you?

<details><summary>Answers</summary>

1. 3.3 × 4.7 / 49.7 = 0.31 V (edge of VIL). With 100 kΩ: 3.3 × 100 / 145 = 2.3 V, solidly *on*: a stronger pull-down would have been the resistor fix, but the pin change removed the fight entirely.
2. ΔV = 0.3 A × 20 µs / C: 10 µF → 600 mV (reset territory), 47 µF → 128 mV, 100 µF → 60 mV. Then derate for DC bias and the 100 µF may really be 60 µF → 100 mV, still fine.
3. τ = 10 ms. It delays `EN` so the 3V3 rail and the module's internal regulators are settled before the chip starts; the ESP32-S3 datasheet's power-up sequence asks for it.
4. IO21 floats during deep sleep (pins are not driven), the TPS22916's smart pull-down may or may not hold, and the camera rail can switch on: sleep current jumps from the 25 µA profile to the "3 mA with camera board attached" profile, 72 mAh/day, i.e. the cell is flat by morning.

</details>

## 1.3 MOSFETs as switches and the load-switch pattern

**Why it matters in mcring.** Three TPS22916 load switches gate the camera rail (U2, IO21), the WS2812 rail (U9, IO33) and the speaker amp rail (U11, IO34); each has a pull-down on `ON` so the
rail is off while the MCU floats (`hardware/electrical/README.md` §3, power tree). An AO3400 N-channel MOSFET (Q1, gate from IO9 with 100 kΩ pull-down) is the low-side switch on the J2 aux pads.
`firmware/ring-esp32s3/src/power.cpp` drops `PIN_RGB_PWR` and the amp rail before `esp_deep_sleep_start()`. The reason all this exists is one line in the research: an un-gated camera board idles
at 3 mA, 120 × the whole standby budget, and an un-gated MAX98357A at 2.4 mA is 58 mAh/day, twice the cell.

**The concepts.** A MOSFET is a voltage-controlled switch: the gate-to-source voltage Vgs decides whether current flows between drain and source. An N-channel device turns on when the gate is
pulled *above* the source by more than its threshold Vgs(th), which is "barely conducts", not "fully on"; look at the Rds(on) column for the Vgs you will actually drive (a logic-level part is one
that is fully on at 2.5–3.3 V; the AO3400 is tens of milliohms at 3.3 V). On, it is a small resistor: P = I²·Rds(on), so 100 mA through 50 mΩ is 0.5 mW, nothing. Off, it leaks nanoamps. The gate
is a capacitor, so a GPIO can drive it directly but should never be left floating: the 100 kΩ gate pull-down on Q1 defines "off" during reset and deep sleep. *Low-side* switching (N-channel
between load and ground) is the easy case: the source is at 0 V, so a 3.3 V GPIO gives Vgs =
3.3 V. *High-side* switching (between supply and load, which you need when the load must see ground, like a camera with a ground-referenced DVP bus) wants a P-channel device,
which turns on when its gate is pulled *below* its source. The source sits at the rail, so to turn it *off* the gate must be pulled up to the rail, and a
3.3 V GPIO cannot do that to a 4.2 V VBAT rail. That is one reason for a load-switch IC: the TPS22916 is a P-channel
high-side switch plus a gate driver, a level-shifted `ON` input, a controlled turn-on slew and, on some variants, a quick-output-discharge pull-down, in a 0.78 × 0.78 mm package. Controlled slew
matters on a tiny cell: switching 3.3 V onto the camera's 10 µF in 1 ms (the "C" variant's class of rise time, which is why the README asks for ~1 ms before the first I²S sample) draws an inrush
of I = C·dV/dt = 10 µF × 3.3 V / 1 ms = 33 mA; a hard switch would dump the same charge in microseconds as an ampere-class spike pulled from a 30 mAh cell. Two more facts close the loop with the
firmware rules. First, every CMOS input has protection diodes to its supply pins; a high level on the input of an *unpowered* chip forward-biases that diode and powers the chip through it. This
is the WS2812 DIN story (R7) and the I²S story (R22–R24, 1 kΩ limits the back-feed to (3.3 − 0.7) / 1 kΩ ≈ 2.6 mA per pin): the pin states of a gated-off peripheral's inputs matter, and "park the
lines low before sleep" is the firmware half of the load-switch pattern. Second, a load switch's own leakage (10 nA) is what the gated rail costs in sleep, so the pattern buys three orders of
magnitude for a 0.78 mm part.

**Learn it.**

| Resource | Type | Time | Why this one |
|---|---|---|---|
| [GreatScott!: Electronic Basics #23, Transistor (MOSFET) as a Switch](https://www.youtube.com/watch?v=o4_NeqlJgOs) | video | ~8 min | N- and P-channel as switches, Vgs(th) vs fully on, gate resistor; the right first video |
| [EEVblog #748: How Do Transistors Work?](https://www.youtube.com/watch?v=qUeK7pHe0rI) | video | ~20 min | BJT and MOSFET explained at the silicon level, so Vgs and the body diode stop being magic |
| [SparkFun: Transistors](https://learn.sparkfun.com/tutorials/transistors) | article | 45 min | BJT crash course (saturation, cutoff, base resistor); useful for the DRV2605L's and amp's internals and for Q1 alternatives |
| [Core Electronics: MOSFETs for makers](https://core-electronics.com.au/guides/mosfets-for-makers-getting-started-with-high-power-control/) | article | 20 min | Choosing and wiring a MOSFET as a low-side switch from a microcontroller; the Q1 case exactly |
| [TI SLVA652: Basics of Load Switches](https://www.ti.com/lit/SLVA652) | article | 30 min | Why an integrated load switch instead of a discrete FET: sequencing, leakage, inrush control, controlled power-down |
| [TI TPS22916 product page and datasheet](https://www.ti.com/product/TPS22916) | datasheet | 30 min | The part on the board: 60 mΩ, 10 nA leakage, B/C/N variants, the "smart pull-down" on `ON` the README relies on |

**Check yourself.**

1. Why can a 3.3 V GPIO not reliably turn *off* a P-channel MOSFET whose source is on VBAT (3.3–4.2 V)? What does the TPS22916 add that fixes this?
2. Switching the camera rail (10 µF total) in 1 ms versus 10 µs: what inrush current in each case?
3. Using `tuning_calc.py speaker`'s 2.4 mA amp quiescent figure, how many mAh per day does an un-gated amp cost, and what fraction of a 30 mAh cell is that?
4. During a reset the ESP32-S3's pins float for tens of milliseconds. List what R17, R18 and R20 each do in that window.

<details><summary>Answers</summary>

1. Off needs Vgs ≈ 0, i.e. gate at the source voltage, up to 4.2 V; a 3.3 V output leaves Vgs = −0.9 V, partly on. A load switch level-shifts `ON` internally and drives the gate from the input rail.
2. I = C·dV/dt: 10 µF × 3.3 V / 1 ms = 33 mA; / 10 µs = 3.3 A (limited in practice by ESR and trace inductance, but a nasty spike for a 30 mAh cell and its PCM).
3. 2.4 mA × 24 h = 57.6 mAh/day ≈ 190 % of the cell per day. Hence U11 and `SD_MODE` tied to the gated rail.
4. R17 holds the camera load switch off (camera rail 0 V), R18 holds the LED rail off, R20 holds the amp rail off. Without them a floating `ON` could turn a rail on at every reset and at every deep-sleep entry.

</details>

## 1.4 LDO versus buck

**Why it matters in mcring.** The 3V3 rail comes from a TPS62840 buck (60 nA quiescent, 750 mA, R12 = 267 kΩ sets 3.3 V,
2.2 µH + 10 µF/10 µF), with a TLV75533 LDO named as the fallback "if you accept the dropout at 3.4 V battery"
(`hardware/schematic-notes.md`). Behind the camera load switch, two XC6206 LDOs make 2.8 V (AVDD) and 1.2 V (DVDD). The PCB design rules ask for 1 oz copper "for the 100 mW class LDO dissipation"
and a tight CIN–L–COUT loop for the buck (`hardware/electrical/README.md` §5). Those three choices are the whole LDO-vs-buck trade.

**The concepts.** A linear regulator (LDO = low-dropout linear regulator) is a transistor in series with the load that burns the difference: Vout is held by throttling, so Iin ≈ Iout and Ploss =
(Vin − Vout) · I. Efficiency is simply Vout / Vin. From a full LiPo at 4.2 V to 3.3 V the LDO is 79 % efficient and at 300 mA wastes 270 mW as heat; at 3.7 V, 89 %. *Dropout* is the minimum Vin −
Vout at which it still regulates (0.1–0.3 V for a good LDO at low current, more at high current): at a 3.4 V battery a 3.3 V LDO is at the edge, and below that the output just follows the input
minus the dropout. LDOs are tiny, cheap, quiet (good PSRR, no switching noise) and need only two capacitors, which is why the camera's
2.8 V and 1.2 V rails use them: the camera is on for 0.6 s per shot, the loss is (3.3 − 2.8) × ~50 mA = 25 mW for that
0.6 s, and noise on an image sensor's analog supply is the thing you least want. A buck (step-down switching) converter
chops the input with a switch into an inductor and capacitor, so energy is transferred rather than burnt: efficiencies of 85–95 % over a wide range, Iin ≈ Iout · Vout / Vin. It needs an inductor,
a careful layout (the SW node radiates), and it produces switching ripple. At very light load a modern buck drops into a power-save (PFM) mode, pulsing only when the output sags; the TPS62840
keeps good efficiency down to microamp loads and idles at 60 nA, which is why it is in a product that sleeps 99.9 % of the time. When Vin falls to within a few hundred millivolts of Vout the buck
goes to 100 % duty and behaves like an LDO with Rds(on) + inductor resistance as its dropout: on a 3.35 V battery the "3.3 V" rail becomes
3.35 − I · ~0.3 Ω, i.e. 3.26 V at 300 mA. The ESP32-S3 runs down to 3.0 V and the BATTERY_EMPTY_MV of 3300 in
`config.h` keeps the system out of that corner anyway. Two budgeting rules follow. For the *active* current, efficiency matters: a 300 mA capture peak costs the cell 300 mA through an LDO but
~270 mA (at 3.7 V in, 90 % efficient) through a buck. For the *standby* current, quiescent current matters: a regulator's IQ is paid 24 h a day, so a 5 µA LDO costs
0.12 mAh/day, 20 % of the 0.6 mAh/day stage-1 profile, while the TPS62840's 60 nA is invisible.

**Learn it.**

| Resource | Type | Time | Why this one |
|---|---|---|---|
| [TI: LDO basics video series](https://training.ti.com/ldo-basics-video-series) | video course | ~1 h (8 short parts) | Dropout, current limit, PSRR, noise, thermals: everything the XC6206 and TLV75533 lines in the BOM assume |
| [TI SNVA559: Switching regulator fundamentals](https://www.ti.com/lit/snva559) | article | 1–2 h | Inductance, PWM, buck topology, input/output capacitor roles, measuring ripple and efficiency |
| [EEVblog #110: Let's Design a DC to DC Switchmode Converter](https://www.youtube.com/watch?v=qGp82xhybs4) | video | ~1 h | Designs, builds and measures a buck from a datasheet; shows what the inductor and SW node really do |
| [TI TPS62840 product page and datasheet](https://www.ti.com/product/TPS62840) | datasheet | 45 min | The part on the board: 60 nA IQ, VSET table (267 kΩ = 3.3 V), power-save mode, 100 % duty behaviour |

**Check yourself.**

1. LDO from 4.2 V to 3.3 V at the 300 mA capture peak: efficiency and power lost. Same at 3.7 V.
2. The battery is at 3.35 V and the ESP32-S3 draws 300 mA. What does the TPS62840 output, roughly, and which parts on the board care?
3. An alternative 3.3 V LDO has IQ = 25 µA. How many mAh/day is that, and how does it compare to the whole 25 µA standby profile?
4. Which matters more for days-per-charge on the stage-1 ring, regulator efficiency or regulator quiescent current? Use the two regimes in `hardware/power-budget.txt` to argue it.

<details><summary>Answers</summary>

1. 3.3 / 4.2 = 79 %, loss (4.2 − 3.3) × 0.3 = 0.27 W. At 3.7 V: 89 %, 0.12 W. On a 0.6 mm board with no heatsink, 270 mW is a hot spot, hence the 1 oz copper note even for the small LDOs.
2. 100 % duty: ≈ 3.35 − 0.3 × 0.3 Ω ≈ 3.26 V. The ESP32-S3 (≥ 3.0 V) and the DRV2605L are fine; the WS2812 is already below its 3.7 V minimum by design (README item 10); the camera's LDOs each need their own dropout on top, so CAM_2V8 is safe but DVDD/AVDD margins shrink.
3. 25 µA × 24 h = 0.6 mAh/day, which alone equals the entire 25 µA stage-1 standby budget and would halve standby-only days.
4. In the "25 µA, 30 shots/day" profile, shots cost 30 × 154 µAh = 4.6 mAh/day and standby 0.6 mAh/day: efficiency on the active peaks (saving ~10 % of 4.6 mAh) and IQ (which can add 0.6 mAh/day) are the same order. On a stage-2 ring at 2–3 shots/day, IQ dominates completely.

</details>

## 1.5 Reading a datasheet: absolute maximum, typical versus maximum, timing diagrams

**Why it matters in mcring.** `hardware/electrical/README.md` §6 is a 20-item list of "assumptions to verify against the datasheets", and each item is a datasheet-reading skill: a ball map
(BQ25100 A1 IN … C2 VSS), a programming equation (K_ISET = 230 A·Ω → 9.1 kΩ = 25 mA), a logic threshold (TPS22916 VIL ≥ 0.35 V against the 4.7 kΩ pull-down), an absolute-maximum rating that could
not be read (item 19: are the MAX98357A digital inputs rated to VDD + 0.3 V or to +6 V independent of VDD? R22–R24 exist because the answer is unknown), and a footnote (IO26 and the PSRAM pins).
The DRV2605L register values in `docs/build-helpers/tuning_calc.py drv2605` are the datasheet's formulas typed in.

**The concepts.** A datasheet has a standard shape, and the trick is knowing which table answers which question. The *front page* sells; skim it for the headline numbers (60 nA, 10 nA leakage, 1
mA termination) and then distrust them until you find them in a table with conditions. The *pin / ball table* and *package drawing* are what the netlist and footprint must match exactly;
`hardware/electrical/mcring_v1.py` fails its self-check if a GPIO net drifts, but nothing checks that "pin 4 = SD_MODE" is true except you. *Absolute maximum ratings* are stress limits, not
operating points: exceeding them even briefly may destroy the part, and operating near them is not guaranteed to work. The BQ25100's IN pin is rated to −0.3 V; a ring seated backwards in a 2-pin
cradle puts −5 V on the pads, so D2 became a bidirectional TVS and D3 a series Schottky (README item 16). *Recommended operating conditions* are the design window (supply range, temperature,
logic levels). *Electrical characteristics* give min / typ / max under stated test conditions. Only min and max are guaranteed; *typ* is what a sample did at 25 °C. The ESP32-S3 deep-sleep figure
is 7–8 µA typical, and people measure 19–50 µA on some boards; the DRV2605L standby is "< 4 µA" and `tuning_calc.py sleep` uses 4 because that is the max. For a power budget use max where the
sheet gives one; for a divider use the leakage max (item 14's 50 nA). *Logic levels* are four numbers: the driver's VOH(min) and VOL(max), the receiver's VIH(min) and VIL(max), and the driver's
must clear the receiver's with margin. The WS2812 asks VIH ≥ 0.7·VDD: at VDD = 4.2 V that is 2.94 V, above the ESP32-S3's VOH(min) of
0.8 × 3.3 = 2.64 V, so the LED rail had to be 3V3 (then VIH = 2.31 V) rather than VBAT (README item 10). *Timing
diagrams* show relationships, not absolute times: read the arrows and the named parameters (t_ON, setup, hold, rise), then find their values in the switching-characteristics table. The
TPS22916C's turn-on time is about a millisecond, which sets the ≥ 1 ms wait before the first I²S sample; an I²S BCLK of 32 × 16 kHz = 512 kHz has a 977 ns half period, and the 1 kΩ series
resistor into ~10 pF of pin capacitance adds τ = 10 ns, so it is harmless (README item 20). *Programming equations* like I_SET = K_ISET / R_ISET are where the BOM's 9.1 kΩ and 11.5 kΩ come from;
always check the constant's units (A·Ω) and the valid resistor range. Finally, the *typical application* and *layout* sections are the vendor telling you the capacitors and loop shapes they
tested with, and the *errata* or revision history tell you what the previous datasheet got wrong. Keep your own §6-style list: every number you took from a sheet, which table it came from, and
whether it was typ or max.

**Learn it.**

| Resource | Type | Time | Why this one |
|---|---|---|---|
| [SparkFun: How to Read a Datasheet](https://www.sparkfun.com/tutorials/223) | article | 20 min | The classic beginner tour: first page, pinout, abs max, characteristics, errata |
| [Digi-Key Maker.io: How to Read and Understand Technical Datasheets](https://www.digikey.com/en/maker/tutorials/2024/how-to-read-and-understand-technical-datasheets) | article | 20 min | Recent, explicit on absolute maximum vs recommended operating conditions and why both exist |
| [TI SZZA036: Understanding and Interpreting Standard-Logic Data Sheets](https://www.ti.com/lit/SZZA036) | article | 1–2 h (skim) | Parameter-by-parameter definitions of VIH/VIL/VOH/VOL, timing and conditions; the reference for item 10 |
| [WaveDrom timing-diagram editor](https://wavedrom.com/) | interactive | 20 min | Draw the I²S BCLK/LRCLK/DIN relationship or the TPS22916 ON→VOUT delay yourself; reading diagrams gets easy once you have written one |
| [TI BQ25100 datasheet](https://www.ti.com/lit/gpn/BQ25100) | datasheet | 45 min | Practice target: find the ball map, K_ISET, K_PRETERM, the −0.3 V abs max on IN and the termination behaviour, then check README §6 item 4 |
| [Elecia White, *Making Embedded Systems*, 2nd ed.](https://www.oreilly.com/library/view/making-embedded-systems/9781098151539/) | book | chapter on hardware/datasheets, 1 h | Written for the firmware person who has to read schematics and datasheets; the voice this guide tries to copy |

**Check yourself.**

1. You swap the 30 mAh cell for a 20 mAh one and want 0.8 C. Using I_SET = K_ISET / R_ISET with K_ISET = 230 A·Ω, what R_ISET?
2. From the WS2812 rule VIH ≥ 0.7·VDD and the ESP32-S3 VOH(min) = 0.8 × 3.3 V: does the data line work at VLED = 3.3 V? At 3.7 V (the LED's own minimum)?
3. A regulator's IQ reads "60 nA typ, 240 nA max". Which number goes in `tuning_calc.py sleep`, and does it change anything at the 25 µA scale?
4. State the two facts about the BQ25100 IN pin and the cradle that together explain why D2 is bidirectional *and* D3 exists.

<details><summary>Answers</summary>

1. I = 0.8 × 20 mA = 16 mA; R = 230 / 0.016 = 14.4 kΩ → 14.3 kΩ (E96). Check the datasheet's allowed R_ISET range before trusting it.
2. At 3.3 V: VIH = 2.31 V < 2.64 V, works. At 3.7 V: VIH = 2.59 V vs 2.64 V, 50 mV of margin, marginal; at 4.2 V it fails. That is why the review chose 3V3 and accepted running the LED below its minimum.
3. The max, 240 nA. It is still 0.006 mAh/day, 1 % of the standby budget: the right habit, no practical change.
4. Abs max on IN is −0.3 V; a reversed ring presents −5 V on the pads. A unidirectional TVS would conduct forward at −0.7 V and hold IN below its limit; a bidirectional TVS blocks both ways, and the series Schottky stops any reverse current reaching IN.

</details>

## 1.6 SMD packages, pitch, 0402/0603, QFN/DSBGA/WLCSP, and what that means for hand assembly

**Why it matters in mcring.** The stage-1 BOM mixes packages on purpose: 0402/0603 passives, SOT-23 and SOT-583 regulators, a VSSOP-10 DRV2605L (3 × 3 mm, 0.5 mm pitch), an LGA-12 LIS2DW12 (2 × 2
mm, 0.5 mm), a 16-TQFN MAX98357A chosen over the 9-bump WLP "for hand assembly", and three parts that are *not* hand-friendly: two TPS22916 in a 0.78 ×
0.78 mm, 0.4 mm-pitch WCSP and the BQ25100 in a 1.6 × 0.9 mm DSBGA-6. Those three force the 0.10 / 0.10 mm track/clearance, 0.2 mm drills, NSMD pads, ENIG finish and two 0.10
mm stencils in `hardware/electrical/README.md` §5 and `docs/07-build-guide.md` §2.2, and the documented fallback is a SOT-23-5 TPS22917 if the fab cannot do it. Stage 2's nRF52840 WLCSP (3.5 ×
3.6 mm) and rigid-flex are listed as a risk in `docs/04-feasibility-and-risks.md` for the same reason.

**The concepts.** Passive sizes are four-digit *imperial* codes in hundredths of an inch: 0402 is 1.0 × 0.5 mm, 0603 is
1.6 × 0.8 mm, 0805 is 2.0 × 1.25 mm, 1206 is 3.2 × 1.6 mm. Metric codes exist for the same parts and collide with them (a
metric 0603 is an imperial 0201, 0.6 × 0.3 mm), so a BOM must say which system it uses. 0603 is the comfortable hand size; 0402 is routine with tweezers, a fine tip and a magnifier, and standard
for a board this dense. *Pitch* is the centre-to-centre spacing of pins or balls. Leaded packages (SOT-23, SOIC, VSSOP, TQFP) expose their pins beside the body, so you can drag-solder or touch
each one with an iron and inspect the fillets; 0.5 mm pitch is the practical limit for most people with an iron. No-lead packages (QFN/TQFN, DFN, LGA) have pads under the edges of the body and
often a large exposed thermal pad underneath; you cannot reach the pads with an iron, so they want paste and reflow (hot plate, oven or hot air), and they self-align as the solder melts. The
MAX98357A's 16-TQFN with 0.5 mm pitch is at the easy end of this class; its exposed pad must get paste and should sit on a grounded pour with vias. Ball packages (BGA, DSBGA, WCSP/WLCSP) put
solder balls under the die; a WLCSP is literally the bare die with balls, so it is small (the TPS22916 is 0.78 mm square), fragile, and impossible to inspect without X-ray. They demand: a stencil
(1:1 apertures, do not let the fab shrink them), a flat, co-planar finish (ENIG rather than HASL), non-solder-mask-defined pads of 0.22–0.25 mm, and a profile with a real soak so all balls melt
together. Fan-out is the layout cost: at 0.4 mm pitch there is no room for a trace between balls, and a 2 × 2 or 2 × 3 array only works because every ball is on the perimeter (README §5). Thin
boards help the via aspect ratio: 0.6 mm with 0.2 mm drills is 3:1. Two assembly facts decide the build order in `docs/07-build-guide.md` §2.3: the bottom side carries almost every IC and is
reflowed first; the top side (module, FPC connector, switch) goes on second, and the bottom parts survive the second reflow hanging on surface tension, which is fine for 0402s, SOT-23s and
DSBGAs. Alloy choice is a temperature choice: SnBi low-temperature paste melts at 138 °C and peaks at 165–175 °C, kind to a 0.6 mm board, a plastic switch and a microphone; SAC305 melts at 217 °C
and peaks at 235–245 °C and is what module and camera makers assume. After reflow, inspect under a microscope: every DSBGA sits flat with no bridging visible at the perimeter balls, then test
continuity between neighbouring pins before applying power.

**Learn it.**

| Resource | Type | Time | Why this one |
|---|---|---|---|
| [SparkFun: Integrated Circuits](https://learn.sparkfun.com/tutorials/integrated-circuits) | article | 30 min | DIP → SOIC → QFP → QFN → BGA with photos and the hand-solderability of each, plus pin-1 conventions |
| [Electronics Notes: SMD passive component sizes and the imperial/metric trap](https://www.electronics-notes.com/articles/electronic_components/surface-mount-technology-smd-smt/passive-component-size-codes-overlap-trap.php) | article | 10 min | The 0402/0603 dimension table and the exact collision that ruins a passives order |
| [JLCPCB: IC package types explained](https://jlcpcb.com/blog/ic-package-types-guide) | article | 15 min | SOIC, QFP, QFN, BGA, LGA, CSP from the fab's point of view, including what their assembly can and cannot place |
| [TI AN-1112 (SNVA009): DSBGA wafer-level chip-scale package](https://www.ti.com/lit/snva009) | article | 30 min | Handling, pad design, stencil and reflow for exactly the BQ25100/TPS22916 class of package |
| [Adafruit: SMT Manufacturing](https://learn.adafruit.com/smt-manufacturing) | article | 45 min | Paste storage, stencils, squeegee technique, syringe placement, reflow and clean-up for small runs |
| [Adafruit Guide to Excellent Soldering: Surface mount](https://learn.adafruit.com/adafruit-guide-excellent-soldering/surface-mount) | article | 15 min | Heat the pad first, solder away from the iron, wick for bridges: the iron technique for the 0402s and SOT-23s |

**Check yourself.**

1. A supplier lists "0603" capacitors with dimensions 0.6 × 0.3 mm. Which system is that, and what happens if you place them on the stage-1 footprints?
2. Sort the stage-1 ICs into iron-only, paste-and-hot-air-possible, and stencil-plus-reflow-mandatory: TPS62840 (SOT-583), DRV2605L (VSSOP-10), LIS2DW12 (LGA-12), MAX98357A (16-TQFN), TPS22916 (WCSP-4), BQ25100 (DSBGA-6).
3. Your fab's standard rules are 0.127 mm track/space and 0.3 mm drills. Which part changes and to what, and what else must be re-run?
4. Why does `docs/07-build-guide.md` §2.3 reflow the bottom side first, and which paste would you choose for a board that also carries a plastic side switch and a MEMS microphone?

<details><summary>Answers</summary>

1. Metric 0603 = imperial 0201. On an imperial 0603 footprint (1.6 × 0.8 mm) the part will tombstone or fall between the pads.
2. Iron-only: TPS62840, DRV2605L (0.5 mm leaded). Hot air or hot plate with hand paste possible: LIS2DW12 (LGA, pads reachable at the edge with care), MAX98357A (TQFN, exposed pad needs paste). Stencil + reflow mandatory, no inspection without X-ray: TPS22916, BQ25100.
3. Both TPS22916 (and U11) become TPS22917DBV in SOT-23-5 with the same nets, edited in `hardware/electrical/mcring_v1.py`; then regenerate the netlist and re-run `hardware/pcb/floorplan.py`, because the larger footprint moves parts and the placement checks must pass again.
4. The bottom holds 72 of 87 parts including the DSBGAs, which need the flattest, most controlled first reflow; the module on top is heavy and goes second, with the bottom parts held by surface tension. SnBi (peak 165–175 °C) spares the switch, mic and 0.6 mm board, provided every part on the board tolerates a low-temperature alloy; otherwise SAC305 with the module makers' profile.

</details>

## 1.7 ESD basics

**Why it matters in mcring.** The ring is worn on a hand, the most electrostatically charged object in most rooms, and it has exposed conductors: two ENIG charging pads in the inner band, a
copper touch electrode under 0.8 mm of resin, and a u.FL antenna lead. `hardware/schematic-notes.md` puts a PESD5V0S1BB TVS (D2) on the charging input and 1 kΩ in series with the touch pad. The
electrical README's longest arguments (items 10 and 20, R7 and R22–R24) are about the *internal* ESD protection diodes every chip has, and how they turn an unpowered chip into a leak when a
neighbouring pin is high. And the parts you will hand-place, 0.4 mm-pitch WCSPs and a bare-die-sized DSBGA, are among the most ESD-sensitive things on the board.

**The concepts.** Rubbing or separating two materials transfers charge (triboelectric charging); walking across a carpet can leave a person at several thousand volts, and dry air makes it worse.
When that charge finds a conductor it discharges in nanoseconds with peak currents of amperes: that is ESD. Engineers model it three ways: the *human body model* (HBM, a 100 pF body through 1.5
kΩ), the *charged device model* (CDM, the part itself is charged and discharges through one pin, the dominant failure in automated handling) and the machine model. Many components are damaged
below 100 V, far below the ~3 kV a person can feel. Damage is either *catastrophic* (the pin is dead, you find it at bring-up) or *latent* (a weakened junction that fails weeks later in the
field; the one you never trace). Every CMOS input carries clamp diodes to its supply and ground rails that shunt a discharge away from the gate oxide; they are rated for a few hundred volts to a
few kilovolts HBM and are the reason chips survive normal handling. They are also why a high level on an input of an unpowered chip forward-biases the diode to VDD and powers the chip through it,
the mechanism behind R7 and R22–R24: a series resistor turns an unbounded diode current into a bounded (2.6 mA) one. System-level ESD (the IEC 61000-4-2 test, ±8 kV contact) hits whatever a user
can touch, so protection lives at the connector or pad: a TVS diode clamps the pad to ground before the current reaches the IC (D2 is bidirectional because the cradle can present either
polarity), a series resistor limits what gets through (the touch line's 1 kΩ), and a short, wide ground return gives the energy somewhere to go. Spacing matters too: air breaks down at roughly 1
kV per 0.3 mm, so the ≥ 3 mm between the two charging pads is also an ESD gap. At the bench the rules are mundane and non-negotiable for WLCSP work: a grounded wrist strap, a dissipative mat, a
grounded soldering iron tip and hot plate, parts kept in their trays or tape until placement, no fleece, and humidity above ~40 % if you can manage it. Handle bare dies by the edges with ESD-safe
tweezers and never slide them across a surface.

**Learn it.**

| Resource | Type | Time | Why this one |
|---|---|---|---|
| [EOS/ESD Association: Fundamentals Part 1, An Introduction to ESD](https://www.esda.org/esd-overview/esd-fundamentals/part-1-an-introduction-to-esd/) | article | 20 min | Charge generation, HBM/CDM/MM, catastrophic vs latent failure, device sensitivity; the authoritative primer |
| [EOS/ESD Association: Fundamentals series index](https://www.esda.org/esd-overview/esd-fundamentals/) | article series | 1–2 h | Parts 2–3 cover control principles and bench materials (mats, straps, dissipative vs conductive) |
| [TI: ESD Essentials, What is electrostatic discharge?](https://www.ti.com/video/5757235691001) | video | ~5 min | The short version, with practical system-protection tips, from a TVS vendor |
| [TI: Getting started with interface protection (video series)](https://www.ti.com/video/series/getting-started-with-interface-protection.html) | video series | ~30 min | TVS selection, clamping voltage, where to put the protection relative to the connector: the D2 decision |
| [TI: Logic electrostatic discharge (ESD) protection](https://www.ti.com/video/6276931340001) | video | ~5 min | How the on-chip diodes work and what their ratings mean, i.e. the physics behind README items 10 and 20 |

**Check yourself.**

1. Why must D2 be bidirectional, and what did the earlier unidirectional TVS do to the BQ25100's IN pin when the ring was reversed?
2. List the conductors on the finished stage-1 ring a user can touch, and say what protects each.
3. Explain, in terms of the on-chip ESD diodes, why `audio_out.cpp` must park IO35–37 low while the amp rail is off, and why R22–R24 make a wrong state a drain rather than damage.
4. Write the five-line bench checklist you will follow before opening the TPS22916 tape.

<details><summary>Answers</summary>

1. The cradle can apply ±5 V. A unidirectional TVS forward-conducts at about −0.7 V, holding IN at −0.7 V, below its −0.3 V absolute maximum while passing cradle current through a SOD-523. Bidirectional parts block both polarities; D3 then stops any reverse path.
2. Charging pads (D2 TVS + D3 Schottky, ≥ 3 mm gap, keyed cradle), touch electrode (0.8 mm resin, then 1 kΩ into the pin), the antenna (behind resin; the u.FL lead is inside the bay). Everything else is under the shell.
3. With VAMP at 0 V, a high I²S line forward-biases the amp input's diode to VDD and tries to power the amp (and the SD_MODE pull-down) through that pin. 1 kΩ bounds the current to ≈ 2.6 mA per pin: no diode damage, but a battery drain of the un-gated-amp class, so firmware must still park the pins.
4. Wrist strap on and clipped to the mat's ground; dissipative mat under the board; iron tip and hot plate grounded; parts stay in tape/tray until placement, picked by the edges with ESD-safe tweezers; no synthetic fleece, humidity up if possible.

</details>
