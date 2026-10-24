#!/usr/bin/env python3
"""Stage-0 bench wiring diagram: Seeed XIAO ESP32S3 Sense + DRV2605L/LRA + LIS2DW12 + button + piezo
+ battery divider + LiPo + the optional MAX98357A I2S amp breakout with a 10 mm speaker.
Pure Python → out/wiring_stage0.svg/.png and wiring_stage0.md.

Pin assignments are BOARD_XIAO_ESP32S3_SENSE from firmware/ring-esp32s3/src/config.h + config_audio.h:
  D0/A0 = GPIO1 battery sense, D1 = GPIO2 button, D2 = GPIO3 haptic (DRV EN), D3 = GPIO4 buzzer,
  D4 = GPIO5 SDA, D5 = GPIO6 SCL, D8 = GPIO7 IMU INT1, D9 = GPIO8 touch,
  D6 = GPIO43 I2S LRCLK, D7 = GPIO44 I2S BCLK, D10 = GPIO9 I2S DIN (was PIN_AUX; the air-puff experiment
  is parked on the dev kit, config_audio.h sets PIN_AUX -1). Amp SD and VIN go to 3V3; PIN_SPEAKER_EN = -1.
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from svgkit import SVG  # noqa: E402

OUT = os.path.join(HERE, "out")

# colours
C_3V3, C_GND, C_BAT, C_SDA, C_SCL, C_SIG, C_INT, C_LRA, C_OPT, C_I2S = (
    "#d62728", "#111111", "#b03a2e", "#1f77b4", "#d4a017", "#2ca02c", "#8e44ad", "#8c564b", "#7f8c8d", "#17a589")

# XIAO header (top view, USB-C up).  Left column D0..D6, right column 5V, GND, 3V3, D10, D9, D8, D7.
LEFT = [("D0 / A0", "GPIO1", "BAT_SENSE"), ("D1", "GPIO2", "BUTTON"), ("D2", "GPIO3", "HAPTIC (DRV EN)"),
        ("D3", "GPIO4", "BUZZER"), ("D4 / SDA", "GPIO5", "I²C SDA"), ("D5 / SCL", "GPIO6", "I²C SCL"),
        ("D6 / TX", "GPIO43", "I²S LRC (amp)")]
RIGHT = [("5V", "VBUS", "n/c"), ("GND", "GND", "GND"), ("3V3", "3V3", "3.3 V out ≤ 700 mA"),
         ("D10", "GPIO9", "I²S DIN"), ("D9", "GPIO8", "TOUCH (optional pad)"), ("D8", "GPIO7", "IMU INT1"),
         ("D7 / RX", "GPIO44", "I²S BCLK (amp)")]

XX0, XX1, XY0, XY1 = 600, 860, 200, 620      # XIAO body
PIN_Y = [250 + 55 * i for i in range(7)]
LPIN_X, RPIN_X = 570, 890                    # wire attachment points (end of the pin stubs)

WIRES = []   # (colour, points, label, (lx, ly), anchor, dash, rotate)


def wire(color, pts, label, lpos, anchor="start", dash=None, rotate=None):
    WIRES.append((color, pts, label, lpos, anchor, dash, rotate))


# ---- define every wire ------------------------------------------------------------------------
# battery pads → LiPo
wire(C_BAT, [(680, 612), (680, 700)], "BAT+ (LiPo red)", (688, 655))
wire(C_GND, [(780, 612), (780, 700)], "BAT− (LiPo black)", (788, 655))
# divider mid-point → A0
wire(C_SIG, [(340, 165), (530, 165), (530, 250), (LPIN_X, 250)], "D0 / A0 (GPIO1) ← VBAT/2", (522, 238), anchor="end")
# button
wire(C_SIG, [(LPIN_X, 305), (480, 305)], "D1 / GPIO2 ← button", (525, 293), anchor="middle")
# haptic EN (optional)
wire(C_OPT, [(LPIN_X, 360), (545, 360), (545, 810), (330, 810)], "D2 / GPIO3 → DRV EN (optional)", (553, 740), dash="6 4", rotate=-90)
# piezo
wire(C_SIG, [(LPIN_X, 415), (480, 415)], "D3 / GPIO4 → piezo", (525, 403), anchor="middle")
# I2C
wire(C_SDA, [(LPIN_X, 470), (520, 470), (520, 880), (1000, 880), (1000, 680), (1060, 680)], "D4 / GPIO5 SDA (bus)", (760, 870), anchor="middle")
wire(C_SCL, [(LPIN_X, 525), (500, 525), (500, 905), (980, 905), (980, 655), (1060, 655)], "D5 / GPIO6 SCL (bus)", (760, 917), anchor="middle")
wire(C_SDA, [(520, 750), (330, 750)], "SDA → DRV2605L", (415, 741), anchor="end")
wire(C_SCL, [(500, 720), (330, 720)], "SCL → DRV2605L", (415, 710), anchor="end")
wire(C_SDA, [(1000, 880), (1000, 680)], "SDA → LIS2DW12", (1006, 866))
wire(C_SCL, [(980, 905), (980, 655)], "SCL → LIS2DW12", (972, 760), anchor="end")
# power
wire(C_3V3, [(RPIN_X, 360), (940, 360), (940, 950), (420, 950), (420, 660), (330, 660)], "3V3 → DRV VIN", (375, 650), anchor="middle")
wire(C_3V3, [(940, 605), (1060, 605)], "3V3 → LIS VDD", (1000, 596), anchor="middle")
wire(C_3V3, [], "3V3 bus (XIAO 3V3 pin)", (760, 963), anchor="middle")
wire(C_GND, [(RPIN_X, 305), (960, 305), (960, 975), (440, 975), (440, 690), (330, 690)], "GND → DRV GND", (375, 681), anchor="middle")
wire(C_GND, [(960, 630), (1060, 630)], "GND → LIS GND", (1000, 642), anchor="middle")
wire(C_GND, [], "GND bus (XIAO GND pin)", (760, 990), anchor="middle")
wire(C_GND, [(1060, 755), (1020, 755)], "", (0, 0))
wire(C_3V3, [(1060, 780), (1035, 780), (1035, 805)], "", (0, 0))
# INT1
wire(C_INT, [(1060, 705), (912, 705), (912, 525), (RPIN_X, 525)], "INT1 → D8 / GPIO7 (EXT1 wake)", (990, 696), anchor="middle")
# LRA
wire(C_LRA, [(120, 700), (85, 700)], "OUT+", (100, 690), anchor="middle")
wire(C_LRA, [(120, 730), (85, 730)], "OUT−", (100, 745), anchor="middle")
# optional / n-c stubs on the right
wire(C_OPT, [(RPIN_X, 470), (915, 470)], "D9 / GPIO8 → optional touch pad: copper foil / coin via 1 kΩ", (960, 470), dash="4 3")
wire(C_OPT, [(RPIN_X, 250), (915, 250)], "5V n/c", (960, 250), dash="4 3")
# ---- optional MAX98357A I2S amp breakout (box at x 1330-1530, y 530-760; left pins DIN/BCLK/LRC/GAIN, right pins VIN/GND/SD)
AMP_X0, AMP_X1, AMP_Y0, AMP_Y1 = 1330, 1530, 530, 760
AMP_PIN_Y = {"DIN": 600, "BCLK": 630, "LRC": 660, "GAIN": 700, "VIN": 600, "GND": 630, "SD": 660}
# DIN from D10 runs through the corridor between the check-list box and the LIS breakout (y 540)
wire(C_I2S, [(RPIN_X, 415), (926, 415), (926, 540), (1300, 540), (1300, AMP_PIN_Y["DIN"]), (AMP_X0, AMP_PIN_Y["DIN"])],
     "D10 / GPIO9 → I²S DIN (was AUX)", (1110, 532), anchor="middle")
# BCLK from D7 and LRC from D6 run under the I2C bus lines and above the 3V3/GND buses (y 920 / 935)
wire(C_I2S, [(RPIN_X, 580), (900, 580), (900, 920), (1310, 920), (1310, AMP_PIN_Y["BCLK"]), (AMP_X0, AMP_PIN_Y["BCLK"])],
     "D7 / GPIO44 → I²S BCLK", (1105, 915), anchor="middle")
wire(C_I2S, [(LPIN_X, 580), (558, 580), (558, 935), (1320, 935), (1320, AMP_PIN_Y["LRC"]), (AMP_X0, AMP_PIN_Y["LRC"])],
     "D6 / GPIO43 → I²S LRC", (600, 931))
# amp power from the 3V3 / GND buses (right of the amp), SD tied to 3V3 = left-channel mode
wire(C_3V3, [(940, 950), (1560, 950), (1560, AMP_PIN_Y["VIN"]), (AMP_X1, AMP_PIN_Y["VIN"])], "3V3 → amp VIN", (1250, 962), anchor="middle")
wire(C_GND, [(960, 975), (1575, 975), (1575, AMP_PIN_Y["GND"]), (AMP_X1, AMP_PIN_Y["GND"])], "GND → amp GND", (1250, 987), anchor="middle")
wire(C_3V3, [(AMP_X1, AMP_PIN_Y["SD"]), (1560, AMP_PIN_Y["SD"])], "SD→3V3", (1566, 655))
# speaker on the amp's terminal block
wire(C_LRA, [(1400, AMP_Y1), (1400, 808)], "+", (1392, 790), anchor="end")
wire(C_LRA, [(1460, AMP_Y1), (1460, 808)], "−", (1468, 790))

JUNCTIONS = [(400, 165), (520, 750), (500, 720), (940, 605), (960, 630), (1000, 880), (980, 905),
             (940, 950), (960, 975), (1560, AMP_PIN_Y["SD"])]


def gnd_symbol(svg, x, y, label="GND"):
    svg.line(x, y, x, y + 10, stroke=C_GND, sw=2)
    svg.line(x - 12, y + 10, x + 12, y + 10, stroke=C_GND, sw=2)
    svg.line(x - 8, y + 15, x + 8, y + 15, stroke=C_GND, sw=2)
    svg.line(x - 4, y + 20, x + 4, y + 20, stroke=C_GND, sw=2)
    if label:
        svg.text(x + 16, y + 14, label, size=9, fill=C_GND)


def resistor(svg, x0, y0, x1, y1, label):
    svg.rect(min(x0, x1), min(y0, y1), abs(x1 - x0), abs(y1 - y0), fill="#fff", stroke="#333", sw=1.5)
    if label:
        svg.text((x0 + x1) / 2, (y0 + y1) / 2, label, size=9, anchor="middle", weight="bold")


def draw() -> None:
    svg = SVG(1640, 1060)
    svg.text(20, 30, "mcring stage 0 — bench wiring: Seeed XIAO ESP32S3 Sense (+ optional MAX98357A speaker)", size=22, weight="bold")
    svg.text(20, 54, "BOARD_XIAO_ESP32S3_SENSE pin map (firmware/ring-esp32s3/src/config.h + config_audio.h). Top view, USB-C up. Every wire is labelled.",
             size=11.5, fill="#444")
    svg.text(20, 72, "Colours: red 3V3 · black GND · dark-red BAT+ · blue SDA · amber SCL · green GPIO · purple INT · teal I²S · brown LRA/speaker · grey dashed = optional / n/c.",
             size=11.5, fill="#444")

    # ---- XIAO + Sense ----
    svg.rect(585, 185, 290, 445, fill="none", stroke="#555", sw=1.2, dash="6 4", rx=8)
    svg.text(730, 176, "Sense board on top (B2B): OV2640, PDM mic GPIO41/42, microSD unused",
             size=9.5, anchor="middle", fill="#555", italic=True)
    svg.rect(XX0, XY0, XX1 - XX0, XY1 - XY0, fill="#1b2631", stroke="#000", sw=2, rx=10)
    svg.rect(700, 190, 60, 24, fill="#95a5a6", stroke="#333", sw=1, rx=4)
    svg.text(730, 202, "USB-C", size=9, anchor="middle", fill="#111", weight="bold")
    svg.text(730, 232, "XIAO ESP32S3 Sense", size=13, anchor="middle", fill="#fff", weight="bold")
    svg.rect(698, 255, 64, 64, fill="#2c3e50", stroke="#aab7b8", sw=1, rx=6)
    svg.circle(730, 287, 20, fill="#111", stroke="#aab7b8", sw=1.5)
    svg.text(730, 335, "OV2640 (on Sense)", size=8.5, anchor="middle", fill="#ddd")
    svg.rect(700, 355, 60, 28, fill="#34495e", stroke="#aab7b8", sw=1, rx=3)
    svg.text(730, 369, "ESP32-S3", size=8.5, anchor="middle", fill="#fff")
    svg.text(730, 400, "PDM mic (Sense)", size=8.5, anchor="middle", fill="#ddd")
    svg.text(730, 420, "user LED GPIO21", size=8.5, anchor="middle", fill="#ddd")
    svg.text(730, 445, "on-board charger (USB → LiPo)", size=8.5, anchor="middle", fill="#ddd")
    svg.text(730, 560, "BAT pads on the UNDERSIDE", size=9, anchor="middle", fill="#f9e79f")
    for x, lab in [(680, "BAT+"), (780, "BAT−")]:
        svg.rect(x - 16, 584, 32, 28, fill="#f9e79f", stroke="#7d6608", sw=1.2, rx=3)
        svg.text(x, 598, lab, size=9, anchor="middle", weight="bold")
    # header pins
    for i, (lab, gpio, fn) in enumerate(LEFT):
        y = PIN_Y[i]
        svg.line(XX0, y, LPIN_X, y, stroke="#aab7b8", sw=3)
        svg.circle(LPIN_X, y, 4, fill="#fff", stroke="#333", sw=1)
        svg.text(XX0 + 8, y - 6, lab, size=10, fill="#fff", weight="bold")
        svg.text(XX0 + 8, y + 8, f"{gpio} · {fn}", size=8, fill="#d5dbdb")
    for i, (lab, gpio, fn) in enumerate(RIGHT):
        y = PIN_Y[i]
        svg.line(XX1, y, RPIN_X, y, stroke="#aab7b8", sw=3)
        svg.circle(RPIN_X, y, 4, fill="#fff", stroke="#333", sw=1)
        svg.text(XX1 - 8, y - 6, lab, size=10, fill="#fff", weight="bold", anchor="end")
        svg.text(XX1 - 8, y + 8, f"{gpio} · {fn}", size=8, fill="#d5dbdb", anchor="end")

    # ---- LiPo ----
    svg.rect(640, 700, 180, 60, fill="#f9e79f", stroke="#7d6608", sw=1.5, rx=6)
    svg.text(730, 722, "LiPo 1S 100 mAh (with PCM)", size=11, anchor="middle", weight="bold")
    svg.text(730, 742, "JST-PH or solder to the BAT pads — polarity!", size=9, anchor="middle")

    # ---- battery divider (top-left) ----
    svg.rect(150, 100, 370, 148, fill="#fdfefe", stroke="#aaa", sw=1, dash="3 3", rx=6)
    svg.text(160, 116, "Battery sense divider (BATTERY_DIVIDER = 2.0, ≈ 20 µA drain)", size=10, weight="bold", fill="#333")
    # BAT+ net flag
    svg.polygon([(200, 165), (212, 158), (230, 158), (230, 172), (212, 172)], fill=C_BAT, stroke="none")
    svg.text(162, 190, "BAT+ = LiPo red = XIAO BAT+ pad", size=8.5, fill=C_BAT)
    svg.text(162, 203, "(net flag — same node as the pad above)", size=8, fill="#777", italic=True)
    resistor(svg, 230, 155, 310, 175, "R1 100 kΩ")
    svg.line(310, 165, 340, 165, stroke=C_SIG, sw=2)
    svg.circle(340, 165, 3.8, fill="#111", stroke="none")
    svg.line(340, 165, 340, 182, stroke=C_SIG, sw=2)
    resistor(svg, 330, 182, 350, 214, "")
    svg.text(356, 192, "R2", size=9, weight="bold"); svg.text(356, 204, "100 kΩ", size=9)
    gnd_symbol(svg, 340, 214, "")
    svg.line(400, 165, 400, 185, stroke=C_SIG, sw=2)
    svg.line(388, 185, 412, 185, stroke="#333", sw=2.5)
    svg.line(388, 193, 412, 193, stroke="#333", sw=2.5)
    svg.line(400, 193, 400, 212, stroke=C_GND, sw=2)
    svg.text(416, 192, "C1 100 nF", size=9)
    gnd_symbol(svg, 400, 212, "GND")

    # ---- button ----
    svg.circle(480, 305, 4, fill="#fff", stroke="#333", sw=1.5)
    svg.circle(440, 305, 4, fill="#fff", stroke="#333", sw=1.5)
    svg.line(476, 304, 445, 290, stroke="#333", sw=2)
    svg.line(440, 305, 420, 305, stroke=C_GND, sw=2)
    gnd_symbol(svg, 420, 305, "GND")
    svg.text(450, 345, "tactile SW (internal pull-up, EXT0 wake)", size=8.5, anchor="middle")

    # ---- piezo ----
    svg.circle(455, 415, 20, fill="#fff", stroke="#333", sw=1.5)
    svg.circle(455, 415, 12, fill="none", stroke="#333", sw=1)
    svg.text(455, 450, "piezo 12 mm", size=9, anchor="middle")
    svg.line(435, 415, 420, 415, stroke=C_GND, sw=2)
    gnd_symbol(svg, 420, 415, "GND")
    svg.line(480, 415, 475, 415, stroke=C_SIG, sw=2)

    # ---- DRV2605L breakout ----
    svg.rect(120, 620, 210, 220, fill="#eaf2f8", stroke="#1b4f72", sw=1.5, rx=6)
    svg.text(225, 638, "DRV2605L breakout", size=12, anchor="middle", weight="bold", fill="#1b4f72")
    svg.text(225, 652, "Adafruit 2305 / clone · I²C 0x5A", size=8.5, anchor="middle", fill="#1b4f72")
    for y, lab in [(660, "VIN"), (690, "GND"), (720, "SCL"), (750, "SDA"), (780, "IN/TRIG"), (810, "EN")]:
        svg.line(330, y, 345, y, stroke="#1b4f72", sw=3)
        svg.circle(330, y, 3.5, fill="#fff", stroke="#1b4f72", sw=1.2)
        svg.text(322, y + 3, lab, size=9, anchor="end", fill="#1b4f72", weight="bold")
    svg.text(322, 793, "n/c (I²C RTP mode)", size=7.5, anchor="end", fill="#555")
    svg.text(225, 828, "EN: on-board pull-up / tie to VIN if D2 is not used", size=7.5, anchor="middle", fill="#555")
    for y, lab in [(700, "OUT+ / M+"), (730, "OUT− / M−")]:
        svg.circle(120, y, 3.5, fill="#fff", stroke="#1b4f72", sw=1.2)
        svg.text(128, y + 3, lab, size=9, fill="#1b4f72", weight="bold")
    # LRA
    svg.circle(55, 715, 28, fill="#d7bde2", stroke="#4a235a", sw=1.5)
    svg.text(55, 711, "LRA", size=10, anchor="middle", weight="bold")
    svg.text(55, 724, "Ø8 mm", size=8, anchor="middle")
    svg.text(55, 758, "INEED LRA0825BC / 235 Hz", size=7.5, anchor="middle")
    svg.text(55, 770, "(polarity irrelevant)", size=7.5, anchor="middle")

    # ---- LIS2DW12 breakout ----
    svg.rect(1060, 560, 230, 245, fill="#eafaf1", stroke="#1e8449", sw=1.5, rx=6)
    svg.text(1175, 578, "LIS2DW12 breakout", size=12, anchor="middle", weight="bold", fill="#1e8449")
    svg.text(1175, 593, "any STEVAL / clone · I²C 0x18 (SA0 = GND)", size=8.5, anchor="middle", fill="#1e8449")
    for y, lab in [(605, "VDD"), (630, "GND"), (655, "SCL"), (680, "SDA"), (705, "INT1"), (730, "INT2"), (755, "SA0/SDO"), (780, "CS")]:
        svg.line(1060, y, 1075, y, stroke="#1e8449", sw=3)
        svg.circle(1060, y, 3.5, fill="#fff", stroke="#1e8449", sw=1.2)
        svg.text(1080, y + 3, lab, size=9, fill="#1e8449", weight="bold")
    svg.text(1130, 733, "n/c", size=8, fill="#555")
    svg.text(1175, 797, "0.1 µF on VDD is on the breakout", size=8, anchor="middle", fill="#555")
    gnd_symbol(svg, 1020, 755, "")
    svg.text(1035, 819, "3V3", size=9, fill=C_3V3, weight="bold", anchor="middle")
    svg.text(1065, 822, "SA0 → GND  →  I²C address 0x18", size=9, fill="#333")
    svg.text(1065, 836, "CS → 3V3 (I²C mode; skip if the breakout already ties it)", size=9, fill="#333")

    # ---- MAX98357A I2S amp breakout (optional) + 10 mm speaker ----
    svg.rect(AMP_X0, AMP_Y0, AMP_X1 - AMP_X0, AMP_Y1 - AMP_Y0, fill="#fdf2e9", stroke="#b9770e", sw=1.5, rx=6)
    svg.text((AMP_X0 + AMP_X1) / 2, AMP_Y0 + 18, "MAX98357A I²S amp (optional)", size=12, anchor="middle", weight="bold", fill="#b9770e")
    svg.text((AMP_X0 + AMP_X1) / 2, AMP_Y0 + 32, "Adafruit 3006 / clone · class-D mono · 2.5–5.5 V", size=8.5, anchor="middle", fill="#b9770e")
    for lab in ("DIN", "BCLK", "LRC", "GAIN"):
        y = AMP_PIN_Y[lab]
        svg.line(AMP_X0, y, AMP_X0 + 15, y, stroke="#b9770e", sw=3)
        svg.circle(AMP_X0, y, 3.5, fill="#fff", stroke="#b9770e", sw=1.2)
        svg.text(AMP_X0 + 20, y + 3, lab, size=9, fill="#b9770e", weight="bold")
    svg.text(AMP_X0 + 56, AMP_PIN_Y["GAIN"] + 3, "open = 9 dB (firmware volume trims clipping at 3.3 V)", size=7.5, fill="#555")
    for lab in ("VIN", "GND", "SD"):
        y = AMP_PIN_Y[lab]
        svg.line(AMP_X1 - 15, y, AMP_X1, y, stroke="#b9770e", sw=3)
        svg.circle(AMP_X1, y, 3.5, fill="#fff", stroke="#b9770e", sw=1.2)
        svg.text(AMP_X1 - 20, y + 3, lab, size=9, fill="#b9770e", weight="bold", anchor="end")
    svg.text((AMP_X0 + AMP_X1) / 2, 722, "SD → 3V3 = left channel; the breakout's own pull-up ((L+R)/2)", size=7.5, anchor="middle", fill="#555")
    svg.text((AMP_X0 + AMP_X1) / 2, 734, "works too — the firmware writes mono into both I²S slots", size=7.5, anchor="middle", fill="#555")
    svg.text((AMP_X0 + AMP_X1) / 2, 750, "speaker terminal block ▼  (≈ 2.4 mA idle: SD has no GPIO on the dev kit)", size=7.5, anchor="middle", fill="#555")
    for x in (1400, 1460):
        svg.circle(x, AMP_Y1, 3.5, fill="#fff", stroke="#b9770e", sw=1.2)
    svg.circle(1430, 838, 30, fill="#d7bde2", stroke="#4a235a", sw=1.5)
    svg.circle(1430, 838, 18, fill="none", stroke="#4a235a", sw=1)
    svg.text(1430, 835, "speaker", size=9, anchor="middle", weight="bold")
    svg.text(1430, 847, "Ø10 · 8 Ω", size=8, anchor="middle")
    svg.text(1430, 884, "PUI AS01008MR-2-R (stage-1 part)", size=7.5, anchor="middle")
    svg.text(1430, 896, "or a 1 W 8 Ω oval (Adafruit 3923) for the bench", size=7.5, anchor="middle")
    svg.text(1430, 908, "polarity irrelevant", size=7.5, anchor="middle")

    # ---- wires ----
    for color, pts, label, (lx, ly), anchor, dash, rot in WIRES:
        if pts:
            svg.polyline(pts, stroke=color, sw=2.4, dash=dash, linejoin="miter")
        if label:
            svg.text(lx, ly, label, size=9, fill=color, anchor=anchor, rotate=rot,
                     weight="bold" if color in (C_3V3, C_GND) else "normal")
    for (jx, jy) in JUNCTIONS:
        svg.circle(jx, jy, 3.8, fill="#111", stroke="none")
    svg.text(1010, 1045, "wire crossings without a dot are NOT connected", size=9, fill="#555", italic=True)

    # ---- legend ----
    lx, ly = 20, 880
    svg.rect(lx - 6, ly - 18, 300, 186, fill="#fdfefe", stroke="#bbb", sw=1, rx=6)
    svg.text(lx, ly, "Wire colours", size=11, weight="bold")
    for i, (c, t) in enumerate([(C_3V3, "3V3 (XIAO 3V3 pin → VIN/VDD, amp VIN + SD)"), (C_GND, "GND"), (C_BAT, "BAT+ (raw cell voltage)"),
                                (C_SDA, "I²C SDA (D4 / GPIO5)"), (C_SCL, "I²C SCL (D5 / GPIO6)"), (C_SIG, "GPIO signals"),
                                (C_INT, "interrupt INT1 → D8 / GPIO7"), (C_I2S, "I²S to the amp (D7 BCLK, D6 LRC, D10 DIN)"),
                                (C_LRA, "LRA / speaker drive pair"), (C_OPT, "optional / leave open")]):
        svg.line(lx, ly + 16 + i * 15, lx + 30, ly + 16 + i * 15, stroke=c, sw=3)
        svg.text(lx + 38, ly + 16 + i * 15, t, size=9)

    # ---- check list ----
    cx, cy = 1070, 60
    svg.rect(cx - 10, cy - 16, 420, 410, fill="#fef9e7", stroke="#b7950b", sw=1.2, rx=6)
    svg.text(cx, cy, "Check before power-on", size=13, weight="bold", fill="#7d6608")
    checks = [
        "1. LiPo polarity: red → BAT+, black → BAT− (underside pads). A reversed",
        "   cell kills the XIAO charger. Cell has a PCM. Nothing on the 5V pin.",
        "2. Ohmmeter: BAT+ to GND and 3V3 to GND are not shorted (kΩ, not 0).",
        "3. Divider: BAT+ → R1 100k → A0 → R2 100k → GND, C1 100 nF A0–GND.",
        "   A0 must never see > 3.3 V (both R = 100k, so VBAT/2 ≤ 2.1 V).",
        "4. DRV2605L VIN = 3V3 (not 5V). OUT+/OUT− only to the LRA — never to",
        "   GND or a supply. Set LRA rated/overdrive voltage in firmware ≤ 1.25 Vrms.",
        "5. I²C: one SDA, one SCL, shared by both breakouts; their on-board pull-ups",
        "   (2 x 10k in parallel ≈ 5k) are fine at 400 kHz. No extra pull-ups needed.",
        "6. LIS2DW12: SA0 → GND (0x18), CS → 3V3 if exposed, INT1 → D8 only.",
        "7. Button and piezo go to GND, not to 3V3 (GPIO2/GPIO4 drive them",
        "   with the internal pull-up / LEDC).",
        "8. GPIO2 (D1) is not a strapping pin on the S3 — but keep D1 released at",
        "   reset anyway. D6/D7 carry I²S once the amp is fitted (logs are USB-CDC).",
        "9. Sense board seated fully on both B2B connectors; camera FPC latched.",
        "10. First power from USB with the cell disconnected; check 3V3 = 3.3 V,",
        "    then connect the cell and confirm the charge LED.",
        "11. i2cdetect / firmware boot log must list 0x18 and 0x5A.",
        "12. The dev kit draws ~3 mA in deep sleep with the Sense board attached",
        "    (no camera power gate) — expected, see hardware/power-budget.txt.",
        "13. Speaker amp (optional): VIN = 3V3 (not 5V), SD → 3V3, GAIN open; BCLK → D7,",
        "    LRC → D6, DIN → D10. Speaker only on the amp's +/− terminal, never to GND/3V3.",
        "14. With the amp fitted D6/D7 are I²S (no UART0 logs) and D10 is no longer PIN_AUX.",
    ]
    svg.multiline(cx, cy + 20, checks, size=9, lh=16)

    svg.save(os.path.join(OUT, "wiring_stage0.svg"), png_scale=2.0)


def write_md() -> None:
    rows = [
        ("XIAO D0 / A0 (GPIO1)", "divider mid-point", "BAT+ → R1 100 kΩ → **A0** → R2 100 kΩ → GND; C1 100 nF A0–GND", "green"),
        ("XIAO D1 (GPIO2)", "tactile button → GND", "internal pull-up, EXT0 deep-sleep wake", "green"),
        ("XIAO D2 (GPIO3)", "DRV2605L EN (optional)", "only if the breakout exposes EN; otherwise leave open (pull-up on the breakout)", "grey, dashed"),
        ("XIAO D3 (GPIO4)", "piezo (+)", "piezo (−) → GND; LEDC tone", "green"),
        ("XIAO D4 (GPIO5)", "SDA", "DRV2605L SDA + LIS2DW12 SDA", "blue"),
        ("XIAO D5 (GPIO6)", "SCL", "DRV2605L SCL + LIS2DW12 SCL", "amber"),
        ("XIAO D8 (GPIO7)", "LIS2DW12 INT1", "double-tap interrupt, EXT1 wake (any-high)", "purple"),
        ("XIAO D9 (GPIO8)", "touch pad (optional)", "copper foil / coin via 1 kΩ; touch channel T8", "grey, dashed"),
        ("XIAO D10 (GPIO9)", "MAX98357A DIN (optional speaker)", "I²S data; **was `PIN_AUX`** — `config_audio.h` reassigns D10 and sets `PIN_AUX` −1 on the dev kit (the air-puff experiment is parked)", "teal"),
        ("XIAO D7 / RX (GPIO44)", "MAX98357A BCLK (optional speaker)", "I²S bit clock, 32 × fs = 512 kHz at 16 kHz; UART0 RXD0 is free (logging is USB-CDC)", "teal"),
        ("XIAO D6 / TX (GPIO43)", "MAX98357A LRC (optional speaker)", "I²S word clock = 16 kHz; UART0 TXD0 — the ROM banner at reset is ~50 ms of garbage frames without BCLK, inaudible", "teal"),
        ("XIAO 3V3", "DRV2605L VIN, LIS2DW12 VDD (+ CS), MAX98357A VIN + SD", "3.3 V regulator output; SD → 3V3 = left-channel mode (the breakout's own pull-up, (L+R)/2, works too: mono is written into both slots)", "red"),
        ("XIAO GND", "DRV2605L GND, LIS2DW12 GND, LIS SA0, MAX98357A GND, button, piezo, divider, C1", "common ground", "black"),
        ("XIAO BAT+ / BAT− (underside pads)", "LiPo 1S 100 mAh (PCM)", "BAT+ also feeds the divider", "dark red / black"),
        ("DRV2605L OUT+ / OUT−", "LRA 8 mm (INEED LRA0825BC-0167F)", "polarity irrelevant; closed-loop LRA mode", "brown"),
        ("MAX98357A + / − terminal", "10 mm 8 Ω speaker (PUI AS01008MR-2-R, or a 1 W 8 Ω oval for the bench)", "polarity irrelevant; GAIN left open = 9 dB; `PIN_SPEAKER_EN` is −1 on the dev kit, so the amp idles at ~2.4 mA", "brown"),
        ("XIAO 5V", "—", "leave open", "—"),
        ("Sense board", "B2B on top of the XIAO", "OV2640 DVP (GPIO10–18, 38–40, 47, 48), PDM mic (GPIO41/42)", "—"),
    ]
    md = ["# Stage-0 bench wiring — XIAO ESP32S3 Sense", "",
          "Drawing: `out/wiring_stage0.svg` / `.png` (generated by `wiring_stage0.py`). Pin map = "
          "`BOARD_XIAO_ESP32S3_SENSE` in `firmware/ring-esp32s3/src/config.h` + `config_audio.h` (also `hardware/pinmap.md`). "
          "The MAX98357A amp + speaker are optional: without them D6/D7/D10 stay open and the firmware still runs "
          "(`HAS_SPEAKER` is 1 on this board, so the I²S pins just drive nothing).", "",
          "## Connections", "", "| From | To | Detail | Colour |", "|---|---|---|---|"]
    md += [f"| {a} | {b} | {c} | {d} |" for a, b, c, d in rows]
    md += ["", "## XIAO header (top view, USB-C up)", "",
           "| Left column | GPIO | Use | Right column | GPIO | Use |", "|---|---|---|---|---|---|"]
    for (l, lg, lf), (r, rg, rf) in zip(LEFT, RIGHT):
        md.append(f"| {l} | {lg} | {lf} | {r} | {rg} | {rf} |")
    md += ["", "## Parts", "",
           "* Seeed XIAO ESP32S3 **Sense** (camera + mic expansion board included)",
           "* DRV2605L breakout (Adafruit 2305 or clone) + 8 mm LRA (INEED LRA0825BC-0167F, or any 2.5–3.3 mm coin LRA)",
           "* LIS2DW12 breakout (SA0 pin accessible); 0.1 µF already on the breakout",
           "* 6 × 6 mm tactile button, 12 mm piezo sounder, 2 × 100 kΩ 1 %, 1 × 100 nF",
           "* LiPo 1S 100 mAh with PCM (XIAO charger ≈ 100 mA, so ~1 C — fine)",
           "* optional: MAX98357A I²S amp breakout (Adafruit 3006 or clone) + a 10 mm 8 Ω speaker (PUI AS01008MR-2-R — "
           "the stage-1 part — or a 1 W 8 Ω oval such as Adafruit 3923) on BCLK D7 / LRC D6 / DIN D10, SD + VIN → 3V3",
           "* breadboard + jumper wires; optional copper-foil touch pad + 1 kΩ", "",
           "## Check before power-on", "",
           "1. **LiPo polarity**: red → BAT+, black → BAT− on the underside pads; the cell has a PCM. Nothing on the 5V pin.",
           "2. Ohmmeter: BAT+ ↔ GND and 3V3 ↔ GND read kΩ, not 0 Ω.",
           "3. Divider is BAT+ → 100 k → A0 → 100 k → GND with 100 nF on A0; A0 never sees more than VBAT/2 ≈ 2.1 V.",
           "4. DRV2605L VIN = 3V3 (not 5 V); OUT+/OUT− only to the LRA. In firmware the LRA rated voltage is ≤ 1.25 Vrms.",
           "5. One SDA, one SCL shared by both breakouts; their on-board pull-ups are enough — add none.",
           "6. LIS2DW12 SA0 → GND (address 0x18); CS → 3V3 if exposed; INT1 → D8 only.",
           "7. Button and piezo return to GND, never to 3V3.",
           "8. Keep D1 (button) released at reset; D6/D7 carry I²S once the amp is fitted (USB-CDC logging is the default anyway).",
           "9. Sense board fully seated on both B2B connectors, camera FPC latched.",
           "10. First power from USB with the cell disconnected → 3V3 = 3.3 V; then connect the cell, charge LED on.",
           "11. Boot log / `i2cdetect` lists **0x18** and **0x5A**.",
           "12. ~3 mA deep-sleep current with the Sense board attached is expected on the dev kit (no camera power gate).",
           "13. Speaker amp (optional): VIN = 3V3 (not 5 V), SD → 3V3, GAIN open; BCLK → D7, LRC → D6, DIN → D10; the speaker "
           "only on the amp's +/− terminal, never to GND or 3V3. Expect ~2.4 mA extra idle current (no SD GPIO on the dev kit).",
           "14. With the amp fitted D10 is no longer `PIN_AUX` — the air-puff experiment is parked on the dev kit.",
           ""]
    with open(os.path.join(HERE, "wiring_stage0.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md))


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    draw()
    write_md()
    print("wrote out/wiring_stage0.svg, out/wiring_stage0.png, wiring_stage0.md")
