# 10 · Ordering the stage-1 board assembled (and never soldering)

The stage-1 ring board is designed so that the **assembler places every part on the PCB** and the owner only
plugs things in: the cell, the charging-pad pigtail, the LRA and the optional speaker each go into a 2-pin
Molex Pico-EZmate header on the board's top, the camera flex drops into a flip-lock ZIF, the antenna snaps
onto the module's u.FL. This page is the ordering procedure — JLCPCB first, PCBWay as the alternative — plus
what is consigned vs sourced, why the 0.4 mm BGAs force the "Standard" assembly tier, what the double-sided
build costs, and the list of things that are still yours to do when the boards arrive.

Inputs (all generated, keep them in sync by re-running the scripts):

| File | Made by | What it is |
|---|---|---|
| `hardware/electrical/out/mcring_v1.net` | `hardware/electrical/mcring_v1.py` | the netlist (KiCad import) — you lay the board out from it |
| `hardware/electrical/out/mcring_v1_bom.csv` | same | the engineering BOM (MPN, manufacturer, LCSC column, off-board parts) |
| `hardware/pcb/board_params.json`, `hardware/pcb/floorplan.md` | `hardware/pcb/floorplan.py` | the placement every part must keep (the enclosure is generated from it) |
| `hardware/pcb/out/mcring_v1_cpl.csv` | `hardware/pcb/export_cpl.py` | pick-and-place: `Designator, Mid X, Mid Y, Layer, Rotation` |
| `hardware/pcb/out/mcring_v1_bom_jlc.csv` | same | assembler BOM: `Comment, Designator, Footprint, LCSC Part #` |
| `hardware/pcb/out/mcring_v1_pcba_notes.md` | same | sourcing status of every line, consigned parts, DNP list, rotation assumptions, joint count |
| Gerbers + drill (`mcring_v1_gerbers.zip`) | your layout tool | the only input not generated here — see §1 |

## 1. Before you can order: the layout

The repository holds the design at netlist + floorplan level, not a routed board. One layout pass in KiCad
(or any tool) is needed — ask someone, or do it yourself; it is the one step that is neither soldering nor
ordering:

1. Import `out/mcring_v1.net` into pcbnew (`hardware/electrical/README.md` §4 lists the custom footprints,
   now including `Connector_Molex:Molex_Pico-EZmate_78171-0002_1x02-1MP_P1.20mm_Vertical` for J1/J3/J4/J5 and
   the Hirose `FH12-24S-0.5SH` pattern for FPC1).
2. Draw the outline from `board_params.json`: **26.5 × 22.8 mm**, r 1.5, and the four **2.4 × 1.1 mm wire
   notches** in the right edge at x = 7.65 / 12.4 / 17.1 / 21.8 (`edge_notches_mm`) — half-round or
   rectangular, no copper within 0.3 mm.
3. Place every part at the centre `floorplan.py` gives (`parts` in the JSON, or import `out/mcring_v1_cpl.csv`
   as a position file). The four headers go with their **wire-exit end toward the notch**; the rest of the
   rotation/pin-1 choices are yours.
4. Route to `hardware/electrical/README.md` §5 (0.10/0.10 mm fine rules, 0.2 mm drill, NSMD 0.22–0.25 mm
   DSBGA pads with 0.03 mm mask expansion, ENIG).
5. Export Gerbers + Excellon drill with the **drill/place origin on the board's front-left corner**, X along the
   finger, so the generated CPL matches — or export the CPL from the tool (KiCad: Fabrication Outputs →
   Component Placement → rename the columns to `Designator, Mid X, Mid Y, Rotation, Layer`).
6. Run `python3 hardware/pcb/export_cpl.py` once more after the layout to refresh the BOM/CPL/notes.

## 2. Which assembly tier, and why

| | JLCPCB **Economic** PCBA | JLCPCB **Standard** PCBA (use this) | PCBWay PCBA |
|---|---|---|---|
| Min BGA pitch | 0.5 mm | **0.35 mm** | 0.3 mm rigid (with X-ray) |
| Sides | single only | **single or double** | single or double |
| Setup / stencil | $8 / $1.50 | **$25 (1 side) / $50 (2 sides)**, stencil **$7.86 / $15.72** | quote-based, no public fee list |
| Per-joint placement | — | **$0.0016 / joint** | in the quote |
| Extended-part fee | $3 per unique extended part | feeder loading charged on all lines (sources disagree on the rate — read the live quote) | in the quote |
| Consigned parts | no | **yes** | yes, plus cable/harness assembly on request |

Two parts on this board are 0.4 mm-pitch DSBGAs — the three TPS22916 load switches (U2, U9, U11) and the
BQ25100 charger (U7) — and 67 of the 73 placed parts are on the **bottom** with the module, FPC1, switch,
LED, bulk cap and the four headers on the top. That rules Economic out twice over (pitch and single side), so
the order is **Standard PCBA, both sides**. The fine-pitch rules the board needs anyway (0.1/0.1 mm,
0.2 mm drills, ENIG) are JLCPCB "advanced" PCB options; tick them.

Could it be single-sided to use the cheap tier? Not with the 15.4 mm module and the 16 mm FPC connector on
top and 67 parts underneath on a 26.5 × 22.8 mm board — and 0.4 mm BGAs are out on Economic regardless.
If you ever change the TPS22916 to the SOT-23-5 TPS22917DBV (same nets, `hardware/electrical/README.md`
§5), the BGA constraint goes away but the double-side one stays.

## 3. Consigned vs sourced parts

"Sourced" = JLCPCB buys it from LCSC and reels it onto the machine. "Consigned" = you buy it, ship it to
JLCPCB with the order number, and they place it (JLCPCB calls this *Consign Parts*; there is also *Global
Sourcing Parts*, where they buy from DigiKey/Mouser for you at a markup and lead time — use it if you do not
want to handle a parcel to Shenzhen). `out/mcring_v1_pcba_notes.md` carries the per-line status; the summary:

| Status | Lines | Parts |
|---|---|---|
| LCSC number recorded (sourced) | 14 | BQ25100 (C2871910), LIS2DW12 (C189624), MAX98357A (C910544), DRV2605L DGST (C425927 — the 250-piece reel of the same part; DGSR is C527464), TPS62840 (C2071859), XC6206P282MR-G (C2891263), AO3400A (C20917), WS2812B-2020 (C965555), FH12-24S-0.5SH(55) (C202112), 10 kΩ (C60490), 4.7 kΩ (C105871), 100 nF (C71629 — LCSC marks it "not recommended for new designs"; let the BOM tool substitute a basic 0402), 1 µF (C76999), 10 µF 0603 (C77041) |
| **Consigned** (not on LCSC at the research snapshot) | 3 | **ESP32-S3-MINI-1U-N4R2** (only the N8 without PSRAM and the PCB-antenna MINI-1 are stocked), **TPS22916CYFPR** ×3 per board, **Molex 78171-0002** ×4 per board |
| No C-number recorded — match in the BOM tool | 14 | the other resistor values, the 100 µF 1206, L1 2016 inductor, D2/D3 SOD-523, XC6206P122MR, T3902 mic, B3U-3000P switch — JLCPCB's BOM tool proposes a match from the MPN or the value + package; accept a *basic* 0402 where one exists (no feeder fee), search the MPN for the rest, consign what is missing |

For a 5-board run order consigned parts with the attrition JLCPCB asks for (they state the minimum on the
order page; plan +2–5 pieces per line, more for 0402-sized parts): 7 modules, 20 TPS22916, 24 Pico-EZmate
headers. Keep the DigiKey/Mouser packing list — it goes in the parcel.

## 4. The JLCPCB order, step by step

1. **jlcpcb.com → Order now → Add gerber file** (`mcring_v1_gerbers.zip`). Check the preview: 26.5 × 22.8 mm,
   4 notches on one long edge, 2 layers.
2. **PCB settings**: 2 layers; **thickness 0.6 mm**; FR-4 TG 150+; 1 oz; **surface finish ENIG**; min
   track/space **0.1/0.1 mm** (pick the advanced option when it appears — "0.09 mm" at JLCPCB); min hole
   **0.2 mm**; solder mask green or black; silkscreen none under the module (your Gerber decides); "Remove
   order number: specify location"; quantity **5**.
3. Toggle **PCB Assembly** on. Choose **Standard** (not Economic), **both sides**, assembly quantity **5**,
   tooling holes "added by JLCPCB" (the board has none), confirm the parts-selection and placement steps.
4. **Upload BOM and CPL**: `hardware/pcb/out/mcring_v1_bom_jlc.csv` and `mcring_v1_cpl.csv` (or the pair
   exported from your layout tool). The columns are exactly what the uploader expects; if it asks you to map,
   map Comment / Designator / Footprint / LCSC Part # and Designator / Mid X / Mid Y / Layer / Rotation.
5. **Parts selection**: every line with a C-number resolves itself. For the 14 blank lines accept the
   proposed basic part or search the MPN; for the 3 consigned lines pick **Consign** (or Global Sourcing).
   Mark **U4 DNP** if your OV2640 head regulates DVDD itself (`hardware/electrical/README.md` §1 item 3).
   Leave the speaker group populated unless you are sure you will never want the on-ring speaker — the J5
   header is populated either way.
6. **Component placement preview**: check **polarity and rotation** of U1 (u.FL end at the board's back edge,
   x = 26.5), FPC1 (mouth at the front edge, x = 0), D1 (DIN toward R7), D2/D3 (D3 cathode toward U7), the
   ICs' pin 1, and that the **four headers have their wire-exit end facing the notch edge**. Rotate in the
   preview if needed (the uploaded rotation is 0 for all ICs/connectors; JLCPCB re-aligns to its library
   footprint and shows the result).
7. **Remarks** box (DFM): *"0.4 mm pitch DSBGA on U2/U7/U9/U11: please keep the stencil apertures 1:1 with the
   pads, do not shrink; ENIG; parts under U1 none. Four consigned part types will ship separately."*
8. Save to cart, review the quote (§6), pay. JLCPCB emails a DFM review within 1–2 days; answer any question
   about the DSBGAs or the notches (they are just outline features).
9. **Consignment parcel**: on the order page open the consigned-parts instructions, print the label with the
   order number, pack the module, the TPS22916 and the Pico-EZmate headers in their original reels/cut tape
   with the packing list, ship (DHL/FedEx, 3–6 days). Production starts when the parcel is booked in.
10. Delivery in roughly 2–3 weeks after the parcel arrives. JLCPCB's assembly includes AOI; they do not
    X-ray 0.4 mm BGAs by default — if a board misbehaves on the power check (`docs/07-build-guide.md` §2.3)
    the charger/load-switch balls are the first suspects.

## 5. The PCBWay variant

Same files, same tier logic. On **pcbway.com → PCB Assembly** fill the online form (qty 5, both sides,
turnkey or "combo" with consigned parts), upload Gerbers, BOM and CPL, and wait for the human quote (1–2
working days). Two things PCBWay does that JLCPCB does not:

* **X-ray inspection of BGAs** on request — worth asking for on the DSBGAs.
* **Cable / harness assembly**: ask them to price "attach the supplied Pico-EZmate pigtails to the supplied
  cell, LRA and speaker and solder the two ENIG coupons to the charging pigtail" (8 joints + 2 coupons per
  ring). If they take it, the ring is 100 % solder-free on your side, with no cable shop and no solder-seal
  sleeves (§7). Send the parts with the consignment.

## 6. What five boards cost (estimate, October 2026 list prices)

| Item | Amount |
|---|---|
| 5 × PCB, 2-layer 0.6 mm ENIG, advanced rules | $15–30 |
| Standard PCBA setup, both sides | $50 |
| Two stencils | $15.72 |
| Placement, ≈ 290 joints × 5 boards | ≈ $2.5 |
| Feeder / extended-part fees (31 lines; the rate per line is quoted live) | $0–90 |
| Sourced parts for 5 boards + attrition | ≈ $90–140 (the FH12, BQ25100, MAX98357A, LIS2DW12, DRV2605L, TPS62840 and the passives) |
| Consigned parts (7 modules ≈ $45, 20 TPS22916 ≈ $7, 24 headers ≈ $10) + courier to Shenzhen | ≈ $90–120 |
| Shipping back (DHL) + tax | $25–45 |
| **Total for 5 assembled boards** | **≈ $300–490**, i.e. $60–100 per board; the research report's own bracket was $330–420 |

Not in that table, bought separately per ring: cell $1–2.5, LRA $3–5, speaker $1.5–3, 2 pigtail cables
$4.60 (36920-0201, cut in half), flex antenna $3–5, OV2640 head $1–4, enclosure print $2–15, copper foil +
foam, two ENIG coupons, the silver pen ($46, one tube does many rings) — ≈ $20–40 per ring.

## 7. What is still yours to do, and how to do it without an iron

The board arrives with **nothing to solder on it**. What remains are the off-board parts and their joints:

| Step | How |
|---|---|
| Camera head | push the flex into FPC1, flip the lock down (bottom contact: contacts toward the board) |
| Antenna | press the MHF1 plug straight onto the module's u.FL until it clicks; glue the flex to the back wall |
| Cell → J1 | the cell's two leads must end in a Pico-EZmate plug (W1 pigtail); plug it into J1 |
| LRA → J4 | same, W3 pigtail |
| Speaker → J5 | same, W4 pigtail (optional) |
| Charging pads → J3 | the W2 pigtail's bare ends go through the band's two Ø1.1 channels to the 3 × 2 mm ENIG coupons in the windows |
| Touch | copper foil on the lid underside, foam block on TPAD1 |
| Close | lid on, key in, mechanical sequence in `docs/07-build-guide.md` §2.6 |

The **8 wire joints per ring** (two leads each on the cell, LRA, speaker, and the two band contacts) are the
only joints left anywhere. Three ways to have them made without touching a soldering iron, in order of
preference:

1. **Have the parts delivered terminated.** A cable/harness shop (the research found Pico-EZmate harnesses
   listed by small shops such as Hoohaa; any "custom wire harness" seller takes a drawing: *28 AWG, 50 mm,
   78172-0002 housing one end, bare 3 mm tinned the other*) will crimp the pigtails and solder them to the
   cell, LRA and speaker leads for a few dollars per harness at the 5–10 piece level. PCBWay's harness
   service (§5) does the same inside the board order.
2. **Solder-seal heat-shrink sleeves** (white, 26–30 AWG size, $5–10 per 50): slide a sleeve over the joint
   of the pre-crimped pigtail and the part's lead, heat with a heat gun (or a lighter at a distance) until
   the solder ring flows and the sleeve shrinks. No iron, no flux, no skill; the joint is insulated. For the
   two band contacts use the **silver conductive pen** (MG Chemicals 842AR-P) to bond the bare wire end to
   the ENIG coupon, UV-glue the coupon into its window — the charge current is ≤ 25 mA, so the pen's
   0.3–0.8 Ω/cm is irrelevant there (never use it on the speaker or LRA path).
3. **A makerspace / a friend with an iron**: 8 joints, ten minutes. Bring the pigtails cut to length.

Keep the board itself out of all of this: there is nothing on it to touch, and the four plugs come out again
for debugging (the test pads stay reachable with the board seated and the lid off).

## 8. Checklist before you click "pay"

- [ ] outline 26.5 × 22.8 with four 2.4 × 1.1 notches on the +y edge; 0.6 mm; ENIG; 0.1/0.1; 0.2 mm drills
- [ ] Standard PCBA, both sides, qty 5
- [ ] BOM: 31 lines, 3 consigned (module, TPS22916, 78171-0002), U4 DNP decided, speaker group decided
- [ ] placement preview: U1 u.FL end at the back edge, FPC1 mouth at the front edge, headers' wire exit toward the notches, D1/D2/D3/IC pin 1
- [ ] DFM remark about 1:1 DSBGA apertures
- [ ] consignment parcel booked with the order number; attrition quantities met
- [ ] separately ordered: cells, LRAs, speakers, 2 × 36920-0201 per ring (or a terminated harness set), antennas, OV2640 heads, foil + foam, ENIG coupons, silver pen or solder-seal sleeves, enclosure prints
