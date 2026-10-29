#!/usr/bin/env python3
"""Touch-ring build sheet: everything inside the band.

One flex circuit wraps around the inside of the band, a curved 15-20 mAh cell fills the rest,
and a resin (later ceramic) outer wall covers the touch strip; clear epoxy forms the inner
surface. Nothing sits on top of the ring.

Reads hardware/bom/touch-ring-parts.csv. Writes standalone SVGs to hardware/touch-ring/out/ and
the published page docs/touch-ring-build.html (the same drawings inlined, theme-aware).
Geometry is in millimetres for a size 10 ring; balloon numbers are the CSV item numbers.

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
CSV_PATH = os.path.join(ROOT, "hardware", "bom", "touch-ring-parts.csv")
OUT = os.path.join(HERE, "out")
PAGE = os.path.join(ROOT, "docs", "touch-ring-build.html")

# The only literal hues; each reads on light and dark grounds. Everything else is currentColor.
COPPER = "#c8742e"   # touch slider
GOLD = "#b8922a"     # charge contacts
POWER = "#d64541"    # 3V0 and battery +
I2C = "#3f82d6"      # SDA / SCL
IRQ = "#9061d4"      # interrupt lines
ANALOG = "#1f9e89"   # NTC and battery sense
MONO = "IBM Plex Mono, Menlo, monospace"

# Band geometry (mm), size 10 (19.8 mm inside diameter). Radii from the ring's centre.
R_IN = 9.9           # inner surface (clear epoxy skin)
R_FLEX_IN = 12.05    # inner face of the flex, where parts are mounted
R_FLEX_OUT = 12.17   # 0.12 mm two-layer flex; slider copper on this face
R_OUT = 12.8         # outer surface; 0.63 mm resin wall over the slider
BAND_W, SIDE_WALL, FLEX_W = 8.4, 0.6, 6.6
FLEX_T0, FLEX_T1 = -40.0, 210.0          # the flex is a C from -40 deg to 210 deg (0 = top)
BAT_T0, BAT_T1, BAT_R0, BAT_R1 = 210.0, 323.5, 10.4, 12.0
SLIDER_T0, SLIDER_T1, SLIDER_GAP = -36.0, 36.0, 2.0
KEEPOUT = (37.5, 46.5)                   # no copper near the module's antenna end
R_MID = (R_FLEX_IN + R_FLEX_OUT) / 2
FLEX_LEN = math.radians(FLEX_T1 - FLEX_T0) * R_MID   # ~52.8 mm

# Parts on the inner face of the flex: (key, angle, length along band, width across, height)
PARTS = {
    "iqs": (-14.0, 3.0, 3.0, 0.55),
    "acc": (12.0, 2.0, 2.0, 0.7),
    "ldo": (28.0, 2.9, 1.6, 1.1),
    "ble": (63.0, 6.5, 6.5, 1.2),
    "chg": (100.0, 1.6, 0.9, 0.5),
    "dio": (108.0, 1.6, 0.8, 0.6),
    "ntc": (145.0, 1.0, 0.5, 0.5),
    "ppg": (180.0, 5.6, 3.3, 1.55),
}
CONTACTS = (157.0, 203.0)
SWD = (116.0, 123.0, 130.0, 137.0)


def esc(s: str) -> str:
    return html.escape(s, quote=True)


def slider_segments():
    w = (SLIDER_T1 - SLIDER_T0 - 3 * SLIDER_GAP) / 4
    return [(SLIDER_T0 + i * (w + SLIDER_GAP), SLIDER_T0 + i * (w + SLIDER_GAP) + w) for i in range(4)]


class Fig:
    """Minimal SVG accumulator. Coordinates in px; callers convert from mm."""

    def __init__(self, w: float, h: float, ident: str, label: str, y0: float = 0.0):
        self.w, self.h, self.ident, self.label, self.y0 = w, h, ident, label, y0
        self.items: list[str] = []

    def add(self, s: str) -> None:
        self.items.append(s)

    @staticmethod
    def _style(fill, op, stroke, sw, dash, sop):
        a = [f'fill="{fill}"']
        if op is not None:
            a.append(f'fill-opacity="{op}"')
        a.append(f'stroke="{stroke}" stroke-width="{sw}"')
        if sop is not None:
            a.append(f'stroke-opacity="{sop}"')
        if dash:
            a.append(f'stroke-dasharray="{dash}"')
        return " ".join(a)

    def rect(self, x, y, w, h, fill="none", op=None, stroke="currentColor", sw=1.0, rx=0.0,
             dash=None, sop=None, rotate=None) -> None:
        t = f' transform="rotate({rotate[0]:.2f} {rotate[1]:.1f} {rotate[2]:.1f})"' if rotate else ""
        r = f' rx="{rx:.1f}"' if rx else ""
        self.add(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}"{r} '
                 f'{self._style(fill, op, stroke, sw, dash, sop)}{t}/>')

    def path(self, d, fill="none", op=None, stroke="currentColor", sw=1.0, dash=None, sop=None):
        self.add(f'<path d="{d}" {self._style(fill, op, stroke, sw, dash, sop)}/>')

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

    def poly(self, pts, stroke="currentColor", sw=1.0, dash=None, fill="none") -> None:
        p = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        d = f' stroke-dasharray="{dash}"' if dash else ""
        self.add(f'<polyline points="{p}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" '
                 f'stroke-linejoin="round" stroke-linecap="round"{d}/>')

    def circle(self, cx, cy, r, fill="none", op=None, stroke="currentColor", sw=1.0, dash=None,
               sop=None) -> None:
        self.add(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" '
                 f'{self._style(fill, op, stroke, sw, dash, sop)}/>')

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
        self.line(x1, y, x2, y, sw=0.8)
        self.line(x1, y - 5, x1, y + 5, sw=0.8)
        self.line(x2, y - 5, x2, y + 5, sw=0.8)
        self.text((x1 + x2) / 2, y + 15, label, size=11, anchor="middle", op=0.8)

    def dim_v(self, x, y1, y2, label) -> None:
        self.line(x, y1, x, y2, sw=0.8)
        self.line(x - 5, y1, x + 5, y1, sw=0.8)
        self.line(x - 5, y2, x + 5, y2, sw=0.8)
        self.text(x - 8, (y1 + y2) / 2 + 4, label, size=11, anchor="end", op=0.8)

    def tag(self, x, y, label, color, where) -> None:
        """Net label attached at (x, y); `where` is the side of the attach point it sits on."""
        w, h = 8 + 6.6 * len(label), 16
        if where == "below":
            bx, by = x - w / 2, y
        elif where == "above":
            bx, by = x - w / 2, y - h
        elif where == "right":
            bx, by = x, y - h / 2
        else:  # left
            bx, by = x - w, y - h / 2
        self.rect(bx, by, w, h, rx=3, stroke=color, sw=1.1)
        self.text(bx + w / 2, by + 11.5, label, size=10.5, anchor="middle", fill=color, weight="600")

    def svg(self, standalone: bool) -> str:
        defs = (f'<defs><marker id="{self.ident}-arrow" viewBox="0 0 10 10" refX="9" refY="5" '
                f'markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
                f'<path d="M0,0 L10,5 L0,10 z" fill="currentColor"/></marker></defs>')
        head = (f'<svg viewBox="0 {self.y0:.0f} {self.w:.0f} {self.h:.0f}" role="img" '
                f'aria-label="{esc(self.label)}" class="dwg dwg-{self.ident}" '
                f'font-family="IBM Plex Sans, Helvetica, Arial, sans-serif"')
        if standalone:
            head += ' xmlns="http://www.w3.org/2000/svg" color="#18211d"'
            body = (f'<rect x="0" y="{self.y0:.0f}" width="{self.w:.0f}" height="{self.h:.0f}" '
                    f'fill="#ffffff"/>'
                    + "".join(self.items))
        else:
            body = "".join(self.items)
        return f"{head}>{defs}{body}</svg>"


# ---------------------------------------------------------------------------------------------
# Figure 1: end view, looking along the finger from the fingertip (0 deg = back of the hand)

def fig_end() -> Fig:
    f = Fig(700, 545, "end", "End view of the ring with everything inside the band: the flex "
            "circuit runs from minus 40 to 210 degrees just under the outer wall, carrying the "
            "touch slider on its outer face and the touch controller, accelerometer, regulator, "
            "Bluetooth module and charger on its inner face; the curved battery fills the left "
            "side; charge contacts and the optional heart-rate sensor sit at the palm side.")
    S, cx, cy = 13.0, 345.0, 280.0

    def P(r, th):
        a = math.radians(th)
        return cx + S * r * math.sin(a), cy - S * r * math.cos(a)

    def sector(r1, r2, t1, t2, **kw):
        large = 1 if (t2 - t1) % 360 > 180 else 0
        (x1, y1), (x2, y2) = P(r2, t1), P(r2, t2)
        (x3, y3), (x4, y4) = P(r1, t2), P(r1, t1)
        f.path(f"M{x1:.1f},{y1:.1f} A{S * r2:.1f},{S * r2:.1f} 0 {large} 1 {x2:.1f},{y2:.1f} "
               f"L{x3:.1f},{y3:.1f} A{S * r1:.1f},{S * r1:.1f} 0 {large} 0 {x4:.1f},{y4:.1f} Z", **kw)

    def chip(th, length, height, r_top=R_FLEX_IN, **kw):
        top = math.sqrt(r_top ** 2 - (length / 2) ** 2)   # flat part on the curved flex
        f.rect(cx - S * length / 2, cy - S * top, S * length, S * height,
               rotate=(th, cx, cy), **kw)

    f.circle(cx, cy, S * 9.6, fill="currentColor", op=0.05, stroke="none", sw=0)
    f.text(cx, cy + 4, "finger", size=12, anchor="middle", op=0.55)
    f.circle(cx, cy, S * (R_IN + R_FLEX_IN) / 2, stroke="currentColor", sw=S * (R_FLEX_IN - R_IN),
             sop=0.06)
    f.circle(cx, cy, S * (R_FLEX_OUT + R_OUT) / 2, stroke="currentColor",
             sw=S * (R_OUT - R_FLEX_OUT), sop=0.22)
    f.circle(cx, cy, S * R_OUT, sw=1)
    f.circle(cx, cy, S * R_IN, sw=0.8)
    sector(R_FLEX_OUT, R_OUT, KEEPOUT[0], KEEPOUT[1], fill="none", sw=1, dash="2 2")
    sector(R_FLEX_IN, R_FLEX_OUT, FLEX_T0, FLEX_T1, fill="currentColor", op=0.6, sw=0.4)
    for t1, t2 in slider_segments():
        sector(R_FLEX_OUT, R_FLEX_OUT + 0.2, t1, t2, fill=COPPER, stroke=COPPER, sw=0.4)
    sector(BAT_R0, BAT_R1, BAT_T0, BAT_T1, fill="currentColor", op=0.24, sw=1)
    bx, by = P(11.2, 270)
    f.text(bx, by + 3.5, "LiPo", size=9.5, anchor="middle", op=0.85)
    for key, (th, length, _w, height) in PARTS.items():
        if key == "ppg":
            continue
        style = dict(fill="currentColor", op=0.45, sw=0.8)
        if key == "ntc":
            style = dict(fill=ANALOG, op=0.5, stroke=ANALOG, sw=0.8, dash="2 1.5")
        chip(th, length, height, **style)
    chip(180.0, 5.6, 1.55, fill="currentColor", op=0.1, sw=1, dash="4 3")
    top = math.sqrt(R_FLEX_IN ** 2 - 2.8 ** 2) - 1.55
    f.rect(cx - S * 2.0, cy - S * top, S * 4.0, S * (top - R_IN), rotate=(180, cx, cy),
           fill="none", sw=0.8, dash="2 2")
    for th in CONTACTS:
        chip(th, 0.8, R_FLEX_IN - R_IN, fill=GOLD, stroke=GOLD, sw=0.5)
    for th in SWD:
        x, y = P(R_FLEX_IN - 0.15, th)
        f.circle(x, y, 2.4, fill="currentColor", stroke="none", sw=0)
    # labels and balloons
    f.text(cx, 30, "top: back of the hand", size=11.5, anchor="middle", op=0.75)
    f.text(cx, 46, "touch slider S0–S3 under the outer wall", size=11.5, anchor="middle",
           fill=COPPER, weight="600")
    f.text(cx, 538, "palm side", size=11.5, anchor="middle", op=0.75)
    kx, ky = P(R_OUT + 1.6, 42.5)
    f.text(kx + 6, ky - 6, "antenna keep-out", size=10.5, op=0.75)
    sx, sy = P(R_OUT + 3.2, 128)
    f.text(sx + 4, sy + 4, "SWD test pads", size=10.5, op=0.75)
    rb = 15.6
    for num, th_b, th_t, r_t in [("3", -20, -14, 11.7), ("4", 6, 12, 11.6), ("6", 28, 28, 11.4),
                                 ("2", 63, 63, 11.1), ("1", 88, 88, R_MID), ("5", 103, 100, 11.8),
                                 ("12", 300, 300, 12.5), ("10", 262, 262, 11.2),
                                 ("13", 232, 232, 10.15), ("16", 146, 145, 11.6),
                                 ("11", 160, 157, 10.6), ("14", 180, 180, 10.9),
                                 ("11", 200, 203, 10.6)]:
        bxp, byp = P(rb, th_b)
        txp, typ = P(r_t, th_t)
        f.balloon(bxp, byp, num, txp, typ)
    return f


# ---------------------------------------------------------------------------------------------
# Figure 2: cuts across the band at the top, the side and the palm

def fig_sections() -> Fig:
    f = Fig(850, 236, "sec", "Three cuts across the band, 8.4 mm wide and 2.9 mm thick: at the top "
            "the outer wall, slider copper, flex and touch controller; at the side the curved "
            "battery; at the palm side the optional heart-rate sensor looking through a clear "
            "epoxy window. Clear epoxy fills the channel and forms the inner surface.")
    S = 20.0
    t = R_OUT - R_IN                  # 2.9 mm
    wall = R_OUT - R_FLEX_OUT         # 0.63 mm
    y0 = 58.0
    panels = [(60.0, "At the top: touch"), (320.0, "At the side: battery"),
              (580.0, "At the palm: sensor (optional)")]

    def X(x0, x):
        return x0 + S * x

    def Y(y):
        return y0 + S * y

    for i, (x0, title) in enumerate(panels):
        f.text(X(x0, BAND_W / 2), 30, title, size=12, anchor="middle", weight="600")
        f.rect(X(x0, SIDE_WALL), Y(wall), S * (BAND_W - 2 * SIDE_WALL), S * (t - wall),
               fill="currentColor", op=0.05, sw=0.6, sop=0.5, dash="3 2")
        f.rect(X(x0, 0), Y(0), S * BAND_W, S * wall, fill="currentColor", op=0.22, sw=0.9)
        f.rect(X(x0, 0), Y(wall), S * SIDE_WALL, S * (t - wall), fill="currentColor", op=0.22, sw=0.9)
        f.rect(X(x0, BAND_W - SIDE_WALL), Y(wall), S * SIDE_WALL, S * (t - wall),
               fill="currentColor", op=0.22, sw=0.9)
        fx = (BAND_W - FLEX_W) / 2
        if i == 0:
            f.rect(X(x0, fx + 0.5), Y(wall - 0.06), S * (FLEX_W - 1.0), 2.4, fill=COPPER,
                   stroke=COPPER, sw=0.3)
            f.rect(X(x0, fx), Y(wall + 0.06), S * FLEX_W, S * 0.12, fill="currentColor", op=0.6, sw=0.4)
            f.rect(X(x0, BAND_W / 2 - 1.5), Y(wall + 0.18), S * 3.0, S * 0.55, fill="currentColor",
                   op=0.45, sw=0.8)
            f.balloon(X(x0, 1.2), 200, "12", X(x0, 0.4), Y(0.3))
            f.balloon(X(x0, 3.0), 200, "1", X(x0, 2.0), Y(wall + 0.12))
            f.balloon(X(x0, 4.6), 200, "3", X(x0, 4.6), Y(wall + 0.5))
            f.balloon(X(x0, 6.4), 200, "13", X(x0, 6.4), Y(2.3))
            f.dim_v(X(x0, 0) - 10, Y(0), Y(t), "2.9")
            f.dim_h(X(x0, 0), X(x0, BAND_W), Y(t) + 14, "8.4 mm")
            f.text(X(x0, BAND_W) + 8, Y(0) + 9, "outside", size=10.5, op=0.7)
            f.text(X(x0, BAND_W) + 8, Y(t), "finger", size=10.5, op=0.7)
        elif i == 1:
            f.rect(X(x0, 0.7), Y(wall + 0.05), S * 7.0, S * 1.6, fill="currentColor", op=0.24, rx=3)
            f.text(X(x0, BAND_W / 2), Y(wall + 0.95), "curved LiPo 1.6 × 7 mm", size=10.5,
                   anchor="middle", op=0.85)
            f.balloon(X(x0, 3.0), 200, "10", X(x0, 3.0), Y(wall + 1.6))
            f.balloon(X(x0, 5.4), 200, "13", X(x0, 5.4), Y(2.6))
        else:
            f.rect(X(x0, fx), Y(wall + 0.06), S * FLEX_W, S * 0.12, fill="currentColor", op=0.6, sw=0.4)
            f.rect(X(x0, BAND_W / 2 - 1.65), Y(wall + 0.18), S * 3.3, S * 1.55, fill="currentColor",
                   op=0.12, sw=1, dash="4 3")
            f.rect(X(x0, BAND_W / 2 - 1.2), Y(wall + 1.73), S * 2.4, S * (t - wall - 1.73),
                   fill="none", sw=0.8, dash="2 2")
            f.text(X(x0, BAND_W) + 8, Y(t) - 2, "clear window", size=10.5, op=0.7)
            f.balloon(X(x0, 2.4), 200, "1", X(x0, 1.6), Y(wall + 0.12))
            f.balloon(X(x0, 4.8), 200, "14", X(x0, 4.8), Y(wall + 1.7))
    return f


# ---------------------------------------------------------------------------------------------
# Figure 3: the flex laid flat (both faces), to scale

def fig_flex() -> Fig:
    f = Fig(720, 350, "flex", "The flex circuit laid flat, 52.8 by 6.6 mm: the outer face carries "
            "the four slider segments over the top 72 degrees, an antenna keep-out and the "
            "stiffener under the module; the inner face carries battery tab pads, touch "
            "controller, accelerometer, regulator, Bluetooth module, charger, diode, SWD pads, "
            "thermistor, two charge contact pads and the optional heart-rate sensor.")
    S, x0 = 11.0, 92.0
    yo, yi = 74.0, 208.0          # top edges of the outer-face and inner-face strips

    def X(th):
        return x0 + S * math.radians(th - FLEX_T0) * R_MID

    def across(y_top, w):
        return y_top + S * (FLEX_W - w) / 2

    L = S * FLEX_LEN
    for y, name in [(yo, "outer face"), (yi, "inner face")]:
        f.rect(x0, y, L, S * FLEX_W, fill="currentColor", op=0.06, sw=1.2, rx=4)
        f.text(x0 - 10, y + S * FLEX_W / 2 - 2, name, size=11.5, anchor="end", weight="600")
        f.text(x0 - 10, y + S * FLEX_W / 2 + 12, "toward the wall" if y == yo else "toward the finger",
               size=10, anchor="end", op=0.65)
    # angle scale
    for th, lab in [(-40, "−40°"), (0, "0° top"), (90, "90°"), (180, "180° palm"), (210, "210°")]:
        x = X(th)
        f.line(x, yo - 14, x, yo - 4, sw=0.9)
        f.text(x, yo - 20, lab, size=10.5, anchor="middle", op=0.8)
    f.text(x0 + L / 2, 26, f"52.8 mm long · 6.6 mm wide · 0.12 mm thick", size=11.5,
           anchor="middle", op=0.85)
    # outer face: slider, keep-out, stiffener
    for i, (t1, t2) in enumerate(slider_segments()):
        f.rect(X(t1), across(yo, 5.6), X(t2) - X(t1), S * 5.6, fill=COPPER, stroke=COPPER, sw=0.5)
        f.text((X(t1) + X(t2)) / 2, yo + S * FLEX_W / 2 + 4, f"S{i}", size=11, anchor="middle",
               fill="#ffffff", weight="600")
    for y in (yo, yi):
        f.rect(X(KEEPOUT[0]), y + 2, X(KEEPOUT[1]) - X(KEEPOUT[0]), S * FLEX_W - 4, sw=0.9,
               dash="2 2")
    ble_t = PARTS["ble"][0]
    half = math.degrees(3.25 / R_MID)
    f.rect(X(ble_t - half), across(yo, 6.2), X(ble_t + half) - X(ble_t - half), S * 6.2,
           sw=0.9, dash="5 3")
    f.text((X(ble_t - half) + X(ble_t + half)) / 2, yo + S * FLEX_W / 2 + 4, "stiffener",
           size=10, anchor="middle", op=0.7)
    f.text((X(KEEPOUT[0]) + X(KEEPOUT[1])) / 2, yo + S * FLEX_W + 16, "antenna keep-out",
           size=10, anchor="middle", op=0.75)
    # inner face: tab pads, parts, SWD pads, contacts
    for j, lab in enumerate(["B+", "B−"]):
        f.rect(x0 + 4, yi + 6 + j * 30, 16, 24, fill=POWER if j == 0 else "currentColor",
               op=0.85 if j == 0 else 0.6, sw=0.5, stroke=POWER if j == 0 else "currentColor")
        f.text(x0 + 26, yi + 22 + j * 30, lab, size=10, op=0.8)
    for key, (th, length, width, _h) in PARTS.items():
        x1 = X(th) - S * length / 2
        if key == "ppg":
            f.rect(x1, across(yi, width), S * length, S * width, fill="currentColor", op=0.1,
                   sw=1, dash="4 3")
        elif key == "ntc":
            f.rect(x1, across(yi, width), S * length, S * width, fill=ANALOG, op=0.5, stroke=ANALOG,
                   sw=0.8, dash="2 1.5")
        else:
            f.rect(x1, across(yi, width), S * length, S * width, fill="currentColor", op=0.4, sw=0.8)
    for th in SWD:
        f.circle(X(th), yi + S * FLEX_W / 2, S * 0.5, fill="currentColor", op=0.6, sw=0.6)
    f.text((X(SWD[0]) + X(SWD[-1])) / 2, yi + 14, "SWD", size=10, anchor="middle", op=0.8)
    for th, lab in zip(CONTACTS, ["+", "−"]):
        f.rect(X(th) - S * 1.0, across(yi, 3.0), S * 2.0, S * 3.0, fill=GOLD, op=0.85, stroke=GOLD,
               sw=0.5)
        f.text(X(th), yi + S * FLEX_W / 2 + 4, lab, size=12, anchor="middle", fill="#ffffff",
               weight="700")
    # balloons below the inner face
    yb = yi + S * FLEX_W + 34
    yt = yi + S * FLEX_W - 2
    for num, th in [("3", -14), ("4", 12), ("6", 28), ("2", 63), ("5", 100), ("7", 108),
                    ("16", 145), ("11", 157), ("14", 180), ("11", 203)]:
        f.balloon(X(th) + (0 if num != "7" else 6), yb, num, X(th), yt - 6)
    f.balloon(x0 + 12, yb, "10", x0 + 12, yt - 6)
    f.text(x0 + 30, yb + 22, "battery tabs", size=10, op=0.7)
    return f


# ---------------------------------------------------------------------------------------------
# Figure 4: wiring

def fig_wiring() -> Fig:
    f = Fig(1000, 470, "wire", "Wiring: charge contacts through a reverse-polarity diode to the "
            "BQ25100 charger and the curved cell; a 3.0 V regulator feeds the ANNA-B402 module and "
            "sensors; the IQS7211E touch controller, LIS2DW12 accelerometer and optional MAX30102 "
            "share one I2C bus with their interrupt lines on module GPIOs; the slider segments sit "
            "on the outer face of the flex.", y0=70)
    mono = MONO

    def box(x0, y0, x1, y1, title, sub=None, dashed=False):
        f.rect(x0, y0, x1 - x0, y1 - y0, fill="currentColor", op=0.04 if not dashed else 0.02,
               sw=1.4, rx=8, dash="6 4" if dashed else None)
        f.text((x0 + x1) / 2, y0 + 20, title, size=12.5, anchor="middle", weight="600")
        if sub:
            f.text((x0 + x1) / 2, y0 + 36, sub, size=10.5, anchor="middle", op=0.7)

    def pin_l(x, y, name, color, length=14, dash=None):
        f.text(x + 8, y + 4, name, size=10.5, family=mono)
        f.line(x, y, x - length, y, stroke=color, sw=1.6, dash=dash)

    def pin_r(x, y, name, color, length=14, dash=None):
        f.text(x - 8, y + 4, name, size=10.5, anchor="end", family=mono)
        f.line(x, y, x + length, y, stroke=color, sw=1.6, dash=dash)

    # charge contacts and diode
    box(20, 90, 120, 180, "Contacts #11")
    pin_r(120, 125, "+", POWER, length=0)
    pin_r(120, 155, "−", "currentColor", length=0)
    f.line(120, 125, 150, 125, stroke=POWER, sw=1.6)
    f.add('<path d="M150,117 L150,133 L164,125 Z" fill="currentColor"/>')
    f.line(165, 116, 165, 134, sw=1.6)
    f.line(165, 125, 186, 125, stroke=POWER, sw=1.6)
    f.text(157, 108, "#7", size=10, anchor="middle", op=0.75)
    f.line(120, 155, 140, 155, sw=1.6)
    f.tag(140, 155, "GND", "currentColor", "right")
    # charger, battery, regulator
    box(200, 80, 320, 250, "BQ25100 #5", "charger, 15 mA")
    pin_l(200, 125, "IN", POWER)
    pin_l(200, 175, "GND", "currentColor", length=0)
    f.line(200, 175, 186, 175, sw=1.6)
    f.tag(186, 175, "GND", "currentColor", "left")
    pin_l(200, 215, "ISET", ANALOG, length=0)
    f.line(200, 215, 190, 215, stroke=ANALOG, sw=1.6)
    f.rect(166, 209, 24, 12, stroke=ANALOG, sw=1.2)
    f.line(166, 215, 158, 215, stroke=ANALOG, sw=1.6)
    f.tag(158, 215, "GND", "currentColor", "left")
    pin_r(320, 200, "/CHG", IRQ, length=0)
    f.line(320, 200, 430, 200, stroke=IRQ, sw=1.6)
    f.text(290, 245, "BAT", size=10.5, anchor="middle", family=mono)
    f.line(290, 250, 290, 290, stroke=POWER, sw=1.8)
    f.circle(290, 270, 2.6, fill=POWER, stroke="none", sw=0)
    f.line(290, 270, 240, 270, stroke=POWER, sw=1.6)
    f.tag(240, 270, "VBAT", POWER, "left")
    box(200, 290, 320, 350, "Curved LiPo #10", "15–20 mAh, protected")
    f.line(260, 350, 260, 362, sw=1.6)
    f.tag(260, 362, "GND", "currentColor", "below")
    box(200, 400, 320, 460, "3.0 V LDO #6", "XC6206, ~1 µA")
    f.line(200, 430, 186, 430, stroke=POWER, sw=1.6)
    f.tag(186, 430, "VBAT", POWER, "left")
    f.line(320, 430, 334, 430, stroke=POWER, sw=1.6)
    f.tag(334, 430, "3V0", POWER, "right")
    f.line(260, 460, 260, 472, sw=1.6)
    f.tag(260, 472, "GND", "currentColor", "below")
    # small blocks between power and module
    f.rect(340, 278, 76, 26, sw=1.1, rx=4, stroke=ANALOG)
    f.text(378, 295, "VBAT ÷ 2", size=10.5, anchor="middle", fill=ANALOG)
    f.line(416, 291, 430, 291, stroke=ANALOG, sw=1.6)
    f.rect(340, 322, 76, 26, sw=1.1, rx=4, stroke=ANALOG, dash="4 3")
    f.text(378, 339, "NTC #16", size=10.5, anchor="middle", fill=ANALOG)
    f.line(416, 335, 430, 335, stroke=ANALOG, sw=1.6, dash="5 3")
    f.rect(340, 372, 76, 50, sw=1.1, rx=4)
    f.text(378, 391, "SWD pads", size=10.5, anchor="middle")
    f.text(378, 406, "on the flex", size=10, anchor="middle", op=0.7)
    f.line(416, 385, 430, 385, sw=1.6)
    f.line(416, 410, 430, 410, sw=1.6)
    # module
    box(430, 80, 630, 460, "ANNA-B402 #2", "nRF52833 + antenna")
    for y, name, c in [(150, "VCC", POWER), (180, "GND", "currentColor"), (204, "CHG_STAT", IRQ),
                       (291, "VBAT_SENSE", ANALOG), (335, "NTC", ANALOG), (385, "SWDIO", "currentColor"),
                       (410, "SWDCLK", "currentColor")]:
        f.text(438, y + 4, name, size=10.5, family=mono)
    f.line(430, 150, 416, 150, stroke=POWER, sw=1.6)
    f.tag(416, 150, "3V0", POWER, "left")
    f.line(430, 180, 416, 180, sw=1.6)
    f.tag(416, 180, "GND", "currentColor", "left")
    for y, name in [(150, "SDA"), (180, "SCL"), (210, "TOUCH_RDY"), (330, "ACC_INT"),
                    (445, "PPG_INT")]:
        f.text(622, y + 4, name, size=10.5, anchor="end", family=mono)
    for i, s in enumerate(["BLE · HID · DFU", "GPIOs assigned", "at layout"]):
        f.text(530, 242 + 16 * i, s, size=10.5, anchor="middle", op=0.6)
    # touch controller and slider
    box(730, 110, 880, 245, "IQS7211E #3", "I2C 0x56")
    for y, name, c in [(150, "SDA", I2C), (180, "SCL", I2C), (210, "RDY", IRQ)]:
        f.text(738, y + 4, name, size=10.5, family=mono)
        f.line(630, y, 730, y, stroke=c, sw=1.6)
    for y, name in [(140, "Tx"), (162, "Rx0"), (182, "Rx1"), (202, "Rx2"), (222, "Rx3")]:
        f.text(872, y + 4, name, size=10, anchor="end", family=mono)
        f.line(880, y, 918 if name != "Tx" else 962, y, stroke=COPPER, sw=1.4)
    for i, y in enumerate([162, 182, 202, 222]):
        f.rect(918, y - 8, 34, 16, fill=COPPER, stroke=COPPER, sw=0.5, rx=2)
        f.text(935, y + 4, f"S{i}", size=10, anchor="middle", fill="#ffffff", weight="600")
    f.line(962, 140, 962, 230, stroke=COPPER, sw=2.2)
    f.text(940, 104, "slider", size=10.5, anchor="middle", op=0.8)
    f.text(940, 118, "outer face", size=10, anchor="middle", op=0.65)
    f.line(770, 245, 770, 257, stroke=POWER, sw=1.6)
    f.tag(770, 257, "3V0", POWER, "below")
    f.line(840, 245, 840, 257, sw=1.6)
    f.tag(840, 257, "GND", "currentColor", "below")
    # accelerometer
    box(730, 290, 880, 360, "LIS2DW12 #4", "I2C 0x18")
    f.text(738, 334, "INT1", size=10.5, family=mono)
    f.line(630, 330, 730, 330, stroke=IRQ, sw=1.6)
    for y, name in [(318, "SDA"), (342, "SCL")]:
        f.line(880, y, 894, y, stroke=I2C, sw=1.6)
        f.tag(894, y, name, I2C, "right")
    f.text(842, 354, "3V0 · GND", size=9.5, anchor="middle", op=0.6)
    # optional heart-rate sensor
    box(730, 395, 880, 490, "MAX30102 #14", "optional · I2C 0x57", dashed=True)
    f.text(738, 449, "INT", size=10.5, family=mono)
    f.line(630, 445, 730, 445, stroke=IRQ, sw=1.6, dash="5 3")
    for y, name in [(440, "SDA"), (462, "SCL")]:
        f.line(880, y, 894, y, stroke=I2C, sw=1.6, dash="5 3")
        f.tag(894, y, name, I2C, "right")
    f.text(805, 476, "VDD 1V8 (#15) · VLED VBAT", size=9.5, anchor="middle", op=0.65)
    f.text(530, 480, "I2C pull-ups 4.7 kΩ to 3V0", size=10.5, anchor="middle", op=0.7)
    # legend
    leg = [(20, 508, POWER, None, "VBAT / 3V0"), (140, 508, "currentColor", None, "GND"),
           (220, 508, I2C, None, "I2C"), (290, 508, IRQ, None, "interrupt / status"),
           (20, 530, ANALOG, None, "analog"), (140, 530, COPPER, None, "slider copper"),
           (290, 530, "currentColor", "5 3", "optional (health)")]
    for x, y, c, dash, s in leg:
        f.line(x, y - 4, x + 20, y - 4, stroke=c, sw=2, dash=dash)
        f.text(x + 26, y, s, size=10.5)
    return f


# ---------------------------------------------------------------------------------------------
# Parts list

SECTIONS = [
    ("flex", "Flex circuit", "Ordered as one job: JLCPCB makes the flex and places the parts. Chips "
                             "come from LCSC through JLC, or from DigiKey/Mouser and are shipped to JLC."),
    ("ring", "Battery and band", "The cell, the printed shell and what turns the flex into a ring."),
    ("health", "Health add-on", "Optional. Leave these footprints empty until the cheap-ring "
                                "accuracy check says it's worth it."),
    ("dock", "Charging dock", "Two spring pins in a printed cradle, powered from USB-C."),
    ("program", "Programming", "The flex can only be flashed by wire before it is potted."),
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
    if hi < 1:
        return f"${lo:.2f}–{hi:.2f}"
    return f"${lo:.0f}–{hi:.0f}" if lo >= 1 else f"${lo:.2f}–{hi:.0f}"


def total(rows, keys) -> tuple[float, float]:
    sel = [r for r in rows if r["section"] in keys]
    return sum(r["qty"] * r["lo"] for r in sel), sum(r["qty"] * r["hi"] for r in sel)


def find_link(source: str, find: str) -> str | None:
    q = urllib.parse.quote_plus(find.split(" OR ")[0].split(" (")[0])
    s = source.lower()
    if s.startswith("aliexpress"):
        return "https://www.aliexpress.com/wholesale?SearchText=" + q
    if s.startswith("lcsc"):
        return "https://www.lcsc.com/search?q=" + q
    if s.startswith("digikey"):
        return "https://www.digikey.com/en/products/result?keywords=" + q
    if s.startswith("battery"):
        return ("https://www.lipobatteries.net/hot-selling-lipo-battery/"
                "curved-smart-ring-lipo-battery-batteries-lpcv170722-15mah/")
    if s.startswith("jlc3dp"):
        return "https://jlc3dp.com/"
    if s.startswith("jlcpcb"):
        return "https://jlcpcb.com/"
    return None


def parts_html(rows) -> str:
    out = []
    for key, title, blurb in SECTIONS:
        lo, hi = total(rows, [key])
        out.append(f'<section class="psec" aria-labelledby="h-{key}">'
                   f'<div class="psec-head"><h3 id="h-{key}">{esc(title)}</h3>'
                   f'<span class="sub">≈ {money(lo, hi)}</span></div>'
                   f'<p class="note">{esc(blurb)}</p>'
                   f'<div class="tablewrap"><table class="parts"><thead><tr>'
                   f'<th scope="col"><span class="sr">Bought</span></th><th scope="col">#</th>'
                   f'<th scope="col">Qty</th><th scope="col">Part and what to check</th>'
                   f'<th scope="col">Where · what to search</th>'
                   f'<th scope="col" class="num">≈ each</th></tr></thead><tbody>')
        for r in [r for r in rows if r["section"] == key]:
            link = find_link(r["source"], r["find"])
            open_a = (f'<a href="{esc(link)}" target="_blank" rel="noopener">Open</a>' if link else "")
            out.append(
                f'<tr data-item="{esc(r["item"])}" data-qty="{r["qty"]}" data-lo="{r["lo"]}" '
                f'data-hi="{r["hi"]}" data-section="{key}">'
                f'<td><input type="checkbox" id="got-{esc(r["item"])}" '
                f'aria-label="Bought item {esc(r["item"])}"></td>'
                f'<td class="itemno">{esc(r["item"])}</td><td class="num">{r["qty"]}</td>'
                f'<td class="what"><strong>{esc(r["part"])}</strong>'
                f'<span class="check">{esc(r["check"])}</span>'
                f'<span class="use">{esc(r["used_for"])}</span></td>'
                f'<td class="search"><span class="src">{esc(r["source"])}</span>'
                f'<code>{esc(r["find"])}</code>'
                f'<span class="acts"><button type="button" class="copy" data-term="{esc(r["find"])}">'
                f'Copy</button>{open_a}</span></td>'
                f'<td class="num">{money(r["lo"], r["hi"])}</td></tr>')
        out.append("</tbody></table></div></section>")
    return "".join(out)


PIN_TABLE = [
    ("3V0 (LDO out)", "Module VCC, IQS7211E VDD, LIS2DW12 VDD, I2C pull-ups", "XC6206 drops the 3.0–4.2 V cell to 3.0 V at about 1 µA quiescent"),
    ("VBAT", "LDO in, VBAT ÷ 2 divider, MAX30102 VLED", "Cell through its protection board"),
    ("SDA / SCL", "IQS7211E 0x56, LIS2DW12 0x18, MAX30102 0x57", "One bus, 4.7 kΩ pull-ups"),
    ("TOUCH_RDY", "IQS7211E RDY", "Touch controller says a new reading is ready"),
    ("ACC_INT", "LIS2DW12 INT1", "Tap confirmation and wake-up"),
    ("PPG_INT", "MAX30102 INT (optional)", "Sample ready"),
    ("CHG_STAT", "BQ25100 /CHG", "Low while charging"),
    ("VBAT_SENSE", "1 MΩ / 1 MΩ divider", "Battery percentage; draws about 2 µA"),
    ("NTC", "NTC divider (optional)", "Skin-temperature trend"),
    ("SWDIO / SWDCLK", "Four 1 mm pads on the flex", "Flash the bootloader before potting; BLE updates after"),
    ("Tx, Rx0–Rx3", "Slider copper on the outer face", "Four segments over the top 72°, under the 0.63 mm wall"),
]


def pin_table_html() -> str:
    rows = "".join(f"<tr><td><code>{esc(a)}</code></td><td>{esc(b)}</td><td>{esc(c)}</td></tr>"
                   for a, b, c in PIN_TABLE)
    return ('<div class="tablewrap"><table class="pins"><thead><tr><th scope="col">Net</th>'
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
.lede { max-width: 68ch; font-size: 16px; }
.facts { display: flex; flex-wrap: wrap; gap: 8px 28px; margin: 4px 0 0; }
.facts div { display: flex; flex-direction: column; }
.facts dt { font-family: var(--font-mono); font-size: 11px; letter-spacing: 0.06em;
  text-transform: uppercase; color: var(--muted); }
.facts dd { margin: 0; font-family: var(--font-display); font-size: 20px; font-weight: 600;
  font-variant-numeric: tabular-nums; }
section.block { display: flex; flex-direction: column; gap: 16px; }
.block > p { max-width: 70ch; color: var(--muted); }
.figs { display: grid; grid-template-columns: minmax(0, 1fr); gap: 16px; }
figure { margin: 0; background: var(--surface); border: 1px solid var(--rule); border-radius: 6px;
  display: flex; flex-direction: column; min-width: 0; }
.dwgbox { overflow-x: auto; padding: 14px 14px 4px; }
svg.dwg { display: block; width: 100%; height: auto; color: var(--fg);
  font-family: var(--font-body); margin: 0 auto; }
.dwg-end { min-width: 520px; max-width: 700px; } .dwg-sec { min-width: 640px; max-width: 850px; }
.dwg-flex { min-width: 620px; max-width: 760px; } .dwg-wire { min-width: 820px; }
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
table.parts { min-width: 800px; }
.itemno { font-family: var(--font-mono); font-weight: 600; color: var(--accent); }
.what strong { display: block; font-weight: 600; }
.what .check { display: block; font-size: 13.5px; margin-top: 3px; }
.what .use { display: block; color: var(--muted); font-size: 12.5px; margin-top: 3px; }
.search { min-width: 230px; }
.search .src { display: block; font-size: 12.5px; color: var(--muted); }
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
@media (max-width: 760px) { .cols { grid-template-columns: minmax(0, 1fr); } }
"""

JS = """
(function () {
  var KEY = "touch-ring-inband-bought-v1";
  var saved = {};
  try { saved = JSON.parse(localStorage.getItem(KEY) || "{}") || {}; } catch (e) { saved = {}; }
  var rows = Array.prototype.slice.call(document.querySelectorAll("table.parts tbody tr"));
  function fmt(n) { return "$" + Math.round(n); }
  function update() {
    var lo = 0, hi = 0, n = 0;
    rows.forEach(function (r) {
      var box = r.querySelector("input");
      r.classList.toggle("got", box.checked);
      if (box.checked) return;
      var q = +r.dataset.qty;
      lo += q * +r.dataset.lo; hi += q * +r.dataset.hi; n += 1;
    });
    document.getElementById("left-all").textContent = n ? fmt(lo) + "–" + fmt(hi).slice(1) : "nothing";
    document.getElementById("left-all-n").textContent = n + (n === 1 ? " item" : " items") + " left to buy";
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

KEY = [("1", "flex circuit"), ("2", "ANNA-B402 Bluetooth module"), ("3", "IQS7211E touch"),
       ("4", "LIS2DW12 accelerometer"), ("5", "BQ25100 charger"), ("6", "3.0 V regulator"),
       ("7", "reverse-polarity diode"), ("10", "curved LiPo"), ("11", "charge contacts"),
       ("12", "printed shell"), ("13", "clear epoxy"), ("14", "MAX30102 (optional)"),
       ("16", "NTC (optional)")]


def key_html() -> str:
    return "".join(f"<span><b>{esc(a)}</b>{esc(b)}</span>" for a, b in KEY)


def page(end: Fig, sec: Fig, flex: Fig, wire: Fig, rows) -> str:
    per_lo, per_hi = total(rows, ["flex", "ring"])
    all_lo = sum(r["qty"] * r["lo"] for r in rows)
    all_hi = sum(r["qty"] * r["hi"] for r in rows)
    return f"""<title>Touch Ring Build Sheet</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans+Condensed:wght@500;600&family=IBM+Plex+Sans:wght@400;500;600&display=swap">
<style>{CSS}</style>
<div class="wrap">
<header>
  <p class="eyebrow">mcring · R1-class touch ring · everything inside the band</p>
  <h1>Touch Ring Build Sheet</h1>
  <p class="lede">Nothing sits on top. Like the Even R1 and Oura, everything lives inside an
  8.4 × 2.9 mm band: one flex circuit wrapped around the inside, a curved 15–20 mAh cell, a
  resin outer wall with the touch slider just under it, and clear epoxy for the inner surface.
  The circled numbers in the drawings are the item numbers in the parts list.</p>
  <dl class="facts">
    <div><dt>Band (size 10)</dt><dd>8.4 × 2.9 mm</dd></div>
    <div><dt>First 5 rings, parts</dt><dd>≈ {money(per_lo, per_hi)}</dd></div>
    <div><dt>Battery</dt><dd>15–20 mAh curved</dd></div>
    <div><dt>Gestures</dt><dd>tap · double · hold · swipe</dd></div>
  </dl>
</header>

<section class="block" aria-labelledby="h-dwg">
  <h2 id="h-dwg">How it fits inside the band</h2>
  <p>To scale for a size 10 ring (19.8 mm inside). Angles run clockwise from the top of the band
  (the back of the hand) as seen from the fingertip.</p>
  <div class="figs">
    <figure><div class="dwgbox">{end.svg(False)}</div>
      <figcaption><b>End view.</b> The flex circuit runs from −40° to 210° just under the outer
      wall. Its outer face carries the four slider segments over the top; its inner face carries
      the parts. The curved cell fills the left side. The charge contacts and the optional
      heart-rate sensor sit at the palm, where they touch the skin.</figcaption></figure>
    <figure><div class="dwgbox">{sec.svg(False)}</div>
      <figcaption><b>Cuts across the band.</b> The wall over the slider is 0.63 mm of plastic
      (later ceramic): thin enough for the touch signal, never metal. The cell is the thickest
      part and sets the band at 2.9 mm, the same as an Oura Ring 4.</figcaption></figure>
    <figure><div class="dwgbox">{flex.svg(False)}</div>
      <figcaption><b>The flex laid flat.</b> This is the outline to draw in KiCad: 52.8 × 6.6 mm,
      two copper layers, 0.12 mm thick. Parts on the inner face only, slider copper on the outer
      face, no copper anywhere near the module's antenna end.</figcaption></figure>
  </div>
  <div class="key" aria-label="Balloon key">{key_html()}</div>
</section>

<section class="block" aria-labelledby="h-wire">
  <h2 id="h-wire">Wiring</h2>
  <p>Net tags (3V0, VBAT, GND, SDA, SCL) connect to every other tag with the same name. Which
  module pin carries each signal is chosen when the flex is laid out.</p>
  <figure><div class="dwgbox">{wire.svg(False)}</div>
    <figcaption><b>Schematic.</b> The dock feeds the charger through a diode, so a ring put on
    backwards is safe. One 3.0 V regulator powers everything. The touch controller, the
    accelerometer and the optional heart-rate sensor share one I2C bus, each with its own
    interrupt line.</figcaption></figure>
  {pin_table_html()}
</section>

<section class="block" aria-labelledby="h-parts">
  <h2 id="h-parts">Parts to order</h2>
  <p>Chips this small don't come reliably from AliExpress, so the flex and its parts come from
  JLCPCB, LCSC and DigiKey/Mouser; AliExpress covers the dock, the programmer, consumables and
  tools. Quantities are for a first batch of 5 rings. Prices are rough ranges, not quotes.</p>
  <div class="status" role="status">
    <strong id="left-all">≈ {money(all_lo, all_hi)}</strong>
    <span id="left-all-n">{len(rows)} items left to buy</span>
    <span>Parts for the 5 rings themselves: ≈ {money(per_lo, per_hi)}</span>
    <button type="button" id="reset">Clear ticks</button>
  </div>
  {parts_html(rows)}
</section>

<section class="block" aria-labelledby="h-build">
  <h2 id="h-build">Build order</h2>
  <div class="cols">
    <ol class="steps">
      <li>Write the firmware on the bench board (#22) while the flex is being made: gestures,
      BLE HID, mcring events, and a bootloader that takes updates over Bluetooth.</li>
      <li>Draw the flex in KiCad from the flat layout above and order 5 assembled boards
      from JLCPCB.</li>
      <li>Bring each flex up while it is still flat: 3.7 V on the battery pads, flash over the
      SWD pads, check touch through a 0.6 mm sheet of plastic, and check Bluetooth range.</li>
      <li>Solder the curved cell to the tab pads, quickly, on the tabs only. Insulate with
      Kapton.</li>
      <li>Solder a 2.2 mm gold pin upright on each contact pad.</li>
      <li>Curve the flex into the printed shell, slider side against the outer wall, and tack it
      with a drop of epoxy.</li>
      <li>Pour clear epoxy in two passes and let the bubbles rise. Once cured, sand the inside
      smooth and the contact pins flush.</li>
      <li>Charge it on the dock. From here on, firmware updates go over Bluetooth only.</li>
    </ol>
    <ul class="gotchas" aria-label="Checks before you pot it">
      <li>After potting there is no wire access. Prove an update over Bluetooth works before
      step 7.</li>
      <li>Keep all copper, the cell and the contacts away from the module's antenna end, and
      check range before potting.</li>
      <li>The layout is drawn for size 10. Below size 8 the flex is too long: lay it out again
      with a shorter cell.</li>
      <li>The outer wall must be plastic or ceramic. A zirconia shell made by the UIUC furnace
      route drops into the same design.</li>
      <li>Use only a cell with its protection board, and never heat the cell body.</li>
    </ul>
  </div>
</section>

<footer>
  <p>Source: <code>hardware/touch-ring/build_sheet.py</code> in the mcring repo draws these figures
  and this page from <code>hardware/bom/touch-ring-parts.csv</code>. Background and costs:
  <code>docs/11-touch-ring-r1-class.md</code>.</p>
  <p>Part sizes come from datasheets and listings; check the IQS7211E and cell drawings before
  laying out the flex.</p>
</footer>
</div>
<script>{JS}</script>
"""


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    end, sec, flex, wire = fig_end(), fig_sections(), fig_flex(), fig_wiring()
    for name, fig in [("ring-end-view", end), ("ring-band-sections", sec),
                      ("ring-flex-layout", flex), ("ring-wiring", wire)]:
        with open(os.path.join(OUT, f"{name}.svg"), "w") as fh:
            fh.write(fig.svg(True) + "\n")
    rows = load_parts()
    with open(PAGE, "w") as fh:
        fh.write(page(end, sec, flex, wire, rows))
    print(f"flex length {FLEX_LEN:.1f} mm; wrote {OUT}/*.svg and {os.path.relpath(PAGE, ROOT)}")


if __name__ == "__main__":
    main()
