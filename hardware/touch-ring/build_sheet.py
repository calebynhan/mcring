#!/usr/bin/env python3
"""Touch-ring build sheet: assembly drawings, wiring schematic and the AliExpress list as one page.

Reads hardware/bom/touch-ring-aliexpress.csv. Writes standalone SVGs to hardware/touch-ring/out/
and the published page docs/touch-ring-build.html (the same drawings inlined, theme-aware).
Drawing geometry is in millimetres at S px/mm; balloon numbers are the CSV item numbers.

    python3 hardware/touch-ring/build_sheet.py
"""
from __future__ import annotations

import csv
import html
import math
import os
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
CSV_PATH = os.path.join(ROOT, "hardware", "bom", "touch-ring-aliexpress.csv")
OUT = os.path.join(HERE, "out")
PAGE = os.path.join(ROOT, "docs", "touch-ring-build.html")

S = 8  # px per mm

# The only literal hues; each reads on light and dark grounds. Everything else is currentColor.
COPPER = "#c8742e"   # touch electrodes
POWER = "#d64541"    # 3V3 and battery +
I2C = "#3f82d6"      # SDA / SCL
IRQ = "#9061d4"      # interrupt lines
ANALOG = "#1f9e89"   # NTC divider

# Pod and part sizes (mm). Pod = printed shell: 34 long (along the finger) x 25 wide x 10 tall.
POD_L, POD_W, POD_H = 34.0, 25.0, 10.0
ELEC_W, ELEC_GAP, ELEC_LEN = 6.0, 1.5, 18.0
ELEC_X0 = (POD_L - (4 * ELEC_W + 3 * ELEC_GAP)) / 2  # 2.75


def esc(s: str) -> str:
    return html.escape(s, quote=True)


class Fig:
    """Minimal SVG accumulator. Coordinates in px; callers convert from mm."""

    def __init__(self, w: float, h: float, ident: str, label: str, y0: float = 0.0):
        self.w, self.h, self.ident, self.label, self.y0 = w, h, ident, label, y0
        self.items: list[str] = []
        self.defs: list[str] = []

    def add(self, s: str) -> None:
        self.items.append(s)

    def rect(self, x, y, w, h, fill="none", op=None, stroke="currentColor", sw=1.0, rx=0.0,
             dash=None, sop=None) -> None:
        a = [f'x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}"']
        if rx:
            a.append(f'rx="{rx:.1f}"')
        a.append(f'fill="{fill}"')
        if op is not None:
            a.append(f'fill-opacity="{op}"')
        a.append(f'stroke="{stroke}" stroke-width="{sw}"')
        if sop is not None:
            a.append(f'stroke-opacity="{sop}"')
        if dash:
            a.append(f'stroke-dasharray="{dash}"')
        self.add(f"<rect {' '.join(a)}/>")

    def line(self, x1, y1, x2, y2, stroke="currentColor", sw=1.0, dash=None, sop=None,
             start=None, end=None) -> None:
        a = [f'x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{stroke}" '
             f'stroke-width="{sw}" stroke-linecap="round"']
        if dash:
            a.append(f'stroke-dasharray="{dash}"')
        if sop is not None:
            a.append(f'stroke-opacity="{sop}"')
        if start:
            a.append(f'marker-start="url(#{self.ident}-{start})"')
        if end:
            a.append(f'marker-end="url(#{self.ident}-{end})"')
        self.add(f"<line {' '.join(a)}/>")

    def poly(self, pts, stroke="currentColor", sw=1.0, dash=None) -> None:
        p = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        d = f' stroke-dasharray="{dash}"' if dash else ""
        self.add(f'<polyline points="{p}" fill="none" stroke="{stroke}" stroke-width="{sw}" '
                 f'stroke-linejoin="round" stroke-linecap="round"{d}/>')

    def circle(self, cx, cy, r, fill="none", op=None, stroke="currentColor", sw=1.0, dash=None,
               sop=None) -> None:
        a = [f'cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="{fill}"']
        if op is not None:
            a.append(f'fill-opacity="{op}"')
        a.append(f'stroke="{stroke}" stroke-width="{sw}"')
        if sop is not None:
            a.append(f'stroke-opacity="{sop}"')
        if dash:
            a.append(f'stroke-dasharray="{dash}"')
        self.add(f"<circle {' '.join(a)}/>")

    def text(self, x, y, s, size=12, anchor="start", weight=None, op=None, fill="currentColor",
             family=None) -> None:
        a = [f'x="{x:.1f}" y="{y:.1f}" font-size="{size}" text-anchor="{anchor}" fill="{fill}"']
        if weight:
            a.append(f'font-weight="{weight}"')
        if op is not None:
            a.append(f'fill-opacity="{op}"')
        if family:
            a.append(f'font-family="{family}"')
        self.add(f"<text {' '.join(a)}>{esc(s)}</text>")

    def balloon(self, cx, cy, label, tx, ty, r=9.0) -> None:
        """Item-number balloon at (cx, cy) with a leader to the part at (tx, ty)."""
        d = math.hypot(tx - cx, ty - cy) or 1.0
        sx, sy = cx + r * (tx - cx) / d, cy + r * (ty - cy) / d
        self.line(sx, sy, tx, ty, sw=0.9)
        self.circle(tx, ty, 1.8, fill="currentColor", stroke="none", sw=0)
        self.circle(cx, cy, r, sw=1.2)
        self.add(f'<text x="{cx:.1f}" y="{cy:.1f}" dy="0.35em" font-size="10.5" font-weight="600" '
                 f'text-anchor="middle" fill="currentColor">{esc(label)}</text>')

    def dim_h(self, x1, x2, y, label) -> None:
        self.line(x1, y, x2, y, sw=0.8, start="tick", end="tick")
        self.line(x1, y - 5, x1, y + 5, sw=0.8)
        self.line(x2, y - 5, x2, y + 5, sw=0.8)
        self.text((x1 + x2) / 2, y - 5, label, size=11, anchor="middle", op=0.8)

    def dim_v(self, x, y1, y2, label, side="left") -> None:
        self.line(x, y1, x, y2, sw=0.8)
        self.line(x - 5, y1, x + 5, y1, sw=0.8)
        self.line(x - 5, y2, x + 5, y2, sw=0.8)
        if side == "left":
            self.text(x - 6, (y1 + y2) / 2 + 4, label, size=11, anchor="end", op=0.8)
        else:
            self.text(x + 6, (y1 + y2) / 2 + 4, label, size=11, anchor="start", op=0.8)

    def tag(self, x, y, label, color, where) -> None:
        """Net label attached at (x, y); `where` is the side of the attach point it sits on."""
        w, h = 8 + 6.6 * len(label), 16
        if where == "below":
            bx, by = x - w / 2, y
        elif where == "right":
            bx, by = x, y - h / 2
        else:  # left
            bx, by = x - w, y - h / 2
        self.rect(bx, by, w, h, rx=3, stroke=color, sw=1.1)
        self.text(bx + w / 2, by + 11.5, label, size=10.5, anchor="middle", fill=color, weight="600")

    def svg(self, standalone: bool) -> str:
        defs = (
            f'<defs><marker id="{self.ident}-arrow" viewBox="0 0 10 10" refX="9" refY="5" '
            f'markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
            f'<path d="M0,0 L10,5 L0,10 z" fill="currentColor"/></marker>'
            f'<marker id="{self.ident}-tick" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="0" '
            f'markerHeight="0"><path d="M5,0 L5,10" stroke="currentColor"/></marker></defs>'
        )
        head = (f'<svg viewBox="0 {self.y0:.0f} {self.w:.0f} {self.h:.0f}" role="img" '
                f'aria-label="{esc(self.label)}" class="dwg dwg-{self.ident}" '
                f'font-family="IBM Plex Sans, Helvetica, Arial, sans-serif"')
        if standalone:
            head += ' xmlns="http://www.w3.org/2000/svg" color="#18211d"'
            body = (f'<rect x="0" y="{self.y0:.0f}" width="{self.w:.0f}" height="{self.h:.0f}" '
                    f'fill="#ffffff"/>' + "".join(self.items))
        else:
            body = "".join(self.items)
        return f"{head}>{defs}{body}</svg>"


# ---------------------------------------------------------------------------------------------
# Figure 1: longitudinal section (finger runs left to right, USB-C end toward the hand)

def fig_side() -> Fig:
    f = Fig(545, 345, "side", "Side section of the touch ring: printed pod on an adjustable ring "
            "blank; copper electrodes under the lid, MPR121 below them, XIAO and LiPo side by side "
            "on the floor; optional MAX30102 and NTC inside the band on the palm side.")
    ox, oy = 170, 50

    def X(x):
        return ox + S * x

    def Y(y):
        return oy + S * y

    # finger (behind everything)
    f.rect(X(-6), Y(11.6), S * 46, S * 16.4, fill="currentColor", op=0.05, sop=0.35, dash="4 3",
           rx=S * 8.2)
    f.text(X(-4.2), Y(19.8) + 4, "finger", size=11, op=0.6)
    f.text(X(38.5), Y(19.8) + 4, "toward fingertip →", size=11, anchor="end", op=0.6)
    # band seen edge-on, and the blank's flat pad
    f.rect(X(15.75), Y(10.8), S * 2.5, S * 20.6, fill="currentColor", op=0.16)
    f.rect(X(7), Y(10), S * 20, S * 0.8, fill="currentColor", op=0.3)
    # printed pod: lid, floor, walls (USB-C slot in the left wall)
    for (x, y, w, h) in [(0, 0, POD_L, 1), (0, 9, POD_L, 1), (0, 1, 1, 3.8), (0, 8, 1, 1),
                         (33, 1, 1, 8)]:
        f.rect(X(x), Y(y), S * w, S * h, fill="currentColor", op=0.14)
    # copper electrodes under the lid, and their leads down to the MPR121
    for i in range(4):
        x0 = ELEC_X0 + i * (ELEC_W + ELEC_GAP)
        f.rect(X(x0), Y(1.0), S * ELEC_W, S * 0.35, fill=COPPER, stroke=COPPER, sw=0.5)
        f.line(X(x0 + 3), Y(1.35), X(x0 + 3), Y(2.7), stroke=COPPER, sw=1.2)
    # MPR121 module (components up), foam tape below it
    f.rect(X(1.5), Y(2.7), S * 31, S * 1.6, fill="currentColor", op=0.32, sw=0.8)
    f.rect(X(15.5), Y(1.9), S * 3, S * 0.8, fill="currentColor", op=0.55, sw=0.6)
    f.rect(X(1.5), Y(4.3), S * 31, S * 0.5, fill="currentColor", op=0.07, sop=0.5, dash="2 2")
    # XIAO nRF52840 Sense: PCB on the floor, shielded radio, USB-C receptacle in the wall slot
    f.rect(X(1), Y(8), S * 21, S * 1, fill="currentColor", op=0.32, sw=0.8)
    f.rect(X(10), Y(6.3), S * 10, S * 1.7, fill="currentColor", op=0.45, sw=0.6)
    f.rect(X(0.4), Y(4.8), S * 7.4, S * 3.2, fill="currentColor", op=0.22, rx=4)
    f.text(X(8.4), Y(6.0), "XIAO nRF52840", size=10, op=0.75)
    # LiPo beside it
    f.rect(X(23), Y(5), S * 10, S * 4, fill="currentColor", op=0.2, rx=3)
    f.text(X(28), Y(7.4), "LiPo", size=11, anchor="middle", op=0.8)
    # optional health parts on the palm side, and their wires up the band
    f.rect(X(10.5), Y(28.0), S * 13, S * 1.8, fill="currentColor", op=0.08, dash="4 3")
    f.circle(X(25), Y(28.9), 4, fill=ANALOG, op=0.45, stroke=ANALOG, dash="2 2")
    f.line(X(18.7), Y(28.0), X(18.7), Y(10.8), sw=1.4, dash="4 3", sop=0.6)
    # callouts
    f.text(160, 104, "USB-C slot: charge + flash", size=11, anchor="end")
    f.line(162, 101, 174, 101, sw=0.9)
    f.balloon(140, 126, "1", X(1.5), Y(8.6))
    f.balloon(X(9.5), 20, "2", X(9.5), Y(3.0))
    f.balloon(X(5.75), 20, "3", X(5.75), Y(1.0))
    f.balloon(X(17.0), 20, "6", X(17.0), Y(4.55))
    f.balloon(470, 62, "P", X(34), Y(2))
    f.balloon(470, 106, "4", X(31), Y(7))
    f.balloon(510, 133, "5", X(27), Y(10.4))
    f.balloon(X(12.5), 326, "11", X(12.5), Y(29.8))
    f.balloon(X(25), 326, "12", X(25), Y(28.9) + 4)
    return f


# ---------------------------------------------------------------------------------------------
# Figure 2: end view (looking along the finger from the fingertip)

def fig_end() -> Fig:
    f = Fig(330, 345, "end", "End view looking along the finger: 25 mm wide, 10 mm tall pod on the "
            "ring blank's pad; one electrode strip spans the width; optional MAX30102 and NTC sit "
            "inside the band against the palm side of the finger.")
    ox, oy = 60, 50

    def X(x):
        return ox + S * x

    def Y(y):
        return oy + S * y

    cx = X(12.5)
    f.circle(cx, Y(19.8), S * 8.2, fill="currentColor", op=0.05, sop=0.35, dash="4 3")
    f.text(cx, Y(19.8) + 4, "finger", size=11, anchor="middle", op=0.6)
    f.circle(cx, Y(21.5), S * 10.3, stroke="currentColor", sw=S * 0.8, sop=0.3)
    f.circle(cx, Y(21.5), S * 10.7, sw=0.8)
    f.circle(cx, Y(21.5), S * 9.9, sw=0.8)
    f.text(cx, Y(32.2) + 18, "palm side", size=11, anchor="middle", op=0.6)
    f.rect(X(2.5), Y(10), S * 20, S * 0.8, fill="currentColor", op=0.3)
    for (x, y, w, h) in [(0, 0, POD_W, 1), (0, 9, POD_W, 1), (0, 1, 1, 8), (24, 1, 1, 8)]:
        f.rect(X(x), Y(y), S * w, S * h, fill="currentColor", op=0.14)
    f.rect(X(3.5), Y(1.0), S * ELEC_LEN, S * 0.35, fill=COPPER, stroke=COPPER, sw=0.5)
    f.line(X(5), Y(1.35), X(5), Y(2.7), stroke=COPPER, sw=1.2)
    f.rect(X(2), Y(2.7), S * 21, S * 1.6, fill="currentColor", op=0.32, sw=0.8)
    f.rect(X(11), Y(1.9), S * 3, S * 0.8, fill="currentColor", op=0.55, sw=0.6)
    f.rect(X(2), Y(4.3), S * 21, S * 0.5, fill="currentColor", op=0.07, sop=0.5, dash="2 2")
    f.rect(X(1), Y(8), S * 17.8, S * 1, fill="currentColor", op=0.32, sw=0.8)
    f.rect(X(4), Y(6.3), S * 11, S * 1.7, fill="currentColor", op=0.45, sw=0.6)
    f.rect(X(8), Y(28.0), S * 9, S * 1.8, fill="currentColor", op=0.08, dash="4 3")
    f.circle(X(18.6), Y(28.6), 4, fill=ANALOG, op=0.45, stroke=ANALOG, dash="2 2")
    f.dim_h(X(0), X(POD_W), 34, "25 mm")
    f.dim_v(44, Y(0), Y(POD_H), "10 mm", side="left")
    f.balloon(300, 54, "P", X(25), Y(0.5))
    f.balloon(300, 82, "2", X(23), Y(3.5))
    f.balloon(300, 118, "1", X(18.8), Y(8.5))
    f.balloon(300, 222, "5", cx + S * 10.7, Y(21.5))
    f.balloon(300, 262, "12", X(18.6) + 3, Y(28.6) - 3)
    f.balloon(300, 298, "11", X(17), Y(29.4))
    return f


# ---------------------------------------------------------------------------------------------
# Figure 3: top view of the touch surface

def fig_top() -> Fig:
    f = Fig(430, 312, "top", "Top view of the lid: four 6 by 18 mm copper electrodes E0 to E3 in a "
            "row along the finger with 1.5 mm gaps; swipe along the row, tap or hold anywhere; "
            "USB-C slot at the hand end.")
    ox, oy = 50, 50

    def X(x):
        return ox + S * x

    def Y(y):
        return oy + S * y

    f.rect(X(0), Y(0), S * POD_L, S * POD_W, fill="currentColor", op=0.06, sw=1.2, rx=16)
    f.text(X(POD_L / 2), Y(2.3), "tap · double tap · hold: anywhere", size=11, anchor="middle",
           op=0.75)
    for i in range(4):
        x0 = ELEC_X0 + i * (ELEC_W + ELEC_GAP)
        f.rect(X(x0), Y(3.5), S * ELEC_W, S * ELEC_LEN, fill=COPPER, op=0.85, stroke=COPPER, sw=0.6)
        f.text(X(x0 + 3), Y(23.4), f"E{i}", size=11, anchor="middle", weight="600")
    f.rect(X(-0.6), Y(5.45), S * 0.6, S * 8.9, fill="currentColor", op=0.5, stroke="none", sw=0)
    f.text(X(-1.2), Y(10.3), "USB-C", size=11, anchor="end")
    f.dim_h(X(0), X(POD_L), 30, "34 mm")
    f.dim_v(X(POD_L) + 18, Y(0), Y(POD_W), "25 mm", side="right")
    f.line(X(3), 280, X(31), 280, sw=1.4, start="arrow", end="arrow")
    f.text(X(3) - 8, 284, "back", size=11, anchor="end")
    f.text(X(31) + 8, 284, "forward", size=11)
    f.text(X(POD_L / 2), 302, "swipe along the row of electrodes", size=11, anchor="middle", op=0.75)
    return f


# ---------------------------------------------------------------------------------------------
# Figure 4: wiring

XIAO_LEFT = ["D0 / A0", "D1", "D2", "D3", "D4 / SDA", "D5 / SCL", "D6"]
XIAO_RIGHT = ["5V", "GND", "3V3", "D10", "D9", "D8", "D7"]


def fig_wiring() -> Fig:
    f = Fig(880, 450, "wire", "Wiring: MPR121 IRQ, SDA and SCL go straight to XIAO D3, D4 and D5 and "
            "its electrodes E0 to E3 to the copper strips; the optional NTC divider uses D0 and D1, "
            "the optional MAX30102 shares the I2C bus with its interrupt on D8; the LiPo solders to "
            "the XIAO's battery pads.", y0=70)
    bx0, bx1, by0, by1 = 340, 580, 110, 400
    row = [150 + 36 * k for k in range(7)]
    # XIAO
    f.rect(bx0, by0, bx1 - bx0, by1 - by0, fill="currentColor", op=0.05, sw=1.4, rx=10)
    f.rect(430, 98, 60, 12, fill="currentColor", op=0.3, rx=3)
    f.text(460, 90, "USB-C", size=11, anchor="middle", op=0.8)
    f.text(460, 134, "XIAO nRF52840 Sense · #1", size=12.5, anchor="middle", weight="600")
    for k, name in enumerate(XIAO_LEFT):
        f.text(bx0 + 10, row[k] + 4, name, size=11, family="IBM Plex Mono, Menlo, monospace")
    for k, name in enumerate(XIAO_RIGHT):
        f.text(bx1 - 10, row[k] + 4, name, size=11, anchor="end",
               family="IBM Plex Mono, Menlo, monospace")
    for i, s in enumerate(["on board:", "IMU (tap check)", "PDM mic", "BLE radio", "LiPo charger"]):
        f.text(460, 254 + 18 * i, s, size=10.5, anchor="middle", op=0.65)
    used_left = {0: ANALOG, 1: ANALOG, 3: IRQ, 4: I2C, 5: I2C}
    used_right = {1: "currentColor", 2: POWER, 5: IRQ}
    for k, c in used_left.items():
        f.line(bx0, row[k], bx0 - 14, row[k], stroke=c, sw=1.6)
        f.circle(bx0 - 14, row[k], 2.2, fill=c, stroke="none", sw=0)
    for k, c in used_right.items():
        f.line(bx1, row[k], bx1 + 14, row[k], stroke=c, sw=1.6)
        f.circle(bx1 + 14, row[k], 2.2, fill=c, stroke="none", sw=0)
    f.tag(bx1 + 20, row[1], "GND", "currentColor", "right")
    f.line(bx1 + 14, row[1], bx1 + 20, row[1], sw=1.6)
    f.tag(bx1 + 20, row[2], "3V3", POWER, "right")
    f.line(bx1 + 14, row[2], bx1 + 20, row[2], stroke=POWER, sw=1.6)
    # battery pads and cell
    f.rect(424, 396, 12, 8, fill=POWER, stroke=POWER, sw=0.5)
    f.rect(484, 396, 12, 8, fill="currentColor", sw=0.5)
    f.line(430, 404, 430, 450, stroke=POWER, sw=2)
    f.line(490, 404, 490, 450, sw=2)
    f.text(424, 424, "BAT+", size=10.5, anchor="end", fill=POWER, weight="600")
    f.text(496, 424, "BAT−", size=10.5, weight="600")
    f.text(536, 424, "(underside pads)", size=10, op=0.6)
    f.rect(395, 450, 130, 48, fill="currentColor", op=0.06, rx=6)
    f.text(460, 470, "LiPo 401020 · #4", size=11, anchor="middle", weight="600")
    f.text(460, 488, "≥ 50 mAh, protected", size=10.5, anchor="middle", op=0.75)
    # MPR121
    mx0, mx1, my0, my1 = 110, 270, 210, 390
    f.rect(mx0, my0, mx1 - mx0, my1 - my0, fill="currentColor", op=0.05, sw=1.4, rx=8)
    f.text(190, 234, "MPR121 · #2", size=12.5, anchor="middle", weight="600")
    f.text(190, 250, "I2C 0x5B", size=11, anchor="middle", op=0.7)
    for name, k, c in [("IRQ", 3, IRQ), ("SDA", 4, I2C), ("SCL", 5, I2C)]:
        f.text(mx1 - 8, row[k] + 4, name, size=11, anchor="end",
               family="IBM Plex Mono, Menlo, monospace")
        f.line(mx1, row[k], bx0 - 14, row[k], stroke=c, sw=1.6)
    for x, name, net, c in [(150, "VCC", "3V3", POWER), (190, "ADDR", "3V3", POWER),
                            (230, "GND", "GND", "currentColor")]:
        f.text(x, my1 - 8, name, size=10.5, anchor="middle",
               family="IBM Plex Mono, Menlo, monospace")
        f.line(x, my1, x, my1 + 14, stroke=c, sw=1.6)
        f.tag(x, my1 + 14, net, c, "below")
    f.text(190, 446, "ADDR → 3V3 sets address 0x5B", size=10.5, anchor="middle", op=0.75)
    f.text(190, 364, "E4–E11 unused", size=10, anchor="middle", op=0.55)
    f.text(52, 222, "copper tape #3", size=10.5, anchor="middle", op=0.8)
    for i, y in enumerate([246, 276, 306, 336]):
        f.text(mx0 + 8, y + 4, f"E{i}", size=11, family="IBM Plex Mono, Menlo, monospace")
        f.line(mx0, y, 64, y, stroke=COPPER, sw=1.6)
        f.rect(40, y - 10, 24, 20, fill=COPPER, stroke=COPPER, sw=0.6, rx=2)
    f.text(52, 362, "under the lid", size=10.5, anchor="middle", op=0.8)
    # NTC divider (optional): D1 drives 3.3 V only while reading, A0 reads the midpoint
    n = (296, row[0])
    f.line(n[0], n[1], bx0 - 14, row[0], stroke=ANALOG, sw=1.6, dash="5 3")
    f.circle(n[0], n[1], 2.6, fill=ANALOG, stroke="none", sw=0)
    f.line(n[0], n[1], n[0], 156, stroke=ANALOG, sw=1.6, dash="5 3")
    f.rect(290, 156, 12, 24, stroke=ANALOG, sw=1.3)
    f.poly([(n[0], 180), (n[0], row[1]), (bx0 - 14, row[1])], stroke=ANALOG, sw=1.6, dash="5 3")
    f.text(284, 172, "10 kΩ · #13", size=10.5, anchor="end", fill=ANALOG)
    f.line(n[0], n[1], n[0], 136, stroke=ANALOG, sw=1.6, dash="5 3")
    f.rect(290, 112, 12, 24, stroke=ANALOG, sw=1.3)
    f.poly([(283, 140), (287, 140), (305, 108)], stroke=ANALOG, sw=1.1)
    f.line(n[0], 112, n[0], 100, stroke=ANALOG, sw=1.6, dash="5 3")
    f.tag(n[0], 84, "GND", "currentColor", "below")
    f.text(284, 128, "NTC 10k · #12", size=10.5, anchor="end", fill=ANALOG)
    # MAX30102 (optional)
    ax0, ax1, ay0, ay1 = 680, 840, 236, 400
    f.rect(ax0, ay0, ax1 - ax0, ay1 - ay0, fill="currentColor", op=0.03, sw=1.4, rx=8, dash="6 4")
    f.text(760, 258, "MAX30102 · #11", size=12.5, anchor="middle", weight="600")
    f.text(760, 274, "optional · I2C 0x57", size=11, anchor="middle", op=0.7)
    for name, y, c, flag in [("SDA", row[4], I2C, "SDA"), ("INT", row[5], IRQ, None),
                             ("SCL", row[6], I2C, "SCL")]:
        f.text(ax0 + 8, y + 4, name, size=11, family="IBM Plex Mono, Menlo, monospace")
        if flag:
            f.line(ax0, y, ax0 - 12, y, stroke=c, sw=1.6, dash="5 3")
            f.tag(ax0 - 12, y, flag, c, "left")
    f.line(bx1 + 14, row[5], ax0, row[5], stroke=IRQ, sw=1.6, dash="5 3")
    for x, name, net, c in [(720, "VIN", "3V3", POWER), (800, "GND", "GND", "currentColor")]:
        f.text(x, ay1 - 8, name, size=10.5, anchor="middle",
               family="IBM Plex Mono, Menlo, monospace")
        f.line(x, ay1, x, ay1 + 14, stroke=c, sw=1.6, dash="5 3")
        f.tag(x, ay1 + 14, net, c, "below")
    f.text(760, 456, "same I2C bus as the MPR121", size=10.5, anchor="middle", op=0.7)
    # legend
    leg = [(20, 482, POWER, None, "3V3 / battery +"), (160, 482, "currentColor", None, "GND"),
           (240, 482, I2C, None, "I2C (SDA, SCL)"), (20, 504, IRQ, None, "interrupt"),
           (160, 504, ANALOG, None, "analog"), (240, 504, "currentColor", "5 3",
                                                 "optional (health)")]
    for x, y, c, dash, s in leg:
        f.line(x, y - 4, x + 20, y - 4, stroke=c, sw=2, dash=dash)
        f.text(x + 26, y, s, size=10.5)
    return f


# ---------------------------------------------------------------------------------------------
# Parts list

SECTIONS = [
    ("ring", "The ring", "Required. Everything in the drawing except the printed pod."),
    ("health", "Health add-on", "Optional. Populate after the cheap-ring accuracy check."),
    ("check", "Accuracy check first", "Optional. Tells you whether cheap finger PPG is good enough "
                                      "before you build the add-on (docs/11 section 6)."),
    ("bench", "Bench testing", "Breadboard everything before it goes in the pod."),
    ("tools", "Tools", "Skip what you already own."),
]


def load_parts() -> list[dict]:
    with open(CSV_PATH, newline="") as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        r["qty"] = int(r["qty"])
        r["lo"] = float(r["usd_each_low"])
        r["hi"] = float(r["usd_each_high"])
    return rows


def money(lo: float, hi: float) -> str:
    return f"${lo:.0f}–{hi:.0f}"


def section_total(rows, key) -> tuple[float, float]:
    sel = [r for r in rows if r["section"] == key]
    return sum(r["qty"] * r["lo"] for r in sel), sum(r["qty"] * r["hi"] for r in sel)


def parts_html(rows) -> str:
    out = []
    for key, title, blurb in SECTIONS:
        lo, hi = section_total(rows, key)
        out.append(f'<section class="psec" aria-labelledby="h-{key}">'
                   f'<div class="psec-head"><h3 id="h-{key}">{esc(title)}</h3>'
                   f'<span class="sub">≈ {money(lo, hi)}</span></div>'
                   f'<p class="note">{esc(blurb)}</p>'
                   f'<div class="tablewrap"><table class="parts"><thead><tr>'
                   f'<th scope="col"><span class="sr">Bought</span></th><th scope="col">#</th>'
                   f'<th scope="col">Qty</th><th scope="col">Part and what to check</th>'
                   f'<th scope="col">Search AliExpress</th><th scope="col" class="num">≈ each</th>'
                   f'</tr></thead><tbody>')
        for r in [r for r in rows if r["section"] == key]:
            term = r["search_aliexpress"]
            url = "https://www.aliexpress.com/wholesale?SearchText=" + urllib.parse.quote_plus(term)
            out.append(
                f'<tr data-item="{esc(r["item"])}" data-qty="{r["qty"]}" data-lo="{r["lo"]}" '
                f'data-hi="{r["hi"]}" data-section="{key}">'
                f'<td><input type="checkbox" id="got-{esc(r["item"])}" '
                f'aria-label="Bought item {esc(r["item"])}"></td>'
                f'<td class="itemno">{esc(r["item"])}</td><td class="num">{r["qty"]}</td>'
                f'<td class="what"><strong>{esc(r["part"])}</strong>'
                f'<span class="check">{esc(r["check_in_listing"])}</span>'
                f'<span class="use">{esc(r["used_for"])}</span></td>'
                f'<td class="search"><code>{esc(term)}</code>'
                f'<span class="acts"><button type="button" class="copy" data-term="{esc(term)}">'
                f'Copy</button><a href="{esc(url)}" target="_blank" rel="noopener">Open</a></span>'
                f'</td><td class="num">{money(r["lo"], r["hi"])}</td></tr>')
        out.append("</tbody></table></div></section>")
    return "".join(out)


PIN_TABLE = [
    ("3V3", "MPR121 VCC and ADDR; MAX30102 VIN", "3.3 V supply; ADDR to 3V3 moves the MPR121 to 0x5B"),
    ("GND", "MPR121 GND, MAX30102 GND, NTC", ""),
    ("D4 / SDA", "MPR121 SDA, MAX30102 SDA", "I2C data"),
    ("D5 / SCL", "MPR121 SCL, MAX30102 SCL", "I2C clock"),
    ("D3", "MPR121 IRQ", "Low when a touch changes"),
    ("D8", "MAX30102 INT (optional)", "Sample ready"),
    ("D0 / A0", "NTC divider midpoint (optional)", "Skin-temperature reading"),
    ("D1", "Top of the 10 kΩ resistor (optional)", "Driven high only while reading, so the divider "
                                                    "draws nothing between readings"),
    ("BAT+ / BAT−", "LiPo red / black", "Pads on the XIAO's underside; the XIAO charges the cell "
                                        "from USB-C"),
    ("On board", "IMU, PDM mic", "No wiring: the IMU confirms taps, the mic can take the voice ask"),
]


def pin_table_html() -> str:
    rows = "".join(f"<tr><td><code>{esc(a)}</code></td><td>{esc(b)}</td><td>{esc(c)}</td></tr>"
                   for a, b, c in PIN_TABLE)
    return ('<div class="tablewrap"><table class="pins"><thead><tr><th scope="col">XIAO pin</th>'
            '<th scope="col">Connects to</th><th scope="col">Why</th></tr></thead>'
            f"<tbody>{rows}</tbody></table></div>")


# ---------------------------------------------------------------------------------------------
# Page

CSS = """
/* Layout: one reading column of drawing sheets; figures and tables scroll sideways on phones. */
:root {
  --bg: #f1f4f2; --surface: #ffffff; --fg: #17201c; --muted: #5a6661; --rule: #d3dbd6;
  --accent: #a85a24; --accent-soft: #f4e6db; --done: #2f7a55;
  --font-display: "IBM Plex Sans Condensed", "Arial Narrow", Arial, sans-serif;
  --font-body: "IBM Plex Sans", "Helvetica Neue", Arial, sans-serif;
  --font-mono: "IBM Plex Mono", Menlo, Consolas, monospace;
}
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --bg: #0f1311; --surface: #161b18; --fg: #e1e7e3; --muted: #97a39d; --rule: #29312d;
  --accent: #e0935a; --accent-soft: #2a1f17; --done: #6cc196; color-scheme: dark; } }
:root[data-theme="dark"] {
  --bg: #0f1311; --surface: #161b18; --fg: #e1e7e3; --muted: #97a39d; --rule: #29312d;
  --accent: #e0935a; --accent-soft: #2a1f17; --done: #6cc196; color-scheme: dark; }
* { box-sizing: border-box; }
body { background: var(--bg); color: var(--fg); font-family: var(--font-body); font-size: 15px;
  line-height: 1.55; padding-left: max(16px, env(safe-area-inset-left, 0px));
  padding-right: max(16px, env(safe-area-inset-right, 0px)); padding-block: 28px 56px; }
.wrap { max-width: 1080px; margin: 0 auto; display: flex; flex-direction: column; gap: 44px; }
h1, h2, h3 { font-family: var(--font-display); text-wrap: balance; margin: 0; line-height: 1.15; }
h1 { font-size: clamp(30px, 5vw, 44px); font-weight: 600; letter-spacing: -0.01em; }
h2 { font-size: 24px; font-weight: 600; }
h3 { font-size: 18px; font-weight: 600; }
p { margin: 0; }
.eyebrow { font-family: var(--font-mono); font-size: 12px; letter-spacing: 0.08em;
  text-transform: uppercase; color: var(--accent); }
header { display: flex; flex-direction: column; gap: 14px; border-bottom: 2px solid var(--fg);
  padding-bottom: 22px; }
.lede { max-width: 68ch; color: var(--fg); font-size: 16px; }
.facts { display: flex; flex-wrap: wrap; gap: 8px 28px; margin: 4px 0 0; }
.facts div { display: flex; flex-direction: column; }
.facts dt { font-family: var(--font-mono); font-size: 11px; letter-spacing: 0.06em;
  text-transform: uppercase; color: var(--muted); }
.facts dd { margin: 0; font-family: var(--font-display); font-size: 20px; font-weight: 600;
  font-variant-numeric: tabular-nums; }
section.block { display: flex; flex-direction: column; gap: 16px; }
.block > p { max-width: 70ch; color: var(--muted); }
.figs { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }
.figs .wide { grid-column: 1 / -1; }
figure { margin: 0; background: var(--surface); border: 1px solid var(--rule); border-radius: 6px;
  display: flex; flex-direction: column; min-width: 0; }
.dwgbox { overflow-x: auto; padding: 14px 14px 4px; }
svg.dwg { display: block; width: 100%; height: auto; color: var(--fg);
  font-family: var(--font-body); }
.dwg-side { min-width: 520px; } .dwg-end { min-width: 300px; } .dwg-top { min-width: 400px; }
.dwg-wire { min-width: 760px; }
figcaption { padding: 10px 16px 14px; font-size: 13.5px; color: var(--muted);
  border-top: 1px solid var(--rule); }
figcaption b { color: var(--fg); font-weight: 600; }
.key { display: flex; flex-wrap: wrap; gap: 6px 18px; font-size: 13.5px; }
.key span { white-space: nowrap; }
.key b { display: inline-grid; place-items: center; min-width: 22px; height: 22px; padding: 0 5px;
  border: 1.2px solid var(--fg); border-radius: 11px; font-size: 11.5px; margin-right: 6px;
  font-variant-numeric: tabular-nums; }
.tablewrap { overflow-x: auto; background: var(--surface); border: 1px solid var(--rule);
  border-radius: 6px; }
table { border-collapse: collapse; width: 100%; font-size: 14px; }
th { text-align: left; font-family: var(--font-mono); font-weight: 500; font-size: 11px;
  letter-spacing: 0.06em; text-transform: uppercase; color: var(--muted); padding: 10px 12px;
  border-bottom: 1px solid var(--rule); white-space: nowrap; }
td { padding: 11px 12px; border-bottom: 1px solid var(--rule); vertical-align: top; }
tbody tr:last-child td { border-bottom: 0; }
td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
td code, .search code { font-family: var(--font-mono); font-size: 12.5px; }
table.pins td:first-child { white-space: nowrap; }
table.parts { min-width: 760px; }
.itemno { font-family: var(--font-mono); font-weight: 600; color: var(--accent); }
.what strong { display: block; font-weight: 600; }
.what .check { display: block; color: var(--fg); font-size: 13.5px; margin-top: 3px; }
.what .use { display: block; color: var(--muted); font-size: 12.5px; margin-top: 3px; }
.search { min-width: 210px; }
.search code { display: block; overflow-wrap: anywhere; }
.acts { display: flex; gap: 8px; margin-top: 6px; }
.acts button, .acts a { font: 500 12px var(--font-body); color: var(--accent);
  background: transparent; border: 1px solid var(--accent); border-radius: 4px; padding: 3px 9px;
  text-decoration: none; cursor: pointer; }
.acts button:hover, .acts a:hover { background: var(--accent-soft); }
:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
input[type="checkbox"] { width: 18px; height: 18px; accent-color: var(--done); margin: 2px 0 0; }
tr.got td { opacity: 0.5; } tr.got td:first-child { opacity: 1; }
tr.got .what strong { text-decoration: line-through; }
.psec { display: flex; flex-direction: column; gap: 8px; }
.psec-head { display: flex; align-items: baseline; justify-content: space-between; gap: 12px;
  flex-wrap: wrap; }
.psec-head .sub { font-family: var(--font-mono); font-size: 13px; color: var(--muted);
  font-variant-numeric: tabular-nums; }
.note { color: var(--muted); font-size: 13.5px; }
.status { display: flex; flex-wrap: wrap; align-items: baseline; gap: 6px 20px; padding: 14px 16px;
  background: var(--accent-soft); border-radius: 6px; }
.status strong { font-family: var(--font-display); font-size: 20px; font-variant-numeric: tabular-nums; }
.status span { color: var(--muted); font-size: 13.5px; }
.status button { margin-left: auto; font: 500 12.5px var(--font-body); color: var(--fg);
  background: transparent; border: 1px solid var(--rule); border-radius: 4px; padding: 4px 10px;
  cursor: pointer; }
.cols { display: grid; grid-template-columns: minmax(0, 3fr) minmax(0, 2fr); gap: 28px; }
ol.steps { margin: 0; padding-left: 22px; display: flex; flex-direction: column; gap: 10px;
  max-width: 70ch; }
ol.steps li::marker { font-family: var(--font-mono); color: var(--accent); }
ul.gotchas { margin: 0; padding: 14px 18px 14px 34px; background: var(--surface);
  border: 1px solid var(--rule); border-radius: 6px; display: flex; flex-direction: column;
  gap: 8px; font-size: 14px; }
footer { color: var(--muted); font-size: 13px; border-top: 1px solid var(--rule); padding-top: 16px;
  display: flex; flex-direction: column; gap: 6px; max-width: 80ch; }
.sr { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); }
@media (max-width: 760px) { .figs { grid-template-columns: minmax(0, 1fr); }
  .cols { grid-template-columns: minmax(0, 1fr); } }
"""

JS = """
(function () {
  var KEY = "touch-ring-bought-v1";
  var saved = {};
  try { saved = JSON.parse(localStorage.getItem(KEY) || "{}") || {}; } catch (e) { saved = {}; }
  var rows = Array.prototype.slice.call(document.querySelectorAll("table.parts tbody tr"));
  function fmt(n) { return "$" + Math.round(n); }
  function update() {
    var lo = 0, hi = 0, n = 0, ringLo = 0, ringHi = 0, ringN = 0;
    rows.forEach(function (r) {
      var box = r.querySelector("input");
      r.classList.toggle("got", box.checked);
      if (box.checked) return;
      var q = +r.dataset.qty, l = q * +r.dataset.lo, h = q * +r.dataset.hi;
      lo += l; hi += h; n += 1;
      if (r.dataset.section === "ring") { ringLo += l; ringHi += h; ringN += 1; }
    });
    document.getElementById("left-all").textContent = n ? fmt(lo) + "–" + fmt(hi).slice(1) : "nothing";
    document.getElementById("left-all-n").textContent = n + (n === 1 ? " item" : " items") + " left in total";
    document.getElementById("left-ring").textContent = ringN
      ? "The ring alone: " + fmt(ringLo) + "–" + fmt(ringHi).slice(1) + " for " + ringN + (ringN === 1 ? " item" : " items")
      : "Everything for the ring is ticked off";
  }
  rows.forEach(function (r) {
    var box = r.querySelector("input");
    box.checked = !!saved[r.dataset.item];
    box.addEventListener("change", function () {
      saved[r.dataset.item] = box.checked;
      try { localStorage.setItem(KEY, JSON.stringify(saved)); } catch (e) {}
      update();
    });
  });
  document.getElementById("reset").addEventListener("click", function () {
    saved = {};
    try { localStorage.removeItem(KEY); } catch (e) {}
    rows.forEach(function (r) { r.querySelector("input").checked = false; });
    update();
  });
  Array.prototype.forEach.call(document.querySelectorAll("button.copy"), function (b) {
    b.addEventListener("click", function () {
      var term = b.dataset.term;
      function done(t) { b.textContent = t; setTimeout(function () { b.textContent = "Copy"; }, 1400); }
      function fallback() {
        var code = b.closest("td").querySelector("code");
        var range = document.createRange(); range.selectNodeContents(code);
        var sel = window.getSelection(); sel.removeAllRanges(); sel.addRange(range);
        done("Selected");
      }
      try {
        navigator.clipboard.writeText(term).then(function () { done("Copied"); }, fallback);
      } catch (e) { fallback(); }
    });
  });
  update();
})();
"""


def page(side: Fig, end: Fig, top: Fig, wire: Fig, rows) -> str:
    ring_lo, ring_hi = section_total(rows, "ring")
    all_lo = sum(r["qty"] * r["lo"] for r in rows)
    all_hi = sum(r["qty"] * r["hi"] for r in rows)
    key = [("1", "XIAO nRF52840 Sense"), ("2", "MPR121 touch module"), ("3", "copper electrodes"),
           ("4", "LiPo 401020"), ("5", "adjustable ring blank"), ("6", "foam tape"),
           ("11", "MAX30102 (optional)"), ("12", "NTC (optional)"), ("P", "printed pod and lid")]
    key_html = "".join(f"<span><b>{esc(a)}</b>{esc(b)}</span>" for a, b in key)
    return f"""<title>Touch Ring Build Sheet</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans+Condensed:wght@500;600&family=IBM+Plex+Sans:wght@400;500;600&display=swap">
<style>{CSS}</style>
<div class="wrap">
<header>
  <p class="eyebrow">mcring · R1-class touch ring · oversized prototype</p>
  <h1>Touch Ring Build Sheet</h1>
  <p class="lede">A Seeed XIAO nRF52840 Sense and an MPR121 touch module in a small printed pod,
  glued to an adjustable steel ring blank. Four copper-tape electrodes under the lid give tap,
  double tap, hold and swipe. Every part except the pod comes from AliExpress. The circled
  numbers in the drawings are the item numbers in the parts list.</p>
  <dl class="facts">
    <div><dt>Ring parts</dt><dd>≈ {money(ring_lo, ring_hi)}</dd></div>
    <div><dt>Everything listed</dt><dd>≈ {money(all_lo, all_hi)}</dd></div>
    <div><dt>Pod</dt><dd>34 × 25 × 10 mm</dd></div>
    <div><dt>Gestures</dt><dd>tap · double · hold · swipe</dd></div>
  </dl>
</header>

<section class="block" aria-labelledby="h-dwg">
  <h2 id="h-dwg">How it goes together</h2>
  <p>Drawn to scale at 8 px per mm on a size 10 band (19.8 mm inside). The pod sits on the back of
  the finger with its long side along the finger; the USB-C end faces the hand. The finger is
  drawn small enough to leave room for the optional heart-rate sensor, which needs the band about
  one size larger than you would otherwise wear.</p>
  <div class="figs">
    <figure class="wide"><div class="dwgbox">{side.svg(False)}</div>
      <figcaption><b>Side section.</b> Copper electrodes under a 1 mm plastic lid, the MPR121 just
      below them, then the XIAO and the LiPo side by side on the floor. The pod is glued to the
      blank's flat pad. Dashed: the optional heart-rate sensor and thermistor inside the band,
      with their wires running up the band into the pod.</figcaption></figure>
    <figure><div class="dwgbox">{end.svg(False)}</div>
      <figcaption><b>End view</b>, looking along the finger. The steel band sits more than 10 mm
      below the electrodes, which is far enough not to swamp the touch signal.</figcaption></figure>
    <figure><div class="dwgbox">{top.svg(False)}</div>
      <figcaption><b>Lid from above.</b> Four 6 × 18 mm strips with 1.5 mm gaps. A swipe crosses
      them in order; a tap or hold covers one or two at once.</figcaption></figure>
  </div>
  <div class="key" aria-label="Balloon key">{key_html}</div>
</section>

<section class="block" aria-labelledby="h-wire">
  <h2 id="h-wire">Wiring</h2>
  <p>Ten connections for the ring, seven more for the optional health parts. Net tags (3V3, GND,
  SDA, SCL) connect to the XIAO pin with the same name.</p>
  <figure><div class="dwgbox">{wire.svg(False)}</div>
    <figcaption><b>Schematic.</b> The MPR121's interrupt and I2C lines run straight across to D3,
    D4 and D5. Its ADDR pin goes to 3V3, which moves it to address 0x5B and keeps 0x5A free for the
    bench haptic driver. The battery solders to the pads under the XIAO, which charges it from
    USB-C.</figcaption></figure>
  {pin_table_html()}
</section>

<section class="block" aria-labelledby="h-parts">
  <h2 id="h-parts">Parts to order</h2>
  <p>Prices are rough AliExpress ranges, not quotes: listings couldn't be opened while this sheet
  was made, so check each listing against the second line of its row. Tick items off as you buy
  them; the ticks stay in this browser only.</p>
  <div class="status" role="status">
    <strong id="left-all">≈ {money(all_lo, all_hi)}</strong>
    <span id="left-all-n">{len(rows)} items left in total</span>
    <span id="left-ring">The ring alone: {money(ring_lo, ring_hi)}</span>
    <button type="button" id="reset">Clear ticks</button>
  </div>
  {parts_html(rows)}
  <p class="note">Not from AliExpress: the pod (34 × 25 × 10 mm outside, 1 mm walls and lid, a
  USB-C slot in one end), printed in resin by JLC3DP or any local printer. The IQS7211E touch chip
  for the later custom board comes from DigiKey or LCSC, not AliExpress.</p>
</section>

<section class="block" aria-labelledby="h-build">
  <h2 id="h-build">Assembly order</h2>
  <div class="cols">
    <ol class="steps">
      <li>Bench first. XIAO on the breadboard; MPR121 by jumpers (3V3, GND, D4, D5, D3, ADDR to 3V3).
      An I2C scan should show 0x5B. Tape four copper strips to a card and check each one
      registers.</li>
      <li>Print the pod. The lid must be plastic: metal over the electrodes kills the touch
      signal.</li>
      <li>Electrodes: four 6 × 18 mm copper strips on the underside of the lid, 1.5 mm apart.
      Solder a short 30 AWG lead to the end of each.</li>
      <li>Battery: check polarity with the meter, solder red to BAT+ and black to BAT− under the
      XIAO, then cover the joints and the cell with Kapton. Plug in USB-C; the charge LED
      lights.</li>
      <li>Fit: XIAO on the floor with USB-C in the slot, cell beside it, foam tape over both,
      MPR121 on the foam, leads to E0–E3, lid on. Tack everything with UV resin.</li>
      <li>Glue the pod to the blank's pad, centred on the band, and size the band to your
      finger.</li>
      <li>Optional health: MAX30102 inside the band on the palm side with the NTC beside it,
      under a thin clear resin window. Run the wires up the side of the band into the pod
      through a 2 mm hole in the floor beside the pad.</li>
    </ol>
    <ul class="gotchas" aria-label="Checks before you power it">
      <li>The MPR121 and the DRV2605L both default to 0x5A. ADDR to 3V3 fixes it.</li>
      <li>The XIAO charges at 50 mA by default, so the cell must be at least 50 mAh.</li>
      <li>Many purple MAX30102 boards pull I2C up to 1.8 V; the XIAO won't read them.</li>
      <li>Never use a cell without its protection board, and never bend or pierce one.</li>
      <li>Firmware is the next step: read the MPR121, confirm taps with the IMU, send BLE HID
      and mcring events.</li>
    </ul>
  </div>
</section>

<footer>
  <p>Source: <code>hardware/touch-ring/build_sheet.py</code> in the mcring repo draws these figures
  and this page from <code>hardware/bom/touch-ring-aliexpress.csv</code>. Background and the
  production design: <code>docs/11-touch-ring-r1-class.md</code>.</p>
  <p>Sizes of AliExpress modules vary by seller; measure yours before printing the pod.</p>
</footer>
</div>
<script>{JS}</script>
"""


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    side, end, top, wire = fig_side(), fig_end(), fig_top(), fig_wiring()
    for name, fig in [("ring-side-section", side), ("ring-end-view", end), ("ring-top-view", top),
                      ("ring-wiring", wire)]:
        with open(os.path.join(OUT, f"{name}.svg"), "w") as fh:
            fh.write(fig.svg(True) + "\n")
    rows = load_parts()
    with open(PAGE, "w") as fh:
        fh.write(page(side, end, top, wire, rows))
    print(f"wrote {OUT}/*.svg and {os.path.relpath(PAGE, ROOT)}")


if __name__ == "__main__":
    main()
