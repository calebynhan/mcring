#!/usr/bin/env python3
"""mcring v1 (stage 1) — PCB floorplan generator.

Pure Python. Produces, in out/:
  floorplan_top.svg/.png      to-scale top-side placement (components, keepouts, critical nets)
  floorplan_bottom.svg/.png   to-scale bottom-side placement (seen from below, mirrored)
  stackup.svg/.png            vertical stack through the signet + camera-pod section
and, next to this script:
  board_params.json           the numbers the enclosure (CAD) step is generated from
  floorplan.md                human-readable placement table, keepouts, route notes

Coordinate system (board, mm):  origin = FRONT-LEFT corner of the board seen from the TOP.
  x runs along the finger from the FRONT edge (camera / FPC connector, x = 0) to the BACK edge
    (antenna / u.FL end, x = board_length).
  y runs across the finger from the LEFT edge (switch side, y = 0) to the RIGHT edge (y = board_width).
Part sizes are given as w (along x) × h (along y). Parts on the bottom use the same coordinates
(no mirroring in the data); the bottom drawing mirrors y so it looks like the real bottom view.

Reference designators follow hardware/electrical/out/mcring_v1_nets.md (U1..U9, C1..C24, R1..R19,
D1, D2, L1, Q1, SW1, FPC1, J1, J2, M1, MK1, BZ1, TP1..TP8, TPAD1).
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
    width=18.0,         # across the finger (left → right)
    thickness=0.6,
    corner_r=1.5,
)
L, W = BOARD["length"], BOARD["width"]

# The module sits with its u.FL / antenna end flush with the BACK edge.
MODULE = dict(w=15.4, h=15.4, height=2.4)
MODULE_X0 = L - MODULE["w"]            # 11.1
MODULE_CX = MODULE_X0 + MODULE["w"] / 2  # 18.8
MODULE_CY = W / 2                        # 9.0

ANT_KEEPOUT_X0 = L - 2.0   # last 2.0 mm of the board under the u.FL end: no copper, either layer
ANT_BEYOND_MM = 5.0        # and 5 mm beyond the back edge: no metal / cell / LRA (enclosure rule)

# Heights the CAD step has to clear
UFL_MATED_HEIGHT = 2.9     # module substrate (~0.8) + mated U.FL-R-SMT / U.FL-LP-040 pair (2.0) + 0.1
TOP_MAX_HEIGHT = max(MODULE["height"], UFL_MATED_HEIGHT)   # 2.9
BOTTOM_MAX_HEIGHT = 1.15   # VSSOP-10 (U5) and SOT-23 (U3/U4/Q1) are 1.10–1.15 max

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


def tp(ref, cx, cy, label, note=""):
    return Part(ref, "TP 1.0 mm", "bottom", cx, cy, 1.0, 1.0, "tp", 0.0, label, note)


SWITCH_OFFSET = 8.0     # centre of SW1 from the front edge
SWITCH_CY = 1.45        # body y 0.2..2.7, plunger points out of the LEFT edge (y < 0)
TPAD = dict(cx=8.1, cy=5.6, w=3.0, h=4.0, gap=0.5, ring=0.3)   # 3 × 4 mm copper, hatched GND ring around
LED_XY = (8.1, 10.0)
MIC_XY = (8.1, 15.85)   # mic body centre (bottom side) == port hole == lid hole position

PARTS: list[Part] = [
    # ---------------- TOP ----------------
    Part("U1", "ESP32-S3-MINI-1U-N4R2", "top", MODULE_CX, MODULE_CY, MODULE["w"], MODULE["h"], "module",
         MODULE["height"], "U1  ESP32-S3-MINI-1U", "u.FL / antenna end flush with the BACK edge; no copper under the last 2 mm"),
    Part("FPC1", "24-pin 0.5 mm FPC, bottom contact", "top", 2.5, W / 2, 4.0, 16.0, "connector", 2.0,
         "FPC1  24p 0.5 mm  (OV2640 head)", "FPC enters from the FRONT edge; keep x 4.5–5.5 free of parts > 0.6 mm for the actuator"),
    Part("SW1", "Omron B3U-3000P", "top", SWITCH_OFFSET, SWITCH_CY, 3.0, 2.5, "switch", 1.2, "SW1",
         "side-actuated, plunger out of the LEFT edge"),
    Part("TPAD1", "touch pad 3×4 mm copper", "top", TPAD["cx"], TPAD["cy"], TPAD["w"], TPAD["h"], "copper", 0.0,
         "TPAD1", "hatched GND ring 0.5 mm away; NO copper under it on the bottom"),
    Part("D1", "WS2812B-2020", "top", LED_XY[0], LED_XY[1], 2.0, 2.0, "led", 0.9, "D1", "under the lid window"),
    r0402("R7", 6.3, LED_XY[1], side="top", label="R7", note="100 Ω WS2812 data series"),
    Part("C3", "100 µF 1206", "top", 8.1, 13.0, 3.2, 1.6, "passive", 1.8, "C3 100µ", "3V3 bulk for capture/radio peaks"),

    # ---------------- BOTTOM: camera power cluster (front-left, under FPC1 power pins) ----------------
    r0402("C11", 1.8, 1.9, along="y", note="1 µF CAM_2V8 at U3 out"),
    r0402("R16", 1.8, 3.2, along="y", note="10k CAM_RESET pull-up (CAM_3V3)"),
    r0402("C14", 1.8, 4.5, along="y", note="100n CAM_RESET delay"),
    r0402("C12", 1.8, 5.8, along="y", note="1 µF CAM_1V2 at U4 out"),
    r0402("C9", 1.8, 7.1, along="y", note="1 µF U2 VIN"),
    r0402("R5", 1.0, 3.5, along="y", note="4.7k SIOD pull-up (FPC pin 3)"),
    r0402("C13", 1.0, 4.8, along="y", note="100n AVDD at FPC pin 4"),
    r0402("R6", 1.0, 6.1, along="y", note="4.7k SIOC pull-up (FPC pin 5)"),
    r0402("C24", 1.0, 7.4, along="y", note="100n DOVDD at FPC pin 11"),
    Part("U3", "XC6206P282MR SOT-23", "bottom", 3.7, 3.6, 2.9, 1.6, "ic", 1.15, "U3 2.8V", "AVDD LDO"),
    Part("U4", "XC6206P122MR SOT-23", "bottom", 3.7, 5.6, 2.9, 1.6, "ic", 1.15, "U4 1.2V", "DVDD LDO (DNP if the head regulates DVDD)"),
    Part("U2", "TPS22916C DSBGA-4", "bottom", 3.2, 7.4, 1.2, 0.9, "ic", 0.6, "U2", "camera rail load switch, ON = IO21"),
    r0402("C10", 4.5, 7.4, note="1 µF CAM_3V3 at U2 out"),
    r0402("R17", 5.8, 7.0, note="100k CAM_PWR_EN pull-down"),

    # ---------------- BOTTOM: under the switch / front-left edge ----------------
    pad("BZ1a", 6.3, 1.2, 1.2, label="PZ", note="piezo wire (BUZZ_DRV)"),
    pad("BZ1b", 8.3, 1.2, 1.2, label="PZ-", note="piezo wire return (GND)"),
    r0402("C22", 10.2, 1.3, note="100n BUTTON filter"),
    r0402("R15", 9.0, 2.6, note="100 Ω piezo series"),
    r0402("R13", 10.3, 5.6, along="y", note="1k touch series — just outside the pad"),

    # ---------------- BOTTOM: mic + LED supply gate (front-right) ----------------
    Part("MK1", "TDK T3902 PDM mic (bottom port)", "bottom", MIC_XY[0], MIC_XY[1], 2.65, 3.5, "mic", 0.98, "MK1",
         "bottom-port mic mounted on the BOTTOM; its port hole goes THROUGH the board and the lid hole sits above"),
    r0402("C19", 5.8, 15.9, note="100n mic VDD"),
    Part("U9", "TPS22916C DSBGA-4", "bottom", 10.3, 15.5, 1.2, 0.9, "ic", 0.6, "U9", "WS2812 supply gate VBAT→VLED, ON = IO44"),
    r0402("C20", 10.3, 14.3, note="100n VLED"),
    r0402("C21", 10.3, 16.8, note="1 µF VLED"),

    # ---------------- BOTTOM: power cluster (back-left) ----------------
    pad("J1a", 12.4, 1.3, 1.5, label="BAT+", note="301012 cell lead (VBAT)"),
    pad("J1b", 14.4, 1.3, 1.5, label="BAT-", note="301012 cell lead (GND)"),
    pad("PAD1w", 17.4, 1.3, 1.5, label="CHG+", note="wire to PAD1 (inner band, +5 V pogo)"),
    pad("PAD2w", 19.4, 1.3, 1.5, label="CHG-", note="wire to PAD2 (inner band, GND)"),
    c0603("C1", 11.6, 3.3, note="10 µF buck input"),
    Part("L1", "2.2 µH 2016 (DFE201610E)", "bottom", 13.7, 3.3, 2.0, 1.6, "inductor", 1.0, "L1", "buck inductor — tight loop with U8/C2"),
    c0603("C2", 15.8, 3.3, note="10 µF buck output"),
    Part("D2", "PESD5V0S1UB SOD-523", "bottom", 18.4, 2.9, 1.2, 0.8, "diode", 0.6, "D2", "TVS on CHG_IN, < 2 mm from the pad"),
    Part("U8", "TPS62840DLC SOT-583", "bottom", 12.6, 5.6, 2.1, 1.6, "ic", 0.6, "U8 buck", "3V3 buck"),
    r0402("R12", 14.4, 5.3, note="VSET (3.3 V code)"),
    Part("U7", "BQ25100 DSBGA-6", "bottom", 16.6, 5.3, 1.6, 0.9, "ic", 0.6, "U7", "charger 25 mA / 1 mA term"),
    r0402("C7", 18.4, 5.3, note="1 µF charger IN"),
    r0402("R8", 11.8, 6.9, note="100k divider top (VBAT)"),
    r0402("R9", 13.0, 6.9, note="100k divider bottom"),
    r0402("C23", 14.2, 6.9, note="100n BAT_SENSE"),
    r0402("C8", 15.6, 6.9, note="1 µF charger OUT / VBAT"),
    r0402("R10", 16.9, 6.9, note="9.1k ISET"),
    r0402("R11", 18.1, 6.9, note="11.5k PRE_TERM"),
    r0402("R19", 19.3, 6.9, note="100k nCHG pull-up"),

    # ---------------- BOTTOM: aux + I2C sensors (right half) ----------------
    Part("Q1", "AO3400A SOT-23", "bottom", 14.6, 9.3, 2.9, 1.6, "ic", 1.15, "Q1 aux", "low-side N-FET, gate IO9"),
    r0402("R14", 17.0, 9.3, note="100k AUX_EN pull-down"),
    pad("J2a", 14.2, 11.2, 1.2, label="AUX+", note="VBAT to the aux load"),
    pad("J2b", 15.8, 11.2, 1.2, label="AUXd", note="open drain of Q1"),
    Part("U5", "DRV2605L VSSOP-10", "bottom", 16.2, 13.6, 3.0, 3.0, "ic", 1.1, "U5 DRV2605L", "haptic driver 0x5A"),
    r0402("C15", 13.6, 12.6, along="y", note="1 µF DRV VDD"),
    r0402("C16", 13.6, 14.0, along="y", note="1 µF DRV REG"),
    pad("M1a", 15.4, 16.7, 1.5, label="LRA+", note="LRA wire OUT+"),
    pad("M1b", 17.4, 16.7, 1.5, label="LRA-", note="LRA wire OUT-"),
    r0402("R3", 18.2, 11.0, note="4.7k SDA pull-up"),
    r0402("R4", 19.4, 11.0, note="4.7k SCL pull-up"),
    Part("U6", "LIS2DW12 LGA-12 2×2", "bottom", 20.3, 13.8, 2.0, 2.0, "ic", 0.7, "U6", "accelerometer 0x18 (SA0=GND)"),
    r0402("C17", 20.3, 15.9, note="100n LIS VDD"),
    r0402("C18", 18.9, 15.9, note="100n LIS VDD_IO"),
    c0603("C4", 20.4, 9.3, note="10 µF module 3V3"),
    r0402("C5", 21.0, 10.5, note="100n module 3V3"),
    r0402("R18", 21.4, 11.6, note="4.7k LED_PWR_EN pull-down"),

    # ---------------- BOTTOM: module straps / test pads (back) ----------------
    r0402("R2", 21.2, 1.6, note="10k IO0 pull-up"),
    r0402("R1", 21.2, 16.6, note="10k EN pull-up"),
    r0402("C6", 22.6, 16.6, note="1 µF EN delay"),
    tp("TP1", 22.9, 3.0, "IO0"),
    tp("TP2", 22.9, 4.5, "EN"),
    tp("TP3", 22.9, 6.0, "D-", "USB_DM IO19"),
    tp("TP4", 22.9, 7.5, "D+", "USB_DP IO20"),
    tp("TP5", 22.9, 9.0, "GND"),
    tp("TP6", 22.9, 10.5, "3V3"),
    tp("TP7", 22.9, 12.0, "nCHG"),
    tp("TP8", 22.9, 13.5, "VBAT"),
]

# ----------------------------------------------------------------------------------------------
# 3. Keepouts / zones  (x0, y0, x1, y1 in board mm)
# ----------------------------------------------------------------------------------------------
TPAD_RING = (TPAD["cx"] - TPAD["w"] / 2 - TPAD["gap"] - TPAD["ring"], TPAD["cy"] - TPAD["h"] / 2 - TPAD["gap"] - TPAD["ring"],
             TPAD["cx"] + TPAD["w"] / 2 + TPAD["gap"] + TPAD["ring"], TPAD["cy"] + TPAD["h"] / 2 + TPAD["gap"] + TPAD["ring"])
TPAD_NOCOPPER = (TPAD["cx"] - TPAD["w"] / 2, TPAD["cy"] - TPAD["h"] / 2, TPAD["cx"] + TPAD["w"] / 2, TPAD["cy"] + TPAD["h"] / 2)

ZONES = [
    # name, side ('both'|'top'|'bottom'), rect, style, text
    ("ANT", "both", (ANT_KEEPOUT_X0, 0.0, L, W), "keepout",
     "antenna / u.FL end: no copper, no vias, either layer (+5 mm beyond the edge: no metal, cell or LRA)"),
    ("TPAD_NC", "bottom", TPAD_NOCOPPER, "keepout", "no copper under the touch pad"),
    ("FPC_ACT", "top", (4.5, 1.0, 5.5, 17.0), "clearance", "FPC actuator swing: parts ≤ 0.6 mm only"),
    ("DVP", "bottom", (1.0, 8.3, MODULE_X0 + 1.5, 13.8), "corridor",
     "DVP bus corridor: Y2..Y9, PCLK, HREF, VSYNC, XCLK from FPC1 pins 7–22 to the module front/right pins (≤ 15 mm, no other signals)"),
    ("VIAF", "bottom", (MODULE_X0, 8.3, MODULE_X0 + 1.5, 13.8), "corridor", "via field up to the module pads"),
]

MIC_HOLE_D = 0.6   # through-board acoustic port (match the T3902 port position/size at layout)

# FPC pin order assumed (ESP32-CAM / Arducam M0031) — pin 1 at the LEFT end of FPC1 (low y)
FPC_PINS = ["NC", "AGND", "SIOD", "AVDD 2.8", "SIOC", "RESET", "VSYNC", "PWDN", "HREF", "DVDD 1.2", "DOVDD 3.3",
            "Y9", "XCLK", "Y8", "DGND", "Y7", "PCLK", "Y6", "Y2", "Y5", "Y3", "Y4", "NC", "NC"]
FPC_GPIO = {"SIOD": "IO40", "SIOC": "IO39", "VSYNC": "IO38", "HREF": "IO47", "Y9": "IO48", "XCLK": "IO10",
            "Y8": "IO11", "Y7": "IO12", "PCLK": "IO13", "Y6": "IO14", "Y2": "IO15", "Y5": "IO16", "Y3": "IO17", "Y4": "IO18"}
FPC_PIN_PITCH = 0.5
FPC_PIN_Y0 = W / 2 - (len(FPC_PINS) - 1) * FPC_PIN_PITCH / 2   # 3.25


def fpc_pin_y(n: int) -> float:
    return FPC_PIN_Y0 + (n - 1) * FPC_PIN_PITCH


# Route-critical nets: (label, side, polyline of board points, colour)
NETS = [
    ("DVP ×12 (Y2–Y9, PCLK, HREF, VSYNC, XCLK) → U1", "bottom", [(2.5, 11.0), (MODULE_X0 + 0.8, 11.0)], "#c0392b"),
    ("SCCB SIOD/SIOC + R5/R6 to CAM_3V3", "bottom", [(1.0, 4.8), (MODULE_X0 + 0.8, 4.8)], "#8e44ad"),
    ("3V3 → U2 → CAM_3V3 → U3/U4 → FPC1 power pins", "bottom", [(3.2, 7.4), (3.7, 5.6), (3.7, 3.6), (1.0, 4.8)], "#e67e22"),
    ("buck loop C1–U8–L1–C2 (tight, same layer)", "bottom", [(11.6, 3.3), (12.6, 5.6), (13.7, 3.3), (15.8, 3.3)], "#d35400"),
    ("CHG pads → D2 TVS → U7 IN", "bottom", [(18.4, 1.3), (18.4, 2.9), (17.0, 5.3)], "#16a085"),
    ("VBAT: J1 → U8 VIN, U7 OUT, U9 VIN, R8", "bottom", [(12.4, 1.3), (12.0, 5.0), (11.8, 6.9)], "#1f618d"),
    ("I²C SDA/SCL (IO5/IO6) → U5, U6, R3/R4", "bottom", [(16.2, 13.6), (18.8, 11.0), (20.3, 13.8)], "#2e86c1"),
    ("LRA OUT+/OUT− (0.3 mm pair)", "bottom", [(16.2, 15.1), (16.4, 16.7)], "#7d6608"),
    ("VLED: U9 → D1 (via to top) / RGB_DATA IO43 → R7 → D1", "bottom", [(10.3, 15.5), (10.3, 12.0), (8.1, 10.0)], "#117a65"),
    ("PDM CLK/DATA (IO42/IO41) → MK1", "bottom", [(MODULE_X0 + 0.8, 15.85), (9.5, 15.85)], "#6c3483"),
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


def run_checks() -> list[str]:
    problems: list[str] = []
    notes: list[str] = []
    EDGE = 0.4
    for p in PARTS:
        # inside the outline (SW1 may touch the edge: side-actuated by design)
        lim = 0.0 if p.ref == "SW1" else EDGE
        back_lim = 0.0 if p.ref == "U1" else lim      # the module's antenna end is flush with the back edge by design
        if p.x0 < lim - 1e-6 or p.y0 < lim - 1e-6 or p.x1 > L - back_lim + 1e-6 or p.y1 > W - lim + 1e-6:
            problems.append(f"{p.ref} ({p.side}) violates the {lim} mm edge clearance: {rect_of(p)}")
        # antenna keepout: nothing but the module itself
        if p.ref != "U1" and _overlap(rect_of(p), (ANT_KEEPOUT_X0, 0, L, W)) > 0:
            problems.append(f"{p.ref} is inside the antenna keepout (x ≥ {ANT_KEEPOUT_X0})")
        # heights
        if p.side == "bottom" and p.height > BOTTOM_MAX_HEIGHT + 1e-6:
            problems.append(f"{p.ref} is {p.height} mm tall on the bottom (max {BOTTOM_MAX_HEIGHT})")
        if p.side == "top" and p.height > TOP_MAX_HEIGHT + 1e-6:
            problems.append(f"{p.ref} is {p.height} mm tall on the top (max {TOP_MAX_HEIGHT})")
        # no copper under the touch pad
        if p.side == "bottom" and _overlap(rect_of(p), TPAD_NOCOPPER) > 0:
            problems.append(f"{p.ref} sits under the touch pad (no-copper zone)")
        # FPC actuator clearance
        if p.side == "top" and p.ref != "FPC1" and p.height > 0.6 and _overlap(rect_of(p), (4.5, 1.0, 5.5, 17.0)) > 0:
            problems.append(f"{p.ref} is in the FPC actuator clearance zone")
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
        if p.side == "bottom" and _overlap(rect_of(p), ZONES[3][2]) > 0 and p.kind != "tp":
            notes.append(f"note: {p.ref} lies in the DVP corridor")
    # mic hole must be clear on the top side
    for p in PARTS:
        if p.side == "top" and _overlap(rect_of(p), (MIC_XY[0] - 0.9, MIC_XY[1] - 0.9, MIC_XY[0] + 0.9, MIC_XY[1] + 0.9)) > 0:
            problems.append(f"{p.ref} covers the mic port hole on the top side")
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
    svg = SVG(1240, 780)
    svg.arrow_marker("dim", "#555", 5)
    svg.arrow_marker("net", "#333", 6)
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
    left_label = "LEFT edge (switch)" if not mirrored else "RIGHT edge"
    right_label = "RIGHT edge" if not mirrored else "LEFT edge (switch)"
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

    # module details (top view): u.FL + pin-free antenna edge + shield
    if side == "top":
        u = next(p for p in PARTS if p.ref == "U1")
        (ux, uy) = view(L - 1.2, W / 2)
        svg.circle(ux, uy, S * 1.0, fill="#fff", stroke="#2c3e50", sw=1.2)
        svg.circle(ux, uy, S * 0.4, fill="#2c3e50", stroke="none")
        svg.text(ux, uy - S * 1.5, "u.FL (position per datasheet) → flex antenna down the back wall", size=8, anchor="middle", fill="#2c3e50")
        # pin rows on 3 edges
        for (x0, y0, x1, y1) in [(u.x0, u.y0, u.x0 + 0.9, u.y1), (u.x0, u.y0, u.x1 - 2.0, u.y0 + 0.9), (u.x0, u.y1 - 0.9, u.x1 - 2.0, u.y1)]:
            draw_rect_mm(svg, view, x0, y0, x1, y1, fill="none", stroke="#2c3e50", sw=0.5, dash="1 1")
        (tx, ty) = view(u.x0 + 2.4, W / 2)
        svg.text(tx, ty, "I/O pins on the front edge and both sides; none on the u.FL edge", size=8, anchor="middle", fill="#2c3e50")
        # FPC pins
        for n in range(1, 25):
            (px, py) = view(0.9, fpc_pin_y(n))
            svg.rect(px - 2.5, py - 3.5, 5, 7, fill="#7e5109", stroke="none")
        (px, py) = view(0.9, fpc_pin_y(1))
        svg.text(px, py - 10, "pin 1", size=7, anchor="middle", fill="#7e5109")
        (px, py) = view(0.9, fpc_pin_y(24))
        svg.text(px, py - 10, "pin 24", size=7, anchor="middle", fill="#7e5109")
        (px, py) = view(4.1, fpc_pin_y(12))
        svg.text(px, py, "contacts face DOWN (bottom-contact); FPC enters from the front edge", size=7.5, anchor="middle", fill="#7e5109")
        # LED window / mic hole / switch plunger
        (lx, ly) = view(*LED_XY)
        svg.circle(lx, ly, S * 1.5, fill="none", stroke="#c0392b", sw=0.8, dash="3 2")
        svg.line(lx + S * 1.5, ly, bx + bw + 10, ly - 12, stroke="#c0392b", sw=0.6)
        svg.text(bx + bw + 12, ly - 12, "lid window Ø3 over D1", size=8.5, fill="#c0392b")
        (sx, sy) = view(SWITCH_OFFSET, 0.0)
        svg.polygon([(sx - 9, sy), (sx + 9, sy), (sx + 9, sy - 8), (sx - 9, sy - 8)], fill="#6c3483", stroke="none")
        svg.text(sx - 12, sy + 14, "plunger through the LEFT wall", size=8, fill="#6c3483", anchor="end")
    # mic hole (both views)
    (mx, my) = view(*MIC_XY)
    svg.circle(mx, my, S * MIC_HOLE_D / 2, fill="#fff", stroke="#1b4f72", sw=1.2)
    if side == "top":
        svg.line(mx + S * 0.4, my, bx + bw + 10, my + 10, stroke="#1b4f72", sw=0.6)
        svg.text(bx + bw + 12, my + 10, "mic port Ø0.6 (lid hole above)", size=8.5, fill="#1b4f72")
    else:
        svg.line(mx - S * 0.4, my, bx - 10, my + 10, stroke="#1b4f72", sw=0.6)
        svg.text(bx - 12, my + 10, "mic port Ø0.6 (MK1 is bottom-port)", size=8.5, fill="#1b4f72", anchor="end")

    # critical nets
    for label, nside, pts, col in NETS:
        if nside != side:
            continue
        ppts = [view(x, y) for x, y in pts]
        svg.polyline(ppts, stroke=col, sw=2.2, marker="net", opacity=0.75)

    # ----- right-hand panel: legend + tables -----
    px0 = 640
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
        for s_ in ["Top layer: module footprint + fan-out, FPC1 pads, SW1, D1/R7, C3, touch pad + GND hatch; GND pour elsewhere.",
                   "Bottom layer: all small ICs/passives, wire pads, test pads, DVP corridor, I²C, power cluster; GND pour.",
                   "Module GND pads → ≥ 9 vias to the bottom pour; keep the last 2 mm (u.FL end) free of copper/vias on both layers."]:
            svg.text(px0 + 22, y - 3, s_, size=9, fill="#444"); y += 13
    y += 8

    svg.text(px0, y, f"Parts on the {side} side  (ref · footprint · centre x,y mm · w×h · height)", size=13, weight="bold"); y += 16
    col_w = 300
    rows = [p for p in PARTS if p.side == side]
    n_per_col = 36
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
    ("301012 LiPo cell", 3.00, "#f9e79f", "3 × 10 × 12, flat under the board, leads to J1"),
    ("clearance cell → bottom parts", 0.35, "#ffffff", "foam/Kapton on the cell"),
    ("bottom-side parts", BOTTOM_MAX_HEIGHT, "#d5f5e3", "VSSOP-10 / SOT-23 ≤ 1.15; mic 0.98"),
    ("PCB FR-4 2-layer", BOARD["thickness"], "#2ecc71", "0.6 mm, ENIG"),
    ("top-side parts", TOP_MAX_HEIGHT, "#dfe9f3", "module 2.4; mated u.FL ≈ 2.9; FPC1 2.0; C3 1.8"),
    ("clearance → lid", 0.30, "#ffffff", ""),
    ("lid (resin)", 1.20, "#e5e8e8", "LED window 1.0–1.5 thin; mic hole Ø0.8"),
]
POD = dict(fpc_loop=2.5, head_thick=1.3, barrel_len=4.5, barrel_d=4.5, head_sq=8.5, wall=1.2, roof_gap=0.3)


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
    svg.text(x0, base - Z * total - 30, f"Signet top = {total:.2f} mm above the skin = {total - 3.2:.2f} mm above a 3.2 mm band wall.",
             size=11, weight="bold", fill="#922b21")
    svg.text(x0, base - Z * total - 14, f"Alternative (cell in the palm-side thick zone, as in the old .scad): remove the 3.0 cell layer → "
             f"{total - 3.0:.2f} mm.", size=10, fill="#444")

    # ---- camera pod section (side view, cut at y = 9 through the lens axis) ----
    px0 = 830.0
    Xs = 22.0   # px per mm horizontal for the section
    svg.text(px0, 100, "Camera pod — side section along the finger (board front edge at x = 0)", size=13, weight="bold")
    svg.text(px0, 118, "+x → toward the back (antenna); the pod extends in front of the board (negative x).", size=10, fill="#444")
    z_board_bot = sum(t for _, t, _, _ in STACK[:4])   # 5.70
    z_board_top = z_board_bot + BOARD["thickness"]     # 6.30
    z_lid_bot = z_board_top + TOP_MAX_HEIGHT + 0.30     # 9.50
    z_lid_top = z_lid_bot + 1.2                         # 10.70
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

    # camera head: vertical plate in front of the board, optical axis along -x
    lens_z = 5.5
    head_x1 = -POD["fpc_loop"]                      # back face of the head
    head_x0 = head_x1 - POD["head_thick"]           # front face (barrel base)
    barrel_x0 = head_x0 - POD["barrel_len"]         # barrel front
    hz0, hz1 = lens_z - POD["head_sq"] / 2, lens_z + POD["head_sq"] / 2
    svg.rect(SX(head_x0), SZ(hz1), Xs * POD["head_thick"], Z * POD["head_sq"], fill="#34495e", stroke="#111", sw=1)
    svg.rect(SX(barrel_x0), SZ(lens_z + POD["barrel_d"] / 2), Xs * POD["barrel_len"], Z * POD["barrel_d"], fill="#2c3e50", stroke="#111", sw=1)
    svg.text(SX(barrel_x0 + POD["barrel_len"] / 2), SZ(lens_z), "lens Ø4.5", size=9, anchor="middle", fill="#fff")
    svg.text(SX(head_x0 + POD["head_thick"] / 2), SZ(hz1) - 6, "OV2640 head 8.5 × 8.5 × 1.3 (+4.5 barrel)", size=8.5, anchor="middle", fill="#111")
    svg.text(SX(head_x1 + 0.2), SZ(hz0) + 12, "cell is only under the bay, not under the pod", size=8, fill="#555")
    # FPC loop: from the head's back face to the connector mouth at the board front edge
    svg.path(f"M {SX(head_x1):.1f} {SZ(lens_z + 3):.1f} C {SX(head_x1 + 1.2):.1f} {SZ(lens_z + 3):.1f}, "
             f"{SX(-0.6):.1f} {SZ(z_board_top + 0.9):.1f}, {SX(0.6):.1f} {SZ(z_board_top + 0.6):.1f}",
             stroke="#e67e22", sw=3)
    svg.text(SX(head_x1 + 0.3), SZ(lens_z + 3.8), "24-pin FPC (exits the head sideways, loops back)", size=8, fill="#e67e22")
    # lens axis
    svg.line(SX(barrel_x0 - 2.5), SZ(lens_z), SX(1.0), SZ(lens_z), stroke="#c0392b", sw=0.8, dash="6 3")
    svg.text(SX(head_x1 + 0.2), SZ(lens_z) - 8, f"lens axis z = {lens_z:.1f}", size=9, fill="#c0392b")
    # pod walls
    pod_front = barrel_x0 - POD["wall"] + POD["barrel_len"] * 0 - 0.0   # barrel front flush with the pod face
    pod_front = barrel_x0
    roof_bot = hz1 + POD["roof_gap"]
    roof_top = roof_bot + POD["wall"]
    floor_top = hz0 - POD["roof_gap"]
    svg.rect(SX(pod_front - POD["wall"]), SZ(roof_top), Xs * POD["wall"], Z * (roof_top - 1.2), fill="#e5e8e8", stroke="#333", sw=1)   # front wall
    svg.rect(SX(pod_front - POD["wall"]), SZ(roof_top), Xs * (-(pod_front - POD["wall"]) + 0.5), Z * POD["wall"], fill="#e5e8e8", stroke="#333", sw=1)  # roof
    svg.rect(SX(pod_front - POD["wall"]), SZ(1.2), Xs * (-(pod_front - POD["wall"]) + band_c - 6), Z * 1.2, fill="#e5e8e8", stroke="#333", sw=1)  # floor
    # lens bore through the front wall
    svg.rect(SX(pod_front - POD["wall"]), SZ(lens_z + POD["barrel_d"] / 2 + 0.1), Xs * POD["wall"], Z * (POD["barrel_d"] + 0.2), fill="#fff", stroke="#333", sw=0.6)
    svg.text(SX(pod_front - POD["wall"]) - 4, SZ(lens_z + 3.2), "bore Ø4.7", size=8.5, anchor="end")
    # dimensions
    svg.dim_h(SX(pod_front - POD["wall"]), SX(0), SZ(roof_top) - 14, f"pod depth {-(pod_front - POD['wall']):.1f} in front of the board edge", size=9)
    svg.dim_v(SZ(roof_top), SZ(0), SX(pod_front - POD["wall"]) - 30, f"pod height {roof_top:.1f}", size=9)
    svg.text(px0, 140, f"Lens axis z = {lens_z:.1f}; head spans z {hz0:.2f}–{hz1:.2f}; pod roof underside {roof_bot:.2f}, top {roof_top:.2f} "
             f"({roof_top - z_lid_top:+.2f} vs the bay lid).", size=10, fill="#444")
    svg.text(px0, 156, f"Pod interior: {-(pod_front):.1f} deep × ≥ 9.2 wide (head 8.5 + 0.35 per side) — head is centred on y = {W/2:.1f}.", size=10, fill="#444")
    svg.save(path, png_scale=2.0)
    return dict(z_board_bottom=z_board_bot, z_board_top=z_board_top, z_lid_bottom=z_lid_bot, z_lid_top=z_lid_top,
                signet_height=total, lens_axis_z=lens_z, head_z=[hz0, hz1], pod_roof_top=roof_top,
                pod_depth_from_board_edge=-(pod_front - POD["wall"]), pod_interior_depth=-pod_front)


# ----------------------------------------------------------------------------------------------
# 7. Outputs: board_params.json + floorplan.md
# ----------------------------------------------------------------------------------------------
def write_params(stack_info: dict) -> dict:
    sw = next(p for p in PARTS if p.ref == "SW1")
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
            "Module ESP32-S3-MINI-1U 15.4x15.4x2.4 with its u.FL end flush with the back edge; keep 5 mm behind the "
            "back edge free of metal, cell and LRA, and route the flex antenna down the back wall. top_max_height "
            "is the mated u.FL plug (2.9), the module shield is 2.4 (the lid may be lower over the front strip, "
            "x < 11.1: tallest part there is FPC1 at 2.0). Bottom parts max 1.15 (SOT-23/VSSOP) - allow >= 0.35 "
            "clearance to the cell. Mic MK1 is a bottom-port part mounted on the BOTTOM side at mic_xy; its 0.6 mm "
            "port goes through the board, so the lid needs a ~0.8 mm hole straight above mic_xy. LED D1 is on top "
            "at led_xy under a 1.0-1.5 mm thinned window (~3 mm). Switch SW1 body 3.0x2.5x1.2 on the top side, "
            "plunger pointing out of the left edge at x = switch_offset; wall slot ~3.2 x 1.5 centred z = board_top+0.6. "
            "Touch pad 3x4 copper on top at touchpad_xy (needs only a thin, non-conductive lid: <= 1.0 mm there or "
            "an opening). FPC connector FPC1 on top at x 0.5-4.5 spanning y 1-17, FPC enters from the front edge; the "
            "camera head sits in a pod in front of the board (see stackup.svg / pod_mm). Wire pads for the cell "
            "(J1), charging pads (PAD1/2), LRA (M1), piezo (BZ1) and aux (J2) are all on the BOTTOM side, so the "
            "wire channel into the band should open under the board near x 12-20 (left) and x 15-18 (right)."
        ),
        # ---- extras for the CAD step ----
        "switch_xy_mm": [sw.cx, sw.cy],
        "switch_body_mm": [sw.w, sw.h, sw.height],
        "module_size_mm": [MODULE["w"], MODULE["h"], MODULE["height"]],
        "module_front_edge_x_mm": round(MODULE_X0, 2),
        "ufl_mated_height_mm": UFL_MATED_HEIGHT,
        "front_strip_max_height_mm": 2.0,
        "antenna_keepout_on_board_mm": round(L - ANT_KEEPOUT_X0, 2),
        "antenna_keepout_beyond_edge_mm": ANT_BEYOND_MM,
        "fpc_connector_mm": {"x0": 0.5, "x1": 4.5, "y0": 1.0, "y1": 17.0, "height": 2.0, "pin1_y": round(fpc_pin_y(1), 2)},
        "led_window_d_mm": 3.0,
        "mic_hole_d_mm": 0.8,
        "mic_port_board_hole_d_mm": MIC_HOLE_D,
        "touchpad_size_mm": [TPAD["w"], TPAD["h"]],
        "stack_mm": {
            "band_wall": 1.2, "cell": 3.0, "cell_clearance": 0.35, "bottom_parts": BOTTOM_MAX_HEIGHT,
            "pcb": BOARD["thickness"], "top_parts": TOP_MAX_HEIGHT, "lid_clearance": 0.30, "lid": 1.2,
            "z_board_bottom": round(stack_info["z_board_bottom"], 2), "z_board_top": round(stack_info["z_board_top"], 2),
            "z_lid_bottom": round(stack_info["z_lid_bottom"], 2), "z_lid_top": round(stack_info["z_lid_top"], 2),
            "signet_height_above_skin": round(stack_info["signet_height"], 2),
            "signet_height_above_skin_cell_in_band": round(stack_info["signet_height"] - 3.0, 2),
        },
        "pod_mm": {
            "lens_axis_z": stack_info["lens_axis_z"], "lens_barrel_d": POD["barrel_d"], "bore_d": 4.7,
            "head_square": POD["head_sq"], "head_thickness": POD["head_thick"], "barrel_length": POD["barrel_len"],
            "fpc_loop": POD["fpc_loop"], "wall": POD["wall"],
            "interior_depth_from_board_edge": round(stack_info["pod_interior_depth"], 2),
            "depth_from_board_edge_incl_wall": round(stack_info["pod_depth_from_board_edge"], 2),
            "interior_width": 9.2, "roof_top_z": round(stack_info["pod_roof_top"], 2),
            "head_z": [round(v, 2) for v in stack_info["head_z"]],
        },
        "wire_pads_bottom_mm": {p.ref: [p.cx, p.cy] for p in PARTS if p.kind == "pad"},
        "test_pads_bottom_mm": {p.label: [p.cx, p.cy] for p in PARTS if p.kind == "tp"},
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

    st = params["stack_mm"]; pod = params["pod_mm"]
    md = f"""# mcring v1 — stage-1 PCB floorplan

Generated by `floorplan.py` (pure Python → SVG/PNG, no CAD). Drawings: `out/floorplan_top.*`,
`out/floorplan_bottom.*`, `out/stackup.*`. Numbers for the enclosure: `board_params.json`.
Reference designators and nets follow `hardware/electrical/out/mcring_v1_nets.md`.

## 1. Board

| Item | Value |
|---|---|
| Outline | **{L} × {W} mm**, rounded corners r = {BOARD['corner_r']} mm, 2-layer FR-4 **0.6 mm**, ENIG |
| Orientation | x along the finger: **front edge = camera / FPC** (x = 0), **back edge = antenna / u.FL** (x = {L}); y across the finger: **left edge = switch** (y = 0) |
| Module | ESP32-S3-MINI-1U 15.4 × 15.4 × 2.4, centre ({params['module_xy_mm'][0]}, {params['module_xy_mm'][1]}), u.FL end **flush with the back edge** |
| Top side | U1 module, FPC1 (24-pin 0.5 mm bottom-contact), SW1 side switch, D1 WS2812B-2020 + R7, C3 100 µF 1206, TPAD1 3 × 4 copper touch pad with hatched GND ring |
| Bottom side (≤ {BOTTOM_MAX_HEIGHT} mm) | everything else: U2–U9, L1, D2, Q1, MK1 mic (bottom-port, port through the board), 37 × 0402, 3 × 0603, wire pads (cell, charge pads, LRA, piezo, aux), 8 test pads |
| Tallest top part | mated u.FL plug on the module ≈ {UFL_MATED_HEIGHT} mm (module shield 2.4; front strip x < {MODULE_X0:.1f}: FPC1 2.0) |
| Why {L} long | {MODULE_X0:.1f} mm front strip (FPC1 4.0 + 1.0 actuator clearance + 5.6 for SW1/TPAD1/D1/C3/mic port) + 15.4 module |
| Why {W} wide | FPC1 body 16 mm + 2 × 1.0 edge; module 15.4 + 2 × 1.3 |

## 2. Placement — top side

{table('top')}

Touch pad guard ring: hatched top copper {TPAD['ring']} mm wide, {TPAD['gap']} mm from the pad, no copper under the pad on the
bottom layer. LED window Ø3 in the lid above D1 ({LED_XY[0]}, {LED_XY[1]}). Mic port hole Ø{MIC_HOLE_D} through the board at
({MIC_XY[0]}, {MIC_XY[1]}) with an Ø0.8 lid hole above it (nothing else on the top side within 0.9 mm).

## 3. Placement — bottom side

{table('bottom')}

## 4. Keep-outs and zones

| Zone | Layers | Rectangle (x0, y0 – x1, y1) | Rule |
|---|---|---|---|
| Antenna / u.FL end | both | ({ANT_KEEPOUT_X0:.1f}, 0 – {L}, {W}) | no copper, no vias; **+{ANT_BEYOND_MM} mm beyond the back edge** no metal, cell or LRA (enclosure) |
| Touch pad | bottom | ({TPAD_NOCOPPER[0]:.1f}, {TPAD_NOCOPPER[1]:.1f} – {TPAD_NOCOPPER[2]:.1f}, {TPAD_NOCOPPER[3]:.1f}) | no copper under TPAD1; R13 just outside it |
| FPC actuator swing | top | (4.5, 1.0 – 5.5, 17.0) | parts ≤ 0.6 mm only (R7 is fine) |
| DVP corridor | bottom | (1.0, 8.3 – {MODULE_X0 + 1.5:.1f}, 13.8) | Y2–Y9, PCLK, HREF, VSYNC, XCLK only; vias up to U1 in the last 1.5 mm |
| Under the module | top | module footprint | bare FR-4 under the shield (no silkscreen), ≥ 9 GND vias on the thermal pads |

## 5. Layer usage

* **Top**: module footprint + fan-out, FPC1, SW1, D1/R7, C3, touch pad + GND hatch, GND pour. The DVP bus leaves
  FPC1 on the top layer, drops to the bottom corridor, and comes back up at the module's front-left pins.
* **Bottom**: all small ICs and passives, wire pads, test pads, the DVP corridor, I²C, the power cluster; GND pour
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
| Charge input | CHG+ pad → D2 TVS (< 2 mm) → U7 IN with C7; CHG− straight to the GND pour |
| VBAT | J1 → C8 / U7 OUT → U8 VIN → U9 VIN → R8; 0.4 mm trunk |
| I²C | IO5/IO6 → R3/R4 → U5, U6 — one short daisy chain on the right half |
| LRA OUT+/OUT− | 0.3 mm pair, U5 → M1 pads (2 mm) |
| VLED / RGB_DATA | U9 → via → D1 (top); IO43 → R7 → D1 DIN |
| PDM CLK/DATA | IO42/IO41 → MK1 on the right-front, ≤ 10 mm |
| USB D−/D+ | IO19/IO20 → TP3/TP4 stubs only (≤ 4 mm), nothing else on the nets |
| Touch | IO8 → R13 (1 kΩ) → TPAD1; keep the trace short and away from the DVP corridor |

## 7. Camera FPC pin order (assumed ESP32-CAM / Arducam M0031 — verify on the purchased head)

Pin 1 is at the LEFT end of FPC1 (low y); pitch 0.5 mm; contacts face the board (bottom-contact connector).

{chr(10).join(fpc_rows)}

## 8. Stack (see `out/stackup.svg`)

skin → band wall {st['band_wall']} → cell {st['cell']} → clearance {st['cell_clearance']} → bottom parts {st['bottom_parts']} →
PCB {st['pcb']} → top parts {st['top_parts']} → clearance {st['lid_clearance']} → lid {st['lid']}:
board bottom at z = {st['z_board_bottom']}, board top z = {st['z_board_top']}, lid underside z = {st['z_lid_bottom']},
**signet top z = {st['signet_height_above_skin']} mm** above the skin ({st['signet_height_above_skin_cell_in_band']} mm if the cell moves to the
palm-side thick zone of the band as in the old `.scad`).

Camera pod: lens axis z = {pod['lens_axis_z']}, head 8.5 × 8.5 × 1.3 + Ø4.5 × 4.5 barrel, FPC loop {pod['fpc_loop']} mm, interior
depth {pod['interior_depth_from_board_edge']} mm in front of the board edge ({pod['depth_from_board_edge_incl_wall']} incl. the 1.2 wall), interior width ≥ {pod['interior_width']},
roof top z = {pod['roof_top_z']} ({pod['roof_top_z'] - st['z_lid_top']:+.2f} vs the bay lid — the pod is marginally taller than the lid, or raise the lid clearance by 0.4).

## 9. Deviations from the task text / earlier notes

1. **Mic on the BOTTOM side**, not the top: the TDK T3902 is a bottom-port microphone, so the acoustic path is
   through the board. Mounted on the bottom at `mic_xy`, its port hole goes up through the PCB to a lid hole straight
   above — a top mount would have needed a sound channel under the board. Height 0.98 mm fits the bottom limit.
2. **Battery via two solder pads (J1a/J1b) instead of the JST SH BM02B** in the electrical BOM: the vertical SH
   header is 4.25 mm tall and the side-entry SM02B 2.9 mm — neither fits the bottom (1.15) and the top strip has
   no room. The netlist's J1 pins 1/2 map to the two pads.
3. **top_max_height = 2.9 mm**, not 2.4: the mated u.FL plug on the module is taller than the shield can.
4. **bottom_max_height = 1.15 mm** (task: 1.1): VSSOP-10 and SOT-23 bodies are 1.10–1.15 max.
5. **8 test pads** (IO0, EN, USB D−, D+, GND, 3V3, nCHG, VBAT) per the electrical netlist, not 4.
6. **SW2 (optional IO0 boot button, DNP) is not placed** — no top-side room; use TP1 (IO0) + TP2 (EN).
7. GPIO use follows the post-fix `BOARD_MCRING_V1` (CAM_PWR = IO21, RGB = IO43, LED_PWR_EN = IO44, USB on 19/20).
8. Board is {L} × {W} instead of the old 26 × 12 bay: the 15.4 mm module and the 16 mm FPC connector set the width.

## 10. Checks performed by the script

{chr(10).join('* ' + m for m in check_msgs) if check_msgs else '* no overlaps, no edge/keep-out/height violations'}
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
          f"({sum(p.side == 'top' for p in PARTS)} top / {sum(p.side == 'bottom' for p in PARTS)} bottom)")
    print("wrote", ", ".join(sorted(os.listdir(OUT))), "+ board_params.json, floorplan.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
