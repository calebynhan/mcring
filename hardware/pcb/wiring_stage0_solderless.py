#!/usr/bin/env python3
"""Stage-0 *no-solder* bench rig: pre-soldered Seeed XIAO ESP32S3 Sense seated in Seeed's Expansion Board Base
for XIAO (103030356) + Grove Haptic Motor (DRV2605L + ERM) + LIS3DH STEMMA QT breakout + JST LiPo, with the
optional MAX98357A amp + speaker as the one item that still has header holes.
Pure Python → out/wiring_stage0_solderless.svg/.png and wiring_stage0_solderless.md. The soldered breadboard rig
stays in wiring_stage0.py (this file does not touch it).

Pin assignments are BOARD_XIAO_ESP32S3_SENSE + MCRING_XIAO_BASE (firmware/ring-esp32s3/src/config.h + config_audio.h,
platformio env xiao_esp32s3_sense_base):
  D1 = GPIO2 button (the base's user button), D3 = GPIO4 buzzer (the base's passive buzzer on A3), D4/D5 = GPIO5/6 I²C
  (the base's two Grove I²C sockets), D8 = GPIO7 IMU INT1 (jumper from the LIS3DH's INT hole, optional — the firmware
  also polls), D2 = GPIO3 is the base's microSD CS → PIN_HAPTIC parked (-1), D6/D7 = GPIO43/44 I²S LRC/BCLK (= the base's
  Grove-UART socket), D10 = GPIO9 I²S DIN. Battery sense (A0) is not built on this rig → battery % reads "unknown".
Sources for the base's pin use: Seeed wiki (Expansion Board Base for XIAO), Zephyr `seeed_xiao_expansion_board` shield
table, docs/research/04-no-solder-sourcing.md §A2. Not verified from the base's schematic (fetch blocked): whether its
charger output reaches the XIAO's BAT pads or only the 5V/VIN pin, and the exact SD SPI pins (assumed D8/D9/D10).
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from svgkit import SVG  # noqa: E402

OUT = os.path.join(HERE, "out")

# colours (same palette as wiring_stage0.py)
C_3V3, C_GND, C_BAT, C_SDA, C_SCL, C_SIG, C_INT, C_LRA, C_OPT, C_I2S, C_GROVE = (
    "#d62728", "#111111", "#b03a2e", "#1f77b4", "#d4a017", "#2ca02c", "#8e44ad", "#8c564b", "#7f8c8d", "#17a589",
    "#5d6d7e")

# ---- geometry ---------------------------------------------------------------------------------------------
W, H = 1700, 1110
BX0, BX1, BY0, BY1 = 330, 1150, 110, 650           # Expansion Board Base outline
XX0, XX1, XY0, XY1 = 660, 840, 180, 520            # XIAO body (seated in the base's socket)
PIN_Y = [215 + 45 * i for i in range(7)]           # breakout header rows (same order as the XIAO header)
LHX0, LHX1 = 548, 580                              # left breakout header (female) x extent
RHX0, RHX1 = 910, 942                              # right breakout header
LPIN_X, RPIN_X = 540, 940                          # where a jumper plugs in (drawn attachment points)

# (name, GPIO, short tag beside the header, long use for the markdown table)
LEFT = [("D0 / A0", "GPIO1", "bat. sense: n/c", "battery sense — not built on this rig (A0/D0 Grove socket)"),
        ("D1", "GPIO2", "base button", "BUTTON = the base's user button"),
        ("D2", "GPIO3", "SD CS (parked)", "the base's microSD CS — PIN_HAPTIC parked at −1"),
        ("D3", "GPIO4", "base buzzer", "BUZZER = the base's passive buzzer (A3)"),
        ("D4 / SDA", "GPIO5", "I²C SDA (Grove)", "I²C SDA — both Grove I²C sockets, OLED, RTC"),
        ("D5 / SCL", "GPIO6", "I²C SCL (Grove)", "I²C SCL — both Grove I²C sockets, OLED, RTC"),
        ("D6 / TX", "GPIO43", "I²S LRC (UART)", "I²S LRC — the Grove UART socket (optional amp)")]
RIGHT = [("5V", "VBUS", "do not use", "do not use"),
         ("GND", "GND", "GND", "GND"),
         ("3V3", "3V3", "3.3 V out", "3.3 V out"),
         ("D10", "GPIO9", "I²S DIN (jumper)", "I²S DIN — male-male jumper to the optional amp"),
         ("D9", "GPIO8", "touch: n/c", "touch — n/c (the base's SD MISO)"),
         ("D8", "GPIO7", "IMU INT1 (jumper)", "IMU INT1 ← LIS3DH INT (male-male jumper, optional)"),
         ("D7 / RX", "GPIO44", "I²S BCLK (UART)", "I²S BCLK — the Grove UART socket (optional amp)")]

# Grove sockets on the base's bottom edge: (x0, label, sub-label)
GROVE = [(400, "Grove I²C #1", "D4 SDA · D5 SCL"), (560, "Grove I²C #2", "D4 SDA · D5 SCL"),
         (740, "Grove UART", "D7 RX · D6 TX"), (920, "Grove A0 / D0", "GPIO1 · GPIO2")]
GROVE_W, GROVE_Y0, GROVE_Y1 = 90, 606, 644
JST_X, JST_Y0, JST_Y1 = 1104, 182, 240              # JST 2.0 LiPo socket on the base's right edge

# off-board parts
HAP_X0, HAP_X1, HAP_Y0, HAP_Y1 = 340, 610, 770, 912          # Grove Haptic Motor module
LIS_X0, LIS_X1, LIS_Y0, LIS_Y1 = 665, 995, 770, 960          # LIS3DH STEMMA QT breakout
AMP_X0, AMP_X1, AMP_Y0, AMP_Y1 = 1255, 1505, 300, 560        # optional MAX98357A breakout
AMP_PIN_Y = {"DIN": 350, "BCLK": 390, "LRC": 430, "GAIN": 470, "VIN": 350, "GND": 390, "SD": 430}
LIPO_X0, LIPO_X1, LIPO_Y0, LIPO_Y1 = 1225, 1540, 170, 252
INT_X = 1015                                                 # vertical run of the INT jumper

WIRES = []   # (colour, points, label, (lx, ly), anchor, dash, rotate, sw)


def wire(color, pts, label="", lpos=(0, 0), anchor="start", dash=None, rotate=None, sw=2.4):
    WIRES.append((color, pts, label, lpos, anchor, dash, rotate, sw))


def grove_cx(i):
    return GROVE[i][0] + GROVE_W / 2


# ---- define every connection ------------------------------------------------------------------------------
# Grove I²C #1 → Grove Haptic Motor (one Grove cable, 4 conductors drawn as a bundle)
g1 = grove_cx(0)
wire(C_GROVE, [(g1, GROVE_Y1), (g1, HAP_Y0)], "Grove cable (in the kit's module box)", (g1 + 8, 700), sw=5)
# Grove I²C #2 → Grove→STEMMA QT cable → LIS3DH QT socket
g2 = grove_cx(1)
wire(C_GROVE, [(g2, GROVE_Y1), (g2, 705), (740, 705), (740, LIS_Y0)], "Grove → STEMMA QT / Qwiic cable (Adafruit 4528)",
     (750, 746), sw=5)
# LIS3DH INT → D8 (press-fit pin / clip + male-male jumper into the right breakout header)
wire(C_INT, [(LIS_X1, 840), (INT_X, 840), (INT_X, PIN_Y[5]), (RPIN_X, PIN_Y[5])],
     "INT → D8 / GPIO7 (tap-wake) — optional", (INT_X + 10, 846))
# JST LiPo
wire(C_BAT, [(JST_X + 46, 198), (LIPO_X0, 198)], "BAT+", (1187, 188), anchor="middle")
wire(C_GND, [(JST_X + 46, 224), (LIPO_X0, 224)], "BAT−", (1187, 240), anchor="middle")
# ---- optional MAX98357A: Grove-UART socket → 4 male jumpers (D7 BCLK, D6 LRC, VCC, GND), D10 → DIN, SD → VIN
gu = grove_cx(2)
wire(C_I2S, [(gu - 12, GROVE_Y1), (gu - 12, 690), (1190, 690), (1190, AMP_PIN_Y["BCLK"]), (AMP_X0, AMP_PIN_Y["BCLK"])],
     "Grove UART pin D7 / GPIO44 → BCLK", (1026, 683), dash="7 4")
wire(C_I2S, [(gu - 4, GROVE_Y1), (gu - 4, 704), (1204, 704), (1204, AMP_PIN_Y["LRC"]), (AMP_X0, AMP_PIN_Y["LRC"])],
     "Grove UART pin D6 / GPIO43 → LRC", (1026, 697), dash="7 4")
wire(C_3V3, [(gu + 4, GROVE_Y1), (gu + 4, 718), (1545, 718), (1545, AMP_PIN_Y["VIN"]), (AMP_X1, AMP_PIN_Y["VIN"])],
     "Grove VCC (3V3) → amp VIN", (1240, 711), dash="7 4")
wire(C_GND, [(gu + 12, GROVE_Y1), (gu + 12, 732), (1560, 732), (1560, AMP_PIN_Y["GND"]), (AMP_X1, AMP_PIN_Y["GND"])],
     "Grove GND → amp GND", (1240, 745), dash="7 4")
wire(C_I2S, [(RPIN_X, PIN_Y[3]), (1230, PIN_Y[3]), (1230, AMP_PIN_Y["DIN"]), (AMP_X0, AMP_PIN_Y["DIN"])],
     "D10 / GPIO9 → DIN (male-male jumper)", (1085, PIN_Y[3] - 9), anchor="middle", dash="7 4")
wire(C_3V3, [(AMP_X1, AMP_PIN_Y["SD"]), (1545, AMP_PIN_Y["SD"])], "SD→VIN", (1508, AMP_PIN_Y["SD"] - 9), dash="7 4")
# speaker on the amp's pre-soldered terminal block
wire(C_LRA, [(1350, AMP_Y1), (1350, 600)], "+", (1342, 585), anchor="end")
wire(C_LRA, [(1410, AMP_Y1), (1410, 600)], "−", (1418, 585))

JUNCTIONS = [(1545, AMP_PIN_Y["SD"])]


def label_rows(svg, x, y, rows, size=8.5, lh=13, fill="#333"):
    for i, s in enumerate(rows):
        svg.text(x, y + i * lh, s, size=size, fill=fill)


def draw() -> None:
    svg = SVG(W, H)
    svg.text(20, 30, "mcring stage 0 — NO-SOLDER bench rig: XIAO ESP32S3 Sense (pre-soldered) in the Expansion Board Base", size=22, weight="bold")
    svg.text(20, 54, "Everything plugs in: base socket, Grove cables, STEMMA QT, JST battery, male-male jumpers into the base's breakout headers. "
             "Firmware: pio run -e xiao_esp32s3_sense_base (-DMCRING_XIAO_BASE).", size=11.5, fill="#444")
    svg.text(20, 72, "Colours: slate = Grove / QT cable · purple INT · dark-red BAT+ · black GND · red 3V3 · teal I²S · brown speaker · "
             "dashed = optional (speaker amp is the one part whose header holes still want pins).", size=11.5, fill="#444")

    # ---- legend (top left) ----
    lx, ly = 20, 150
    svg.rect(lx - 6, ly - 18, 296, 190, fill="#fdfefe", stroke="#bbb", sw=1, rx=6)
    svg.text(lx, ly, "Wire / cable colours", size=11, weight="bold")
    for i, (c, t) in enumerate([(C_GROVE, "Grove cable / Grove→STEMMA QT cable (I²C + 3V3 + GND)"),
                                (C_INT, "LIS3DH INT → D8 / GPIO7 (jumper; optional)"),
                                (C_BAT, "BAT+ (JST-PH, red)"), (C_GND, "GND / BAT− (black)"),
                                (C_3V3, "3V3 (amp VIN, SD)"), (C_I2S, "I²S to the optional amp (D7 BCLK, D6 LRC, D10 DIN)"),
                                (C_LRA, "speaker pair (pre-soldered terminal block)"),
                                (C_OPT, "n/c — leave open")]):
        svg.line(lx, ly + 16 + i * 15, lx + 30, ly + 16 + i * 15, stroke=c, sw=3)
        svg.text(lx + 38, ly + 16 + i * 15, t, size=9)
    svg.text(lx, ly + 16 + 8 * 15 + 6, "Thick slate = a 4-conductor Grove cable drawn as one bundle.", size=8.5, fill="#555", italic=True)

    # ---- build / flash box (left) ----
    bx, by = 20, 380
    svg.rect(bx - 6, by - 18, 296, 196, fill="#eef5fb", stroke="#7fa6c8", sw=1, rx=6)
    svg.text(bx, by, "Build, flash, expect", size=11, weight="bold", fill="#1b4f72")
    label_rows(svg, bx, by + 18, [
        "cd firmware/ring-esp32s3",
        "pio run -e xiao_esp32s3_sense_base -t upload",
        "pio device monitor -b 115200",
        "",
        "boot log: fw … (xiao-esp32s3-sense+base)",
        "  I imu: LIS3DH ready at 0x18 (double click -> INT1 …)",
        "  I drv: DRV2605L ready (ERM) · autocal ok",
        "  status flags 0x56 = camera+IMU+haptic+speaker",
        "  batt=0mV(255%) — no divider on this rig",
        "button = the base's own button (D1), beep = base buzzer",
        "double-tap the LIS3DH board → hands-free ask",
        "no INT jumper? taps still work (25 ms poll),",
        "  only tap-to-wake from deep sleep is lost",
    ], size=8.5, lh=13, fill="#1b4f72")

    # ---- Expansion Board Base ----
    svg.rect(BX0, BY0, BX1 - BX0, BY1 - BY0, fill="#e8f0e8", stroke="#2e5e2e", sw=2, rx=12)
    svg.text(BX0 + 14, BY0 + 20, "Seeed Expansion Board Base for XIAO (103030356 / Adafruit 5033) — top view, USB-C up", size=12.5, weight="bold", fill="#2e5e2e")
    svg.text(BX0 + 14, BY0 + 36, "all XIAO pins broken out on two female headers · 2 × Grove I²C · Grove UART · Grove A0/D0 · JST 2.0 LiPo + charger (460 mA max) · OLED · RTC · microSD · buzzer · button",
             size=8.5, fill="#2e5e2e")
    # on-base parts (left column, inside the base)
    parts = [
        (190, "User button → D1 (GPIO2)", "= PIN_BUTTON: hold = ask, short = photo"),
        (250, "Passive buzzer → A3 = D3 (GPIO4)", "= PIN_BUZZER: beep cues (off by default)"),
        (310, "OLED 0.96″ SSD1306 · I²C 0x3C", "unused; no clash with 0x5A / 0x18"),
        (370, "RTC PCF8563 · I²C 0x51 (CR1220)", "unused; INT jumper: leave open"),
        (430, "microSD slot — leave EMPTY", "CS = D2 → PIN_HAPTIC parked; SPI D8–D10"),
        (490, "Charger + JST 2.0 LiPo socket →", "≤ 460 mA → use a ≥ 400 mAh cell"),
    ]
    for y, t1, t2 in parts:
        svg.rect(346, y - 14, 192, 44, fill="#fdfefe", stroke="#9bb59b", sw=1, rx=4)
        svg.text(356, y, t1, size=8.8, weight="bold", fill="#1e4620")
        svg.text(356, y + 14, t2, size=7.4, fill="#444")
    svg.text(440, 548, "RESET button · SWD pads · 5 V servo header: unused", size=8, anchor="middle", fill="#555", italic=True)
    svg.text(440, 562, "(the base's charge LED lights while the cell charges)", size=8, anchor="middle", fill="#555", italic=True)

    # XIAO + Sense seated in the socket
    svg.rect(XX0 - 15, XY0 - 14, (XX1 - XX0) + 30, (XY1 - XY0) + 28, fill="none", stroke="#555", sw=1.2, dash="6 4", rx=8)
    svg.text((XX0 + XX1) / 2, XY0 - 20, "Sense board on top (B2B): OV2640, PDM mic GPIO41/42, its microSD unused",
             size=9, anchor="middle", fill="#555", italic=True)
    svg.rect(XX0, XY0, XX1 - XX0, XY1 - XY0, fill="#1b2631", stroke="#000", sw=2, rx=10)
    svg.rect(720, 170, 60, 24, fill="#95a5a6", stroke="#333", sw=1, rx=4)
    svg.text(750, 182, "USB-C", size=9, anchor="middle", fill="#111", weight="bold")
    svg.text(750, 212, "XIAO ESP32S3 Sense", size=12.5, anchor="middle", fill="#fff", weight="bold")
    svg.text(750, 226, "PRE-SOLDERED (Seeed 102010635)", size=8.5, anchor="middle", fill="#f9e79f", weight="bold")
    svg.text(750, 238, "pins point DOWN into the base's socket", size=8, anchor="middle", fill="#f9e79f")
    svg.rect(720, 252, 60, 60, fill="#2c3e50", stroke="#aab7b8", sw=1, rx=6)
    svg.circle(750, 282, 19, fill="#111", stroke="#aab7b8", sw=1.5)
    svg.text(750, 326, "OV2640 (on Sense)", size=8.5, anchor="middle", fill="#ddd")
    svg.rect(720, 340, 60, 28, fill="#34495e", stroke="#aab7b8", sw=1, rx=3)
    svg.text(750, 354, "ESP32-S3", size=8.5, anchor="middle", fill="#fff")
    svg.text(750, 386, "PDM mic (Sense)", size=8.5, anchor="middle", fill="#ddd")
    svg.text(750, 402, "user LED GPIO21 = light cue", size=8.5, anchor="middle", fill="#ddd")
    svg.text(750, 428, "own charger + BAT pads: UNUSED", size=8.5, anchor="middle", fill="#f9e79f")
    svg.text(750, 442, "(the base's JST cell feeds the XIAO —", size=7.8, anchor="middle", fill="#ddd")
    svg.text(750, 454, "via 5V/VIN or BAT pads: not verified)", size=7.8, anchor="middle", fill="#ddd")
    svg.text(750, 480, "14 pins → the two female", size=8.5, anchor="middle", fill="#ddd")
    svg.text(750, 492, "breakout headers beside it", size=8.5, anchor="middle", fill="#ddd")
    # socket pins (short stubs from the XIAO into the base)
    for y in PIN_Y:
        svg.line(XX0 - 10, y, XX0, y, stroke="#aab7b8", sw=3)
        svg.line(XX1, y, XX1 + 10, y, stroke="#aab7b8", sw=3)

    # breakout headers (female): left and right, with the XIAO pin names
    svg.rect(LHX0, PIN_Y[0] - 20, LHX1 - LHX0, PIN_Y[-1] - PIN_Y[0] + 40, fill="#222", stroke="#000", sw=1, rx=3)
    svg.rect(RHX0, PIN_Y[0] - 20, RHX1 - RHX0, PIN_Y[-1] - PIN_Y[0] + 40, fill="#222", stroke="#000", sw=1, rx=3)
    svg.text((LHX0 + LHX1) / 2, PIN_Y[0] - 30, "breakout header (female)", size=7.5, anchor="middle", fill="#333")
    svg.text((RHX0 + RHX1) / 2, PIN_Y[0] - 30, "breakout header (female)", size=7.5, anchor="middle", fill="#333")
    for i, (lab, gpio, fn, _) in enumerate(LEFT):
        y = PIN_Y[i]
        svg.rect(LHX0 + 10, y - 6, 12, 12, fill="#777", stroke="#000", sw=0.8, rx=2)
        svg.line(LHX0, y, LPIN_X, y, stroke="#aab7b8", sw=2)
        svg.circle(LPIN_X, y, 3.5, fill="#fff", stroke="#333", sw=1)
        svg.text(LHX0 + 36, y - 8, lab, size=9, fill="#111", weight="bold")
        svg.text(LHX0 + 36, y + 3, gpio, size=6.8, fill="#555")
        svg.text(LHX0 + 36, y + 13, fn, size=6.8, fill="#333")
    for i, (lab, gpio, fn, _) in enumerate(RIGHT):
        y = PIN_Y[i]
        svg.rect(RHX0 + 10, y - 6, 12, 12, fill="#777", stroke="#000", sw=0.8, rx=2)
        svg.line(RHX1, y, RPIN_X, y, stroke="#aab7b8", sw=2)
        svg.circle(RPIN_X, y, 3.5, fill="#fff", stroke="#333", sw=1)
        svg.text(RHX0 - 4, y - 8, lab, size=9, fill="#111", weight="bold", anchor="end")
        svg.text(RHX0 - 4, y + 3, gpio, size=6.8, fill="#555", anchor="end")
        svg.text(RHX0 - 4, y + 13, fn, size=6.8, fill="#333", anchor="end")

    # Grove sockets on the bottom edge
    for x0, lab, sub in GROVE:
        svg.rect(x0, GROVE_Y0, GROVE_W, GROVE_Y1 - GROVE_Y0, fill="#fff", stroke="#2e5e2e", sw=1.5, rx=3)
        for k in range(4):
            svg.rect(x0 + 12 + k * 18, GROVE_Y0 + 6, 8, 8, fill="#bbb", stroke="#333", sw=0.6)
        svg.text(x0 + GROVE_W / 2, GROVE_Y0 + 24, lab, size=8.5, anchor="middle", weight="bold", fill="#2e5e2e")
        svg.text(x0 + GROVE_W / 2, GROVE_Y0 + 34, sub, size=7, anchor="middle", fill="#444")
    svg.text(grove_cx(3), GROVE_Y0 - 12, "n/c (A0: divider if you build one)", size=7.5, anchor="middle", fill="#555", italic=True)
    svg.text(grove_cx(2), GROVE_Y0 - 12, "no UART Grove *device* here: D6/D7 = I²S", size=7.5, anchor="middle", fill="#555", italic=True)

    # JST LiPo socket on the right edge
    svg.rect(JST_X, JST_Y0, 46, JST_Y1 - JST_Y0, fill="#fff", stroke="#2e5e2e", sw=1.5, rx=3)
    svg.text(JST_X + 23, JST_Y0 + 14, "JST 2.0", size=8, anchor="middle", weight="bold", fill="#2e5e2e")
    svg.text(JST_X + 23, JST_Y0 + 26, "LiPo", size=8, anchor="middle", fill="#2e5e2e")
    svg.text(JST_X + 23, JST_Y0 + 38, "+ / −", size=8, anchor="middle", fill="#2e5e2e")
    svg.text(JST_X + 23, JST_Y0 + 50, "(silk!)", size=7, anchor="middle", fill="#b03a2e")

    # ---- LiPo ----
    svg.rect(LIPO_X0, LIPO_Y0, LIPO_X1 - LIPO_X0, LIPO_Y1 - LIPO_Y0, fill="#f9e79f", stroke="#7d6608", sw=1.5, rx=6)
    svg.text((LIPO_X0 + LIPO_X1) / 2, LIPO_Y0 + 18, "LiPo 1S ≥ 400 mAh, JST-PH plug, with PCM", size=10.5, anchor="middle", weight="bold")
    svg.text((LIPO_X0 + LIPO_X1) / 2, LIPO_Y0 + 34, "Adafruit 3898 (400 mAh) / 1578 (500 mAh) — the base charges at", size=8, anchor="middle")
    svg.text((LIPO_X0 + LIPO_X1) / 2, LIPO_Y0 + 46, "up to 460 mA, too fast for the 100 mAh ring cell (Adafruit 1570)", size=8, anchor="middle")
    svg.text((LIPO_X0 + LIPO_X1) / 2, LIPO_Y0 + 60, "check red = + against the base silkscreen; a forum thread reports", size=7.5, anchor="middle", fill="#b03a2e")
    svg.text((LIPO_X0 + LIPO_X1) / 2, LIPO_Y0 + 71, "reversed pigtails on early units — never force a mismatched plug", size=7.5, anchor="middle", fill="#b03a2e")

    # ---- Grove Haptic Motor ----
    svg.rect(HAP_X0, HAP_Y0, HAP_X1 - HAP_X0, HAP_Y1 - HAP_Y0, fill="#eaf2f8", stroke="#1b4f72", sw=1.5, rx=6)
    svg.rect(g1 - 22, HAP_Y0, 44, 18, fill="#fff", stroke="#1b4f72", sw=1.2, rx=2)
    svg.text(g1, HAP_Y0 + 12, "Grove", size=7.5, anchor="middle", fill="#1b4f72")
    svg.text((HAP_X0 + HAP_X1) / 2, HAP_Y0 + 36, "Grove – Haptic Motor", size=12, anchor="middle", weight="bold", fill="#1b4f72")
    svg.text((HAP_X0 + HAP_X1) / 2, HAP_Y0 + 50, "Seeed 105020011 · DRV2605L · I²C 0x5A", size=8.5, anchor="middle", fill="#1b4f72")
    svg.text((HAP_X0 + HAP_X1) / 2, HAP_Y0 + 66, "ERM coin motor factory-attached — zero joints", size=8.5, anchor="middle", fill="#1b4f72")
    svg.text((HAP_X0 + HAP_X1) / 2, HAP_Y0 + 82, "EN tied on-module → PIN_HAPTIC = -1 in this build", size=7.8, anchor="middle", fill="#555")
    svg.text((HAP_X0 + HAP_X1) / 2, HAP_Y0 + 96, "firmware: HAPTIC_MOTOR_LRA 0 → drv2605_init(false)", size=7.8, anchor="middle", fill="#555")
    svg.text((HAP_X0 + HAP_X1) / 2, HAP_Y0 + 110, "LRA feel returns at stage 1 (INEED LRA0825BC on the board)", size=7.8, anchor="middle", fill="#555")
    svg.text((HAP_X0 + HAP_X1) / 2, HAP_Y0 + 126, "(alt.: Adafruit 2305 DRV2605L QT — motor pads need solder)", size=7.4, anchor="middle", fill="#7f8c8d", italic=True)
    ex, ey = HAP_X0 - 46, (HAP_Y0 + HAP_Y1) / 2
    svg.circle(ex, ey, 26, fill="#d7bde2", stroke="#4a235a", sw=1.5)
    svg.text(ex, ey - 4, "ERM", size=10, anchor="middle", weight="bold")
    svg.text(ex, ey + 9, "on module", size=7, anchor="middle")
    svg.line(HAP_X0, ey - 8, HAP_X0 - 18, ey - 8, stroke=C_LRA, sw=2)
    svg.line(HAP_X0, ey + 8, HAP_X0 - 18, ey + 8, stroke=C_LRA, sw=2)

    # ---- LIS3DH STEMMA QT breakout ----
    svg.rect(LIS_X0, LIS_Y0, LIS_X1 - LIS_X0, LIS_Y1 - LIS_Y0, fill="#eafaf1", stroke="#1e8449", sw=1.5, rx=6)
    svg.rect(740 - 22, LIS_Y0, 44, 18, fill="#fff", stroke="#1e8449", sw=1.2, rx=2)
    svg.text(740, LIS_Y0 + 12, "QT in", size=7.5, anchor="middle", fill="#1e8449")
    svg.rect(930 - 22, LIS_Y0, 44, 18, fill="#fff", stroke="#1e8449", sw=1.2, rx=2)
    svg.text(930, LIS_Y0 + 12, "QT out", size=7.5, anchor="middle", fill="#1e8449")
    svg.text(930, LIS_Y0 + 30, "n/c (daisy-chain spare)", size=7, anchor="middle", fill="#555")
    svg.text((LIS_X0 + LIS_X1) / 2, LIS_Y0 + 48, "LIS3DH accelerometer — STEMMA QT / Qwiic", size=12, anchor="middle", weight="bold", fill="#1e8449")
    svg.text((LIS_X0 + LIS_X1) / 2, LIS_Y0 + 63, "Adafruit 2809 — I²C 0x18 (0x19 with the SDO jumper)", size=8, anchor="middle", fill="#1e8449")
    svg.text((LIS_X0 + LIS_X1) / 2, LIS_Y0 + 76, "or SparkFun Micro LIS3DH Qwiic SEN-29529 (0x19)", size=8, anchor="middle", fill="#1e8449")
    svg.text((LIS_X0 + LIS_X1) / 2, LIS_Y0 + 92, "WHO_AM_I 0x33 — firmware auto-detects LIS2DW12 / LIS3DH at boot", size=8, anchor="middle", fill="#333")
    svg.text((LIS_X0 + LIS_X1) / 2, LIS_Y0 + 106, "double click on X/Y/Z → INT1, latched until CLICK_SRC is read", size=8, anchor="middle", fill="#333")
    svg.text((LIS_X0 + LIS_X1) / 2, LIS_Y0 + 120, "tape it to a finger / a coin: a floating board taps itself", size=8, anchor="middle", fill="#333")
    # INT / I2 through-holes on the right edge
    for y, lab in [(840, "INT"), (870, "I2")]:
        svg.circle(LIS_X1, y, 4.5, fill="#fff", stroke="#1e8449", sw=1.3)
        svg.text(LIS_X1 - 10, y + 3.5, lab, size=8.5, anchor="end", fill="#1e8449", weight="bold")
    svg.text(LIS_X1 - 30, 873, "n/c", size=7, anchor="end", fill="#555")
    svg.text((LIS_X0 + LIS_X1) / 2, LIS_Y0 + 138, "INT is a bare through-hole. Solderless options: a male jumper pin pushed", size=7.6, anchor="middle", fill="#555")
    svg.text((LIS_X0 + LIS_X1) / 2, LIS_Y0 + 150, "in at an angle (friction), a tapped-in hammer-header pin (Adafruit 3662),", size=7.6, anchor="middle", fill="#555")
    svg.text((LIS_X0 + LIS_X1) / 2, LIS_Y0 + 162, "an IC-hook clip — or skip it: the base build polls (no deep-sleep tap-wake)", size=7.6, anchor="middle", fill="#555")
    svg.text((LIS_X0 + LIS_X1) / 2, LIS_Y0 + 174, "other end: male-male jumper into the base's breakout header hole D8", size=7.6, anchor="middle", fill="#555")

    # ---- optional MAX98357A + speaker ----
    svg.rect(AMP_X0, AMP_Y0, AMP_X1 - AMP_X0, AMP_Y1 - AMP_Y0, fill="#fdf2e9", stroke="#b9770e", sw=1.5, rx=6, dash="6 4")
    svg.text((AMP_X0 + AMP_X1) / 2, AMP_Y0 + 16, "MAX98357A I²S amp — OPTIONAL", size=12, anchor="middle", weight="bold", fill="#b9770e")
    svg.text((AMP_X0 + AMP_X1) / 2, AMP_Y0 + 30, "Adafruit 3006: speaker terminal block pre-soldered (2024-06+)", size=8, anchor="middle", fill="#b9770e")
    for lab in ("DIN", "BCLK", "LRC", "GAIN"):
        y = AMP_PIN_Y[lab]
        svg.line(AMP_X0, y, AMP_X0 + 15, y, stroke="#b9770e", sw=3)
        svg.circle(AMP_X0, y, 3.5, fill="#fff", stroke="#b9770e", sw=1.2)
        svg.text(AMP_X0 + 20, y + 3, lab, size=9, fill="#b9770e", weight="bold")
    svg.text(AMP_X0 + 56, AMP_PIN_Y["GAIN"] + 3, "open = 9 dB (volume ≤ 200)", size=7.5, fill="#555")
    for lab in ("VIN", "GND", "SD"):
        y = AMP_PIN_Y[lab]
        svg.line(AMP_X1 - 15, y, AMP_X1, y, stroke="#b9770e", sw=3)
        svg.circle(AMP_X1, y, 3.5, fill="#fff", stroke="#b9770e", sw=1.2)
        svg.text(AMP_X1 - 20, y + 3, lab, size=9, fill="#b9770e", weight="bold", anchor="end")
    svg.text((AMP_X0 + AMP_X1) / 2, 496, "its 7 header holes are NOT soldered:", size=8, anchor="middle", fill="#7d4a00", weight="bold")
    svg.text((AMP_X0 + AMP_X1) / 2, 508, "press-fit hammer-header pins (Adafruit 3662, fit unverified)", size=7.5, anchor="middle", fill="#555")
    svg.text((AMP_X0 + AMP_X1) / 2, 520, "+ female jumpers, or 5 joints at a makerspace, or defer", size=7.5, anchor="middle", fill="#555")
    svg.text((AMP_X0 + AMP_X1) / 2, 532, "to stage 1 (amp is SMT on the board). Headphones need none of this.", size=7.5, anchor="middle", fill="#555")
    svg.text((AMP_X0 + AMP_X1) / 2, 548, "speaker terminal block ▼ (screw, no solder)", size=7.5, anchor="middle", fill="#555")
    for x in (1350, 1410):
        svg.circle(x, AMP_Y1, 3.5, fill="#fff", stroke="#b9770e", sw=1.2)
    svg.circle(1380, 630, 28, fill="#d7bde2", stroke="#4a235a", sw=1.5)
    svg.circle(1380, 630, 17, fill="none", stroke="#4a235a", sw=1)
    svg.text(1380, 627, "speaker", size=9, anchor="middle", weight="bold")
    svg.text(1380, 639, "Ø10 · 8 Ω", size=8, anchor="middle")
    svg.text(1380, 672, "PUI AS01008MR-2-R (stage-1 part) or Adafruit 3923", size=7.5, anchor="middle")
    svg.text(1380, 684, "bare leads into the screw terminal · polarity irrelevant", size=7.5, anchor="middle")
    svg.text(1240, 760, "Grove UART socket → 'Grove to 4-pin male jumper' cable (Seeed 110990210): D7, D6, 3V3, GND in one plug;", size=7.6, fill="#555")
    svg.text(1240, 772, "which Grove pin is D6 and which D7 → base silkscreen; swap BCLK/LRC if there is no sound", size=7.6, fill="#555")

    # ---- wires ----
    for color, pts, label, (lx, ly), anchor, dash, rot, sw in WIRES:
        if pts:
            svg.polyline(pts, stroke=color, sw=sw, dash=dash, linejoin="miter")
        if label:
            svg.text(lx, ly, label, size=9, fill=color, anchor=anchor, rotate=rot,
                     weight="bold" if color in (C_3V3, C_GND, C_BAT) else "normal")
    for (jx, jy) in JUNCTIONS:
        svg.circle(jx, jy, 3.8, fill="#111", stroke="none")

    # ---- check list (bottom right) ----
    cx, cy = 1250, 815
    svg.rect(cx - 10, cy - 18, 440, 300, fill="#fef9e7", stroke="#b7950b", sw=1.2, rx=6)
    svg.text(cx, cy, "Check before power-on (no iron, so no shorts to make — but still:)", size=11.5, weight="bold", fill="#7d6608")
    checks = [
        "1. XIAO seated the right way round (USB-C toward the base's USB end;",
        "   pin 1 / D0 at the base's D0 silkscreen) — reversed = dead board.",
        "2. Sense board clicked onto both B2B connectors; camera FPC latched.",
        "3. LiPo: red = + on the base's JST silkscreen. ≥ 400 mAh (charger 460 mA).",
        "4. Grove Haptic Motor and Grove→QT cable in the two I²C sockets — NOT",
        "   in the UART or A0/D0 socket (UART pins are I²S D6/D7).",
        "5. LIS3DH INT → D8 only (never 3V3/5V). Skipping it is allowed (polling).",
        "6. microSD slot empty: its CS is D2 and its SPI shares D8/D9/D10.",
        "7. Nothing on the 5V header pin. Amp VIN = 3V3 (never 5V); SD → VIN.",
        "8. Speaker leads only in the amp's +/− terminal, never to GND/3V3.",
        "9. First power from USB with the cell unplugged; then plug the cell:",
        "   the base's charge LED lights. Boot log lists 0x5A (drv) and 0x18/19 (imu).",
        "10. Status flags 0x56 (camera+IMU+haptic+speaker); batt reads 255 % = no divider.",
        "11. Deep sleep with the Sense board and the base fitted is milliamps (OLED,",
        "    RTC, charger, no camera power gate) — the bench kit is not for sleep numbers.",
        "12. Build with -e xiao_esp32s3_sense_base; the stock env still runs but drives",
        "    the ERM as an LRA (autocal FAILED) and toggles D2 = the base's SD CS.",
    ]
    svg.multiline(cx, cy + 20, checks, size=8.6, lh=15.5)
    svg.text(20, H - 14, "wire crossings without a dot are NOT connected · dashed = optional · generated by hardware/pcb/wiring_stage0_solderless.py",
             size=9, fill="#555", italic=True)

    svg.save(os.path.join(OUT, "wiring_stage0_solderless.svg"), png_scale=2.0)


def write_md() -> None:
    rows = [
        ("XIAO ESP32S3 Sense (pre-soldered, Seeed 102010635)", "Expansion Board Base socket", "pins point down into the base's two 7-pin female headers; USB-C toward the base's USB end; Sense board stays on top", "—"),
        ("Base user button", "D1 (GPIO2) = `PIN_BUTTON`", "already wired on the base; hold = ask, short press = photo, EXT0 deep-sleep wake", "on-base"),
        ("Base passive buzzer", "A3 = D3 (GPIO4) = `PIN_BUZZER`", "already wired on the base (cuttable trace); beep cues are off by default (`cues_mask` bit 2)", "on-base"),
        ("Base Grove I²C #1", "Grove – Haptic Motor (Seeed 105020011)", "DRV2605L 0x5A + factory-attached ERM; one Grove cable; `HAPTIC_MOTOR_LRA 0` → `drv2605_init(false)`", "slate (Grove)"),
        ("Base Grove I²C #2", "Grove → STEMMA QT / Qwiic cable → LIS3DH breakout QT socket", "Adafruit 4528 or SparkFun PRT-15109; LIS3DH = Adafruit 2809 (0x18) or SparkFun SEN-29529 (0x19); WHO_AM_I 0x33, detected at boot", "slate (Grove/QT)"),
        ("LIS3DH `INT` through-hole", "base breakout header **D8** (GPIO7) = `PIN_IMU_INT`", "male-male jumper; the breakout end is a press-fit pin / hammer-header pin / IC hook. **Optional**: with `MCRING_XIAO_BASE` the firmware polls the latched click source every 25 ms; only tap-to-wake from deep sleep needs the wire", "purple"),
        ("Base JST 2.0 LiPo socket", "LiPo 1S **≥ 400 mAh**, JST-PH, with PCM (Adafruit 3898 / 1578)", "the base charges at up to 460 mA — too much for the 100 mAh ring cell (Adafruit 1570, 1 C = 100 mA); check red = + against the silkscreen", "dark red / black"),
        ("Base microSD slot", "— (leave empty)", "CS = D2 (GPIO3) → `PIN_HAPTIC` is parked at −1 in this build; SPI assumed on D8/D9/D10 (shared with INT1 / touch / I²S DIN)", "—"),
        ("Base OLED 0x3C, RTC 0x51", "— (unused)", "share the I²C bus; no clash with 0x5A / 0x18 / 0x19; RTC INT routing not verified — leave its jumper open", "—"),
        ("Base Grove A0/D0", "— (n/c)", "A0 = GPIO1 = `PIN_BATTERY_ADC`: a 100 k/100 k divider could be built on a breadboard from here, but the cell's + is only on the JST pigtail → not in the kit; STATUS shows battery 255 % (unknown)", "grey"),
        ("Base Grove UART (D7 RX, D6 TX)", "**optional** MAX98357A `BCLK` (D7 / GPIO44), `LRC` (D6 / GPIO43), `VIN` (3V3), `GND`", "'Grove to 4-pin male jumper' cable (Seeed 110990210) into female jumpers / the amp's press-fit pins; the base silkscreen says which Grove pin is D6 and which D7 — swap BCLK/LRC if silent. Never plug a UART Grove *device* here", "teal / red / black, dashed"),
        ("Base breakout header D10 (GPIO9)", "**optional** MAX98357A `DIN`", "male-male jumper; `PIN_AUX` is −1 on the XIAO (air-puff experiment parked)", "teal, dashed"),
        ("MAX98357A `SD`", "`VIN` (3V3)", "left-channel mode; the breakout's own pull-up ((L+R)/2) works too — mono is written into both slots", "red, dashed"),
        ("MAX98357A `+ / −` terminal block", "10 mm 8 Ω speaker (PUI AS01008MR-2-R) or Adafruit 3923", "screw terminal is pre-soldered on Adafruit 3006 since 2024-06; polarity irrelevant; GAIN open = 9 dB → keep volume ≤ 200", "brown"),
        ("XIAO BAT+/BAT− pads, 5V pin, D9", "—", "unused: the cell lives in the base; nothing on 5V; D9 (touch) is the base's SD MISO — no touch pad on this rig", "—"),
    ]
    md = ["# Stage-0 bench wiring — NO-SOLDER variant (XIAO ESP32S3 Sense in the Expansion Board Base)", "",
          "Drawing: `out/wiring_stage0_solderless.svg` / `.png` (generated by `wiring_stage0_solderless.py`). The soldered breadboard rig is "
          "`wiring_stage0.md`; this page replaces it for an owner who does not want to pick up an iron. Pin map = `BOARD_XIAO_ESP32S3_SENSE` "
          "+ `MCRING_XIAO_BASE` (`firmware/ring-esp32s3/src/config.h` + `config_audio.h`), built with "
          "`pio run -e xiao_esp32s3_sense_base -t upload`. Kit: `hardware/bom/stage0-devkit-solderless.csv`; sourcing evidence and the "
          "unverified items: `docs/research/04-no-solder-sourcing.md`.", "",
          "**Joint count: 0.** The pre-soldered XIAO seats in the base, the base already carries the button, buzzer, LiPo socket and charger, "
          "the haptic driver comes with its motor attached on a Grove module, the accelerometer is a STEMMA QT board fed from a Grove→QT cable, "
          "and the one interrupt wire is a jumper into the base's female breakout header. The optional speaker amp is the only part whose "
          "header holes are unsoldered (its speaker terminal block is pre-soldered) — press-fit pins, five joints at a makerspace, or wait for "
          "stage 1 where the amp is on the board.", "",
          "## Connections", "", "| From | To | Detail | Colour in the drawing |", "|---|---|---|---|"]
    md += [f"| {a} | {b} | {c} | {d} |" for a, b, c, d in rows]
    md += ["", "## XIAO header as it appears on the base's breakout headers (top view, USB-C up)", "",
           "| Left column | GPIO | Use on this rig | Right column | GPIO | Use on this rig |", "|---|---|---|---|---|---|"]
    for (l, lg, _, lf), (r, rg, _, rf) in zip(LEFT, RIGHT):
        md.append(f"| {l} | {lg} | {lf} | {r} | {rg} | {rf} |")
    md += ["", "## What the `MCRING_XIAO_BASE` build changes (`config_audio.h`)", "",
           "| Define | Stock XIAO build | `xiao_esp32s3_sense_base` | Why |",
           "|---|---|---|---|",
           "| `PIN_BUTTON` / `PIN_BUZZER` | 2 / 4 | 2 / 4 (restated) | the base's button is on D1 and its buzzer on A3 = D3 — same pins; restated so a base revision is a one-line change |",
           "| `PIN_HAPTIC` | 3 (D2, DRV EN) | −1 | D2 is the base's microSD chip-select; the Grove module's EN is tied on-module |",
           "| `HAPTIC_MOTOR_LRA` | 1 | 0 | Grove Haptic Motor is an ERM → `drv2605_init(false)`; autocal still runs |",
           "| `IMU_POLL_MS` | 0 | 25 | the LIS3DH latches its click interrupt, so polling `CLICK_SRC` catches taps when INT1 is not jumpered |",
           "| `BOARD_NAME` | `xiao-esp32s3-sense` | `xiao-esp32s3-sense+base` | the boot log tells you which build is running |",
           "", "The IMU driver itself needs no flag: `imu_init()` reads WHO_AM_I at 0x18/0x19 and uses the LIS2DW12 (0x44) or the LIS3DH (0x33) back-end "
           "(`src/imu_lis3dh.cpp`). `trigger.cpp` sees the LIS2DW12 `TAP_SRC` bit layout for both.", "",
           "## Parts", "",
           "* Seeed XIAO ESP32S3 **Sense, pre-soldered** (102010635) — the camera + mic board is included",
           "* Seeed **Expansion Board Base for XIAO** (103030356; Adafruit 5033)",
           "* Seeed **Grove – Haptic Motor** (105020011): DRV2605L + ERM, one Grove plug",
           "* Adafruit **LIS3DH STEMMA QT** (2809) or SparkFun Micro LIS3DH Qwiic (SEN-29529)",
           "* Adafruit **Grove → STEMMA QT / Qwiic cable** (4528) or SparkFun PRT-15109",
           "* male-male jumper wires (INT → D8; D10 → DIN); optionally one hammer-header strip (Adafruit 3662) for press-fit pins",
           "* LiPo 1S **≥ 400 mAh** JST-PH with PCM (Adafruit 3898 or 1578) — not the 100 mAh ring cell on this charger",
           "* optional speaker path: Adafruit MAX98357A (3006, terminal block pre-soldered), a 10 mm 8 Ω speaker (PUI AS01008MR-2-R or Adafruit 3923), "
           "a 'Grove to 4-pin male jumper' cable (Seeed 110990210) for the Grove-UART socket, female-female jumpers",
           "* USB-C data cable; Bluetooth headphones paired to the laptop/phone (that is where answers come out — the ring speaker is optional)", "",
           "## Check before power-on", "",
           "1. XIAO orientation in the base socket: USB-C toward the base's USB end, D0 at the base's D0 silkscreen. A reversed board is dead.",
           "2. Sense board fully clicked onto both B2B connectors; camera FPC latched.",
           "3. LiPo: red = + on the base's JST silkscreen (a Seeed forum thread reports reversed pigtails on early units; never force a plug). Cell ≥ 400 mAh — the charger is 460 mA.",
           "4. Grove Haptic Motor and the Grove→QT cable sit in the two **I²C** sockets, not in UART (= I²S D6/D7) or A0/D0.",
           "5. LIS3DH INT jumper → **D8** only (never 3V3 / 5V). Leaving it off is allowed: the firmware polls; only deep-sleep tap-wake is lost.",
           "6. microSD slot empty (CS = D2, SPI shares D8/D9/D10).",
           "7. Nothing on the 5V header pin. Amp (optional) VIN = 3V3, SD → VIN, GAIN open.",
           "8. Speaker leads only in the amp's +/− terminal block.",
           "9. First power from USB with the cell unplugged, then plug the cell: the base's charge LED lights.",
           "10. Boot log: `fw 0.1.0 (xiao-esp32s3-sense+base)`, `I imu: LIS3DH ready at 0x18 …`, `I drv: DRV2605L ready (ERM)`, `autocal ok`; status flags `0x56` "
           "(camera + IMU + haptic + speaker); `batt=0mV(255%)` is expected (no divider).",
           "11. Deep sleep with the base fitted is milliamps (OLED, RTC, charger, no camera power gate): use the soldered rig or stage 1 for sleep numbers.",
           "12. Flash with `-e xiao_esp32s3_sense_base`. The stock `xiao_esp32s3_sense` env still boots but drives the ERM with the LRA profile "
           "(`autocal FAILED`) and toggles D2 — the base's SD CS — as the haptic enable.", "",
           "## Not verified (fetch of the base's schematic was blocked)", "",
           "* whether the base's charger feeds the XIAO's BAT pads or only the 5V/VIN pin (the XIAO's own `BAT` pads are unused either way);",
           "* the base's SD SPI pins (assumed D8/D9/D10 = the XIAO's SPI) and the RTC INT jumper;",
           "* whether Adafruit 3662 hammer-header pins hold in the 1.0 mm holes of Adafruit/SparkFun breakouts;",
           "* list prices (October 2026 snippets): `hardware/bom/stage0-devkit-solderless.csv`.",
           ""]
    with open(os.path.join(HERE, "wiring_stage0_solderless.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md))


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    draw()
    write_md()
    print("wrote out/wiring_stage0_solderless.svg, out/wiring_stage0_solderless.png, wiring_stage0_solderless.md")
