#!/usr/bin/env python3
"""mcring v1 (stage 1) — PCB floorplan generator.

Pure Python. Produces, in out/:
  floorplan_top.svg/.png      to-scale top-side placement (components, keepouts, critical nets)
  floorplan_bottom.svg/.png   to-scale bottom-side placement (seen from below, mirrored)
  stackup.svg/.png            vertical stack through the signet + camera-pod section
and, next to this script:
  board_params.json           the numbers the enclosure (CAD) step is generated from
  floorplan.md                human-readable placement table, keepouts, route notes
(`export_cpl.py` turns the same placement data into the JLCPCB/PCBWay pick-and-place + BOM files.)

Coordinate system (board, mm):  origin = FRONT-LEFT corner of the board seen from the TOP.
  x runs along the finger from the FRONT edge (camera / FPC connector, x = 0) to the BACK edge
    (antenna / u.FL end, x = board_length).
  y runs across the finger from the LEFT edge (switch side, y = 0) to the RIGHT edge (y = board_width).
Part sizes are given as w (along x) × h (along y). Parts on the bottom use the same coordinates
(no mirroring in the data); the bottom drawing mirrors y so it looks like the real bottom view.

Design-for-assembly revision (no soldering by the owner): the board is 22.8 mm wide (was 18.0); the 4.8 mm
added on the RIGHT (+y) side is a TOP-side strip beside the module that carries four 2-pin Molex Pico-EZmate
wire-to-board headers — J4 LRA, J3 charging pads, J1 cell, J5 speaker — each with a wire notch in the board
edge beside it. The old bottom-side wire pads J1a/b, PAD1w/2w, M1a/b and SPK1a/b are gone; only the piezo
pads BZ1a/b (optional, DNP piezo) and the aux pads J2a/b (bench experiment) remain as bare pads. Everything
on the board is placed by the assembler; the owner plugs four pigtails in.

Reference designators follow hardware/electrical/out/mcring_v1_nets.md (U1..U11, C1..C26, R1..R24,
D1, D2, D3, L1, Q1, SW1, FPC1, J1..J5, MK1, BZ1, TP1..TP8, TPAD1). U10/U11/C25/C26/R20-R24/J5 are the optional
speaker amp (MAX98357A behind a third TPS22916, 1 k series resistors in the I2S lines); the speaker itself is
off-board in a pocket in the signet's RIGHT wall, described for the CAD by board_params.json "speaker_mm".
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field, asdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from svgkit import SVG, rounded_rect_path  # noqa: E402

OUT = os.path.join(HERE, "out")

# ----------------------------------------------------------------------------------------------
# 1. Board
# ----------------------------------------------------------------------------------------------
BOARD = dict(
    length=26.5,        # along the finger (front → back)
    width=22.8,         # across the finger (left → right); 18.0 + 4.8 connector strip on the right
    thickness=0.6,
    corner_r=1.5,
)
L, W = BOARD["length"], BOARD["width"]

# The module sits with its u.FL / antenna end flush with the BACK edge. It is NOT centred across the board:
# it keeps the original 1.3 mm to the LEFT (switch) edge, and the 4.8 mm the board grew on the RIGHT is the
# connector strip. The camera axis (FPC1 centre) stays on the finger axis, y = W/2.
MODULE = dict(w=15.4, h=15.4, height=2.4)
MODULE_X0 = L - MODULE["w"]            # 11.1
MODULE_CX = MODULE_X0 + MODULE["w"] / 2  # 18.8
MODULE_CY = 9.0                          # module y 1.3 .. 16.7
MODULE_Y1 = MODULE_CY + MODULE["h"] / 2  # 16.7
FPC_CY = W / 2                           # 11.4 = finger / camera axis

# u.FL end of the module = the last 2 mm of the board. The MINI-1U has NO on-module antenna, so Espressif's
# PCB-antenna copper keep-out does not apply here: the module's own GND/3V3/EN pads (pins 1-3 and 43-48 are the
# ends of the two side rows, i.e. the pads nearest the u.FL — VERIFY against the Espressif footprint) and a solid
# GND pour live in this strip. Rules: no DVP/XCLK/PCLK/PDM traces, no part other than U1, and the pigtail leaves
# the plug over the back edge and runs down the inside of the bay's back wall.
UFL_END_X0 = L - 2.0
ANT_CLEARANCE_MM = 5.0     # flex antenna + pigtail >= 5 mm from the cell, the LRA and any other metal (enclosure rule)

# Heights the CAD step has to clear
UFL_MATED_HEIGHT = 2.9     # module substrate (~0.8) + mated U.FL-R-SMT / U.FL-LP-040 pair (2.0) + 0.1
TOP_MAX_HEIGHT = max(MODULE["height"], UFL_MATED_HEIGHT)   # 2.9
BOTTOM_MAX_HEIGHT = 1.15   # VSSOP-10 (U5) and SOT-23 (U3/U4/Q1) are 1.10–1.15 max; TQFN (U10) 0.75–0.8
BACK_LEDGE_X0 = 23.6       # hardware/cad: the back board ledge spans board x >= 23.6 at the sub-board level, so
                           # bottom-side parts must end before it
LID_CLEARANCE = 0.30       # tallest top part -> lid underside
LID_T = 1.2                # lid plate (CAD `lid_t`)
CELL_POCKET_SLACK = 0.40   # the CAD cuts the cell pocket 3.4 deep for the 3.0 cell (hardware/cad `cell_pocket`)
BORE_D = 4.6               # lens bore as printed (CAD `lens_d`; reamed to the 4.5 barrel)
SWITCH_SLOT = (3.4, 1.6)   # side-switch slot through the bay wall, w (along x) × h (z) (CAD `switch_slot`)

# Touch: the lid underside is TOP_MAX_HEIGHT + LID_CLEARANCE = 3.2 mm above the board, so a bare copper pad on the
# board would sit 4 mm (3.2 air + 0.8 resin) behind the touch surface and never couple to a finger. The electrode
# is therefore a copper-foil pad stuck to the LID underside (under the 0.8 mm touch dimple); TPAD1 on the board is
# only the landing for a compliant conductor (conductive-foam block or SMT spring finger) that the lid compresses.
TOUCH_CONTACT = dict(free_height=3.6, compressed_height=round(TOP_MAX_HEIGHT + LID_CLEARANCE, 2))   # 3.2
LID_ELECTRODE = dict(w=4.0, h=5.0, dielectric=0.8,
                     foil="copper foil 0.05-0.07 mm with conductive adhesive (3M 1181 class), cut 4 x 5 mm")

# ----------------------------------------------------------------------------------------------
# 1b. Wire-to-board connectors (TOP side, right strip) — the design-for-assembly change
# ----------------------------------------------------------------------------------------------
# Molex Pico-EZmate 78171-0002: 1.20 mm pitch, 2 circuits, vertical SMT header with side friction locks,
# mated height 1.55 mm (Molex part page; the mating housing is 78172-0002, pre-made 28 AWG cables 36920-0201 /
# 68801-4146). Header outline: the 3-circuit part is listed as 5.4 long x 4.5 deep, so the 2-circuit header is
# 4.2 (along the pin row) x 4.5 (plug / wire direction) — VERIFY against the Molex drawing before layout,
# together with which end of the 4.5 mm the plug's wires leave (placed here toward +y = the board edge).
# Alternative with the same role: JST ACH BM02B-ACHSS-GAN-ETF (1.2 mm pitch, 4.2 x ~4.3 x 1.4 mm, housing
# ACHR-02V-S, pre-made ASACHSACH28W jumpers) — different land pattern, same courtyard budget.
# Neither fits the BOTTOM (1.15 mm envelope); on the TOP they are the 1.55 mm "mated" box the lid check sees.
CONN = dict(w=4.2, h=4.5, mated_height=1.55, pitch=1.2, mpn="78171-0002", manufacturer="Molex",
            series="Pico-EZmate", housing="78172-0002", cable="36920-0201 (100 mm, 28 AWG, plug both ends: cut in half = two pigtails)",
            alt_mpn="BM02B-ACHSS-GAN-ETF (JST ACH, 1.4 mm, housing ACHR-02V-S, jumpers ASACHSACH28W51..305)")
CONN_GAP_MODULE = 0.5                       # connector courtyard -> module courtyard (fan-out room for the module's right row)
CONN_Y0 = MODULE_Y1 + CONN_GAP_MODULE       # 17.2
CONN_CY = CONN_Y0 + CONN["h"] / 2           # 19.45  (connectors span y 17.2 .. 21.7)
NOTCH = dict(w=2.4, d=1.1)                  # wire notch in the RIGHT board edge beside each connector (two Ø1.0 wires side by
                                            # side + 0.4 slack; depth 1.1 + the 0.3 bay clearance = 1.4 for one wire diameter): y 21.7 .. 22.8
WIRE_OD_MAX = 1.0                           # 28 AWG insulated pigtail wire; the enclosure channels/grooves are sized for it
# (ref, centre x, short name, what plugs in, nets)
CONNECTORS = [
    ("J4", 7.65, "LRA", "LRA M1 (Ø8 x 2.5 in the floor pocket under the front-right of the board)", "LRA_P / LRA_N (U5 OUT+/OUT-)"),
    ("J3", 12.4, "CHG", "charging-pad pigtail to the two inner-band contacts CP1/CP2 (floor wire groove from the -y channel exits)", "CHG_PAD / GND"),
    ("J1", 17.1, "BAT", "cell BT1 (301012, tabs toward +y, lead channel from the pocket's +y edge)", "VBAT / GND"),
    ("J5", 21.8, "SPK", "speaker LS1 in the right-wall pocket (its back is open to the bay above the floor)", "SPK_P / SPK_N (U10 OUTP/OUTN); optional group"),
]
# Charging-pad wires: the two Ø1.1 channels through the slab surface in the bay floor beside the -y wall at board
# x 14.75 / 16.75 (CAD rib_x -1.5 / -3.5), y ~0.7. From there a 1.2 wide x 0.8 deep groove in the sub-board FLOOR
# carries the two wires forward along the -y edge, across the board between the cell pocket and the LRA pocket
# (board x 10.25 = world X 3.0: the only 1.2 mm of floor between the two recesses), and along the +y edge to the
# J3 notch — below every bottom-side part, so the cavity height does not matter.
FLOOR_GROOVE = dict(width=1.2, depth=0.8,
                    path=[(17.4, 1.2), (10.25, 1.2), (10.25, 21.7), (12.4, 21.7)],
                    feeds="J3", note="charging-pad pigtail from the two channel exits (board x 14.75 / 16.75, y ~0.7) to the J3 notch")
CHANNEL_EXITS = [(14.75, 0.7), (16.75, 0.7)]   # where the CAD's Ø1.1 pad-wire channels surface in the bay floor (board xy)

# ----------------------------------------------------------------------------------------------
# 2. Parts
# ----------------------------------------------------------------------------------------------
@dataclass
class Part:
    ref: str
    name: str
    side: str           # "top" | "bottom"
    cx: float
    cy: float
    w: float            # along x (mm)
    h: float            # along y (mm)
    kind: str           # module|connector|ic|passive|pad|tp|switch|led|mic|inductor|diode|copper
    height: float       # mm above the board surface
    label: str = ""     # short text drawn in the part
    note: str = ""

    @property
    def x0(self): return self.cx - self.w / 2
    @property
    def x1(self): return self.cx + self.w / 2
    @property
    def y0(self): return self.cy - self.h / 2
    @property
    def y1(self): return self.cy + self.h / 2


def r0402(ref, cx, cy, side="bottom", along="x", label="", note=""):
    w, h = (1.0, 0.5) if along == "x" else (0.5, 1.0)
    return Part(ref, "0402", side, cx, cy, w, h, "passive", 0.35, label or ref, note)


def c0603(ref, cx, cy, side="bottom", along="x", label="", note=""):
    w, h = (1.6, 0.8) if along == "x" else (0.8, 1.6)
    return Part(ref, "0603", side, cx, cy, w, h, "passive", 0.95, label or ref, note)


def pad(ref, cx, cy, size, side="bottom", label="", note=""):
    return Part(ref, "pad", side, cx, cy, size, size, "pad", 0.0, label or ref, note)


def tp(ref, cx, cy, label, note="", side="top"):
    return Part(ref, "TP 1.0 mm", side, cx, cy, 1.0, 1.0, "tp", 0.0, label, note)


def conn(ref, cx, short, feeds, nets):
    return Part(ref, f"Pico-EZmate 2p ({short})", "top", cx, CONN_CY, CONN["w"], CONN["h"], "connector",
                CONN["mated_height"], f"{ref} {short}", f"{CONN['mpn']} 2-ckt header, wires exit toward +y into the edge notch; {feeds}; {nets}")


# Test pads: all eight on the TOP side so the board can be flashed, probed and bench-powered while it sits in the
# bay (the bottom face is 1.5 mm above the sub-board floor and unreachable once the board is seated).
TP_COL_X = 10.15        # column directly in front of the module's front row (x 11.1): 0.45 mm to the module edge
TP_FRONT_X = 5.2        # beside FPC1, inside the actuator swing zone (pads are 0 mm tall, so that is allowed)


SWITCH_OFFSET = 8.0     # centre of SW1 from the front edge
SWITCH_CY = 1.45        # body y 0.2..2.7, plunger points out of the LEFT edge (y < 0)
TPAD = dict(cx=8.1, cy=5.6, w=3.0, h=4.0, gap=0.5, ring=0.3)   # 3 × 4 mm copper, hatched GND ring around
LED_XY = (8.1, 10.0)
MIC_XY = (8.1, 15.3)    # mic body centre (bottom side) == port hole == lid hole position (0.55 toward -y vs the 18 mm board
                        # so the lid's Ø1.8 mic tube clears the J4 header at y >= 17.2)
FPC_W = 16.0            # FPC1 body along y

PARTS: list[Part] = [
    # ---------------- TOP ----------------
    Part("U1", "ESP32-S3-MINI-1U-N4R2", "top", MODULE_CX, MODULE_CY, MODULE["w"], MODULE["h"], "module",
         MODULE["height"], "U1  ESP32-S3-MINI-1U", "u.FL end flush with the BACK edge; 1.3 mm to the LEFT edge, the connector strip on the RIGHT; GND pour + the module's own pads under the u.FL end are fine (no PCB antenna on the -1U)"),
    Part("FPC1", "24-pin 0.5 mm FPC, bottom contact, flip-lock ZIF", "top", 2.5, FPC_CY, 4.0, FPC_W, "connector", 2.0,
         "FPC1  24p 0.5 mm  (OV2640 head)", "Hirose FH12-24S-0.5SH(55) flip-lock ZIF (alt. Amphenol F32R-1A7H1-11024 slider ZIF, same land pattern); FPC enters from the FRONT edge; keep x 4.5–5.5 free of parts > 0.6 mm for the actuator"),
    Part("SW1", "Omron B3U-3000P", "top", SWITCH_OFFSET, SWITCH_CY, 3.0, 2.5, "switch", 1.2, "SW1",
         "side-actuated, plunger out of the LEFT edge"),
    Part("TPAD1", "touch landing 3×4 mm copper + compliant contact", "top", TPAD["cx"], TPAD["cy"], TPAD["w"], TPAD["h"], "copper",
         TOUCH_CONTACT["compressed_height"], "TPAD1",
         f"landing for a conductive-foam block / spring finger ({TOUCH_CONTACT['free_height']} free, compressed to "
         f"{TOUCH_CONTACT['compressed_height']} by the lid) that reaches the {LID_ELECTRODE['w']:.0f}×{LID_ELECTRODE['h']:.0f} copper-foil "
         f"electrode on the lid underside; hatched GND ring 0.5 mm away; NO copper under it on the bottom"),
    Part("D1", "WS2812B-2020", "top", LED_XY[0], LED_XY[1], 2.0, 2.0, "led", 0.9, "D1", "under the lid window"),
    r0402("R7", 6.3, LED_XY[1], side="top", label="R7", note="1 kΩ WS2812 data series"),
    Part("C3", "100 µF 1206", "top", 7.8, 13.0, 3.2, 1.6, "passive", 1.8, "C3 100µ", "3V3 bulk for capture/radio peaks"),
    # the four wire-to-board headers (right strip, y 17.2–21.7), wires toward the +y edge notches
    *[conn(ref, cx, short, feeds, nets) for ref, cx, short, feeds, nets in CONNECTORS],
    # test pads (top): flash / debug / bench power with the board seated in the bay
    tp("TP1", TP_COL_X, 9.0, "IO0", "boot strap; hold to TP5 (GND) for download mode"),
    tp("TP5", TP_COL_X, 10.5, "GND", "USB GND / bench supply return"),
    tp("TP3", TP_COL_X, 12.0, "D-", "USB_DM IO19 — module front row (pin 23), short stub"),
    tp("TP4", TP_COL_X, 13.5, "D+", "USB_DP IO20 — module front row (pin 24), short stub"),
    tp("TP2", TP_COL_X, 15.0, "EN", "MCU_EN; pulse low to reset"),
    tp("TP6", TP_COL_X, 16.5, "3V3", "buck output (also at C3)"),
    tp("TP8", TP_FRONT_X, 1.0, "VBAT", "bench supply 4.0 V in (with TP5) when no cell is fitted"),
    tp("TP7", TP_FRONT_X, 2.5, "nCHG", "BQ25100 /CHG, low while charging"),

    # ---------------- BOTTOM: camera power cluster (front-left, beside FPC1's power pins at y 5.65 + 0.5·(n−1)) ----------------
    r0402("C9", 1.8, 1.5, along="y", note="1 µF U2 VIN"),
    Part("U2", "TPS22916C DSBGA-4", "bottom", 3.2, 1.5, 1.2, 0.9, "ic", 0.6, "U2", "camera rail load switch, ON = IO21"),
    r0402("C10", 4.5, 1.5, note="1 µF CAM_3V3 at U2 out"),
    r0402("R17", 4.5, 2.7, note="100k CAM_PWR_EN pull-down"),
    r0402("C11", 1.8, 3.4, along="y", note="1 µF CAM_2V8 at U3 out"),
    r0402("R16", 1.8, 4.7, along="y", note="10k CAM_RESET pull-up (CAM_3V3)"),
    r0402("C14", 1.8, 6.0, along="y", note="100n CAM_RESET delay"),
    r0402("C12", 1.8, 7.3, along="y", note="1 µF CAM_1V2 at U4 out"),
    r0402("R5", 1.0, 6.3, along="y", note="4.7k SIOD pull-up (FPC pin 3)"),
    r0402("C13", 1.0, 7.6, along="y", note="100n AVDD at FPC pin 4"),
    r0402("R6", 1.0, 8.9, along="y", note="4.7k SIOC pull-up (FPC pin 5)"),
    r0402("C24", 1.0, 10.2, along="y", note="100n DOVDD at FPC pin 11"),
    Part("U3", "XC6206P282MR SOT-23", "bottom", 3.7, 4.2, 2.9, 1.6, "ic", 1.15, "U3 2.8V", "AVDD LDO"),
    Part("U4", "XC6206P122MR SOT-23", "bottom", 3.7, 6.3, 2.9, 1.6, "ic", 1.15, "U4 1.2V", "DVDD LDO (DNP if the head regulates DVDD)"),

    # ---------------- BOTTOM: under the switch / front-left edge ----------------
    pad("BZ1a", 6.3, 1.2, 1.2, label="PZ", note="piezo wire (BUZZ_DRV) — optional PZ1 (DNP), bare pad kept"),
    pad("BZ1b", 8.3, 1.2, 1.2, label="PZ-", note="piezo wire return (GND)"),
    r0402("C22", 10.2, 1.3, note="100n BUTTON filter"),
    r0402("R15", 9.0, 2.6, note="100 Ω piezo series"),
    r0402("R13", 10.3, 5.6, along="y", note="1k touch series — just outside the pad"),

    # ---------------- BOTTOM: mic + LED supply gate (front-right of the original board) ----------------
    Part("MK1", "TDK T3902 PDM mic (bottom port)", "bottom", MIC_XY[0], MIC_XY[1], 2.65, 3.5, "mic", 0.98, "MK1",
         "bottom-port mic mounted on the BOTTOM; its port hole goes THROUGH the board and the lid hole sits above"),
    r0402("C19", 5.8, 15.9, note="100n mic VDD"),
    Part("U9", "TPS22916C DSBGA-4", "bottom", 10.3, 15.5, 1.2, 0.9, "ic", 0.6, "U9", "WS2812 supply gate 3V3→VLED, ON = IO33 (LED_PWR_EN)"),
    r0402("C20", 10.3, 14.3, note="100n VLED"),
    r0402("C21", 10.3, 16.8, note="1 µF VLED"),

    # ---------------- BOTTOM: buck + battery sense (back-left) ----------------
    c0603("C1", 11.6, 3.3, note="10 µF buck input"),
    Part("L1", "2.2 µH 2016 (DFE201610E)", "bottom", 13.7, 3.3, 2.0, 1.6, "inductor", 1.0, "L1", "buck inductor — tight loop with U8/C2"),
    c0603("C2", 15.8, 3.3, note="10 µF buck output"),
    Part("U8", "TPS62840DLC SOT-583", "bottom", 12.6, 5.6, 2.1, 1.6, "ic", 0.6, "U8 buck", "3V3 buck"),
    r0402("R12", 14.4, 5.3, note="VSET (3.3 V code)"),
    r0402("R8", 11.8, 6.9, note="1 M divider top (VBAT)"),
    r0402("R9", 13.0, 6.9, note="1 M divider bottom"),
    r0402("C23", 14.2, 6.9, note="100n BAT_SENSE"),
    r0402("R2", 12.3, 7.9, note="10k IO0 pull-up"),

    # ---------------- BOTTOM: charger cluster, directly under the J3 (CHG) and J1 (BAT) headers ----------------
    # CHG_PAD comes down from J3 through a via: D2 (TVS) within 2 mm of it, D3 right after, U7 IN; U7 OUT / C8 sit
    # beside the J1 via (VBAT). The 14 mm VBAT trunk to the buck (U8) runs along the bottom.
    # (all rows stay below y 21.3, clear of the 2.4 mm wire notches + 0.3 mm keep-out at y >= 21.4)
    Part("D2", "PESD5V0S1BB SOD-523", "bottom", 10.6, 20.9, 1.2, 0.8, "diode", 0.6, "D2", "bidirectional TVS on CHG_PAD, ≈ 2.3 mm from the J3 via"),
    Part("D3", "PMEG2005EB SOD-523", "bottom", 12.0, 20.9, 1.2, 0.8, "diode", 0.6, "D3", "Schottky CHG_PAD → CHG_IN (reversed-cradle protection), right after D2"),
    r0402("C7", 13.4, 20.9, note="1 µF charger IN"),
    r0402("R11", 10.6, 19.75, note="11.5k PRE_TERM"),
    Part("U7", "BQ25100 DSBGA-6", "bottom", 12.3, 19.75, 1.6, 0.9, "ic", 0.6, "U7", "charger 25 mA / 1 mA term, under J3"),
    r0402("R10", 14.0, 19.75, note="9.1k ISET"),
    r0402("R19", 15.3, 19.75, note="100k nCHG pull-up"),
    r0402("C8", 12.3, 18.6, note="1 µF charger OUT / VBAT (beside the J1 via)"),

    # ---------------- BOTTOM: optional speaker amp block (back-left, under the module) ----------------
    # 3V3 -> U11 -> VAMP -> U10 MAX98357A; I2S from the module (IO35-37) through R22-R24 (1 k series, a column
    # at x 19.2 beside U10's pin-1/16 corner), AMP_PWR_EN IO34. Everything ends before the CAD's back ledge
    # (x >= 23.6) and stays out of the u.FL strip. OUTP/OUTN leave as a 0.3 mm pair up the back column to J5.
    Part("U10", "MAX98357A 16-TQFN 3×3", "bottom", 21.3, 4.3, 3.0, 3.0, "ic", 0.8, "U10 amp",
         "I2S class-D amp, VDD = VAMP (gated), SD_MODE = VAMP; EP to the GND pour; OPTIONAL group"),
    r0402("R22", 19.2, 3.1, along="y", note="1k I2S BCLK series → U10 pin 16 (bounds the ESD back-feed into the unpowered amp while VAMP is off)"),
    r0402("R23", 19.2, 4.3, along="y", note="1k I2S LRCLK series → U10 pin 14"),
    r0402("R24", 19.2, 5.5, along="y", note="1k I2S DIN series → U10 pin 1"),
    r0402("R20", 21.0, 1.3, note="100k AMP_PWR_EN pull-down (IO34)"),
    r0402("R21", 22.5, 1.3, note="100k gain select GAIN_SLOT→VAMP (3 dB; 0R = 6 dB bench option, DNP = 9 dB)"),
    Part("U11", "TPS22916C DSBGA-4", "bottom", 19.9, 7.0, 1.2, 0.9, "ic", 0.6, "U11", "speaker amp rail gate 3V3→VAMP, ON = IO34 (AMP_PWR_EN)"),
    c0603("C25", 21.6, 6.6, note="10 µF VAMP at U10"),
    r0402("C26", 23.0, 6.6, along="y", note="100n VAMP at U10 VDD pins"),

    # ---------------- BOTTOM: aux + I2C sensors (right half) ----------------
    Part("Q1", "AO3400A SOT-23", "bottom", 14.6, 9.3, 2.9, 1.6, "ic", 1.15, "Q1 aux", "low-side N-FET, gate IO9"),
    r0402("R14", 17.0, 9.3, note="100k AUX_EN pull-down"),
    pad("J2a", 14.2, 11.2, 1.2, label="AUX+", note="VBAT to the aux load (bench experiment, bare pad kept)"),
    pad("J2b", 15.8, 11.2, 1.2, label="AUXd", note="open drain of Q1"),
    Part("U5", "DRV2605L VSSOP-10", "bottom", 16.2, 13.6, 3.0, 3.0, "ic", 1.1, "U5 DRV2605L", "haptic driver 0x5A; OUT+/OUT- as a 0.3 mm pair to the J4 via (≈ 10 mm)"),
    r0402("C15", 13.6, 12.6, along="y", note="1 µF DRV VDD"),
    r0402("C16", 13.6, 14.0, along="y", note="1 µF DRV REG"),
    r0402("R3", 18.2, 11.0, note="4.7k SDA pull-up"),
    r0402("R4", 19.4, 11.0, note="4.7k SCL pull-up"),
    Part("U6", "LIS2DW12 LGA-12 2×2", "bottom", 20.3, 13.8, 2.0, 2.0, "ic", 0.7, "U6", "accelerometer 0x18 (SA0=GND)"),
    r0402("C17", 20.3, 15.5, note="100n LIS VDD"),
    r0402("C18", 22.1, 13.8, note="100n LIS VDD_IO"),
    c0603("C4", 20.4, 9.3, note="10 µF module 3V3"),
    r0402("C5", 21.0, 10.5, note="100n module 3V3"),
    r0402("R18", 21.4, 11.6, note="4.7k LED_PWR_EN pull-down"),

    # ---------------- BOTTOM: module straps (back) ----------------
    r0402("R1", 22.8, 15.4, note="10k EN pull-up"),
    r0402("C6", 22.6, 16.6, note="1 µF EN delay"),
]

# ----------------------------------------------------------------------------------------------
# 3. Keepouts / zones  (x0, y0, x1, y1 in board mm)
# ----------------------------------------------------------------------------------------------
TPAD_RING = (TPAD["cx"] - TPAD["w"] / 2 - TPAD["gap"] - TPAD["ring"], TPAD["cy"] - TPAD["h"] / 2 - TPAD["gap"] - TPAD["ring"],
             TPAD["cx"] + TPAD["w"] / 2 + TPAD["gap"] + TPAD["ring"], TPAD["cy"] + TPAD["h"] / 2 + TPAD["gap"] + TPAD["ring"])
TPAD_NOCOPPER = (TPAD["cx"] - TPAD["w"] / 2, TPAD["cy"] - TPAD["h"] / 2, TPAD["cx"] + TPAD["w"] / 2, TPAD["cy"] + TPAD["h"] / 2)
FPC_ACT_ZONE = (4.5, FPC_CY - FPC_W / 2, 5.5, FPC_CY + FPC_W / 2)       # actuator swing: parts <= 0.6 mm only
DVP_ZONE = (1.4, 8.3, MODULE_X0 + 1.5, 13.4)

ZONES = [
    # name, side ('both'|'top'|'bottom'), rect, style, text
    ("UFL", "both", (UFL_END_X0, 0.0, L, W), "clearance",
     "u.FL end: module GND/3V3/EN pads + GND pour are fine here (no PCB antenna on the -1U); no DVP/XCLK/PCLK/PDM "
     "traces, no part other than U1; pigtail exits over the back edge"),
    ("TPAD_NC", "bottom", TPAD_NOCOPPER, "keepout", "no copper under the touch pad"),
    ("FPC_ACT", "top", FPC_ACT_ZONE, "clearance", "FPC actuator swing: parts ≤ 0.6 mm only"),
    ("DVP", "bottom", DVP_ZONE, "corridor",
     "DVP bus corridor: Y2..Y9, PCLK, HREF, VSYNC, XCLK from FPC1 pins 7–22 to the module front/right pins (≤ 15 mm, no other signals)"),
    ("VIAF", "bottom", (MODULE_X0, 8.3, MODULE_X0 + 1.5, 13.4), "corridor", "via field up to the module pads"),
    ("CONN", "top", (5.3, CONN_Y0 - 0.2, UFL_END_X0, W), "clearance",
     "connector strip: the four Pico-EZmate headers + their wire notches; GND pour, no signal traces under the notches"),
]

MIC_HOLE_D = 0.6   # through-board acoustic port (match the T3902 port position/size at layout)


def notch_rect(cx: float, margin: float = 0.0):
    """Keep-out rectangle of a wire notch in the right edge (both sides, copper and parts)."""
    return (cx - NOTCH["w"] / 2 - margin, W - NOTCH["d"] - margin, cx + NOTCH["w"] / 2 + margin, W + 1.0)


NOTCHES = [dict(ref=ref, edge="right", cx=cx, cy=W, w=NOTCH["w"], d=NOTCH["d"]) for ref, cx, _, _, _ in CONNECTORS]

# FPC pin order assumed (ESP32-CAM / Arducam M0031) — pin 1 at the LEFT end of FPC1 (low y)
FPC_PINS = ["NC", "AGND", "SIOD", "AVDD 2.8", "SIOC", "RESET", "VSYNC", "PWDN", "HREF", "DVDD 1.2", "DOVDD 3.3",
            "Y9", "XCLK", "Y8", "DGND", "Y7", "PCLK", "Y6", "Y2", "Y5", "Y3", "Y4", "NC", "NC"]
FPC_GPIO = {"SIOD": "IO40", "SIOC": "IO39", "VSYNC": "IO38", "HREF": "IO47", "Y9": "IO48", "XCLK": "IO10",
            "Y8": "IO11", "Y7": "IO12", "PCLK": "IO13", "Y6": "IO14", "Y2": "IO15", "Y5": "IO16", "Y3": "IO17", "Y4": "IO18"}
FPC_PIN_PITCH = 0.5
FPC_PIN_Y0 = FPC_CY - (len(FPC_PINS) - 1) * FPC_PIN_PITCH / 2   # 5.65


def fpc_pin_y(n: int) -> float:
    return FPC_PIN_Y0 + (n - 1) * FPC_PIN_PITCH


# Route-critical nets: (label, side, polyline of board points, colour)
NETS = [
    ("DVP ×12 (Y2–Y9, PCLK, HREF, VSYNC, XCLK) → U1", "bottom", [(2.5, 12.0), (MODULE_X0 + 0.8, 12.0)], "#c0392b"),
    ("SCCB SIOD/SIOC + R5/R6 to CAM_3V3", "bottom", [(1.0, 7.0), (MODULE_X0 + 0.8, 7.0)], "#8e44ad"),
    ("3V3 → U2 → CAM_3V3 → U3/U4 → FPC1 power pins", "bottom", [(3.2, 1.5), (3.7, 4.2), (3.7, 6.3), (1.0, 7.6)], "#e67e22"),
    ("buck loop C1–U8–L1–C2 (tight, same layer)", "bottom", [(11.6, 3.3), (12.6, 5.6), (13.7, 3.3), (15.8, 3.3)], "#d35400"),
    ("CHG: J3 (via) → D2 TVS → D3 → U7 IN", "bottom", [(12.4, 19.45), (10.6, 20.9), (12.0, 20.9), (12.3, 19.75)], "#16a085"),
    ("VBAT: J1 (via) → C8 / U7 OUT → U8 VIN (14 mm trunk), R8", "bottom", [(17.1, 19.45), (12.3, 18.6), (12.6, 5.6), (11.8, 6.9)], "#1f618d"),
    ("I²C SDA/SCL (IO5/IO6) → U5, U6, R3/R4", "bottom", [(16.2, 13.6), (18.8, 11.0), (20.3, 13.8)], "#2e86c1"),
    ("LRA OUT+/OUT− (0.3 mm pair) → J4 via", "bottom", [(16.2, 15.1), (7.65, 19.45)], "#7d6608"),
    ("VLED: U9 → D1 (via to top) / RGB_DATA IO43 → R7 → D1", "bottom", [(10.3, 15.5), (10.3, 12.0), (8.1, 10.0)], "#117a65"),
    ("PDM CLK/DATA (IO42/IO41) → MK1", "bottom", [(MODULE_X0 + 0.8, 15.3), (9.5, 15.3)], "#6c3483"),
    ("I²S BCLK/LRCLK/DOUT (IO35/36/37) → R22–R24 1 kΩ → U10; AMP_PWR_EN (IO34) → U11", "bottom", [(MODULE_X0 + 0.8, 4.3), (19.8, 4.3)], "#b9770e"),
    ("3V3 → U11 → VAMP (C25/C26) → U10; OUTP/OUTN 0.3 mm pair up the back column → J5 via (≈ 15 mm)", "bottom",
     [(19.9, 7.0), (21.6, 6.6), (22.6, 5.8), (22.95, 17.6), (21.8, 19.45)], "#5b2c6f"),
]

COLORS = {
    "module": ("#dfe9f3", "#2c3e50"),
    "connector": ("#f6e3c5", "#7e5109"),
    "ic": ("#d5f5e3", "#1e8449"),
    "passive": ("#f2f3f4", "#5d6d7e"),
    "inductor": ("#fdebd0", "#9c640c"),
    "diode": ("#fadbd8", "#922b21"),
    "pad": ("#f9e79f", "#7d6608"),
    "tp": ("#fcf3cf", "#7d6608"),
    "switch": ("#e8daef", "#6c3483"),
    "led": ("#fdedec", "#c0392b"),
    "mic": ("#d6eaf8", "#1b4f72"),
    "copper": ("#f5b041", "#9c640c"),
}


# ----------------------------------------------------------------------------------------------
# 4. Checks (run before drawing; the script aborts on a hard violation)
# ----------------------------------------------------------------------------------------------
def _overlap(a, b, tol=0.0) -> float:
    """Overlap area of two (x0,y0,x1,y1) rects after shrinking each by tol/2."""
    ax0, ay0, ax1, ay1 = a[0] + tol / 2, a[1] + tol / 2, a[2] - tol / 2, a[3] - tol / 2
    bx0, by0, bx1, by1 = b[0] + tol / 2, b[1] + tol / 2, b[2] - tol / 2, b[3] - tol / 2
    w = min(ax1, bx1) - max(ax0, bx0)
    h = min(ay1, by1) - max(ay0, by0)
    return w * h if (w > 0 and h > 0) else 0.0


def rect_of(p: Part):
    return (p.x0, p.y0, p.x1, p.y1)


def front_ledge_gap() -> tuple[float, float]:
    """y range (with 0.3 margin) of the bottom parts closest to the front edge (x0 < 1.3): the CAD's two front
    board ledges (board x -0.3..0.7) are placed outside it."""
    near = [p for p in PARTS if p.side == "bottom" and p.x0 < 1.3]
    return (round(min(p.y0 for p in near) - 0.3, 2), round(max(p.y1 for p in near) + 0.3, 2))


def run_checks() -> list[str]:
    problems: list[str] = []
    notes: list[str] = []
    EDGE = 0.4
    module = next(p for p in PARTS if p.ref == "U1")
    for p in PARTS:
        # inside the outline (SW1 may touch the edge: side-actuated by design)
        lim = 0.0 if p.ref == "SW1" else EDGE
        back_lim = 0.0 if p.ref == "U1" else lim      # the module's antenna end is flush with the back edge by design
        if p.x0 < lim - 1e-6 or p.y0 < lim - 1e-6 or p.x1 > L - back_lim + 1e-6 or p.y1 > W - lim + 1e-6:
            problems.append(f"{p.ref} ({p.side}) violates the {lim} mm edge clearance: {rect_of(p)}")
        # u.FL end strip: nothing but the module itself (keeps the pigtail exit clear)
        if p.ref != "U1" and _overlap(rect_of(p), (UFL_END_X0, 0, L, W)) > 0:
            problems.append(f"{p.ref} is inside the u.FL end strip (x ≥ {UFL_END_X0})")
        # heights (TPAD1 carries the compliant touch contact, which is meant to reach the lid underside exactly)
        if p.side == "bottom" and p.height > BOTTOM_MAX_HEIGHT + 1e-6:
            problems.append(f"{p.ref} is {p.height} mm tall on the bottom (max {BOTTOM_MAX_HEIGHT})")
        # the CAD's back ledge carries the board from x = 23.6: nothing on the bottom may reach it
        if p.side == "bottom" and p.x1 > BACK_LEDGE_X0 + 1e-6:
            problems.append(f"{p.ref} ({p.side}) reaches the back board ledge (x ≥ {BACK_LEDGE_X0}): {rect_of(p)}")
        if p.side == "top" and p.ref != "TPAD1" and p.height > TOP_MAX_HEIGHT + 1e-6:
            problems.append(f"{p.ref} is {p.height} mm tall on the top (max {TOP_MAX_HEIGHT})")
        if p.ref == "TPAD1":
            if abs(p.height - (TOP_MAX_HEIGHT + LID_CLEARANCE)) > 1e-6:
                problems.append(f"TPAD1 contact height {p.height} must equal the board-top → lid-underside gap "
                                f"{TOP_MAX_HEIGHT + LID_CLEARANCE:.2f}")
            if TOUCH_CONTACT["free_height"] <= p.height:
                problems.append("touch contact free height must exceed the compressed height (needs preload)")
        # test pads live on the top side (reachable with the board seated in the bay)
        if p.kind == "tp" and p.side != "top":
            problems.append(f"{p.ref} test pad is on the {p.side} side — unreachable once the board is seated")
        # no copper under the touch pad
        if p.side == "bottom" and _overlap(rect_of(p), TPAD_NOCOPPER) > 0:
            problems.append(f"{p.ref} sits under the touch pad (no-copper zone)")
        # FPC actuator clearance (0 mm test pads are allowed in the swing zone)
        if p.side == "top" and p.ref != "FPC1" and p.height > 0.6 and _overlap(rect_of(p), FPC_ACT_ZONE) > 0:
            problems.append(f"{p.ref} is in the FPC actuator clearance zone")
        # keep the test pads clear of the module's land pattern (probe slip onto the grounded shield)
        if p.kind == "tp" and p.x1 > MODULE_X0 - 0.4 + 1e-6 and p.y0 < module.y1 and p.y1 > module.y0:
            problems.append(f"{p.ref} is closer than 0.4 mm to the module's front edge")
        # wire-to-board headers: TOP side, in the right strip, >= CONN_GAP_MODULE from the module, out of the u.FL strip
        if p.kind == "connector" and p.ref != "FPC1":
            if p.side != "top":
                problems.append(f"{p.ref} must be on the TOP side (bottom envelope is {BOTTOM_MAX_HEIGHT} mm, header is {p.height})")
            if p.x1 > module.x0 and p.y0 < module.y1 + CONN_GAP_MODULE - 1e-6:
                problems.append(f"{p.ref} is closer than {CONN_GAP_MODULE} mm to the module's right row")
            if W - p.y1 < NOTCH["d"] - 1e-6:
                problems.append(f"{p.ref} overlaps its own wire notch (needs {NOTCH['d']} mm to the right edge)")
        # nothing (either side) in a wire notch or within 0.3 mm of it
        for n in NOTCHES:
            if p.ref != n["ref"] and _overlap(rect_of(p), notch_rect(n["cx"], 0.3)) > 0:
                problems.append(f"{p.ref} ({p.side}) lies in / beside the {n['ref']} wire notch")
    # pairwise overlaps on the same side (0.1 mm courtyard shrink → parts may be 0.1 mm apart at closest)
    for i, a in enumerate(PARTS):
        for b in PARTS[i + 1:]:
            if a.side != b.side:
                continue
            if _overlap(rect_of(a), rect_of(b), tol=-0.2) > 1e-9:   # grow each by 0.1 → demand ≥ 0.1 mm gap
                problems.append(f"{a.ref} and {b.ref} are closer than 0.1 mm on the {a.side} side")
    # top parts (other than TPAD1) must not sit inside the touch-pad ring
    for p in PARTS:
        if p.side == "top" and p.ref not in ("TPAD1",) and _overlap(rect_of(p), TPAD_RING) > 0:
            problems.append(f"{p.ref} overlaps the touch pad guard ring")
    # bottom parts inside the DVP corridor (soft: warn)
    for p in PARTS:
        if p.side == "bottom" and _overlap(rect_of(p), DVP_ZONE) > 0 and p.kind != "tp":
            notes.append(f"note: {p.ref} lies in the DVP corridor")
    # mic hole must be clear on the top side (the lid's Ø1.8 tube lands there)
    for p in PARTS:
        if p.side == "top" and _overlap(rect_of(p), (MIC_XY[0] - 0.9, MIC_XY[1] - 0.9, MIC_XY[0] + 0.9, MIC_XY[1] + 0.9)) > 0:
            problems.append(f"{p.ref} covers the mic port hole on the top side")
    # every connector of the netlist's plug-in set is placed, exactly once
    refs = [p.ref for p in PARTS]
    for ref in ("J1", "J3", "J4", "J5", "FPC1"):
        if refs.count(ref) != 1:
            problems.append(f"connector {ref} placed {refs.count(ref)} times")
    # the floor wire groove must cross the board where there is floor between the cell pocket and the LRA pocket
    # (CAD: cell pocket board x 10.85–21.25, LRA pocket board x 1.25–9.65 at the groove's y); keep the cross leg there
    xs = {x for x, _ in FLOOR_GROOVE["path"]}
    if not any(9.65 + FLOOR_GROOVE["width"] / 2 - 1e-6 <= x <= 10.85 - FLOOR_GROOVE["width"] / 2 + 1e-6 for x in xs):
        problems.append("floor wire groove: its cross-board leg must lie in board x 10.25 ± 0.0 (between the LRA and cell pockets)")
    # the groove must start over both channel exits
    gx0, gx1 = min(x for x, _ in FLOOR_GROOVE["path"][:2]), max(x for x, _ in FLOOR_GROOVE["path"][:2])
    for ex, ey in CHANNEL_EXITS:
        if not (gx0 <= ex <= gx1 and abs(ey - FLOOR_GROOVE["path"][0][1]) <= FLOOR_GROOVE["width"] / 2 + 0.55):
            problems.append(f"floor wire groove does not reach the channel exit at {ex}, {ey}")
    return problems + notes


# ----------------------------------------------------------------------------------------------
# 5. Drawing — board views
# ----------------------------------------------------------------------------------------------
S = 18.0          # px per mm
OX, OY = 150.0, 120.0   # board origin in the picture


def make_view(side: str):
    """Return f(x, y) -> (px, py). Front edge at the TOP of the picture. Bottom view is mirrored in y."""
    if side == "top":
        return lambda x, y: (OX + S * y, OY + S * x)
    return lambda x, y: (OX + S * (W - y), OY + S * x)


def draw_rect_mm(svg: SVG, view, x0, y0, x1, y1, **kw):
    (px0, py0), (px1, py1) = view(x0, y0), view(x1, y1)
    x, y = min(px0, px1), min(py0, py1)
    svg.rect(x, y, abs(px1 - px0), abs(py1 - py0), **kw)


def draw_board(side: str, title: str, path: str) -> None:
    svg = SVG(1400, 800)
    svg.arrow_marker("dim", "#555", 5)
    svg.arrow_marker("net", "#333", 6)
    svg.arrow_marker("wire", "#7e5109", 6)
    svg.hatch("gndhatch", "#9c640c", spacing=4, sw=0.7)
    svg.hatch("keep", "#c0392b", spacing=6, sw=0.9, angle=-45)
    svg.hatch("corr", "#1f618d", spacing=6, sw=0.6, angle=45)
    view = make_view(side)
    mirrored = side == "bottom"

    # title
    svg.text(20, 28, title, size=20, weight="bold")
    svg.text(20, 52, f"mcring v1 stage-1 board — {L:.1f} × {W:.1f} × {BOARD['thickness']} mm, 2 layers, "
             f"r = {BOARD['corner_r']} mm.  Scale {S:.0f} px/mm.  Front (camera) edge at the top of the page.", size=12, fill="#444")
    if mirrored:
        svg.text(20, 70, "Seen from BELOW: the board's LEFT edge (switch) is on the RIGHT of this picture. "
                 "Top-side parts are ghosted (dashed).", size=12, fill="#922b21", italic=True)
    else:
        svg.text(20, 70, "Seen from ABOVE. Bottom-side parts are ghosted (dashed) for reference.", size=12, fill="#444", italic=True)

    # outline
    (bx, by) = view(0, 0) if not mirrored else view(0, W)
    bw, bh = S * W, S * L
    svg.add(f'<path d="{rounded_rect_path(bx, by, bw, bh, S * BOARD["corner_r"])}" fill="#fbfcf7" stroke="#222" stroke-width="2"/>')

    # edge labels
    svg.text(bx + bw / 2, by - 40, "FRONT — camera / FPC edge (toward the fingertip)", size=12, anchor="middle", weight="bold", fill="#7e5109")
    svg.text(bx + bw / 2, by + bh + 46, "BACK — antenna / u.FL end (toward the wrist)", size=12, anchor="middle", weight="bold", fill="#c0392b")
    left_label = "LEFT edge (switch)" if not mirrored else "RIGHT edge (connector notches)"
    right_label = "RIGHT edge (connector notches)" if not mirrored else "LEFT edge (switch)"
    svg.text(bx - 56, by + bh / 2, left_label, size=11, anchor="middle", rotate=-90, fill="#444")
    svg.text(bx + bw + 100, by + bh / 2, right_label, size=11, anchor="middle", rotate=90, fill="#444")

    # dimensions
    svg.dim_h(bx, bx + bw, by - 16, f"{W:.1f} mm (across finger)", size=10)
    svg.dim_v(by, by + bh, bx - 24, f"{L:.1f} mm (along finger)", size=10)
    # module position dims
    (mx0, my0) = view(MODULE_X0, 0)
    svg.line(bx - 8, my0, bx + bw + 8, my0, stroke="#2c3e50", sw=0.6, dash="4 3")
    svg.text(bx + bw + 12, my0 + 8, f"x = {MODULE_X0:.1f} module front edge", size=9, fill="#2c3e50")
    (_, sy) = view(SWITCH_OFFSET, 0)
    if not mirrored:
        svg.line(bx - 8, sy, bx - 2, sy, stroke="#6c3483", sw=1.2)
        svg.text(bx - 12, sy, f"switch_offset {SWITCH_OFFSET:.1f}", size=9, fill="#6c3483", anchor="end")
    else:
        svg.line(bx + bw + 2, sy, bx + bw + 8, sy, stroke="#6c3483", sw=1.2)
        svg.text(bx + bw + 12, sy - 4, f"switch_offset {SWITCH_OFFSET:.1f}", size=9, fill="#6c3483")

    # zones
    for name, zside, r, style, text in ZONES:
        if zside != "both" and zside != side:
            continue
        if style == "keepout":
            draw_rect_mm(svg, view, *r, fill="url(#keep)", stroke="#c0392b", sw=1.0, dash="5 3", opacity=0.9)
        elif style == "clearance":
            draw_rect_mm(svg, view, *r, fill="#fdf2e9", stroke="#e67e22", sw=0.8, dash="3 3")
        else:
            draw_rect_mm(svg, view, *r, fill="url(#corr)", stroke="#1f618d", sw=0.7, dash="2 3", opacity=0.6)

    # wire notches in the right edge (both views): a half-round bite of NOTCH w x d
    for n in NOTCHES:
        (nx, ny) = view(n["cx"], W)
        r_px = S * n["w"] / 2
        d_px = S * n["d"]
        dirn = 1 if not mirrored else -1      # notch opens toward the picture's right (top view) / left (bottom view)
        x_edge = nx
        svg.add(f'<path d="M {x_edge:.1f} {ny - r_px:.1f} L {x_edge - dirn * d_px:.1f} {ny - r_px:.1f} '
                f'A {r_px:.1f} {r_px:.1f} 0 0 {0 if dirn > 0 else 1} {x_edge - dirn * d_px:.1f} {ny + r_px:.1f} L {x_edge:.1f} {ny + r_px:.1f} Z" '
                f'fill="#ffffff" stroke="#222" stroke-width="1.6"/>')
        if not mirrored:
            svg.text(nx + 18, ny - 10, f"{n['ref']} notch {n['w']}×{n['d']}", size=7.5, fill="#7e5109")

    # touch-pad guard ring (top copper) — drawn on the top view, ghosted on the bottom
    if side == "top":
        draw_rect_mm(svg, view, *TPAD_RING, fill="url(#gndhatch)", stroke="#9c640c", sw=0.8)
        draw_rect_mm(svg, view, TPAD_RING[0] + TPAD["ring"], TPAD_RING[1] + TPAD["ring"], TPAD_RING[2] - TPAD["ring"],
                     TPAD_RING[3] - TPAD["ring"], fill="#fbfcf7", stroke="#9c640c", sw=0.5)

    # ghosted parts of the other side
    for p in PARTS:
        if p.side == side:
            continue
        if p.kind in ("passive", "tp") and p.w < 1.2 and p.h < 1.2:
            continue   # skip the tiny ones to keep the ghost readable
        draw_rect_mm(svg, view, p.x0, p.y0, p.x1, p.y1, fill="none", stroke="#999", sw=0.8, dash="3 2")
        (cx, cy) = view(p.cx, p.cy)
        if p.w * p.h > 6:
            svg.text(cx, cy, p.ref + " (other side)", size=8, fill="#999", anchor="middle", italic=True)

    # parts of this side
    for p in PARTS:
        if p.side != side:
            continue
        fill, stroke = COLORS[p.kind]
        draw_rect_mm(svg, view, p.x0, p.y0, p.x1, p.y1, fill=fill, stroke=stroke, sw=1.2, rx=1.5 if p.kind == "pad" else 0.5,
                     title=f"{p.ref} {p.name} @ ({p.cx:.2f}, {p.cy:.2f}) {p.w}×{p.h} mm, h={p.height} mm")
        (cx, cy) = view(p.cx, p.cy)
        area = p.w * p.h
        if area >= 8:
            svg.text(cx, cy - 2, p.label, size=11, anchor="middle", weight="bold", fill=stroke)
            svg.text(cx, cy + 11, f"{p.w}×{p.h}  h{p.height}", size=8, anchor="middle", fill="#555")
        elif area >= 2.0:
            svg.text(cx, cy, p.label, size=8, anchor="middle", weight="bold", fill=stroke)
        else:
            rot = -90 if (p.h > p.w) else 0
            svg.text(cx, cy, p.label, size=6.5, anchor="middle", fill=stroke, rotate=rot)

    # module details (top view): u.FL + pin-free antenna edge + shield; connector plug wire exits
    if side == "top":
        u = next(p for p in PARTS if p.ref == "U1")
        (ux, uy) = view(L - 1.2, 4.45)
        svg.circle(ux, uy, S * 1.0, fill="#fff", stroke="#2c3e50", sw=1.2)
        svg.circle(ux, uy, S * 0.4, fill="#2c3e50", stroke="none")
        svg.text(ux, uy - S * 1.5, "u.FL (position per datasheet) → flex antenna down the back wall", size=8, anchor="start", fill="#2c3e50")
        # pin rows on 3 edges
        for (x0, y0, x1, y1) in [(u.x0, u.y0, u.x0 + 0.9, u.y1), (u.x0, u.y0, u.x1 - 2.0, u.y0 + 0.9), (u.x0, u.y1 - 0.9, u.x1 - 2.0, u.y1)]:
            draw_rect_mm(svg, view, x0, y0, x1, y1, fill="none", stroke="#2c3e50", sw=0.5, dash="1 1")
        (tx, ty) = view(u.x0 + 2.4, MODULE_CY)
        svg.text(tx, ty, "I/O pins on the front edge and both sides; none on the u.FL edge (pin positions: VERIFY vs. the Espressif footprint)", size=8, anchor="middle", fill="#2c3e50")
        # FPC pins
        for n in range(1, 25):
            (px, py) = view(0.9, fpc_pin_y(n))
            svg.rect(px - 2.5, py - 3.5, 5, 7, fill="#7e5109", stroke="none")
        (px, py) = view(0.9, fpc_pin_y(1))
        svg.text(px, py - 10, "pin 1", size=7, anchor="middle", fill="#7e5109")
        (px, py) = view(0.9, fpc_pin_y(24))
        svg.text(px, py - 10, "pin 24", size=7, anchor="middle", fill="#7e5109")
        (px, py) = view(4.1, fpc_pin_y(12))
        svg.text(px, py, "contacts face DOWN (bottom-contact, flip-lock ZIF); FPC enters from the front edge", size=7.5, anchor="middle", fill="#7e5109")
        # plug wire exits: an arrow from each header toward its notch
        for ref, cx, short, _, _ in CONNECTORS:
            (ax, ay) = view(cx, CONN_CY + 1.0)
            (nx, ny) = view(cx, W - 0.2)
            svg.line(ax, ay, nx, ny, stroke="#7e5109", sw=1.6, marker="wire")
        svg.text(bx, by + bh + 66, f"4 × {CONN['series']} {CONN['mpn']} headers (1.2 mm pitch, {CONN['mated_height']} mm mated) in the right strip: pigtails plug in from above, "
                 f"wires drop through the {NOTCH['w']}×{NOTCH['d']} edge notches", size=8.5, anchor="start", fill="#7e5109")
        # LED window / mic hole / switch plunger
        (lx, ly) = view(*LED_XY)
        svg.circle(lx, ly, S * 1.5, fill="none", stroke="#c0392b", sw=0.8, dash="3 2")
        svg.line(lx - S * 1.5, ly, bx - 10, ly + 18, stroke="#c0392b", sw=0.6)
        svg.text(bx - 12, ly + 18, "lid window Ø3 over D1", size=8.5, fill="#c0392b", anchor="end")
        (sx, sy) = view(SWITCH_OFFSET, 0.0)
        svg.polygon([(sx - 9, sy), (sx + 9, sy), (sx + 9, sy - 8), (sx - 9, sy - 8)], fill="#6c3483", stroke="none")
        svg.text(sx - 12, sy + 14, "plunger through the LEFT wall", size=8, fill="#6c3483", anchor="end")
        # touch electrode on the lid (dashed outline of the 4×5 foil above TPAD1)
        draw_rect_mm(svg, view, TPAD["cx"] - LID_ELECTRODE["w"] / 2, TPAD["cy"] - LID_ELECTRODE["h"] / 2,
                     TPAD["cx"] + LID_ELECTRODE["w"] / 2, TPAD["cy"] + LID_ELECTRODE["h"] / 2,
                     fill="none", stroke="#9c640c", sw=0.8, dash="4 2")
        (ex, ey) = view(TPAD["cx"] - LID_ELECTRODE["w"] / 2, TPAD["cy"] - LID_ELECTRODE["h"] / 2)   # foil's front-left corner
        svg.line(ex, ey, bx - 8, ey - 4, stroke="#9c640c", sw=0.6)
        for i, s_ in enumerate([f"touch electrode: {LID_ELECTRODE['w']:.0f}×{LID_ELECTRODE['h']:.0f} Cu foil",
                                f"on the LID underside ({LID_ELECTRODE['dielectric']} resin)",
                                f"foam contact on TPAD1 {TOUCH_CONTACT['free_height']}→{TOUCH_CONTACT['compressed_height']}"]):
            svg.text(bx - 12, ey - 30 + 11 * i, s_, size=8.5, fill="#9c640c", anchor="end")
        # test-pad column (leader from TP1 to the left margin)
        (tx_, ty_) = view(TP_COL_X, 9.0 - 0.5)
        svg.line(tx_, ty_, bx - 10, ty_ + 48, stroke="#7d6608", sw=0.6)
        svg.text(bx - 12, ty_ + 45, "TP1–TP6 on the top side,", size=8.5, fill="#7d6608", anchor="end")
        svg.text(bx - 12, ty_ + 56, "0.45 mm before U1's front row", size=8.5, fill="#7d6608", anchor="end")
    # mic hole (both views)
    (mx, my) = view(*MIC_XY)
    svg.circle(mx, my, S * MIC_HOLE_D / 2, fill="#fff", stroke="#1b4f72", sw=1.2)
    if side == "top":
        svg.line(mx - S * 0.4, my, bx - 10, my + 34, stroke="#1b4f72", sw=0.6)
        svg.text(bx - 12, my + 34, "mic port Ø0.6 (lid hole above)", size=8.5, fill="#1b4f72", anchor="end")
    else:
        svg.line(mx + S * 0.4, my, bx + bw + 10, my + 10, stroke="#1b4f72", sw=0.6)
        svg.text(bx + bw + 12, my + 10, "mic port Ø0.6 (MK1 is bottom-port)", size=8.5, fill="#1b4f72")
        # floor wire groove (in the enclosure's sub-board floor, under the board) + the two channel exits
        pts = [view(x, y) for x, y in FLOOR_GROOVE["path"]]
        svg.polyline(pts, stroke="#16a085", sw=S * FLOOR_GROOVE["width"], opacity=0.25, linejoin="miter")
        svg.polyline(pts, stroke="#16a085", sw=1.0, dash="6 3")
        for ex, ey in CHANNEL_EXITS:
            (cx_, cy_) = view(ex, ey)
            svg.circle(cx_, cy_, S * 0.55, fill="none", stroke="#16a085", sw=1.2, dash="2 2")
        (gx, gy) = view(FLOOR_GROOVE["path"][1][0], FLOOR_GROOVE["path"][1][1])
        svg.text(gx, gy - 14, f"floor wire groove {FLOOR_GROOVE['width']}×{FLOOR_GROOVE['depth']} (enclosure): charging wires from the two channel exits → J3 notch",
                 size=7.5, fill="#16a085", anchor="end")

    # critical nets
    for label, nside, pts, col in NETS:
        if nside != side:
            continue
        ppts = [view(x, y) for x, y in pts]
        svg.polyline(ppts, stroke=col, sw=2.2, marker="net", opacity=0.75)

    # ----- right-hand panel: legend + tables -----
    px0 = 760
    y = 100
    svg.text(px0, y, "Legend", size=13, weight="bold"); y += 18
    for kind, (f, s) in COLORS.items():
        svg.rect(px0, y - 7, 14, 10, fill=f, stroke=s, sw=1)
        svg.text(px0 + 20, y - 2, kind, size=9.5); y += 14
    svg.rect(px0, y - 7, 14, 10, fill="url(#keep)", stroke="#c0392b", sw=1); svg.text(px0 + 20, y - 2, "keep-out (no copper)", size=9.5); y += 14
    svg.rect(px0, y - 7, 14, 10, fill="url(#corr)", stroke="#1f618d", sw=1); svg.text(px0 + 20, y - 2, "routing corridor (bottom)", size=9.5); y += 14
    svg.rect(px0, y - 7, 14, 10, fill="url(#gndhatch)", stroke="#9c640c", sw=1); svg.text(px0 + 20, y - 2, "hatched GND ring (top copper)", size=9.5); y += 20

    svg.text(px0, y, "Route-critical nets on this side", size=13, weight="bold"); y += 16
    for label, nside, pts, col in NETS:
        if nside != side:
            continue
        svg.line(px0, y - 3, px0 + 16, y - 3, stroke=col, sw=3)
        svg.text(px0 + 22, y - 3, label, size=9); y += 13
    if side == "top":
        for s_ in ["Top layer: module footprint + fan-out, FPC1 pads, SW1, D1/R7, C3, touch landing + GND hatch, 8 test pads,",
                   "the four Pico-EZmate headers in the right strip (vias down to the charger / DRV / amp); GND pour elsewhere.",
                   "Bottom layer: all small ICs/passives, the two bare pad pairs (BZ1, J2), DVP corridor, I²C, power cluster; GND pour.",
                   "Module GND pads → ≥ 9 vias to the bottom pour; the u.FL end needs no copper keep-out (no PCB antenna on the -1U)."]:
            svg.text(px0 + 22, y - 3, s_, size=9, fill="#444"); y += 13
    y += 8

    svg.text(px0, y, f"Parts on the {side} side  (ref · footprint · centre x,y mm · w×h · height)", size=13, weight="bold"); y += 16
    col_w = 290
    rows = [p for p in PARTS if p.side == side]
    n_per_col = 40
    for i, p in enumerate(rows):
        cx_ = px0 + (i // n_per_col) * col_w
        cy_ = y + (i % n_per_col) * 11.5
        fill, stroke = COLORS[p.kind]
        svg.rect(cx_, cy_ - 7, 8, 8, fill=fill, stroke=stroke, sw=0.8)
        svg.text(cx_ + 12, cy_ - 3, f"{p.ref:<6} {p.name[:26]:<26} ({p.cx:5.2f},{p.cy:5.2f}) {p.w}×{p.h} h{p.height}",
                 size=8.2, mono=True)
    y += (min(n_per_col, len(rows))) * 11.5 + 10
    svg.h = max(svg.h, y + 20)
    svg.save(path, png_scale=2.0)


# ----------------------------------------------------------------------------------------------
# 6. Drawing — stack-up and camera pod section
# ----------------------------------------------------------------------------------------------
STACK = [
    # (name, thickness, colour, note)
    ("band inner wall (resin)", 1.20, "#e5e8e8", "≥ 1.2 mm between skin and cell"),
    ("301012 LiPo cell", 3.00, "#f9e79f", "3 × 10 × 12, flat under the board, tabs toward +y, pigtail up to J1"),
    ("cell-pocket slack", CELL_POCKET_SLACK, "#fdf6d8", "CAD pocket 3.4 deep for the 3.0 cell"),
    ("clearance cell → bottom parts", 0.35, "#ffffff", "foam/Kapton on the cell"),
    ("bottom-side parts", BOTTOM_MAX_HEIGHT, "#d5f5e3", "VSSOP-10 / SOT-23 ≤ 1.15; mic 0.98; MAX98357A TQFN 0.8; wires in the floor groove below"),
    ("PCB FR-4 2-layer", BOARD["thickness"], "#2ecc71", "0.6 mm, ENIG"),
    ("top-side parts", TOP_MAX_HEIGHT, "#dfe9f3", f"module 2.4; mated u.FL ≈ 2.9; FPC1 2.0; C3 1.8; Pico-EZmate headers {CONN['mated_height']} mated"),
    ("clearance → lid", LID_CLEARANCE, "#ffffff", f"touch contact on TPAD1 bridges parts + gap ({TOUCH_CONTACT['compressed_height']}) to the lid foil"),
    ("lid (resin)", LID_T, "#e5e8e8", "LED window 1.0–1.5 thin; mic hole Ø0.8; touch dimple leaves 0.8 over the foil"),
]
N_STACK_UNDER_BOARD = 5   # rows of STACK below the PCB
Z_BOARD_BOTTOM = round(sum(t for _, t, _, _ in STACK[:N_STACK_UNDER_BOARD]), 2)     # 6.10 above the skin
Z_BOARD_TOP = round(Z_BOARD_BOTTOM + BOARD["thickness"], 2)                            # 6.70
# Camera pod. The enclosure (hardware/cad/mcring_stage1.py) reads floor_relief / head_clear / fpc_fold from board_params.json
# (pod_mm.floor_relief_above_skin, head_clearance, fpc_fold_above_head) and builds the pod as: floor = band wall on top of
# the bore relief, head standing on the floor + head_clear, ceiling = head top + fpc_fold, roof = ceiling + wall.
POD = dict(fpc_loop=2.5, head_thick=1.3, barrel_len=4.5, barrel_d=4.5, head_sq=8.5, wall=1.2,
           floor_relief=0.5,    # the finger bore is opened by 0.5 under the signet so only the band touches the skin
           head_clear=0.3,      # OV2640 head -> pod floor / side walls
           fpc_fold=1.0)        # room above the head for the 180° fold of the camera FPC
ANT_CAVITY_DEPTH = 2.0    # bay interior extends this far behind the board's back edge (u.FL pigtail turn + flex antenna)

# ----------------------------------------------------------------------------------------------
# 6b. Optional speaker — OFF-BOARD, for the CAD (hardware/cad/mcring_stage1.py must read this)
# ----------------------------------------------------------------------------------------------
# Where a Ø10 x 2.9 mm micro speaker can live, given the enclosure as built (hardware/cad/mcring_stage1.py):
#   * inside the bay: no — the sub-board space is 1.5 mm tall, the lid gap 0.3.
#   * "signet_back": no — the 2 mm antenna cavity and the flex antenna (>= 5 mm metal keep-out) are there.
#   * "band_side": no — the band wall is 1.2 mm with the finger behind it; a disc on the band's side would sit
#     between the fingers and its leads would have to run outside the band like the charging wires.
#   * "signet_left_wall" (-y, switch side): the switch key (board x 6.3-9.7) and the two charging-pad wire
#     channels (world X -1.5 / -3.5 = board x 14.75 / 16.75, climbing inside the -y shoulder) force the pocket
#     behind board x ~17.7, and a 10.4 mm pocket then ends 0.7 mm from the flex antenna's plane — the amp's
#     NdFeB magnet + steel yoke inside the antenna's 5 mm keep-out. Only a 4.3 mm bump (sealed wall) avoids it.
#   * "signet_right_wall" (+y): nothing on that wall (the mic port, LED and touch dimple are in the lid, the
#     LRA pocket in the floor, both pad-wire ribs on -y). CHOSEN. The pocket is cut into the +y wall with the
#     signet's +y face pushed out 3.15 mm over the pocket's length; the speaker stands vertically (disc in the
#     xz plane), diaphragm/grille facing +y, back toward the bay. Above the sub-board floor the wall behind it is
#     removed over the pocket outline so the bay is the back volume and the two leads go straight into the
#     sub-board cavity and up through the J5 notch to the header on the board top; below the floor the pocket is a
#     recess in the solid slab.
# Coordinates: board frame (x from the front edge, y from the left edge; z from the BOARD TOP, + toward the lid).
# CAD: X = L/2 - x, Y = y - W/2, Z = z_board_top + z.  Speaker centre: board x 18.45, board y W + 2.0 (2.0 mm
# outside the right edge: back face 0.25 outside the bay wall's inner plane), z -3.2 (3.5 above the skin).
SPEAKER_D, SPEAKER_T = 10.0, 2.9
SPEAKER_CX, SPEAKER_CY, SPEAKER_CZ = 18.45, round(W + 2.0, 2), -3.2      # board frame; z from the board top
SPEAKER_POCKET_CLEAR, SPEAKER_GRILLE_WALL = 0.2, 1.0
_J5 = next(c for c in CONNECTORS if c[0] == "J5")
SPEAKER = {
    "part": "PUI Audio AS01008MR-2-R — Ø10 x 2.9 mm max, 8 Ω, 300 mW rated / 500 mW max, 86 dB, top port, NdFeB "
            "magnet, solder-pad terminals (netlist LS1, off-board; alt. any 10 mm 8 Ω micro speaker); its two leads end in a Pico-EZmate plug",
    "diameter": SPEAKER_D,
    "thickness": SPEAKER_T,
    "location": "signet_right_wall",
    "frame": "board: x from the front edge, y from the left (switch) edge, z from the board TOP (+ toward the lid); "
             "CAD X = L/2 - x, Y = y - W/2, Z = z_board_top + z",
    "centre_board_xyz_mm": [SPEAKER_CX, SPEAKER_CY, SPEAKER_CZ],
    "centre_z_above_skin_mm": round(Z_BOARD_TOP + SPEAKER_CZ, 2),
    "axis": "y",
    "grille_normal": "+y",
    "grille_normal_board": [0, 1, 0],
    "disc_plane": "xz (the speaker stands vertically in the right wall)",
    "speaker_extent_board_mm": {
        "x": [round(SPEAKER_CX - SPEAKER_D / 2, 2), round(SPEAKER_CX + SPEAKER_D / 2, 2)],
        "y": [round(SPEAKER_CY - SPEAKER_T / 2, 2), round(SPEAKER_CY + SPEAKER_T / 2, 2)],
        "z_from_board_top": [round(SPEAKER_CZ - SPEAKER_D / 2, 2), round(SPEAKER_CZ + SPEAKER_D / 2, 2)],
    },
    "pocket_clearance": SPEAKER_POCKET_CLEAR,
    "grille_wall": SPEAKER_GRILLE_WALL,
    "grille": "Ø0.8 holes on a 1.2 mm grid inside Ø8 on the +y face, or 3 slots 0.8 x 6; 1.0 mm wall",
    # back clearance 0.25 (behind the bay wall's inner plane) + speaker + front clearance + grille wall, minus the 1.2 wall it replaces
    "signet_right_face_bump_mm": round(0.25 + SPEAKER_T + SPEAKER_POCKET_CLEAR + SPEAKER_GRILLE_WALL - 1.2, 2),
    "pocket_board_x_range": [round(SPEAKER_CX - SPEAKER_D / 2 - SPEAKER_POCKET_CLEAR, 2),
                             round(SPEAKER_CX + SPEAKER_D / 2 + SPEAKER_POCKET_CLEAR, 2)],
    "back_volume": "open into the bay: remove the +y bay wall over the pocket outline above the sub-board floor "
                   "(z_floor 4.6 .. pocket top 8.7 above the skin) so the bay is the back volume and the leads pass "
                   "straight through; below the floor the pocket is a recess in the solid slab. Sealed alternative: "
                   "keep the 1.2 wall with a 3 x 1.5 wire slot + 3 x Ø1.0 vents into the sub-board cavity and move "
                   "the speaker out so its back sits 0.2 outside the old face (bump 4.3 mm)",
    "connector": {"ref": "J5", "top_xy": [_J5[1], CONN_CY], "notch_xy": [_J5[1], W],
                  "note": "Pico-EZmate header on the board TOP in the right strip; the speaker pigtail comes through the wall "
                          "opening into the sub-board cavity and up through the 1.4 x 1.1 edge notch beside J5"},
    "wire_exit": "two 28 AWG pigtail wires from the speaker's back terminals, -y through the wall opening into the "
                 f"sub-board cavity, up the J5 edge notch (board x {_J5[1]}) to the J5 header on the board top (<= 10 mm)",
    "antenna_clearance_note": "speaker back-left corner to the flex antenna: >= 5.3 along x plus the +y offset of the pocket "
                              "— the CAD fit check measures the 3-D gap (keep-out 5.0)",
    "why_not_left_wall": "switch key at board x 6.3-9.7 and the pad-wire channels at board x 14.75/16.75 push a "
                         "10.4 mm pocket behind x 17.7, whose back end is 0.7 mm from the flex antenna plane",
    "why_not_band_side": "1.2 mm band wall with the finger behind it; no lead path except outside the band",
    "mass_g": 1.0,
}


def draw_stackup(path: str) -> None:
    svg = SVG(1420, 760)
    svg.arrow_marker("dim", "#555", 5)
    svg.text(20, 28, "mcring v1 — vertical stack through the signet and camera-pod section", size=20, weight="bold")
    svg.text(20, 50, "All dimensions mm, measured from the finger skin (z = 0). Scale 40 px/mm.", size=12, fill="#444")

    Z = 40.0   # px per mm (vertical)
    x0, base = 120.0, 700.0   # left edge, skin line (picture y)
    bw = 260.0
    total = sum(t for _, t, _, _ in STACK)
    svg.line(x0 - 40, base, x0 + bw + 40, base, stroke="#8e5b3a", sw=3)
    svg.text(x0 - 44, base + 4, "finger skin  z = 0", size=10, anchor="end", fill="#8e5b3a")
    z = 0.0
    for name, t, col, note in STACK:
        y_top = base - Z * (z + t)
        svg.rect(x0, y_top, bw, Z * t, fill=col, stroke="#333", sw=1)
        label = f"{name}  {t:.2f}"
        if Z * t >= 14:
            svg.text(x0 + 8, y_top + Z * t / 2, label, size=10, weight="bold")
        else:
            svg.text(x0 + 8, y_top + Z * t / 2, label, size=8.5, weight="bold")
        z += t
        svg.line(x0 + bw, base - Z * z, x0 + bw + 30, base - Z * z, stroke="#555", sw=0.8)
        svg.text(x0 + bw + 34, base - Z * z, f"z = {z:.2f}", size=10, fill="#222", weight="bold")
        if note:
            svg.text(x0 + bw + 96, base - Z * z, note, size=8.5, fill="#555")
    svg.dim_v(base - Z * total, base, x0 - 30, f"signet height {total:.2f} mm above the skin", size=10)
    band_wall = STACK[0][1]
    svg.text(x0, base - Z * total - 30, f"Signet top = {total:.2f} mm above the skin = {total - band_wall:.2f} mm above the band's outer "
             f"surface ({band_wall:.1f} mm band wall).", size=11, weight="bold", fill="#922b21")
    cell_layers = 3.0 + CELL_POCKET_SLACK
    svg.text(x0, base - Z * total - 14, f"Alternative (cell in the palm-side thick zone, as in the old .scad): remove the cell + pocket "
             f"({cell_layers:.1f}) → {total - cell_layers:.2f} mm.", size=10, fill="#444")

    # ---- camera pod section (side view, cut at y = W/2 through the lens axis) ----
    px0 = 830.0
    Xs = 22.0   # px per mm horizontal for the section
    svg.text(px0, 100, "Camera pod — side section along the finger (board front edge at x = 0)", size=13, weight="bold")
    svg.text(px0, 118, "+x → toward the back (antenna); the pod extends in front of the board (negative x).", size=10, fill="#444")
    z_board_bot = sum(t for _, t, _, _ in STACK[:N_STACK_UNDER_BOARD])   # 6.10
    z_board_top = z_board_bot + BOARD["thickness"]     # 6.70
    z_lid_bot = z_board_top + TOP_MAX_HEIGHT + LID_CLEARANCE   # 9.90
    z_lid_top = z_lid_bot + LID_T                       # 11.10
    assert abs(z_lid_top - total) < 1e-9
    sec_base = 700.0
    sec_x0 = px0 + 225   # picture x of board front edge (board x = 0)

    def SX(xmm): return sec_x0 + Xs * xmm
    def SZ(zmm): return sec_base - Z * zmm

    # skin + band wall (band is only 12 mm wide along the finger; show its extent centred under the board)
    svg.line(SX(-12), SZ(0), SX(13.5), SZ(0), stroke="#8e5b3a", sw=3)
    svg.text(SX(-12), SZ(0) + 14, "finger skin", size=9, fill="#8e5b3a")
    band_c = L / 2
    svg.rect(SX(band_c - 6), SZ(1.2), Xs * 12, Z * 1.2, fill="#e5e8e8", stroke="#333", sw=1)
    svg.text(SX(band_c), SZ(0.6), "band (12 wide along the finger)", size=8.5, anchor="middle")
    # cell under the board
    svg.rect(SX(band_c - 6), SZ(4.2), Xs * 12, Z * 3.0, fill="#f9e79f", stroke="#333", sw=1)
    svg.text(SX(band_c), SZ(2.7), "cell 3.0 (12 long)", size=9, anchor="middle")
    # board
    svg.rect(SX(0), SZ(z_board_top), Xs * 13.5, Z * BOARD["thickness"], fill="#2ecc71", stroke="#333", sw=1)
    svg.text(SX(7.5), SZ(z_board_top) - 4, "PCB 0.6 (26.5 long, cut at 13.5)", size=8.5, anchor="middle")
    # FPC1 on top at x 0.5..4.5
    svg.rect(SX(0.5), SZ(z_board_top + 2.0), Xs * 4.0, Z * 2.0, fill="#f6e3c5", stroke="#7e5109", sw=1)
    svg.text(SX(2.5), SZ(z_board_top + 1.0), "FPC1", size=9, anchor="middle", fill="#7e5109")
    # module top at x ≥ 11.1
    svg.rect(SX(MODULE_X0), SZ(z_board_top + 2.4), Xs * (13.5 - MODULE_X0), Z * 2.4, fill="#dfe9f3", stroke="#2c3e50", sw=1)
    svg.text(SX(12.3), SZ(z_board_top + 1.2), "U1 2.4", size=9, anchor="middle", fill="#2c3e50")
    # bottom parts band
    svg.rect(SX(0.5), SZ(z_board_bot), Xs * 13.0, Z * BOTTOM_MAX_HEIGHT, fill="#d5f5e3", stroke="#1e8449", sw=0.8, dash="3 2")
    svg.text(SX(7.5), SZ(z_board_bot - BOTTOM_MAX_HEIGHT / 2), f"bottom parts ≤ {BOTTOM_MAX_HEIGHT}", size=8.5, anchor="middle", fill="#1e8449")
    # lid over the bay
    svg.rect(SX(-0.5), SZ(z_lid_top), Xs * 14.0, Z * 1.2, fill="#e5e8e8", stroke="#333", sw=1)
    svg.text(SX(7.0), SZ(z_lid_top - 0.6), f"lid 1.2 (underside z = {z_lid_bot:.2f})", size=9, anchor="middle")

    # camera head: vertical plate in front of the board, optical axis along -x; it stands on the pod floor
    band_wall = STACK[0][1]
    pod_floor_z = POD["floor_relief"] + band_wall       # 1.70
    hz0 = pod_floor_z + POD["head_clear"]               # 2.00
    hz1 = hz0 + POD["head_sq"]                          # 10.50
    lens_z = hz0 + POD["head_sq"] / 2                   # 6.25
    head_x1 = -POD["fpc_loop"]                      # back face of the head
    head_x0 = head_x1 - POD["head_thick"]           # front face (barrel base)
    barrel_x0 = head_x0 - POD["barrel_len"]         # barrel front
    svg.rect(SX(head_x0), SZ(hz1), Xs * POD["head_thick"], Z * POD["head_sq"], fill="#34495e", stroke="#111", sw=1)
    svg.rect(SX(barrel_x0), SZ(lens_z + POD["barrel_d"] / 2), Xs * POD["barrel_len"], Z * POD["barrel_d"], fill="#2c3e50", stroke="#111", sw=1)
    svg.text(SX(barrel_x0 + POD["barrel_len"] / 2), SZ(lens_z), "lens Ø4.5", size=9, anchor="middle", fill="#fff")
    svg.text(SX(head_x0 + POD["head_thick"] / 2), SZ(hz1) - 6, "OV2640 head 8.5 × 8.5 × 1.3 (+4.5 barrel)", size=8.5, anchor="middle", fill="#111")
    svg.text(SX(head_x1 + 0.2), SZ(hz0 + 1.2), "cell is only under the bay, not under the pod", size=8, fill="#555")
    # FPC loop: from the head's back face to the connector mouth at the board front edge
    svg.path(f"M {SX(head_x1):.1f} {SZ(lens_z + 3):.1f} C {SX(head_x1 + 1.2):.1f} {SZ(lens_z + 3):.1f}, "
             f"{SX(-0.6):.1f} {SZ(z_board_top + 0.9):.1f}, {SX(0.6):.1f} {SZ(z_board_top + 0.6):.1f}",
             stroke="#e67e22", sw=3)
    svg.text(SX(head_x1 + 0.3), SZ(lens_z + 3.8), "24-pin FPC (exits the head sideways, loops back)", size=8, fill="#e67e22")
    # lens axis
    svg.line(SX(barrel_x0 - 2.5), SZ(lens_z), SX(1.0), SZ(lens_z), stroke="#c0392b", sw=0.8, dash="6 3")
    svg.text(SX(barrel_x0 - POD["wall"]) - 48, SZ(lens_z) - 8, f"lens axis z = {lens_z:.2f}", size=9, fill="#c0392b", anchor="end")
    # pod walls (as the CAD builds them): floor = band wall on the bore relief, ceiling = head top + FPC fold, roof above the lid
    pod_front = barrel_x0                       # barrel front flush with the pod face
    roof_bot = hz1 + POD["fpc_fold"]            # pod ceiling 11.50
    roof_top = roof_bot + POD["wall"]           # 12.70 — the roof lips back over the lid's front edge
    svg.rect(SX(pod_front - POD["wall"]), SZ(roof_top), Xs * POD["wall"], Z * (roof_top - POD["floor_relief"]), fill="#e5e8e8", stroke="#333", sw=1)   # front wall
    svg.rect(SX(pod_front - POD["wall"]), SZ(roof_top), Xs * (-(pod_front - POD["wall"]) + 1.0), Z * POD["wall"], fill="#e5e8e8", stroke="#333", sw=1)  # roof (+ lip over the lid edge)
    svg.rect(SX(pod_front - POD["wall"]), SZ(pod_floor_z), Xs * (-(pod_front - POD["wall"]) + band_c - 6), Z * band_wall, fill="#e5e8e8", stroke="#333", sw=1)  # floor
    svg.text(SX(pod_front + 0.3), SZ(pod_floor_z) + 10, f"pod floor z {pod_floor_z:.2f} (bore relief {POD['floor_relief']} + wall)", size=8, fill="#555")
    # lens bore through the front wall
    svg.rect(SX(pod_front - POD["wall"]), SZ(lens_z + BORE_D / 2), Xs * POD["wall"], Z * BORE_D, fill="#fff", stroke="#333", sw=0.6)
    svg.text(SX(pod_front - POD["wall"]) - 4, SZ(lens_z + 3.2), f"bore Ø{BORE_D}", size=8.5, anchor="end")
    # dimensions
    svg.dim_h(SX(pod_front - POD["wall"]), SX(0), SZ(roof_top) - 14, f"pod depth {-(pod_front - POD['wall']):.1f} in front of the board edge", size=9)
    svg.dim_v(SZ(roof_top), SZ(0), SX(pod_front - POD["wall"]) - 30, f"pod height {roof_top:.1f}", size=9)
    svg.text(px0, 140, f"Lens axis z = {lens_z:.2f}; head spans z {hz0:.2f}–{hz1:.2f} ({POD['head_clear']} above the pod floor); pod ceiling "
             f"{roof_bot:.2f} (= head top + {POD['fpc_fold']} FPC fold), roof top {roof_top:.2f} ({roof_top - z_lid_top:+.2f} vs the bay lid).", size=10, fill="#444")
    svg.text(px0, 156, f"Pod interior: {-(pod_front):.1f} deep × ≥ 9.2 wide (head 8.5 + 0.35 per side) — head is centred on y = {W/2:.1f} (the finger axis).", size=10, fill="#444")
    svg.save(path, png_scale=2.0)
    return dict(z_board_bottom=z_board_bot, z_board_top=z_board_top, z_lid_bottom=z_lid_bot, z_lid_top=z_lid_top,
                signet_height=total, lens_axis_z=lens_z, head_z=[hz0, hz1], pod_floor_z=pod_floor_z, pod_ceiling_z=roof_bot,
                pod_roof_top=roof_top, pod_depth_from_board_edge=-(pod_front - POD["wall"]), pod_interior_depth=-pod_front)


# ----------------------------------------------------------------------------------------------
# 7. Outputs: board_params.json + floorplan.md
# ----------------------------------------------------------------------------------------------
def connectors_json() -> dict:
    out = {}
    for ref, cx, short, feeds, nets in CONNECTORS:
        out[ref] = {
            "short": short, "cx": cx, "cy": CONN_CY, "w": CONN["w"], "h": CONN["h"],
            "side": "top", "mated_height": CONN["mated_height"], "pitch": CONN["pitch"],
            "mpn": CONN["mpn"], "manufacturer": CONN["manufacturer"], "housing": CONN["housing"], "cable": CONN["cable"],
            "alt_mpn": CONN["alt_mpn"], "feeds": feeds, "nets": nets,
            "wire_exit": "+y (toward the right board edge)",
            "notch": {"edge": "right", "cx": cx, "w": NOTCH["w"], "d": NOTCH["d"],
                      "y0": round(W - NOTCH["d"], 2), "y1": W},
            # envelope of the mated plug + wire bend over the notch, for the CAD placeholder: from the header's +y end
            # to 0.25 mm beyond the board edge (inside the 0.3 mm bay clearance), 1.55 tall
            "plug_mm": {"x0": round(cx - 1.3, 2), "x1": round(cx + 1.3, 2), "y0": round(CONN_CY + CONN["h"] / 2, 2),
                        "y1": round(W + 0.25, 2), "height": CONN["mated_height"]},
        }
    return out


def write_params(stack_info: dict) -> dict:
    sw = next(p for p in PARTS if p.ref == "SW1")
    gap = front_ledge_gap()
    params = {
        "board_length_mm": L,
        "board_width_mm": W,
        "board_thickness_mm": BOARD["thickness"],
        "corner_radius_mm": BOARD["corner_r"],
        "top_max_height_mm": TOP_MAX_HEIGHT,
        "bottom_max_height_mm": BOTTOM_MAX_HEIGHT,
        "camera_connector_edge": "front",
        "antenna_edge": "back",
        "switch_edge": "left",
        "switch_offset_mm": SWITCH_OFFSET,
        "led_xy_mm": [LED_XY[0], LED_XY[1]],
        "mic_xy_mm": [MIC_XY[0], MIC_XY[1]],
        "module_xy_mm": [round(MODULE_CX, 2), round(MODULE_CY, 2)],
        "touchpad_xy_mm": [TPAD["cx"], TPAD["cy"]],
        "notes": (
            "Coordinates from the board's FRONT-LEFT corner seen from the top: x along the finger (0 = front/camera "
            "edge, board_length = back/antenna edge), y across the finger (0 = left edge where the switch is). "
            "Design-for-assembly board: 22.8 wide (18.0 + a 4.8 mm TOP-side connector strip on the RIGHT). "
            "Module ESP32-S3-MINI-1U 15.4x15.4x2.4 at module_xy (1.3 mm from the LEFT edge, not centred) with its "
            "u.FL end flush with the back edge; the u.FL pigtail leaves over the back edge and runs down the inside "
            "of the bay's back wall to the flex antenna, which stays >= antenna_keepout_beyond_edge_mm (5) from the "
            "cell, the LRA and any other metal. top_max_height is the mated u.FL plug (2.9), the module shield is 2.4, "
            "the four Pico-EZmate headers (connectors_top_mm) are 1.55 mated; the lid may be lower over the front "
            "strip (x < 11.1: tallest part there is FPC1 at 2.0). Bottom parts max 1.15 (SOT-23/VSSOP) - allow "
            ">= 0.35 clearance to the cell. Mic MK1 is a bottom-port part mounted on the BOTTOM side at mic_xy; its "
            "0.6 mm port goes through the board, so the lid needs a ~0.8 mm hole straight above mic_xy. LED D1 is on "
            "top at led_xy under a 1.0-1.5 mm thinned window (~3 mm). Switch SW1 body 3.0x2.5x1.2 on the top side, "
            "plunger pointing out of the left edge at x = switch_offset; wall slot switch_slot_mm (3.4 x 1.6) centred "
            "z = board_top+0.6. Touch (touch_mm): the electrode is a 4x5 copper-foil pad on the LID UNDERSIDE at "
            "touchpad_xy under the 0.8 mm dimple; TPAD1 on the board is the landing for a conductive-foam / spring "
            "contact that the lid compresses from 3.6 to 3.2 mm (= top_parts + lid_clearance). The 8 test pads "
            "(test_pads_top_mm) are on the TOP side so the board can be flashed and probed while seated in the bay. "
            "FPC connector FPC1 (Hirose FH12 flip-lock ZIF, bottom contact) on top at x 0.5-4.5, centred on the "
            "finger axis y = W/2; the camera head sits in a pod in front of the board (see stackup.svg / pod_mm). "
            "PLUG-IN PARTS: the cell (J1), the charging-pad pigtail (J3), the LRA (J4) and the optional speaker (J5) "
            "plug into 2-pin Molex Pico-EZmate headers on the TOP in the right strip (y 17.2-21.7); each header has a "
            "1.4 x 1.1 wire notch in the RIGHT board edge beside it (edge_notches_mm) through which the pigtail drops "
            "into the sub-board cavity. The cell lies with its tabs toward +y (cell_tab_edge) so its lead channel runs "
            "from the pocket's +y edge to the wall under J1. The charging wires come up from the two Ø1.1 channels "
            "beside the -y wall and run in a 1.2 x 0.8 groove cut into the sub-board FLOOR (floor_wire_groove_mm) "
            "forward, across the board between the cell and LRA pockets and along the +y edge to the J3 notch. "
            "Only the piezo pads BZ1a/b (optional, DNP) and the aux pads J2a/b (bench experiment) remain bare pads on "
            "the bottom (wire_pads_bottom_mm). The optional 10 mm speaker (speaker_mm) is OFF-BOARD in a pocket in "
            "the signet's RIGHT (+y) wall, grille facing +y, its pigtail entering the sub-board cavity through that "
            "wall and rising through the J5 notch; the amp (U10) and its load switch (U11) are bottom-side parts in "
            "the back-left block. stack_mm and pod_mm carry the enclosure's as-built numbers (cell pocket 3.4 deep, "
            "lid top 11.1, pod roof flush with the lid, bore 4.6)."
        ),
        # ---- extras for the CAD step ----
        "switch_xy_mm": [sw.cx, sw.cy],
        "switch_body_mm": [sw.w, sw.h, sw.height],
        "module_size_mm": [MODULE["w"], MODULE["h"], MODULE["height"]],
        "module_front_edge_x_mm": round(MODULE_X0, 2),
        "module_edge_gap_right_mm": CONN_GAP_MODULE,
        "ufl_mated_height_mm": UFL_MATED_HEIGHT,
        "ufl_xy_mm": [round(L - 0.2, 2), round((3.2 + 5.7) / 2, 2)],
        "front_strip_max_height_mm": 2.0,
        "ufl_end_strip_mm": round(L - UFL_END_X0, 2),
        "ufl_end_rule": "no copper keep-out (MINI-1U has no PCB antenna): module GND/3V3/EN pads + GND pour; no DVP/XCLK/PCLK/PDM traces, no part other than U1; pigtail exits over the back edge",
        "antenna_keepout_beyond_edge_mm": ANT_CLEARANCE_MM,
        "antenna_rule": "flex antenna + pigtail >= 5 mm from the cell, the LRA and any other metal; down the inside of the back wall, then along the band",
        "switch_slot_mm": [SWITCH_SLOT[0], SWITCH_SLOT[1]],
        "fpc_connector_mm": {"x0": 0.5, "x1": 4.5, "y0": round(FPC_CY - FPC_W / 2, 2), "y1": round(FPC_CY + FPC_W / 2, 2),
                             "height": 2.0, "pin1_y": round(fpc_pin_y(1), 2),
                             "part": "Hirose FH12-24S-0.5SH(55), 0.5 mm, 24 pos, bottom contact, flip-lock ZIF, 2.0 mm (LCSC C202112); alt. Amphenol FCI F32R-1A7H1-11024 slider ZIF"},
        "led_window_d_mm": 3.0,
        "mic_hole_d_mm": 0.8,
        "mic_port_board_hole_d_mm": MIC_HOLE_D,
        "touchpad_size_mm": [TPAD["w"], TPAD["h"]],
        "touch_mm": {
            "landing_xy": [TPAD["cx"], TPAD["cy"]], "landing_size": [TPAD["w"], TPAD["h"]],
            "contact": "conductive-foam block (or SMT spring finger) on TPAD1, free height 3.6, compressed to top_parts + lid_clearance",
            "contact_free_height": TOUCH_CONTACT["free_height"], "contact_compressed_height": TOUCH_CONTACT["compressed_height"],
            "lid_electrode_size": [LID_ELECTRODE["w"], LID_ELECTRODE["h"]], "lid_electrode_xy": [TPAD["cx"], TPAD["cy"]],
            "lid_electrode": LID_ELECTRODE["foil"] + " stuck to the lid UNDERSIDE, centred on touchpad_xy",
            "dielectric_over_electrode_max": LID_ELECTRODE["dielectric"],
            "dielectric_note": "lid 1.2 minus the 0.4 touch dimple = 0.8 mm resin between the foil and the finger",
        },
        "stack_mm": {
            "band_wall": 1.2, "cell": 3.0, "cell_pocket_slack": CELL_POCKET_SLACK, "cell_pocket_depth": round(3.0 + CELL_POCKET_SLACK, 2),
            "cell_clearance": 0.35, "bottom_parts": BOTTOM_MAX_HEIGHT,
            "pcb": BOARD["thickness"], "top_parts": TOP_MAX_HEIGHT, "lid_clearance": LID_CLEARANCE, "lid": LID_T,
            "z_board_bottom": round(stack_info["z_board_bottom"], 2), "z_board_top": round(stack_info["z_board_top"], 2),
            "z_lid_bottom": round(stack_info["z_lid_bottom"], 2), "z_lid_top": round(stack_info["z_lid_top"], 2),
            "signet_height_above_skin": round(stack_info["signet_height"], 2),
            "signet_height_above_skin_cell_in_band": round(stack_info["signet_height"] - 3.0 - CELL_POCKET_SLACK, 2),
        },
        "pod_mm": {
            "lens_axis_z": round(stack_info["lens_axis_z"], 2), "lens_barrel_d": POD["barrel_d"], "bore_d": BORE_D,
            "head_square": POD["head_sq"], "head_thickness": POD["head_thick"], "barrel_length": POD["barrel_len"],
            "fpc_loop": POD["fpc_loop"], "wall": POD["wall"],
            "floor_relief_above_skin": POD["floor_relief"], "head_clearance": POD["head_clear"], "fpc_fold_above_head": POD["fpc_fold"],
            "interior_depth_from_board_edge": round(stack_info["pod_interior_depth"], 2),
            "depth_from_board_edge_incl_wall": round(stack_info["pod_depth_from_board_edge"], 2),
            "interior_width": 9.2,
            "floor_z": round(stack_info["pod_floor_z"], 2), "head_z": [round(v, 2) for v in stack_info["head_z"]],
            "ceiling_z": round(stack_info["pod_ceiling_z"], 2), "roof_top_z": round(stack_info["pod_roof_top"], 2),
            "roof_above_lid": round(stack_info["pod_roof_top"] - stack_info["z_lid_top"], 2),
        },
        "antenna_cavity_mm": {
            "depth_behind_board_edge": ANT_CAVITY_DEPTH,
            "note": "bay interior extends behind the board's back edge for the u.FL pigtail turn and the flex antenna glued to the back wall",
        },
        "speaker_mm": SPEAKER,
        # ---- design-for-assembly: plug-in connectors, notches, wire paths ----
        "connectors_top_mm": connectors_json(),
        "edge_notches_mm": NOTCHES,
        "wire_od_max_mm": WIRE_OD_MAX,
        "cell_tab_edge": "+y",
        "cell_lead_channel_mm": {"at_board_x": next(c[1] for c in CONNECTORS if c[0] == "J1"), "width": 3.0, "depth": 0.8,
                                 "note": "from the cell pocket's +y edge to the bay wall under the J1 header, cut into the floor"},
        "floor_wire_groove_mm": FLOOR_GROOVE,
        "channel_exits_board_xy_mm": CHANNEL_EXITS,
        "pad_wire_channel_d_mm": round(2 * 0.55, 2),
        "front_ledge_gap_y_mm": [gap[0], gap[1]],
        "wire_pads_bottom_mm": {p.ref: [p.cx, p.cy] for p in PARTS if p.kind == "pad"},
        "test_pads_top_mm": {p.label: [p.cx, p.cy] for p in PARTS if p.kind == "tp"},
        "parts": [asdict(p) for p in PARTS],
    }
    with open(os.path.join(HERE, "board_params.json"), "w", encoding="utf-8") as f:
        json.dump(params, f, indent=2, ensure_ascii=False)
    return params


def write_md(params: dict, check_msgs: list[str]) -> None:
    def table(side):
        rows = ["| Ref | Part | Centre x, y (mm) | w × h (mm) | Height | Note |", "|---|---|---|---|---|---|"]
        for p in PARTS:
            if p.side == side:
                rows.append(f"| {p.ref} | {p.name} | {p.cx:.2f}, {p.cy:.2f} | {p.w} × {p.h} | {p.height} | {p.note} |")
        return "\n".join(rows)

    fpc_rows = ["| Pin | Signal | Net / GPIO | y on board (mm) |", "|---|---|---|---|"]
    for n, sig in enumerate(FPC_PINS, 1):
        g = FPC_GPIO.get(sig, "")
        if sig.startswith("AVDD"): g = "CAM_2V8 (U3)"
        elif sig.startswith("DVDD"): g = "CAM_1V2 (U4, DNP if internal)"
        elif sig.startswith("DOVDD"): g = "CAM_3V3 (U2)"
        elif sig == "RESET": g = "R16/C14 RC to CAM_3V3"
        elif sig == "PWDN": g = "GND"
        elif sig in ("AGND", "DGND"): g = "GND"
        fpc_rows.append(f"| {n} | {sig} | {g} | {fpc_pin_y(n):.2f} |")

    conn_rows = ["| Ref | Plugs in | Nets | Header centre x, y | Notch (right edge) | Wire path |", "|---|---|---|---|---|---|"]
    paths = {
        "J4": "LRA pigtail from the floor pocket under the front-right of the board, +y under the board edge, up the notch",
        "J3": f"charging pigtail from the two channel exits (board x {CHANNEL_EXITS[0][0]} / {CHANNEL_EXITS[1][0]}, y {CHANNEL_EXITS[0][1]}) in the {FLOOR_GROOVE['width']} × {FLOOR_GROOVE['depth']} floor groove: along the −y edge, across at x {FLOOR_GROOVE['path'][1][0]}, along the +y edge to the notch",
        "J1": "cell pigtail: tabs toward +y, through the 3 × 0.8 lead channel from the pocket's +y edge to the wall, up the notch",
        "J5": "speaker pigtail through the right-wall opening (above the floor) into the cavity, up the notch",
    }
    for ref, cx, short, feeds, nets in CONNECTORS:
        conn_rows.append(f"| {ref} ({short}) | {feeds} | {nets} | {cx:.2f}, {CONN_CY:.2f} | {NOTCH['w']} × {NOTCH['d']} at x = {cx:.2f} | {paths[ref]} |")

    st = params["stack_mm"]; pod = params["pod_mm"]; tm = params["touch_mm"]
    n0402 = sum(1 for p in PARTS if p.side == "bottom" and p.name == "0402")
    n0603 = sum(1 for p in PARTS if p.side == "bottom" and p.name == "0603")
    n_tp = sum(1 for p in PARTS if p.kind == "tp")
    n_placed = sum(1 for p in PARTS if p.kind not in ("pad", "tp", "copper"))
    tp_list = ", ".join(f"{p.ref} {p.label}" for p in sorted((q for q in PARTS if q.kind == "tp"), key=lambda q: q.ref))
    gap = params["front_ledge_gap_y_mm"]
    md = f"""# mcring v1 — stage-1 PCB floorplan

Generated by `floorplan.py` (pure Python → SVG/PNG, no CAD). Drawings: `out/floorplan_top.*`,
`out/floorplan_bottom.*`, `out/stackup.*`. Numbers for the enclosure: `board_params.json`. Pick-and-place and
JLCPCB-format BOM for the assembler: `python3 export_cpl.py` → `out/mcring_v1_cpl.csv`, `out/mcring_v1_bom_jlc.csv`.
Reference designators and nets follow `hardware/electrical/out/mcring_v1_nets.md`.

**Design for assembly (no soldering by the owner).** The board is ordered assembled (double-sided PCBA,
`docs/10-ordering-assembled-boards.md`); every off-board part — cell, charging-pad pigtail, LRA, speaker — **plugs
into a 2-pin Molex Pico-EZmate header on the TOP** of a 4.8 mm strip added on the right (+y) side, and the camera
flex goes into a flip-lock ZIF (Hirose FH12). The assembled board has {n_placed} placed parts and no wire pads except
the two optional bare pairs BZ1 (piezo, DNP) and J2 (aux experiment).

## 1. Board

| Item | Value |
|---|---|
| Outline | **{L} × {W} mm**, rounded corners r = {BOARD['corner_r']} mm, 2-layer FR-4 **0.6 mm**, ENIG; four **{NOTCH['w']} × {NOTCH['d']} mm wire notches** in the right edge at x = {', '.join(f'{c[1]:.2f}' for c in CONNECTORS)} |
| Orientation | x along the finger: **front edge = camera / FPC** (x = 0), **back edge = antenna / u.FL** (x = {L}); y across the finger: **left edge = switch** (y = 0), **right edge = connector notches** (y = {W}) |
| Module | ESP32-S3-MINI-1U 15.4 × 15.4 × 2.4, centre ({params['module_xy_mm'][0]}, {params['module_xy_mm'][1]}) — 1.3 mm from the left edge, **not** centred: the 4.8 mm to its right is the connector strip; u.FL end **flush with the back edge** (pin positions along the three rows: **verify against the Espressif footprint**) |
| Camera axis | FPC1 centred on y = W/2 = {FPC_CY} (the finger / pod axis); pin 1 at y = {fpc_pin_y(1):.2f} |
| Top side | U1 module, FPC1 (24-pin 0.5 mm bottom-contact flip-lock ZIF), SW1 side switch, D1 WS2812B-2020 + R7, C3 100 µF 1206, TPAD1 3 × 4 touch landing with hatched GND ring (the touch **electrode** is a copper foil on the lid underside — §2), **4 × Pico-EZmate 78171-0002 headers** J4 LRA / J3 CHG / J1 BAT / J5 SPK (§2b), **{n_tp} test pads** ({tp_list}) |
| Bottom side (≤ {BOTTOM_MAX_HEIGHT} mm) | everything else: U2–U11 (U10 MAX98357A + U11 its TPS22916 gate = the optional speaker amp), L1, D2, D3, Q1, MK1 mic (bottom-port, port through the board), {n0402} × 0402, {n0603} × 0603, bare pads BZ1a/b (piezo, optional) and J2a/b (aux) |
| Tallest top part | mated u.FL plug on the module ≈ {UFL_MATED_HEIGHT} mm (module shield 2.4; connectors {CONN['mated_height']} mated; front strip x < {MODULE_X0:.1f}: FPC1 2.0) |
| Why {L} long | {MODULE_X0:.1f} mm front strip (FPC1 4.0 + 1.0 actuator clearance + 5.6 for SW1/TPAD1/D1/C3/mic port) + 15.4 module |
| Why {W} wide | 18.0 (module 15.4 + 1.3 + 1.3 edges; FPC1 16 + 2 × 1.0) **+ 4.8 connector strip**: 0.5 module→header gap + 4.5 header depth + {NOTCH['d']} notch/edge clearance. Cost: the signet grows 4.8 mm across the finger (`hardware/cad/fit_report.md`) |

## 2. Placement — top side

{table('top')}

**Touch electrode on the lid, not on the board.** The lid underside is {st['top_parts']} + {st['lid_clearance']} = {tm['contact_compressed_height']} mm
above the board, so a bare copper pad on the board would sit 4 mm (air + 0.8 resin) behind the touch surface — a
12 mm² electrode that far behind the dielectric has negligible finger coupling and `trigger.cpp`'s +25 % threshold
would never fire. Instead: a {tm['lid_electrode_size'][0]:.0f} × {tm['lid_electrode_size'][1]:.0f} mm copper-foil pad ({LID_ELECTRODE['foil']}) is stuck to the
**lid underside** centred on ({TPAD['cx']}, {TPAD['cy']}), under the CAD's 4 × 5 × 0.4 touch dimple, which leaves {tm['dielectric_over_electrode_max']} mm of resin
between the foil and the thumb. TPAD1 on the board is the 3 × 4 copper landing for a compliant conductor — a conductive-foam
block 3 × 4 × {tm['contact_free_height']} mm (or an SMT spring finger of similar free height) that the lid compresses to {tm['contact_compressed_height']} mm — so the
electrode is wired to IO8 through R13 without any flying lead. Guard ring: hatched top copper {TPAD['ring']} mm wide, {TPAD['gap']} mm
from the landing, no copper under it on the bottom layer. LED window Ø3 in the lid above D1 ({LED_XY[0]}, {LED_XY[1]}). Mic port hole
Ø{MIC_HOLE_D} through the board at ({MIC_XY[0]}, {MIC_XY[1]}) with an Ø0.8 lid hole above it (nothing else on the top side within 0.9 mm; the
mic moved 0.55 toward −y so the lid's Ø1.8 tube clears the J4 header).

**Test pads on the top side.** TP1–TP6 (IO0, GND, D−, D+, EN, 3V3) form a column at x = {TP_COL_X}, 0.45 mm in front of the
module's front row, 1.5 mm pitch; TP8 (VBAT) and TP7 (nCHG) sit at x = {TP_FRONT_X} beside FPC1 (0 mm tall, so the actuator swing
zone is fine). All eight are reachable with the board seated on its ledges and the lid off — flashing over USB, holding IO0,
pulsing EN, bench-powering from VBAT/GND and the cradle/nCHG check never need the board lifted.

### 2b. Plug-in connectors (right strip, y {CONN_Y0:.1f}–{CONN_Y0 + CONN['h']:.1f})

Four **Molex Pico-EZmate 78171-0002** (1.20 mm pitch, 2 circuits, vertical SMT header, side friction locks, **{CONN['mated_height']} mm
mated**; mating housing {CONN['housing']}, pre-made cable {CONN['cable']}; alternative {CONN['alt_mpn']}). Header outline
{CONN['w']} along the pin row × {CONN['h']} in the plug/wire direction (from the published 3-circuit 5.4 × 4.5 — **verify against the Molex
drawing**, including which end the plug's wires leave: they must point at the notch). The headers sit {CONN_GAP_MODULE} mm beyond the
module's right row (fan the module's side pads out under the module and via down) and {NOTCH['d']} mm from the right edge; each has a
{NOTCH['w']} × {NOTCH['d']} **notch in the board edge** straight ahead of it (no copper within 0.3 mm), so the pigtail's two wires run ≈ 1 mm over the
board side by side, bend down through the notch (notch + 0.3 bay clearance = 1.4 mm of room for a Ø1.0 28 AWG wire) and reach the part
under the board. Plug / unplug with the board seated and the lid off; the plugs are below the module's shield (2.4 mm).

{chr(10).join(conn_rows)}

The two remaining bare pad pairs are **BZ1a/b** (piezo PZ1 — optional, DNP, no pocket in the enclosure) and **J2a/b** (aux
VBAT + open drain, the air-puff bench experiment). Neither is part of the ring build.

## 3. Placement — bottom side

{table('bottom')}

The charger (U7, D2, D3, C7, C8, R10, R11, R19) sits directly under J3/J1 so the TVS is ≈ 2.3 mm from the J3 via and U7 OUT is beside
the J1 via; the DRV2605L drives J4 through a 10 mm 0.3 mm pair; the amp's OUTP/OUTN pair runs ≈ 15 mm up the back column to J5.

## 4. Keep-outs and zones

| Zone | Layers | Rectangle (x0, y0 – x1, y1) | Rule |
|---|---|---|---|
| u.FL end | both | ({UFL_END_X0:.1f}, 0 – {L}, {W}) | **no copper keep-out** — the MINI-1U has no PCB antenna, and the module's GND 1–2 / 3V3 (3) and GND 43–44 / EN (45) pads are the ends of the two side rows, nearest the u.FL (verify on the footprint), so copper is *required* here: GND pour on both layers, normal fan-out of those pads; no DVP/XCLK/PCLK/PDM traces, no part other than U1. The pigtail leaves the plug over the back edge and runs down the inside of the bay's back wall |
| Antenna (enclosure) | — | — | flex dipole + pigtail **≥ {ANT_CLEARANCE_MM} mm from the cell, the LRA and any other metal**, never under the module or across the DVP corridor; cable ≤ 50 mm |
| Connector strip | top | ({ZONES[5][2][0]}, {ZONES[5][2][1]:.1f} – {UFL_END_X0:.1f}, {W}) | the four headers and their notches; GND pour, vias to the charger/DRV/amp, no signal traces under the notches, nothing within 0.3 mm of a notch on either side (checked) |
| Touch pad | bottom | ({TPAD_NOCOPPER[0]:.1f}, {TPAD_NOCOPPER[1]:.1f} – {TPAD_NOCOPPER[2]:.1f}, {TPAD_NOCOPPER[3]:.1f}) | no copper under TPAD1; R13 just outside it |
| FPC actuator swing | top | ({FPC_ACT_ZONE[0]}, {FPC_ACT_ZONE[1]:.1f} – {FPC_ACT_ZONE[2]}, {FPC_ACT_ZONE[3]:.1f}) | parts ≤ 0.6 mm only (R7 is fine) |
| DVP corridor | bottom | ({DVP_ZONE[0]}, {DVP_ZONE[1]} – {DVP_ZONE[2]:.1f}, {DVP_ZONE[3]}) | Y2–Y9, PCLK, HREF, VSYNC, XCLK only; the upper pins (17–22, y {fpc_pin_y(17):.2f}–{fpc_pin_y(22):.2f}) fan into it between FPC1 and the mic; vias up to U1 in the last 1.5 mm |
| Under the module | top | module footprint | bare FR-4 under the shield (no silkscreen), ≥ 9 GND vias on the thermal pads |
| Back ledge (enclosure) | bottom | (x ≥ {BACK_LEDGE_X0}) | the CAD's back board ledge carries the board here at the sub-board level: no bottom-side part may reach it (checked by the script) |
| Front ledges (enclosure) | bottom | x < 0.7, y < {gap[0]} and y > {gap[1]} | the CAD's two front ledges leave the gap y {gap[0]}–{gap[1]} for the FPC-pin passives at x = 1.0 (`front_ledge_gap_y_mm`) |
| Floor wire groove (enclosure) | — | path {FLOOR_GROOVE['path']} | {FLOOR_GROOVE['width']} × {FLOOR_GROOVE['depth']} groove in the sub-board floor for the charging wires; its cross-board leg at x {FLOOR_GROOVE['path'][1][0]} is the only floor between the LRA pocket (x ≤ 9.65) and the cell pocket (x ≥ 10.85) |
| Speaker pocket (enclosure) | — | right (+y) signet wall, board x {SPEAKER['pocket_board_x_range'][0]}–{SPEAKER['pocket_board_x_range'][1]}, centre {SPEAKER_CY - W:.1f} mm outside the right edge | the Ø{SPEAKER_D} × {SPEAKER_T} speaker LS1 stands vertically in a pocket cut into the +y wall (face pushed out {SPEAKER['signet_right_face_bump_mm']} mm), grille facing +y, back open to the bay; pigtail through the wall to the J5 notch; its magnet stays ≥ 5 mm from the flex antenna — `board_params.json` → `speaker_mm` |

## 5. Layer usage

* **Top**: module footprint + fan-out, FPC1, SW1, D1/R7, C3, touch landing + GND hatch, the 8 test pads, the four
  Pico-EZmate headers (each with a via pair straight down to its bottom-side driver), GND pour. The DVP bus leaves FPC1 on
  the top layer, drops to the bottom corridor, and comes back up at the module's front-left pins.
* **Bottom**: all small ICs and passives, the two bare pad pairs, the DVP corridor, I²C, the power cluster; GND pour
  everywhere else, stitched to the top pour with vias every ≤ 3 mm.
* Design rules per `hardware/electrical/README.md` §5 (0.10/0.10 mm fine, 0.2 mm drill, NSMD DSBGA pads).
* 2 layers is tight: if the DVP + power fan-out does not close, the fallback is a 4-layer 0.6 mm stack
  (sig / GND / PWR / sig) with the same outline — nothing in `board_params.json` changes.

## 6. Route-critical nets

| Net | Rule |
|---|---|
| DVP Y2–Y9, PCLK, HREF, VSYNC, XCLK | corridor on the bottom, ≤ 15 mm, loosely matched (± 5 mm), no other signals in the corridor; XCLK/PCLK away from the antenna end |
| SCCB SIOD/SIOC | pull-ups R5/R6 at the connector, to CAM_3V3 (switched rail) |
| CAM power | 3V3 → U2 → CAM_3V3 → U3 (2.8 V) / U4 (1.2 V) → FPC1 pins 4/10/11; caps C13/C24 within 1 mm of the pins |
| Buck | C1 – U8 – L1 – C2 in a tight loop, SW_NODE minimal area, VOS sense from C2 |
| Charge input | J3 pin 1 (CHG_PAD) → via → D2 TVS (≈ 2.3 mm, clear of the notch) → D3 Schottky → U7 IN with C7; J3 pin 2 straight to the GND pour |
| VBAT | J1 pin 1 → via → C8 / U7 OUT → 0.4 mm trunk (≈ 14 mm) → U8 VIN → R8; J2a |
| I²C | IO5/IO6 → R3/R4 → U5, U6 — one short daisy chain on the right half |
| LRA OUT+/OUT− | 0.3 mm pair, U5 → vias → J4 (≈ 10 mm) |
| VLED / RGB_DATA | U9 → via → D1 (top); IO43 → R7 → D1 DIN |
| PDM CLK/DATA | IO42/IO41 → MK1 on the right-front, ≤ 10 mm |
| USB D−/D+ | IO19/IO20 (module pins 23/24, in the **front row**) → TP3/TP4 directly in front of that row at x = {TP_COL_X}; the stub is the pin-to-pad run, routed as a pair on the top layer, ≤ 10 mm (expect 1–8 mm depending on where pins 23/24 sit along the row — verify on the footprint), nothing else on the nets |
| Touch | IO8 → R13 (1 kΩ) → TPAD1 landing → foam/spring contact → lid foil electrode; keep the trace short and away from the DVP corridor |
| I²S (optional speaker) | IO35/36/37 → R22/R23/R24 (1 kΩ series, the column at x 19.2 beside U10's pin-1/16 corner) → U10 BCLK/LRCLK/DIN (pins 16/14/1), 0.1 mm, 512 kHz / 16 kHz, no matching, no MCLK; the resistors bound the ESD-diode back-feed into the unpowered amp to ≤ 2.6 mA per pin while VAMP is off; AMP_PWR_EN IO34 → U11 ON + R20 |
| VAMP / SPK_P–SPK_N | 3V3 → U11 → C25 (10 µF) + C26 (100 nF, ≤ 1 mm from U10 VDD pins 7/8); OUTP/OUTN as a **0.3 mm pair** up the back column x 22–23.4 to the J5 vias (≈ 15 mm), GND pour both sides, ≥ 1 mm from SDA/SCL, IMU_INT1 and the PDM lines (filterless class D); U10 EP → GND pour with 2–4 vias |

## 7. Camera FPC pin order (assumed ESP32-CAM / Arducam M0031 — verify on the purchased head)

Pin 1 is at the LEFT end of FPC1 (low y); pitch 0.5 mm; contacts face the board (bottom-contact connector).

{chr(10).join(fpc_rows)}

## 8. Stack (see `out/stackup.svg`)

skin → band wall {st['band_wall']} → cell {st['cell']} → cell-pocket slack {st['cell_pocket_slack']} (CAD pocket {st['cell_pocket_depth']} deep) → clearance {st['cell_clearance']} →
bottom parts {st['bottom_parts']} → PCB {st['pcb']} → top parts {st['top_parts']} → clearance {st['lid_clearance']} → lid {st['lid']}:
board bottom at z = {st['z_board_bottom']}, board top z = {st['z_board_top']}, lid underside z = {st['z_lid_bottom']},
**signet top z = {st['signet_height_above_skin']} mm** above the skin ({st['signet_height_above_skin_cell_in_band']} mm if the cell moves to the
palm-side thick zone of the band as in the old `.scad`). These are the enclosure's as-built numbers
(`hardware/cad/fit_report.md`: board bottom 6.10, lid top 11.10). The connectors did not change the stack: the {CONN['mated_height']} mm
mated headers sit on the top under the 3.2 mm lid gap, and the wires run in the floor groove / channels below the parts.

Camera pod (built by the CAD from `pod_mm`): floor z = {pod['floor_z']} (band wall on the {pod['floor_relief_above_skin']} bore relief), head 8.5 × 8.5 × 1.3
+ Ø4.5 × 4.5 barrel standing {pod['head_clearance']} above the floor → head z {pod['head_z'][0]}–{pod['head_z'][1]}, **lens axis z = {pod['lens_axis_z']}**, ceiling z = {pod['ceiling_z']}
(head top + {pod['fpc_fold_above_head']} for the FPC fold), roof top z = {pod['roof_top_z']} ({pod['roof_above_lid']:+.2f} vs the bay lid; the roof lips back over the lid's front
edge). FPC loop {pod['fpc_loop']} mm, interior depth {pod['interior_depth_from_board_edge']} mm in front of the board edge ({pod['depth_from_board_edge_incl_wall']} incl. the 1.2 wall),
interior width ≥ {pod['interior_width']}, bore Ø{pod['bore_d']} (reamed to the 4.5 barrel). Bay interior extends {params['antenna_cavity_mm']['depth_behind_board_edge']} mm behind the
board's back edge for the u.FL pigtail and the flex antenna. Side-switch slot through the left wall {params['switch_slot_mm'][0]} × {params['switch_slot_mm'][1]} mm.

## 9. Deviations from the task text / earlier notes

1. **Mic on the BOTTOM side**, not the top: the TDK T3902 is a bottom-port microphone, so the acoustic path is
   through the board. Mounted on the bottom at `mic_xy`, its port hole goes up through the PCB to a lid hole straight
   above — a top mount would have needed a sound channel under the board. Height 0.98 mm fits the bottom limit.
2. **Cell, charging pads, LRA and speaker on plug-in headers (J1, J3, J4, J5), not wire pads** — see §2b and item 15. The
   vertical JST SH header of the first netlist (4.25 mm) fits neither side; the 1.55 mm Pico-EZmate fits the top.
3. **top_max_height = 2.9 mm**, not 2.4: the mated u.FL plug on the module is taller than the shield can.
4. **bottom_max_height = 1.15 mm** (task: 1.1): VSSOP-10 and SOT-23 bodies are 1.10–1.15 max.
5. **8 test pads** (IO0, EN, USB D−, D+, GND, 3V3, nCHG, VBAT) per the electrical netlist, not 4 — and **on the top side**:
   the bottom face is unreachable once the board sits on its ledges (1.5 mm above the sub-board floor).
6. **SW2 (optional IO0 boot button, DNP) is not placed** — no top-side room; use TP1 (IO0) + TP5 (GND) / TP2 (EN).
7. GPIO use follows the post-fix `BOARD_MCRING_V1` (CAM_PWR = IO21, RGB = IO43, LED_PWR_EN = IO33, USB on 19/20).
8. Board is {L} × {W} instead of the old 26 × 12 bay: the 15.4 mm module and the 16 mm FPC connector set 18.0 of the width,
   the plug-in headers the remaining 4.8 (item 15).
9. **Touch electrode on the lid underside** (copper foil under the dimple) with a compliant contact on TPAD1, instead of a
   bare pad on the board 4 mm behind the touch surface (see §2). `schematic-notes.md`'s "3 × 4 mm copper area on the
   top face" is now the landing; the BOM/build guide need the foam block and the foil.
10. **No antenna copper keep-out on the board**: the earlier "no copper in the last 2 mm" rule was the PCB-antenna rule
    of the MINI-1; the MINI-1U has a u.FL, and its GND/3V3/EN pads sit in exactly that strip. Replaced by the u.FL-end and
    antenna-placement rules in §4.
11. **Stack / pod / bore / slot numbers are computed the way the CAD builds them** (`hardware/cad/mcring_stage1.py`, which
    reads `pod_mm.floor_relief_above_skin / head_clearance / fpc_fold_above_head` and `antenna_cavity_mm` from this JSON):
    cell pocket 3.4 deep (+0.4 slack) → lid top {st['z_lid_top']} not 10.7; pod floor on the 0.5 bore relief, head 0.3 above
    it, 1.0 FPC fold above the head → lens axis {pod['lens_axis_z']} not 5.5, roof {pod['roof_top_z']} ({pod['roof_above_lid']:+.2f} vs the lid) not 11.25;
    bore Ø{pod['bore_d']} not 4.7; switch slot {params['switch_slot_mm'][0]} × {params['switch_slot_mm'][1]} not 3.2 × 1.5. The CAD still hard-codes `cell_pocket`,
    `lens_d`, `lid_t` and `switch_slot` — it should read `stack_mm.cell_pocket_depth`, `pod_mm.bore_d`, `stack_mm.lid` and
    `switch_slot_mm` from this JSON so the two cannot drift again. `hardware/cad/fit_report.md` is the as-built check.
12. **D3** (PMEG2005EB Schottky, CHG_PAD → CHG_IN) is in the charger cluster under J3 (item 15).
13. **Optional speaker amp block** (voice-first, `hardware/electrical/README.md` §1 item 20): U10 MAX98357A 16-TQFN (3 × 3 × 0.8),
    U11 TPS22916, C25 10 µF, C26 100 nF, R20 100 kΩ, R21 100 kΩ (3 dB gain), R22–R24 1 kΩ I²S series (a column at x 19.2 beside
    U10's pin-1/16 corner) in the back-left block under the module (x 18.95–23.4, y 0.4–8.8); the speaker plugs into **J5** on the
    top-right (the SPK1a/b wire pads are gone). The OUTP/OUTN pair runs ≈ 15 mm up the back column — acceptable for a filterless
    class-D output, see §6. Check: nothing on the bottom reaches the CAD's back ledge (x ≥ {BACK_LEDGE_X0}).
14. **Speaker in the signet's RIGHT wall, not the left** (task text offered `signet_left_wall` / `band_side`): on the −y side the
    switch key (x 6.3–9.7) and the two charging-pad wire channels (x 14.75 / 16.75, climbing inside the −y shoulder) push a
    10.4 mm pocket behind x ≈ 17.7, whose back end lands 0.7 mm from the flex antenna's plane — an NdFeB magnet inside the 5 mm
    keep-out. The +y wall has nothing on it (mic port, LED and touch dimple are in the lid, the LRA pocket in the floor, both
    pad-wire ribs on −y). `speaker_mm`: centre board x {SPEAKER_CX}, y {SPEAKER_CY} (2.0 outside the right edge), z {SPEAKER_CZ}
    from the board top ({SPEAKER['centre_z_above_skin_mm']} above the skin); Ø{SPEAKER_D} × {SPEAKER_T}; disc in the xz plane, grille normal +y; pocket
    x {SPEAKER['pocket_board_x_range'][0]}–{SPEAKER['pocket_board_x_range'][1]}, 0.2 clearance, 1.0 grille wall → the signet's +y face grows {SPEAKER['signet_right_face_bump_mm']} mm over that length; back open
    to the bay above the sub-board floor (bay = back volume), recess in the slab below it. "band_side" was rejected: 1.2 mm band
    wall with the finger behind it and no lead path except outside the band.
15. **Design for assembly (this revision).** (a) Board **{W} wide**: a 4.8 mm TOP-side strip on the right carries four Molex
    Pico-EZmate 78171-0002 headers (J4 LRA, J3 CHG, J1 BAT, J5 SPK; 4.2 × 4.5 × {CONN['mated_height']} mated), each with a {NOTCH['w']} × {NOTCH['d']}
    wire notch in the right edge; the module stays 1.3 mm from the left edge (not centred), FPC1 moves to the finger axis
    y = {FPC_CY}. Neither a Pico-EZmate (1.55) nor a JST ACH (1.4) fits the 1.15 mm bottom envelope, and the original top side had
    no 4.5 mm-deep spot, so the board grew rather than the stack (a 0.45 mm taller cavity would also have cost the pod-roof lip).
    (b) The bottom wire pads J1a/b, PAD1w/2w, M1a/b, SPK1a/b are **removed**; BZ1a/b and J2a/b stay as bare pads (optional /
    bench only). (c) The charger cluster moved under J3/J1 (TVS ≈ 2.3 mm from the J3 via); the camera-pin passives follow FPC1
    (+2.4 in y); the mic moved to y {MIC_XY[1]} so the lid tube clears J4; the DVP corridor is ({DVP_ZONE[0]}, {DVP_ZONE[1]} – {DVP_ZONE[2]:.1f}, {DVP_ZONE[3]}).
    (d) Enclosure inputs added to `board_params.json`: `connectors_top_mm` (header + plug envelopes), `edge_notches_mm`,
    `cell_tab_edge` +y with `cell_lead_channel_mm` under J1, `floor_wire_groove_mm` ({FLOOR_GROOVE['width']} × {FLOOR_GROOVE['depth']}, path {FLOOR_GROOVE['path']})
    for the charging wires from the two Ø{params['pad_wire_channel_d_mm']} channel exits, `front_ledge_gap_y_mm` {gap}, `wire_od_max_mm` {WIRE_OD_MAX} (28 AWG pigtails).
16. **FPC1 is the Hirose FH12-24S-0.5SH(55)** (flip-lock ZIF, bottom contact, 2.0 mm, LCSC C202112) — the KiCad land pattern the
    design always used; the Amphenol FCI F32R-1A7H1-11024 (slider ZIF, bottom contact, same pattern) is the alternate. Earlier
    text calling the F32R an "XKB back-flip" was wrong (the F32D is the back-flip/dual-contact sibling).

## 10. Checks performed by the script

{chr(10).join('* ' + m for m in check_msgs) if check_msgs else '* no overlaps, no edge/keep-out/height violations, no bottom part on the back ledge, connectors on top in the right strip, notches clear, floor groove between the pockets'}
"""
    with open(os.path.join(HERE, "floorplan.md"), "w", encoding="utf-8") as f:
        f.write(md)


def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    msgs = run_checks()
    hard = [m for m in msgs if not m.startswith("note:")]
    for m in msgs:
        print(("FAIL " if not m.startswith("note:") else "     ") + m)
    if hard:
        print(f"{len(hard)} placement problem(s) — fix PARTS before drawing")
        return 1
    draw_board("top", "mcring v1 — PCB floorplan, TOP side", os.path.join(OUT, "floorplan_top.svg"))
    draw_board("bottom", "mcring v1 — PCB floorplan, BOTTOM side", os.path.join(OUT, "floorplan_bottom.svg"))
    info = draw_stackup(os.path.join(OUT, "stackup.svg"))
    params = write_params(info)
    write_md(params, msgs if msgs else [])
    print(f"board {L} x {W} x {BOARD['thickness']} mm; {len(PARTS)} placed parts "
          f"({sum(p.side == 'top' for p in PARTS)} top / {sum(p.side == 'bottom' for p in PARTS)} bottom); "
          f"connectors {[c[0] for c in CONNECTORS]} on top at y {CONN_Y0:.1f}-{CONN_Y0 + CONN['h']:.1f}; front ledge gap {front_ledge_gap()}")
    print("wrote", ", ".join(sorted(os.listdir(OUT))), "+ board_params.json, floorplan.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
