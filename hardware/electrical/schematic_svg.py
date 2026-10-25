"""
schematic_svg.py — render net-label-style schematic sheets of mcring_v1 as SVG (+PNG).

One sheet per block: Power, MCU, Camera, Sensors + Haptics, Outputs + Connectors.
ICs are boxes with pins on the left/right ending in net labels; 2-pin passives are small
horizontal boxes; 1-pin pads are stubs.  The layout is computed from pin counts and label
lengths (monospace font, 11 px) so nothing overlaps; a check asserts that part cells are
disjoint.  Output: out/sch_<sheet>.svg and out/sch_<sheet>.png (cairosvg).

Run:  python3 schematic_svg.py
"""
from __future__ import annotations

import os
import sys
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mcring_v1 import GPIO, R_GAIN, R_I2S_SERIES, R_ISET, R_PRETERM, R_VSET, build  # noqa: E402
from netlist_model import Netlist, Part  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")

# ---- typography / geometry (px) --------------------------------------------- #
FONT = "DejaVu Sans Mono, Menlo, Consolas, monospace"
FS_PIN = 11          # pin names and net labels
FS_NUM = 10          # pin numbers
FS_REF = 12          # reference / value header
CW = 0.62            # monospace advance width as a fraction of font size
PITCH = 18           # pin row pitch
STUB = 26            # pin stub length
PAD = 8              # inner box padding
HDR = 34             # header (ref + value) height above the pin rows
CELL_GAP_Y = 26
CELL_GAP_X = 36
MARGIN = 28
TITLE_H = 66

SHEETS = [("Power", "Power: cell + charging pigtails (J1/J3 headers), charger, buck, battery sense"),
          ("MCU", "MCU: ESP32-S3-MINI-1U, straps, USB test pads, I2C pull-ups"),
          ("Camera", "Camera: OV2640 24-pin FPC, load switch, 2.8 V / 1.2 V LDOs, SCCB"),
          ("Sensors", "Sensors + Haptics: DRV2605L + LRA, LIS2DW12, T3902 mic, button, touch"),
          ("Outputs", "Outputs + Connectors: WS2812 (gated), piezo pads, aux pads, MAX98357A speaker amp (gated, optional) + J5 speaker header")]

SHEET_NOTES = {
    "Power": [f"BQ25100: R_ISET {R_ISET} -> ~25 mA (K_ISET 230 A*ohm, VERIFY); R_PRETERM {R_PRETERM} -> 1 mA (K 11.5, VERIFY).",
              f"BQ25100 has PRE_TERM, no TS pin (TS variant = BQ25101). nCHG -> IO{GPIO['nCHG']} (PIN_CHG, active low) + TP7, 100k pull-up.",
              f"TPS62840: R12 {R_VSET} from VSET to GND = 3.3 V code (SLVSE12 Table 1); MODE/STOP low; EN tied to VBAT.",
              "Charging input: CP1/CP2 band contacts (off-board, dashed) -> W2 pigtail -> J3 Pico-EZmate header -> D2 bidirectional TVS -> D3 series",
              "Schottky -> CHG_IN. D3 blocks a ring seated the wrong way round in the 2-pin cradle. J3 pin 1 doubles as the bring-up VBUS entry.",
              "Cell BT1 (off-board) -> W1 pigtail -> J1 Pico-EZmate header (top side; no solder). Battery divider 1 M / 1 M + 100 nF: 2.1 uA.",
              "100 uF 1206 bulk on 3V3 near the module absorbs the 300-370 mA capture/radio peaks."],
    "MCU": [f"IO{GPIO['CAM_PWR_EN']} CAM_PWR_EN (was IO19), IO{GPIO['RGB_DATA']} RGB data (was IO20); IO19/IO20 = native USB test pads.",
            f"IO{GPIO['LED_PWR_EN']} LED_PWR_EN (PIN_RGB_PWR) with 4.7k pull-down: WS2812 rail off at reset and in deep sleep (was IO44/RXD0).",
            "IO26 = SPICS1 of the in-package quad PSRAM -> NC. IO33-IO37 are free on the N4R2 (octal PSRAM parts only use them):",
            f"IO{GPIO['AMP_PWR_EN']} AMP_PWR_EN (PIN_SPEAKER_EN, 100k pull-down), IO{GPIO['I2S_BCLK']}/IO{GPIO['I2S_LRCLK']}/IO{GPIO['I2S_DOUT']} "
            "I2S BCLK/LRCLK/DOUT to the optional MAX98357A (Outputs sheet).",
            "IO44 (RXD0) is the only spare GPIO (grey 'spare'; ROM pull-up at reset). IO45/IO46 straps left floating. Pin table VERIFY.",
            "I2C 4.7k pull-ups on SDA/SCL (DRV2605L 0x5A, LIS2DW12 0x18). EN: 10k + 1 uF. IO0: 10k + pad + DNP button.",
            "ANT1 (off-board): 2.4 GHz flex antenna on the module's u.FL receptacle (not a pad) — see README §5."],
    "Camera": ["FPC pin order = ESP32-CAM / Arducam M0031 OV2640 (pin 1 NC ... 24 Y0) — VERIFY on the purchased head.",
               "FPC1 = Hirose FH12-24S-0.5SH(55): BOTTOM contact, flip-lock ZIF, 2.0 mm, LCSC C202112 (alt Amphenol F32R-1A7H1-11024 slider ZIF).",
               "CAM_3V3 (DOVDD) switched by U2 from IO21; AVDD 2.8 V (U3) and DVDD 1.2 V (U4, DNP if self-regulated) hang off it.",
               "SCCB pull-ups and RESET RC go to the switched rail so the unpowered sensor is never back-fed. PWDN tied low.",
               "Y0/Y1 unused (8-bit bus Y2..Y9 = D0..D7). XCLK 20 MHz from IO10 (LEDC)."],
    "Sensors": ["DRV2605L: IN/TRIG to GND (I2C RTP mode), EN tied to 3V3 (shutdown via EN would block I2C; idle = register STANDBY),",
                "REG 1 uF. OUT+/OUT- -> J4 Pico-EZmate header -> W3 pigtail -> LRA M1 (off-board): INEED LRA0825BC-0167F, 240 Hz, 1.25 Vrms max.",
                "LIS2DW12: SA0 = GND (0x18), CS = VDD_IO (I2C), INT1 -> IO7 (RTC wake), INT2 NC.",
                "T3902: SELECT = GND, CLK IO42, DATA IO41 (I2S0 PDM RX). Button to GND with 100 nF; touch pad via 1k."],
    "Outputs": [f"WS2812B-2020 powered from 3V3 through U9 (TPS22916, ON = IO{GPIO['LED_PWR_EN']}): ~0.6-1 mA idle otherwise.",
                "Data from IO43 through 1 kOhm (limits the boot-chatter back-feed while VLED is off); 100 nF + 1 uF at the LED.",
                "Piezo: IO4 -> 100 Ohm -> BZ1 bare pads; the 9x9 element PZ1 is off-board and optional (DNP until the enclosure has a pocket).",
                "Q1 AO3400 low-side switch from IO9 (100k pull-down): aux pads = VBAT + open drain.",
                f"OPTIONAL speaker (fit U10/U11/C25/C26/R20-R24/LS1 together): 3V3 -> U11 TPS22916 (ON = IO{GPIO['AMP_PWR_EN']} AMP_PWR_EN, 100k "
                "pull-down) -> VAMP -> U10 MAX98357A VDD (10 uF + 100 nF); the amp draws nothing while U11 is open.",
                f"I2S: BCLK IO{GPIO['I2S_BCLK']}, LRCLK IO{GPIO['I2S_LRCLK']}, DIN IO{GPIO['I2S_DOUT']} (512 kHz / 16 kHz, no MCLK), each through "
                f"R22/R23/R24 {R_I2S_SERIES}: bounds the ESD-diode back-feed into the unpowered amp to <= 2.6 mA per pin while VAMP is off.",
                "SD_MODE tied to VAMP = left-channel mode (> 1.4 V; the firmware duplicates mono into both slots). Firmware must still park",
                f"IO35-37 low while AMP_PWR_EN is low (a pin left high is a mA-class drain, not damage). GAIN_SLOT -> R21 {R_GAIN} -> VAMP = 3 dB "
                "(0 dBFS = 1.4 Vrms = 0.25 W into 8 Ohm, inside the speaker's 300 mW rating); R21 0R = 6 dB (0.5 W = speaker max, bench option),",
                "DNP = 9 dB (clips at 3.3 V). TQFN pin table, SD/gain thresholds and the digital-input abs-max rating VERIFY (README §6 17-19).",
                "OUTP/OUTN (0.3 mm pair) -> J5 Pico-EZmate header -> W4 pigtail -> LS1 PUI AS01008MR-2-R 10 mm 8 Ohm (off-board, enclosure speaker pocket)."],
}

POWER_COLORS = {"GND": "#1b7f3a"}
COL_POWER = "#a3261a"
COL_SIGNAL = "#1f4fa3"
COL_NC = "#8a8a8a"
SPARE = "spare"      # pseudo-net label for intentionally free pins


def tw(text: str, fs: int = FS_PIN) -> float:
    return len(text) * fs * CW


# ---- pin side assignment ---------------------------------------------------- #
def sides(part: Part, nl: Netlist) -> Tuple[List[str], List[str]]:
    """Return (left_pin_numbers, right_pin_numbers) in display order."""
    names = part.pins
    byname = {}
    for pn, n in names.items():
        byname.setdefault(n, []).append(pn)

    def pick(*labels):
        out = []
        for lab in labels:
            out += byname.get(lab, [])
        return out

    ref = part.ref
    if ref == "U1":
        left = ["3", "45"] + [pn for pn, n in names.items() if n.startswith("IO") and int(n[2:]) <= 21]
        right = [pn for pn, n in names.items() if (n.startswith("IO") and int(n[2:]) > 21) or n.startswith(("TXD", "RXD"))]
        right += [pn for pn, n in names.items() if n == "GND"]   # collapsed into one "GND 1-2,43-44,46-65" row
        return left, right
    if ref == "FPC1":
        left = pick("NC", "AGND", "AVDD", "DVDD", "DOVDD", "DGND", "SIOD", "SIOC", "RESET", "PWDN")
        right = pick("XCLK", "PCLK", "VSYNC", "HREF", "Y9", "Y8", "Y7", "Y6", "Y5", "Y4", "Y3", "Y2", "Y1", "Y0")
        return left, right
    table = {
        "U5": (("VDD", "REG", "SCL", "SDA", "IN/TRIG", "EN"), ("OUT+", "OUT-", "GND", "NC")),
        "U6": (("VDD", "VDD_IO", "SCL/SPC", "SDA/SDI/SDO", "SA0/SDO", "CS", "RES"), ("INT1", "INT2", "GND")),
        "U7": (("IN", "ISET", "PRE_TERM"), ("OUT", "nCHG", "VSS")),
        "U8": (("VIN", "EN", "STOP", "MODE", "VSET"), ("SW", "VOS", "GND")),
        "U2": (("VIN", "ON"), ("VOUT", "GND")),
        "U9": (("VIN", "ON"), ("VOUT", "GND")),
        "U11": (("VIN", "ON"), ("VOUT", "GND")),
        "U10": (("DIN", "BCLK", "LRCLK", "SD_MODE", "GAIN_SLOT", "VDD"), ("OUTP", "OUTN", "GND", "EP", "NC")),
        "U3": (("VIN",), ("VOUT", "VSS")),
        "U4": (("VIN",), ("VOUT", "VSS")),
        "MK1": (("VDD", "GND"), ("CLK", "DATA", "SELECT")),
        "D1": (("VDD", "DIN"), ("DOUT", "GND")),
        "Q1": (("G",), ("D", "S")),
        "D3": (("A",), ("K",)),      # series Schottky: CHG_PAD (anode) on the left, CHG_IN (cathode) on the right
    }
    if ref in table:
        l, r = table[ref]
        return pick(*l), pick(*r)
    pns = list(names)
    if len(pns) == 1:
        return [], pns
    if len(pns) == 2:
        return [pns[0]], [pns[1]]
    half = (len(pns) + 1) // 2
    return pns[:half], pns[half:]


def collapse_rows(part: Part, pins: List[str], nl: Netlist) -> List[Tuple[str, str, Optional[str]]]:
    """Group same-net GND pins into one row. Returns [(pin_number_label, pin_name, net)];
    net is None for NC pins and the SPARE sentinel for intentionally free pins."""
    rows, gnd = [], []
    for pn in pins:
        net = nl.net_of(part.ref, pn)
        if net is None and pn in part.spare_pins:
            net = SPARE
        if part.pins[pn] == "GND" and net == "GND" and len(part.pins) > 4:
            gnd.append(pn)
        else:
            rows.append((pn, part.pins[pn], net))
    if gnd:
        rows.append((_ranges(gnd), "GND", "GND"))
    return rows


def _ranges(pins: List[str]) -> str:
    nums = sorted(int(p) for p in pins if p.isdigit())
    others = [p for p in pins if not p.isdigit()]
    out, i = [], 0
    while i < len(nums):
        j = i
        while j + 1 < len(nums) and nums[j + 1] == nums[j] + 1:
            j += 1
        out.append(str(nums[i]) if i == j else f"{nums[i]}-{nums[j]}")
        i = j + 1
    return ",".join(out + others)


# ---- per-part cell ---------------------------------------------------------- #
class Cell:
    def __init__(self, part: Part, nl: Netlist):
        self.part = part
        l, r = sides(part, nl)
        self.left = collapse_rows(part, l, nl)
        self.right = collapse_rows(part, r, nl)
        self.two_pin = len(part.pins) == 2
        self.one_pin = len(part.pins) == 1
        if self.two_pin or self.one_pin:
            self.rows = 1
            self.box_w = max(tw(part.value, FS_REF), tw(part.ref, FS_REF), 44) + 2 * PAD
            self.box_h = 30
            self.hdr = 0
            lab_l = tw(self.left[0][2] or "NC") if self.left else 0
            lab_r = tw(self.right[0][2] or "NC") if self.right else 0
            self.left_w = STUB + lab_l + 6 if self.left else 0
            self.right_w = STUB + lab_r + 6
            self.w = self.left_w + self.box_w + self.right_w
            self.h = self.box_h + 20  # value line under the box
        else:
            self.rows = max(len(self.left), len(self.right), 1)
            lw = max([tw(f"{n} {name}", FS_PIN) for n, name, _ in self.left] + [0])
            rw = max([tw(f"{name} {n}", FS_PIN) for n, name, _ in self.right] + [0])
            hdr_w = max(tw(part.ref, FS_REF), tw(part.value, FS_REF))
            self.box_w = max(lw + rw + 3 * PAD + 10, hdr_w + 2 * PAD, 110)
            self.hdr = HDR
            self.box_h = self.hdr + self.rows * PITCH + PAD
            self.left_w = STUB + max([tw(net or "NC") for _, _, net in self.left] + [0]) + 6
            self.right_w = STUB + max([tw(net or "NC") for _, _, net in self.right] + [0]) + 6
            self.w = self.left_w + self.box_w + self.right_w
            self.h = self.box_h
        self.x = self.y = 0.0

    # ---- drawing ------------------------------------------------------------ #
    def svg(self) -> List[str]:
        o: List[str] = []
        p = self.part
        bx = self.x + self.left_w
        by = self.y
        dnp = (" (DNP)" if p.dnp else "") + (" *" if p.offboard else "")
        cls = (" dnp" if p.dnp else "") + (" offboard" if p.offboard else "")
        if self.two_pin or self.one_pin:
            o.append(f'<rect x="{bx:.1f}" y="{by:.1f}" width="{self.box_w:.1f}" height="{self.box_h}" '
                     f'rx="3" class="box{cls}"/>')
            o.append(f'<text x="{bx + self.box_w / 2:.1f}" y="{by + 19:.1f}" class="ref" text-anchor="middle">{esc(p.ref)}</text>')
            o.append(f'<text x="{bx + self.box_w / 2:.1f}" y="{by + self.box_h + 14:.1f}" class="val" '
                     f'text-anchor="middle">{esc(p.value + dnp)}</text>')
            ym = by + self.box_h / 2
            if self.left:
                pn, name, net = self.left[0]
                o += pin_stub(bx, ym, "L", pn, None, net)
            if self.right:
                pn, name, net = self.right[0]
                o += pin_stub(bx + self.box_w, ym, "R", pn, None, net)
            return o
        o.append(f'<rect x="{bx:.1f}" y="{by:.1f}" width="{self.box_w:.1f}" height="{self.box_h:.1f}" '
                 f'rx="4" class="box{cls}"/>')
        o.append(f'<text x="{bx + PAD:.1f}" y="{by + 14:.1f}" class="ref">{esc(p.ref)}</text>')
        o.append(f'<text x="{bx + PAD:.1f}" y="{by + 28:.1f}" class="val">{esc(p.value + dnp)}</text>')
        o.append(f'<line x1="{bx:.1f}" y1="{by + self.hdr - 2:.1f}" x2="{bx + self.box_w:.1f}" y2="{by + self.hdr - 2:.1f}" class="sep"/>')
        for i, (pn, name, net) in enumerate(self.left):
            yy = by + self.hdr + i * PITCH + PITCH / 2 + 1
            o += pin_stub(bx, yy, "L", pn, name, net)
        for i, (pn, name, net) in enumerate(self.right):
            yy = by + self.hdr + i * PITCH + PITCH / 2 + 1
            o += pin_stub(bx + self.box_w, yy, "R", pn, name, net)
        return o


def net_color(net: Optional[str]) -> str:
    if net is None or net == SPARE:
        return COL_NC
    if net in POWER_COLORS:
        return POWER_COLORS[net]
    if Netlist.POWER_NET_RE.match(net):
        return COL_POWER
    return COL_SIGNAL


def pin_stub(x: float, y: float, side: str, pn: str, name: Optional[str], net: Optional[str]) -> List[str]:
    o = []
    d = -1 if side == "L" else 1
    x2 = x + d * STUB
    label = net or "NC"
    col = net_color(net)
    if net == SPARE:
        # intentionally free pin: short grey stub, no cross
        o.append(f'<line x1="{x:.1f}" y1="{y:.1f}" x2="{x + d * 14:.1f}" y2="{y:.1f}" class="wire nc"/>')
        tx = x + d * (STUB + 4)
        anchor = "end" if side == "L" else "start"
        o.append(f'<text x="{tx:.1f}" y="{y + 4:.1f}" class="net spare" fill="{col}" text-anchor="{anchor}">spare</text>')
    elif net is None:
        # no-connect cross
        o.append(f'<line x1="{x:.1f}" y1="{y:.1f}" x2="{x + d * 10:.1f}" y2="{y:.1f}" class="wire nc"/>')
        cx = x + d * 14
        o.append(f'<line x1="{cx - 4:.1f}" y1="{y - 4:.1f}" x2="{cx + 4:.1f}" y2="{y + 4:.1f}" class="wire nc"/>')
        o.append(f'<line x1="{cx - 4:.1f}" y1="{y + 4:.1f}" x2="{cx + 4:.1f}" y2="{y - 4:.1f}" class="wire nc"/>')
        tx = x + d * (STUB + 4)
        anchor = "end" if side == "L" else "start"
        o.append(f'<text x="{tx:.1f}" y="{y + 4:.1f}" class="net" fill="{col}" text-anchor="{anchor}">NC</text>')
    else:
        o.append(f'<line x1="{x:.1f}" y1="{y:.1f}" x2="{x2:.1f}" y2="{y:.1f}" class="wire"/>')
        tx = x2 + d * 4
        anchor = "end" if side == "L" else "start"
        o.append(f'<text x="{tx:.1f}" y="{y + 4:.1f}" class="net" fill="{col}" text-anchor="{anchor}">{esc(label)}</text>')
    if name is not None:
        if side == "L":
            o.append(f'<text x="{x + 3:.1f}" y="{y + 4:.1f}" class="num">{esc(pn)}</text>')
            o.append(f'<text x="{x + 3 + tw(pn + " ", FS_NUM):.1f}" y="{y + 4:.1f}" class="pin">{esc(name)}</text>')
        else:
            o.append(f'<text x="{x - 3:.1f}" y="{y + 4:.1f}" class="num" text-anchor="end">{esc(pn)}</text>')
            o.append(f'<text x="{x - 3 - tw(pn + " ", FS_NUM):.1f}" y="{y + 4:.1f}" class="pin" text-anchor="end">{esc(name)}</text>')
    else:
        # passive: pin number just inside the box edge
        if side == "L":
            o.append(f'<text x="{x + 3:.1f}" y="{y + 4:.1f}" class="num">{esc(pn)}</text>')
        else:
            o.append(f'<text x="{x - 3:.1f}" y="{y + 4:.1f}" class="num" text-anchor="end">{esc(pn)}</text>')
    return o


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ---- layout ----------------------------------------------------------------- #
def layout(cells: List[Cell], k: int) -> Tuple[float, float]:
    """Greedy shelf packing into k columns; cells sorted tallest-first. Returns (W, H)."""
    cols_h = [0.0] * k
    cols: List[List[Cell]] = [[] for _ in range(k)]
    for c in sorted(cells, key=lambda c: (-c.h, -c.w, c.part.ref)):
        i = min(range(k), key=lambda i: (cols_h[i], i))
        cols[i].append(c)
        cols_h[i] += c.h + CELL_GAP_Y
    x = MARGIN
    for col in cols:
        cw = max([c.w for c in col] + [0])
        y = MARGIN + TITLE_H
        for c in col:
            c.x = x
            c.y = y
            y += c.h + CELL_GAP_Y
        x += cw + CELL_GAP_X
    W = x - CELL_GAP_X + MARGIN
    H = MARGIN + TITLE_H + max(cols_h) - CELL_GAP_Y + MARGIN
    return W, H


def best_layout(cells: List[Cell]) -> Tuple[float, float]:
    best = None
    for k in range(1, min(10, len(cells)) + 1):
        W, H = layout(cells, k)
        score = max(W / 1.7, H)          # aim for roughly 17:10 landscape
        if best is None or score < best[0]:
            best = (score, k)
    W, H = layout(cells, best[1])
    return W, H


def check_no_overlap(cells: List[Cell]) -> None:
    rects = [(c.x, c.y, c.x + c.w, c.y + c.h, c.part.ref) for c in cells]
    for i in range(len(rects)):
        for j in range(i + 1, len(rects)):
            a, b = rects[i], rects[j]
            if a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]:
                raise AssertionError(f"overlap between {a[4]} and {b[4]}")


def render_sheet(nl: Netlist, sheet: str, title: str, idx: int, total: int) -> str:
    parts = [p for p in nl.parts.values() if p.sheet == sheet]
    cells = [Cell(p, nl) for p in parts]
    W, H = best_layout(cells)
    check_no_overlap(cells)
    notes = SHEET_NOTES.get(sheet, [])
    notes_h = 16 * len(notes) + 14 + MARGIN if notes else 0
    sub1 = (f"net-label schematic generated by hardware/electrical/schematic_svg.py from mcring_v1.py — "
            f"{len(parts)} parts on this sheet")
    sub2 = ("grey pin numbers are to be VERIFIED against the datasheets; red = power net, green = GND, blue = signal, "
            "x = NC, grey 'spare' = free GPIO; dashed grey box + * = off-board part wired to the board")
    W = max(W, max([tw(n, FS_PIN) for n in notes + [sub1, sub2]] + [0]) + 2 * MARGIN + 12, 900)
    H_total = H + notes_h
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W:.0f}" height="{H_total:.0f}" '
         f'viewBox="0 0 {W:.0f} {H_total:.0f}" font-family="{FONT}">',
         '<style>'
         f'.box{{fill:#fffdf5;stroke:#222;stroke-width:1.2}} .box.dnp{{stroke-dasharray:4 3;fill:#f4f4f4}}'
         f'.box.offboard{{stroke-dasharray:7 3;stroke:#666;fill:#f7f7fb}} .net.spare{{font-weight:normal;font-style:italic}}'
         f'.sep{{stroke:#999;stroke-width:0.8}} .wire{{stroke:#222;stroke-width:1.2}} .wire.nc{{stroke:{COL_NC}}}'
         f'.ref{{font-size:{FS_REF}px;font-weight:bold;fill:#111}} .val{{font-size:{FS_REF}px;fill:#333}}'
         f'.pin{{font-size:{FS_PIN}px;fill:#111}} .num{{font-size:{FS_NUM}px;fill:#777}}'
         f'.net{{font-size:{FS_PIN}px;font-weight:bold}} .title{{font-size:16px;font-weight:bold;fill:#111}}'
         f'.sub{{font-size:{FS_PIN}px;fill:#444}} .note{{font-size:{FS_PIN}px;fill:#333}}'
         '</style>',
         f'<rect x="0" y="0" width="{W:.0f}" height="{H_total:.0f}" fill="#ffffff"/>',
         f'<rect x="{MARGIN / 2}" y="{MARGIN / 2}" width="{W - MARGIN:.0f}" height="{H_total - MARGIN:.0f}" '
         f'fill="none" stroke="#333" stroke-width="1.5"/>',
         f'<text x="{MARGIN}" y="{MARGIN + 18}" class="title">mcring v1 — sheet {idx}/{total}: {esc(title)}</text>',
         f'<text x="{MARGIN}" y="{MARGIN + 36}" class="sub">{esc(sub1)}</text>',
         f'<text x="{MARGIN}" y="{MARGIN + 50}" class="sub">{esc(sub2)}</text>']
    for c in cells:
        o += c.svg()
    if notes:
        y0 = H + 4
        o.append(f'<line x1="{MARGIN}" y1="{y0 - 6}" x2="{W - MARGIN}" y2="{y0 - 6}" class="sep"/>')
        for i, n in enumerate(notes):
            o.append(f'<text x="{MARGIN}" y="{y0 + 12 + 16 * i}" class="note">• {esc(n)}</text>')
    o.append('</svg>')
    return "\n".join(o)


def main() -> int:
    import cairosvg
    os.makedirs(OUT, exist_ok=True)
    nl = build()
    assigned = {p.sheet for p in nl.parts.values()}
    missing = assigned - {s for s, _ in SHEETS}
    if missing:
        raise SystemExit(f"parts on unknown sheets: {missing}")
    for i, (sheet, title) in enumerate(SHEETS, 1):
        svg = render_sheet(nl, sheet, title, i, len(SHEETS))
        svg_path = os.path.join(OUT, f"sch_{sheet.lower()}.svg")
        png_path = os.path.join(OUT, f"sch_{sheet.lower()}.png")
        with open(svg_path, "w", encoding="utf-8") as fh:
            fh.write(svg)
        cairosvg.svg2png(bytestring=svg.encode("utf-8"), write_to=png_path, scale=1.5)
        n = sum(1 for p in nl.parts.values() if p.sheet == sheet)
        print(f"{sheet:8s} {n:3d} parts -> {os.path.basename(svg_path)}, {os.path.basename(png_path)} "
              f"({os.path.getsize(png_path) // 1024} kB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
