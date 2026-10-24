# 2. Batteries and power budgets

The README's first engineering conclusion is "battery and peak current, not chip size, decide the ring", and the two numbers behind it live in `docs/03-hardware-spec.md` §3.1:
a real ring carries 16–22.5 mAh at about 1C, and an ESP32-S3 camera board peaks at 300–370 mA. This file teaches what those numbers mean, how `hardware/power_budget.py`
turns them into days-per-charge, and how to measure them on the bench (`docs/07-build-guide.md` §1.11 and §2.4). Keep `hardware/power-budget.txt` and
`docs/build-helpers/tuning_calc.py` open; every exercise below can be checked against them.

Units: 1 mAh = 1000 µAh = 3600 mAs (milliamp-seconds). Current × time is charge; charge × voltage is energy.

## 2.1 LiPo chemistry and safety

**Why it matters in mcring.** Stage 1 runs on a 301012 flat pouch cell, 30 mAh with a protection circuit module (PCM), sitting in a 10.4 × 12.4 × 3.4 mm pocket in the bay floor with
0.35 mm of clearance above it (`hardware/schematic-notes.md`, `hardware/cad/fit_report.md`); stage 0 uses a 100 mAh cell on the XIAO's charger; stage 2 needs a Grepow curved
cell of 14.5–24 mAh, the part `docs/03` calls the hardest to source. `firmware/ring-esp32s3/src/config.h` sets `BATTERY_FULL_MV 4150` and `BATTERY_EMPTY_MV 3300`, and
`power.cpp` turns millivolts into a percentage with a piecewise-linear table because the discharge curve is not a straight line. The pogo cradle gets a Schottky diode and a
bidirectional TVS because a ring can be seated backwards.

**The concepts.** "LiPo" is a lithium-ion cell in a soft aluminium-laminate pouch; the chemistry (lithium cobalt oxide or NMC cathode, graphite anode) is the same as a phone's. One
cell is nominally 3.7 V: fully charged it sits at 4.2 V, it spends most of its discharge between 3.9 and 3.6 V, and below about 3.5 V the voltage falls off a cliff. That shape is
why `battery_pct()` uses a table (3.7 V is 35 %, 3.9 V is 75 %) and why a cutoff of 3.0 V is "empty" for the chemistry while mcring stops at 3.3 V to keep margin for the buck's
dropout and the voltage droop under a capture peak. The cell is intolerant in four ways. Overcharge above about 4.25 V plates metallic lithium and can start thermal runaway; the
charger's voltage accuracy (±50 mV) is a safety spec. Over-discharge below about 2.5 V dissolves the copper current collector and the cell never recovers; it is also why a ring
left in a drawer for months must be stored around 40–50 % and why the firmware sleeps instead of running the cell flat. Charging below 0 °C plates lithium even at normal voltage.
Mechanical damage, a puncture or a crushed pouch, shorts the separator. A pouch also *swells* as it ages or is abused (gas from electrolyte decomposition), which is the reason the
cell pocket has slack and nothing presses on the pouch. The PCM glued to the cell's tab is a tiny board (typically a DW01-class protection IC and a dual MOSFET) that opens the
circuit on overcharge (~4.25–4.3 V), over-discharge (~2.5–3.0 V), over-current and short circuit; it is the last line of defence, not the charger. Energy-wise, 30 mAh × 3.7 V is
111 mWh ≈ 400 J, about a hundredth of a phone battery, enough to heat a small pouch but not a hazard on the scale of an 18650; still, a cell on a finger gets the same rules as any
lithium cell: no soldering directly to the pouch tabs without heat control, no reflow with the cell fitted, no charging unattended on the bench the first time, and shipping only
as UN38.3-tested cells. Capacity is also not a constant: it falls with cycles (hundreds of full cycles to 80 %), with cold, and with discharge rate, which is why
`power_budget.py` only counts 80 % of the label as usable.

**Learn it.**

| Resource | Type | Time | Why this one |
|---|---|---|---|
| [Adafruit: Li-Ion & LiPoly Batteries](https://learn.adafruit.com/li-ion-and-lipoly-batteries) | article | 30 min | Names, voltages, protection circuitry and proper charging for exactly the hobby pouch cells used at stages 0 and 1 |
| [Battery University BU-204: How do Lithium Batteries Work?](https://www.batteryuniversity.com/article/bu-204-how-do-lithium-batteries-work/) | article | 20 min | The chemistry in plain language: cathode families, why 4.2 V, what ages a cell |
| [Battery University BU-304a: Safety Concerns with Li-ion](https://www.batteryuniversity.com/article/bu-304a-safety-concerns-with-li-ion/) | article | 20 min | Internal shorts, separator failure, thermal runaway, what actually causes field fires |
| [Battery University BU-304: Why are Protection Circuits Needed?](https://www.batteryuniversity.com/article/bu-304-why-are-protection-circuits-needed/) | article | 15 min | What the PCM on the 301012 does and does not do |
| [Battery University BU-808: How to Prolong Lithium-based Batteries](https://www.batteryuniversity.com/article/bu-808-how-to-prolong-lithium-based-batteries/) | article | 30 min | Depth of discharge vs cycle life, storage charge, heat; the data behind the 80 % usable assumption |
| [Battery University: Pouch cell, small but not trouble-free](https://www.batteryuniversity.com/article/pouch-cell-small-but-not-trouble-free/) | article | 10 min | Swelling and mechanical rules for pouch cells, i.e. why the cell pocket has clearance |
| [DigiKey: Oura Ring Teardown (Gen 3 and 2)](https://www.digikey.com/en/maker/projects/oura-ring-teardown-gen-3-and-2/2c005e01f82d429398e78f49591793cc) | article | 15 min | The 16 mAh Grepow cell and BQ25120A charger inside a shipping ring; the reference point for `docs/03` §3.1 |

**Check yourself.**

1. Using the table in `power.cpp`, what percentage does the ring report at 3.75 V? At 3.55 V?
2. Why is `BATTERY_EMPTY_MV` 3300 and not the chemistry's 3000 mV? Name two things on the stage-1 board that need the margin.
3. The cell pocket is 3.4 mm deep for a 3.0 mm cell, with 0.35 mm clearance above. Give two reasons the designers did not make it 3.05 mm.
4. The PCM's over-current trip is a property of the cell's protection board, not of mcring. Why does that matter for the 300 mA capture peak, and where would you look it up?
5. A built ring will sit in a drawer for three months. Is deep sleep enough to protect the cell, and what state of charge do you leave it at?

<details><summary>Answers</summary>

1. 3.75 V lies between 3700 (35 %) and 3800 (55 %): 35 + 50 × 20 / 100 = 45 %. 3.55 V: between 3500 (5 %) and 3600 (15 %): 5 + 50 × 10 / 100 = 10 %.
2. Under a 300 mA peak the cell droops by I × R_internal (hundreds of millivolts on a tiny cell), and the TPS62840 at 100 % duty can only deliver Vin minus its own drop; at 3.0 V the "3V3" rail would be ~2.9 V, below the camera LDOs' needs and near the ESP32-S3's 3.0 V minimum. 3.3 V keeps the rail honest and keeps the cell away from the PCM's over-discharge trip.
3. Pouch cells swell with age and abuse, cell thickness has a tolerance (the 501012 alternative is 5 mm), and pressing on a pouch risks the separator; the fit report keeps 0.35 mm of air.
4. If the PCM's over-current threshold is below the capture peak (small-cell PCMs can trip at a few hundred milliamps), the cell disconnects mid-shot and the ring browns out. The threshold is on the cell/PCM datasheet, and the first bench test in `docs/07` §1.11 should confirm the peak passes.
5. No. Deep sleep at the 25 µA profile is 0.6 mAh/day, 54 mAh in 90 days, more than the cell; at the firmware's 110 µA floor it is 238 mAh. The PCM's over-discharge cutoff is the only backstop, and resting at 2.5–3.0 V ages the cell. Store it at 50–60 % (about 3.8 V), cool, and either top it up monthly or unsolder the cell at J1; a `SLEEP`-forever or ship-mode is a sensible firmware follow-up.

</details>

## 2.2 C-rate, protection circuits, chargers and termination current: why 1C matters for a 16–30 mAh cell

**Why it matters in mcring.** The BQ25100 is programmed for 25 mA (R_ISET 9.1 kΩ, K_ISET = 230 A·Ω), "≈ 0.85 C for the 30 mAh 301012 cell", and for 1 mA termination
(R_PRETERM 11.5 kΩ) (`hardware/electrical/README.md` item 6). The BOM note says an MCP73831 "is OK for ≥ 40 mAh cells", i.e. not for this one. `docs/03` §3.1 says a 1C 16 mAh cell is
"specified for ~16 mA continuous" and that the ESP32-S3 capture peak is 15–20 × that. `power-budget.txt` ends with the sentence "300–370 mA = 15–20C on a 1C-rated 16–22 mAh ring
cell → not viable". Everything in this section is unpacking those lines.

**The concepts.** C-rate normalises current to capacity: a current of 1C empties (or fills) the cell in one hour, so 1C is 16 mA for a 16 mAh cell and 30 mA for a 30 mAh cell;
0.5C is a two-hour rate, 2C a 30-minute rate. Cell datasheets give a *maximum continuous discharge* (often 1C for thin curved cells, 2–5C for hobby pouch cells) and a *maximum
charge* rate (usually ≤ 1C, with 0.5–0.8C recommended for life). Drawing more than the rated C-rate does three things: it heats the cell (loss = I² × R_internal, and a 30 mAh
pouch has an internal resistance of the order of an ohm, not milliohms: 300 mA is 90 mW of heat inside a cell that weighs about a gram), it collapses the terminal voltage (I × R_internal =
0.3 V at 1 Ω, pushing a 3.6 V cell to 3.3 V at the worst moment), and it risks the PCM's over-current trip. 300 mA is 10C on the 30 mAh stage-1 cell and 19C on a 16 mAh Oura cell;
the stage-1 ring gets away with it because of the 100 µF bulk capacitor, the 3.3 V cutoff and short peaks, stage 2 cannot. Charging is the mirror image. A Li-ion charger runs
constant-current/constant-voltage: it pushes the programmed current (25 mA) until the cell reaches 4.2 V, then holds 4.2 V while the current tapers as the cell fills, and
*terminates* when the current falls below a threshold. Battery University's rule is 3–5 % of capacity: 0.9–1.5 mA for 30 mAh, 0.5–0.8 mA for 16 mAh. That is the whole reason for
the BQ25100: its termination goes down to 1 mA, where common hobby chargers (MCP73831: 7.5 % of the programmed current, TP4056: a tenth of its programmed current, which cannot go below ~130 mA) terminate at several
milliamps and would either stop a 30 mAh cell early or, if the taper never reaches their threshold, keep it at 4.2 V indefinitely. Below about 3 V the charger *pre-charges* at a
trickle to wake a deeply discharged cell safely, and a safety timer gives up if the cell never comes round. The programming resistors follow I = K / R, so the 9.1 kΩ gives
230 / 9100 = 25.3 mA and the 11.5 kΩ gives 11.5 / 11 500 = 1.0 mA. Time to full from empty is about capacity / current for the CC phase plus a taper: 30 / 25 = 1.2 h plus ~20 min,
the "~1.5 h" in `docs/07` §2.8. Two more practicalities: the charger delivers at most its programmed current, so a BQ25100 with no cell cannot run a 300 mA ESP32-S3 (README §4: bench
power goes on TP8), and `/CHG` is open-drain active-low, so reading it needs the 100 kΩ pull-up that costs 33 µA only while charging.

**Learn it.**

| Resource | Type | Time | Why this one |
|---|---|---|---|
| [Battery University BU-402: What is C-rate?](https://www.batteryuniversity.com/article/bu-402-what-is-c-rate/) | article | 10 min | The definition with the 1 Ah worked example, and why capacity reads lower at high rate |
| [Battery University BU-409: Charging Lithium-ion](https://www.batteryuniversity.com/article/bu-409-charging-lithium-ion/) | article | 30 min | CC/CV stages, the 4.20 V ± 50 mV limit, the 3–5 % termination rule, no trickle charge; the source of this section's charger rules |
| [TI: Battery management deep dive, on-demand training](https://www.ti.com/video/series/battery-management-deep-dive-on-demand-technical-training.html) | video course | 16 min for "Introduction to Li-Ion battery charging", more if you like | Charger vendor's own walk through CC/CV, pre-charge, termination and safety timers |
| [TI BQ25100 datasheet](https://www.ti.com/lit/gpn/BQ25100) | datasheet | 45 min | The part on the board: K_ISET, K_PRETERM, the 1 mA termination floor, 75 nA battery leakage, no TS pin on this variant |
| [Grepow: smart ring batteries](https://www.grepow.com/wearables/smart-ring.html) | vendor page | 10 min | What a 1C curved ring cell looks like (1.4–1.7 mm thick, 4.5–7 mm wide) and why `docs/03` calls it the hardest part to source |
| [Memfault Interrupt: Smart Ring Development (Part 2), Hardware Design](https://interrupt.memfault.com/blog/smart-ring-development-part-2) | article | 25 min | An open-source ring's charger (BQ25125), rigid-flex and wireless-charging choices; a second opinion on every stage-2 decision |

**Check yourself.**

1. You source a 20 mAh curved cell rated 1C charge. Pick a 0.8C charge current and compute R_ISET (K_ISET = 230 A·Ω). What termination current does the 3–5 % rule want, and can the BQ25100 provide it?
2. Express the ESP32-S3 peak (300 mA) and the nRF52840 radio peak (~5 mA) as C-rates on 16 mAh and on 30 mAh.
3. A 30 mAh cell has 1.2 Ω internal resistance and sits at 3.6 V open-circuit. What terminal voltage does a 300 mA peak produce, and what does `BATTERY_EMPTY_MV` make of that moment?
4. Why can the MCP73831 be "OK for ≥ 40 mAh" but not for 30 mAh? (Its termination is a fixed fraction of the programmed current.)
5. The ring is in its cradle with the cell removed for a bench test. Why does the ESP32-S3 not boot, and where do you put the bench supply?

<details><summary>Answers</summary>

1. 0.8 × 20 = 16 mA → R = 230 / 0.016 = 14.4 kΩ. Termination 3–5 % of 20 mAh = 0.6–1.0 mA; the BQ25100's floor is 1 mA, right at the top of the window, acceptable.
2. 300 mA: 18.75C on 16 mAh, 10C on 30 mAh. 5 mA: 0.31C on 16 mAh, 0.17C on 30 mAh. One is a stress test, the other is a trickle.
3. 3.6 − 0.3 × 1.2 = 3.24 V, below 3300 mV: an eight-sample `battery_mv()` taken during the peak would report "empty" and could trigger `LOW_BATTERY`. Average the reading outside captures, or budget the droop into the threshold.
4. At 40 mAh you can program ~40 mA and its termination (about 3 mA) is ~7.5 % of capacity, already high; at 30 mAh with 25 mA programmed, termination is ~1.9 mA, 6 % of capacity, and the taper on a tiny cell may hover near it. The 1 mA floor of the BQ25100 keeps termination inside the 3–5 % rule for both cells.
5. The charger's output is limited to its 25 mA programmed current, far below the boot current. Put a current-limited 4.0 V supply on TP8 (VBAT) and TP5 (GND); 5 V belongs only on the charging pad net.

</details>

## 2.3 Average versus peak current, µAh arithmetic, sleep versus active duty cycle

**Why it matters in mcring.** `hardware/power_budget.py` models a shot as three (current × time) products plus a 24-hour standby term, and `hardware/power-budget.txt` prints the
result: 153.6 µAh per shot for the ESP32-S3 profile, 0.60 mAh/day at 25 µA standby, 9.1 mAh/day at 380 µA (BLE kept alive in light sleep), 72 mAh/day at the dev kit's un-gated 3 mA.
`docs/build-helpers/tuning_calc.py sleep` shows the firmware's real standby floor is ~110 µA because the LIS2DW12 is left in its 90 µA 400 Hz mode, and `tuning_calc.py speaker`
prices a 10 s spoken answer at 125 mA. `docs/04` says a 10 s answer costs 280–420 µAh, "2–3 × a photo". All of that is one skill: multiply, add, convert.

**The concepts.** A battery does not care about peaks, only about the integral: charge used = Σ (current × time). Convert everything to one unit; µAh is convenient because events
are short and standby is small. An event at 180 mA for 0.6 s is 180 × 0.6 = 108 mAs; divide by 3600 to get 0.030 mAh = 30 µAh. The model's ESP32-S3 shot is 0.6 s × 180 mA
(capture) + 0.5 s × 90 mA (transfer) + 10 s × 40 mA (feedback) = 108 + 45 + 400 = 553 mAs = 153.6 µAh. Notice what dominates: the 10 s haptic *Morse* reply, a relic of the
pre-voice design, is 72 % of the shot. With the current cue scheme (`docs/07` §1.11: a double tick is ~0.2 s at 40–80 mA ≈ 2–4 µAh) a photo question costs about 45 µAh, three times
less than the file says, and `docs/03` §3.3 notes exactly this caveat. A ring-mic question adds the thing the model does not have at all: up to 8 s of recording at 40–60 mA
(§1.11) = 90–130 µAh, plus the 64 KB ADPCM transfer. Standby is the other regime: a constant current × 24 h. 25 µA × 24 = 600 µAh = 0.6 mAh/day; 110 µA = 2.64 mAh/day; 380 µA =
9.1 mAh/day; 3 mA = 72 mAh/day, more than the cell. Days per charge = usable capacity / (standby per day + events per day × charge per event). Which regime dominates is the first
question to ask of any design: for the stage-1 best case, 30 shots × 154 µAh = 4.6 mAh/day against 0.6 mAh/day standby, so shots dominate and the cue change matters; for stage 2
at 2 µAh per cue-only shot, standby dominates and the IMU's wake mode matters. *Duty cycle* is the fraction of time awake; a ring awake 0.1 % of the day at 30 mA averages 30 µA,
about the same as its sleep floor, which is the intuition behind "wake up, do the job fast, go back to sleep" and behind `DEFAULT_IDLE_SLEEP_S 120`: two minutes awake and
advertising at 20–40 mA cost 1 mAh, as much as 20 shots. *Average* current (what the integral divided by time gives you) decides days; *peak* current (the 300 mA spike) decides
C-rate stress, voltage droop and regulator limits, and the two are unrelated: a short peak can be enormous and still cheap in µAh. Measure peaks with a scope on a shunt, measure
charge with an instrument that integrates (a PPK2's window average), and never try to read either from a multimeter's needle.

**Learn it.**

| Resource | Type | Time | Why this one |
|---|---|---|---|
| [Jack Ganssle: Designing Hardware/Firmware for Low Power MCUs](https://www.ganssle.com/reports/ultra-low-power-design.html) | article (report) | 1–2 h | Measured, sceptical treatment of sleep currents, "typical" specs, leaks and duty cycle; the best single read on this section |
| [Jack Ganssle: Leaks and Drains in Low Power](https://www.ganssle.com/rants/leaks_and_drains.html) | article | 15 min | The short version: where the microamps go when the datasheet says they should not |
| [Nordic Online Power Profiler for Bluetooth LE](https://devzone.nordicsemi.com/power/) | interactive | 15 min | Enter a connection interval and payload and read the average current of the radio event; fill the `transfer_ma` line of a stage-2 profile with it |
| [Nordic DevAcademy: Designing Low-Power Bluetooth LE Products](https://academy.nordicsemi.com/courses/designing-low-power-bluetooth-le-products/) | course | 10–12 h | Power budgeting, PMICs, measurement pitfalls, advertising/connection tuning; lesson 4 is the duty-cycle maths applied to BLE |
| [Memfault Interrupt: Understanding Battery Performance of IoT Devices](https://interrupt.memfault.com/blog/monitoring-battery-life) | article | 20 min | Measure each component in each mode, then track state-of-charge deltas per firmware release; how a budget stays true after shipping |
| [ESP-IDF: Sleep Modes (ESP32-S3)](https://docs.espressif.com/projects/esp-idf/en/release-v5.4/esp32s3/api-reference/system/sleep_modes.html) | docs | 30 min | What deep sleep and light sleep keep powered, which wake sources exist (EXT0/EXT1 are what `power.cpp` uses), and what each costs |

**Check yourself.**

1. Recompute the per-shot charge with the 10 s Morse line replaced by a 0.2 s, 60 mA cue. Then add an 8 s, 50 mA ring-mic recording. What does a voice question cost?
2. At what number of shots per day does standby equal shot energy in the "25 µA, 153.6 µAh" profile? In the stage-2 profile with 2 µAh cue-only shots and 30 µA standby?
3. The firmware leaves the ring advertising for 120 s before deep sleep. At 30 mA, how many µAh is one timeout, and how many shots is that worth?
4. Convert the firmware-as-is floor of 110 µA to mAh/day, and give days on a 30 mAh cell (80 % usable) with 30 shots/day at 154 µAh.
5. A 10 s spoken answer at 125 mA versus a 10 s LRA Morse reply at 40 mA versus a 0.2 s double tick at 60 mA: µAh for each.

<details><summary>Answers</summary>

1. 108 + 45 + 12 = 165 mAs = 46 µAh per photo question. Voice: + 8 × 50 = 400 mAs → 565 mAs = 157 µAh, almost exactly the old Morse figure by coincidence.
2. 0.6 mAh / 0.1536 mAh ≈ 3.9 shots/day. Stage 2: 0.72 mAh/day ÷ 0.002 mAh = 360 shots/day, so standby always dominates there.
3. 120 s × 30 mA = 3600 mAs = 1000 µAh = 1 mAh, about 6.5 modelled shots or 22 cue-only photos. Setting `idle_sleep_s` low on a worn ring matters more than most hardware tweaks.
4. 110 µA × 24 = 2.64 mAh/day. Per day: 2.64 + 4.61 = 7.25 mAh; 24 / 7.25 = 3.3 days (versus 4.6 days at 25 µA).
5. 10 × 125 = 1250 mAs = 347 µAh; 10 × 40 = 400 mAs = 111 µAh; 0.2 × 60 = 12 mAs = 3.3 µAh. Speech on the ring is a hundred ticks.

</details>

## 2.4 Measuring current: shunt, multimeter, USB meter, PPK2

**Why it matters in mcring.** `docs/07-build-guide.md` §1.11 is a measurement table: advertising idle 20–40 mA, connected idle 15–30 mA, capture peak 300–370 mA with ~150 mA
average over 1.5 s, recording 40–60 mA, deep sleep ~3 mA with the Sense board and 150–250 µA without. It tells you to unplug USB for every number that matters, to put the meter
"in series with the battery", and to use a PPK2 in source-meter mode for the sleep figures. §2.4's acceptance test is "≤ 130 µA as the firmware stands, ≤ 30 µA after the IMU
follow-up", and the electrical README §4 brings the board up on a current-limited 4.0 V supply at TP8/TP5 and watches for < 20 µA idle before fitting the module.

**The concepts.** Every ammeter is a shunt: a known resistor in the path, V = I × R, and a voltmeter across it. The burden voltage is what the device under test loses. A 1 Ω
shunt reads 300 mV at the 300 mA peak (fine on a scope, too much lost from a 3.6 V cell) and 10 µV at a 10 µA sleep current (unreadable). A 100 Ω shunt reads 1 mV at 10 µA but
would need 30 V at 300 mA. That nine-decade spread is the whole problem of measuring a device that sleeps at microamps and wakes to hundreds of milliamps: no single shunt works,
and a multimeter's µA range (kilohm-class shunt) is the classic trap: the ring wakes, tries to pull 40 mA through 1 kΩ, the supply at the ring collapses and it resets, and the
meter shows nothing useful. Solutions, cheapest first. A *USB inline meter* measures the 5 V side: it sees the charger, the regulator, the dev board's LEDs and whatever the ring
draws, with ~1 mA resolution. Good for "is the capture peak about 300 mA" and for averages while awake; useless for sleep and for anything with USB attached that must not be
(§1.11 step 2). A *shunt plus oscilloscope* shows the shape of the peak (a 50 mΩ–1 Ω resistor in the battery lead, scope across it); this is how you learn that "300 mA" is a
train of radio and camera bursts, and whether the 100 µF is doing its job (probe the 3V3 rail at the same time). A *µCurrent*-style adapter puts a tiny shunt and an amplifier in
front of a multimeter, giving µA and nA ranges with microvolt burden. The *Nordic PPK2* is the tool the repo assumes: an auto-ranging shunt ammeter from sub-microamp to 1 A with
100 nA–1 mA resolution, 100 ksps, that either sits in series (*ampere-meter mode*) or *replaces the battery* at a programmable 0.8–5 V (*source-meter mode*), and whose app shows
the trace, a window average and the charge in a selected window, which is the number `power_budget.py` wants. A Joulescope does the same with more bandwidth and a price to match.
Rules of thumb for honest numbers: measure in series with the *cell* (after the charger) or in source mode replacing it, never on the USB side; disconnect USB entirely (the
charger alone draws milliamps and the USB-serial chip never sleeps); on a dev kit, expect the board's own regulators and LEDs to add tens of microamps, and when Espressif gives
8 µA for a bare module they mean a bare module; measure with the lid off but the IMU, mic and camera connected as they will be worn, because the ring sleeps as a system
(§1.11 shows the 90 µA IMU surprise); let the ring go through a full wake, so you catch the brown-out your meter might cause; and record the window average over a whole
question, not the needle during one. For the stage-1 board add a 0 V check on `CAM_3V3`, `VLED` and `VAMP` in sleep: a rail that is on shows up as 3 mA, 0.6–1 mA or 2.4 mA
respectively, and the readings are more diagnostic than the total.

**Learn it.**

| Resource | Type | Time | Why this one |
|---|---|---|---|
| [Nordic Power Profiler Kit II](https://www.nordicsemi.com/Products/Development-hardware/Power-Profiler-Kit-2) | tool | 10 min | The instrument `docs/07` assumes: ranges, resolution, source vs ampere-meter mode, in one page |
| [Nordic PPK2: Get started](https://www.nordicsemi.com/Products/Development-hardware/Power-Profiler-Kit-2/GetStarted) | docs | 20 min | Wiring for both modes and the Power Profiler app's window average, which is the µAh-per-event measurement |
| [Get your Power Profiler Kit II up and running (video)](https://www.youtube.com/watch?v=B42lPvkUSoc) | video | ~10 min | Watching someone set it up once saves an hour of guessing which pin is VOUT |
| [Power Profiler Kit 2 with an ESP32-S3 in deep sleep (video)](https://www.youtube.com/watch?v=anWftEdv9fQ) | video | ~15 min | The exact combination, ESP32-S3 deep sleep on a PPK2, with the microamp trace on screen |
| [Espressif: Current Consumption Measurement of Modules (ESP32-S3)](https://docs.espressif.com/projects/esp-idf/en/stable/esp32s3/api-guides/current-consumption-measurement-modules.html) | docs | 20 min | Espressif's own method: cut the dev board's supply path, use a low-burden auto-ranging meter (they name the PPK2 and Joulescope), expect ~8 µA bare |
| [Lucidar: ESP32-S3-DevKitM-1 real current consumption in deep sleep](https://lucidar.me/en/esp32/power-consumption-of-esp32-s3-devkitm-1/) | article | 10 min | Someone else's measured dev-kit numbers to compare your §1.11 table against |
| [EEVblog µCurrent GOLD](https://eevblog.com/projects/ucurrent) | tool | 10 min | The clearest statement of the burden-voltage problem and the µV/µA fix; read it even if you buy a PPK2 |

**Check yourself.**

1. Burden voltage of a 1 Ω shunt at 300 mA, and of a multimeter's 1 kΩ µA-range shunt when the ring wakes at 40 mA. Which one reboots the ring?
2. You want both the sleep floor (~25 µA) and the capture peak (300 mA) in one trace. Which instrument and mode, and where is it connected?
3. With USB attached the meter reads 20 mA while the ring reports deep sleep. List three things that current could be.
4. Design a two-minute test that proves the LED rail is really off in sleep without a PPK2.
5. Your PPK2 window average over a 3 s "photo + transfer" is 48 µAh, and over a 10 s "ring-speaker answer" it is 330 µAh. Rewrite the stage-1 `Profile` lines in `power_budget.py` from those numbers.

<details><summary>Answers</summary>

1. 0.3 V and 40 V (impossible; the meter's protection and the ring's regulator both give up well before). The multimeter in µA range causes the brown-out; the 1 Ω is survivable at 3.6 V but costs you 0.3 V of margin, use 0.1 Ω with a scope instead.
2. PPK2 in source-meter mode at 3.8 V replacing the cell (or ampere-meter mode in series with the cell, USB disconnected); its auto-ranging covers 200 nA to 1 A in one recording.
3. The charger pushing current into the cell, the USB-serial bridge / dev board LEDs, and the XIAO's regulator quiescent; none of it is the ring's sleep current, which is why §1.11 says unplug USB first.
4. Multimeter in volts on `VLED` (U9 output) after `I pwr: deep sleep`: 0 V means off. Then force `LED_PWR_EN` high via TP6 and see 3.3 V, proving the gate, not a broken LED, is what you measured.
5. Per shot: capture + transfer ≈ 48 µAh (keep 0.6 s × 180 mA = 30 µAh and raise `transfer` to cover the remaining 18 µAh, e.g. 0.7 s × 90 mA), set `feedback_s` to 0.2 and `feedback_ma` to 60, and add a separate answer term of 10 s × 119 mA (330 µAh × 3600 / 10 s = 119 mA) only for the speaker profile.

</details>

## 2.5 `hardware/power_budget.py`, line by line

**Why it matters in mcring.** This 70-line script is the source of three headline claims: "~65 shots/week at 40 mAh" and "~2,600 shots/week at 20 mAh" in `docs/03`, and the
"104 / 208 / 521 shots" table in `hardware/power-budget.txt`. `docs/build-helpers/tuning_calc.py sleep` and `speaker` are its two extensions. If you change a part, a sleep mode
or a cue, this is the file that tells you what it cost, so you should be able to read and edit it.

**The concepts.** A `Profile` is one hardware-plus-firmware scenario with seven numbers: `capture_s`/`capture_ma` (camera on and JPEG encode), `transfer_s`/`transfer_ma` (BLE
radio busy), `feedback_s`/`feedback_ma` (the reply on the LRA or LED), and `standby_ua` (everything that stays on, 24 hours a day). `mah_per_shot()` is Σ(s × mA) / 3600, the
arithmetic of §2.3; `mah_per_day_standby()` is µA / 1000 × 24. `report()` then does four things for each battery size: `usable = battery × 0.8` (the 80 % allowance for
aging, cold and the 3.3 V cutoff), `shots = usable / per_shot` (the pure-event bound, standby ignored), `days = usable / (standby_per_day + shots_per_day × per_shot)` (the
number you actually live with), and `standby-only days = usable / standby_per_day` (the shelf-life bound). Reading the four profiles is the lesson. Profile 1 (ESP32-S3, camera
gated, BLE off in sleep, 25 µA) and profile 2 (same hardware, BLE connection kept alive, 380 µA) differ only in standby, and at 30 shots/day on 40 mAh the result is 6.1 versus
2.3 days: the decision "sleep with the link down and reconnect on wake" is worth 3× battery life, and it is why `power_tick()` deep-sleeps after `idle_sleep_s`. Profile 3 (dev
kit as-is, 3 mA) shows the un-gated camera: 0.4 days. Profile 4 (nRF52840 + HM01B0, 30 µA) has a cheap shot, 3.6 + 4 = 7.6 mAs of capture and transfer, but the same 400 mAs
Morse reply, so its per-shot figure of 113 µAh is 98 % feedback; drop the Morse line and stage 2 becomes standby-dominated at ~2 µAh per photo. What the model leaves out, in
order of size: the voice recording (8 s × 50 mA ≈ 110 µAh, bigger than a photo; add a `record_s`/`record_ma` pair), the real IMU standby (90 µA at 400 Hz, see
`tuning_calc.py sleep`; profile 1's 25 µA assumes the low-power wake mode that is still a firmware follow-up), the speaker option (`tuning_calc.py speaker` adds 347 µAh per
10 s answer), the BLE link maintenance while the phone is connected during the day (somewhere between profiles 1 and 2), the ~1 µA charger leakage and the cell's own
self-discharge (a few percent per month, invisible against anything else here), and capacity loss with age (part of the 80 %). Run it: `python3 hardware/power_budget.py
--battery 30 --shots-per-day 30`, then edit `PROFILES` to add a cue-only ESP32-S3 line and a voice-question line, and compare with `python3 docs/build-helpers/tuning_calc.py
sleep --imu lp-wakeup` and `... speaker --ma <measured>` once you have PPK2 numbers from §2.4.

**Learn it.**

| Resource | Type | Time | Why this one |
|---|---|---|---|
| [Jack Ganssle: Designing Hardware/Firmware for Low Power MCUs](https://www.ganssle.com/reports/ultra-low-power-design.html) | article (report) | 1–2 h | The checklist of what budgets like this one forget: brown-out detectors, capacitor leakage, "typical" sleep specs, the run-fast-then-sleep question |
| [Nordic Online Power Profiler for Bluetooth LE](https://devzone.nordicsemi.com/power/) | interactive | 15 min | Produces the `transfer_ma` and connection-maintenance numbers for a stage-2 profile instead of guessing 8 mA |
| [Memfault Interrupt: Understanding Battery Performance of IoT Devices](https://interrupt.memfault.com/blog/monitoring-battery-life) | article | 20 min | How to keep a model like `power_budget.py` honest once rings are in use: per-component measurements and state-of-charge deltas |
| [Battery University BU-808: How to Prolong Lithium-based Batteries](https://www.batteryuniversity.com/article/bu-808-how-to-prolong-lithium-based-batteries/) | article | 30 min | The depth-of-discharge data that justifies the `usable = 0.8` factor and tells you what you buy by cutting at 3.3 V |
| [Nordic DevAcademy: Designing Low-Power Bluetooth LE Products, Lesson 4](https://academy.nordicsemi.com/courses/designing-low-power-bluetooth-le-products/lessons/lesson-4-bluetooth-le-power-optimization/) | course lesson | 2 h | Advertising and connection parameters as power knobs: the knobs behind profile 1 vs profile 2 |

**Check yourself.**

1. Run the script for a 30 mAh cell at 30 shots/day and check profile 1 by hand.
2. Add `record_s = 8, record_ma = 50` to profile 1. New per-shot charge and days on 30 mAh?
3. Change profile 1's standby to the firmware-as-is 110 µA. Days on 30 mAh at 30 shots/day? At 5 shots/day?
4. Which profile does the stage-0 XIAO with the Sense board attached match, and what single hardware change moves it to profile 1?
5. Write a stage-2 cues-only profile (0.3 s × 12 mA, 0.5 s × 8 mA, 0.2 s × 60 mA, 30 µA) and give standby-only days and days at 30 shots/day on a 16 mAh cell.

<details><summary>Answers</summary>

1. usable 24 mAh; per shot 0.1536 mAh; per day 0.6 + 30 × 0.1536 = 5.21 mAh; 24 / 5.21 = 4.6 days; standby-only 24 / 0.6 = 40 days.
2. 553 + 400 = 953 mAs = 265 µAh; per day 0.6 + 7.94 = 8.54 mAh; 24 / 8.54 = 2.8 days.
3. 2.64 + 4.61 = 7.25 mAh/day → 3.3 days. At 5 shots/day: 2.64 + 0.77 = 3.41 → 7.0 days; at low usage the IMU mode is the whole story.
4. Profile 3 (3 mA un-gated). The TPS22916 load switch on the camera rail (U2, IO21) with its pull-down is what turns it into profile 1.
5. Per shot 3.6 + 4 + 12 = 19.6 mAs = 5.4 µAh; standby 0.72 mAh/day. Usable 12.8 mAh: standby-only 17.8 days; at 30 shots/day 0.72 + 0.16 = 0.88 mAh/day → 14.5 days. The cell, not the question count, sets stage-2 life.

</details>

## 2.6 The 300 mA ESP32-S3 peak versus the 5 mA nRF52 argument

**Why it matters in mcring.** It is the first "key engineering conclusion" in the README and the reason the project has two firmware trees. `docs/03` §3.1 reduces it to two
numbers; `docs/04`'s risk table says "ring cells are 16–24 mAh @ 1C; ESP32-S3 camera peaks are 300+ mA → nRF52840-class SoC for stage 2"; `docs/research/02-mcu-radio-power.md`
gives the measurements (XIAO Sense 154 mA average, 304–366 mA peaks; nRF52840 TX 4.8 mA, RX 4.6 mA, System OFF 0.4 µA); `power-budget.txt` closes with "15–20C … not viable
without a large buffer capacitor; nRF52840 peaks ~15 mA ≈ 1C". `hardware/pinmap.md`'s stage-2 table shows the price: no camera interface, so the DVP bus is bit-banged.

**The concepts.** A peak does three independent kinds of damage, and only one of them is about energy. First, *C-rate stress*: 300 mA is 19C on a 16 mAh cell rated for 1C.
The cell heats (I²R inside a one-gram pouch), its PCM may trip, and repeated high-rate pulses age it fast. Second, *voltage droop*: ΔV = I × R_internal, and small cells have large
internal resistance (of the order of an ohm for a 16–30 mAh pouch; always read the cell's "internal impedance" line). 300 mA × 1 Ω = 0.3 V. A cell at 3.6 V falls to 3.3 V exactly
when the camera and radio are busiest, the buck loses regulation, and a brown-out at the capture moment corrupts the JPEG or resets the chip. At 5 mA the droop is 5 mV; the nRF52
simply does not have this problem. Third, *regulator and charger limits*: the TPS62840's 750 mA is fine, but a PMIC-class charger with an integrated buck (nPM1100, BQ25120A) must
also be rated for the peak. Why not just add a capacitor? Charge needed = I × t, and the capacitor must supply it with an acceptable droop: C = I × t / ΔV. To carry a 300 mA,
50 ms burst with 0.3 V of droop you need 0.3 × 0.05 / 0.3 = 50 mF, five hundred times the 100 µF on the board; to carry the whole 0.6 s capture at 180 mA you need 0.36 F. Those
are supercapacitors, with their own leakage (microamps, i.e. the standby budget), ESR and volume, in a product whose spare volume is the 0.35 mm above the cell. The 100 µF C3 is
for microsecond transients while the buck catches up (§1.2 of the electronics file), not for carrying a capture. So the alternative is to shrink the peak by a factor of twenty
and accept the costs: an nRF52840-class SoC keeps radio peaks near 5 mA and sleeps at 1.5 µA with the RTC on, an HM01B0 sensor draws under 2 mW at QQVGA, and the
whole ring peaks around 15 mA, 1C of 16 mAh. What you give up is the ESP32-S3's hardware camera interface and JPEG path: the nRF52 bit-bangs 8-bit DVP at low resolution,
grayscale, with software compression, which is why the stage-2 image target is ≤ 20–30 KB and why `docs/07` §3 lists "a recognisable frame in < 300 ms at < 15 mA average" as
the first thing to prove. The energy per shot also drops, 46 µAh to a few µAh in cue-only terms, but that is a side effect; the decision is made by peak current and C-rate, which no
amount of duty-cycling can change. And the ESP32-S3 remains right for stages 0 and 1: 300 mA is 3C on the XIAO's 100 mAh cell (comfortable) and 10C on the 30 mAh stage-1 cell
(rough, but survivable with short peaks, the 100 µF and the 3.3 V cutoff), and its firmware, camera driver and JPEG encoder exist today.

**Learn it.**

| Resource | Type | Time | Why this one |
|---|---|---|---|
| [ESP32-S3 Series Datasheet (Espressif)](https://www.espressif.com/sites/default/files/documentation/esp32-s3_datasheet_en.pdf) | datasheet | 30 min (the current-consumption and power-mode tables) | The radio TX/RX and sleep currents the argument starts from; note that the camera board's 300 mA peaks are a system measurement, not in this sheet |
| [nRF52840 Product Specification v1.8 (Nordic)](https://infocenter.nordicsemi.com/pdf/nRF52840_PS_v1.8.pdf) | datasheet | 30 min (electrical specification, radio and System ON/OFF current) | TX 4.8 mA, RX 4.6 mA, 1.5 µA System ON with RTC, 0.4 µA OFF: the other side of the comparison |
| [Battery University BU-402: What is C-rate?](https://www.batteryuniversity.com/article/bu-402-what-is-c-rate/) | article | 10 min | Why "19C on a 1C cell" is a sentence that ends a design review |
| [DigiKey: Oura Ring Teardown (Gen 3 and 2)](https://www.digikey.com/en/maker/projects/oura-ring-teardown-gen-3-and-2/2c005e01f82d429398e78f49591793cc) | article | 15 min | The 16 mAh cell and the nRF/BQ25120A-class electronics that fit beside it: what "ring size" means in practice |
| [Memfault Interrupt: Smart Ring Development (Part 2), Hardware Design](https://interrupt.memfault.com/blog/smart-ring-development-part-2) | article | 25 min | Another team choosing a sub-10 mA BLE SoC (DA14531 vs nRF52805) for a ring, and why |
| [Nordic Online Power Profiler for Bluetooth LE](https://devzone.nordicsemi.com/power/) | interactive | 15 min | Model the stage-2 transfer: 20 KB over a 15 ms connection interval, 2M PHY, and read the peak and average the radio really draws |
| [Grepow: smart ring batteries](https://www.grepow.com/wearables/smart-ring.html) | vendor page | 10 min | The 1C curved cells that set the ceiling; check the discharge-rate line on any model you consider |

**Check yourself.**

1. Give the C-rate of a 300 mA peak on 16, 30 and 100 mAh cells, and the C-rate of a 15 mA stage-2 peak on 16 mAh.
2. A 16 mAh curved cell has 1.5 Ω internal resistance. Terminal voltage during a 300 mA peak from 3.7 V, and during a 15 mA peak?
3. Size the capacitor that would carry a 300 mA, 50 ms burst with 0.2 V droop. Compare with C3 and with the volume above the cell.
4. Someone proposes keeping the ESP32-S3 at stage 2 but taking only one photo a day "so the energy is tiny". Why does that not help, in one sentence?
5. List the three things stage 2 gives up to get a 15 mA peak, from `hardware/pinmap.md` and `docs/03` §3.4, and the first stage-2 experiment `docs/07` §3 asks for.

<details><summary>Answers</summary>

1. 18.75C, 10C, 3C; 15 mA / 16 mAh = 0.94C.
2. 3.7 − 0.3 × 1.5 = 3.25 V (below the 3.3 V cutoff, mid-shot); 3.7 − 0.015 × 1.5 = 3.68 V.
3. C = 0.3 × 0.05 / 0.2 = 75 mF, 750 × C3. Supercapacitors of that size are millimetres thick and leak microamps; nothing like it fits in the 0.35 mm clearance.
4. Peak current sets C-rate stress and droop at the instant of the shot, independent of how rarely the shot happens; energy per day is a different quantity.
5. The hardware DVP/LCD_CAM camera interface (bit-bang instead), hardware JPEG from the OV2640 (QQVGA grayscale with software compression), and the stage-0/1 firmware tree (a Zephyr skeleton instead). First experiment: capture a recognisable frame from an HM01B0-class sensor on an nRF52840 in < 300 ms at < 15 mA average, measured on the PPK2.

</details>
