"""
mcring_v1.py — electrical design of the stage-1 "mcring v1" ring board.

Single rigid 2-layer 0.6 mm board in the signet bay, ESP32-S3-MINI-1U-N4R2 with the
u.FL end pointing away from the camera.  Nets follow firmware/ring-esp32s3/src/config.h
(BOARD_MCRING_V1) after the IO19/IO20 native-USB conflict was resolved:

    PIN_CAM_PWR  19 -> 21   (RTC GPIO, no boot-time activity, hold-capable in deep sleep)
    PIN_RGB      20 -> 43   (TXD0; ROM boot chatter only reaches a power-gated LED through 1 k)
    PIN_RGB_PWR  33         LED_PWR_EN: second TPS22916 gating the WS2812 (firmware must drive it)
    PIN_CHG      3          BQ25100 /CHG (open drain, 100k pull-up) -> battery_charging()
    PIN_HAPTIC   -1         DRV2605L EN is tied to 3V3; haptics are I2C-only (standby via register)
    IO19/IO20    -> native USB D-/D+ test pads
    spare        IO34, IO35, IO36, IO37, IO44 (RXD0) — free on the N4R2 (quad PSRAM uses only IO26)

Review fixes folded in (see README §1): DRV2605L EN tied high, /CHG on IO3, LED_PWR_EN moved
off RXD0 to IO33, WS2812 fed from 3V3 through U9 with a 1 k data resistor, battery divider
1 M/1 M, R12 = 267 k (TPS62840 3.3 V code), wire-pad footprints for the cell / piezo / charging
pads with the cell, piezo element, band contacts and the u.FL flex antenna as off-board BOM
lines, series Schottky + bidirectional TVS on the charging input.

Run:  python3 mcring_v1.py   -> out/mcring_v1.net, mcring_v1_bom.csv, mcring_v1_nets.md, erc.md

Everything marked VERIFY below is a datasheet item that could not be checked from the
sandbox (no datasheet fetches); the README lists them all.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from netlist_model import Netlist, Part  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")

# --------------------------------------------------------------------------- #
# Design constants (also used by the README generator / report)
# --------------------------------------------------------------------------- #
GPIO = {  # BOARD_MCRING_V1 after the USB fix
    "CAM_XCLK": 10, "CAM_SIOD": 40, "CAM_SIOC": 39,
    "CAM_Y2": 15, "CAM_Y3": 17, "CAM_Y4": 18, "CAM_Y5": 16,
    "CAM_Y6": 14, "CAM_Y7": 12, "CAM_Y8": 11, "CAM_Y9": 48,
    "CAM_VSYNC": 38, "CAM_HREF": 47, "CAM_PCLK": 13,
    "PDM_CLK": 42, "PDM_DATA": 41,
    "BAT_SENSE": 1, "BUTTON": 2, "nCHG": 3, "BUZZER": 4,
    "SDA": 5, "SCL": 6, "IMU_INT1": 7, "TOUCH": 8, "AUX_EN": 9,
    "CAM_PWR_EN": 21,     # was 19 (USB D-)
    "RGB_DATA": 43,       # was 20 (USB D+)
    "LED_PWR_EN": 33,     # WS2812 supply gate (firmware PIN_RGB_PWR); was 44/RXD0 — the ROM enables the
                          # U0RXD pull-up at reset, which fought the pull-down; IO33 has no boot-time role
    "USB_DM": 19, "USB_DP": 20,
    "IO0": 0,
}
# Exposed GPIOs intentionally left free (firmware -1): IO34..IO37 and IO44 (RXD0). On the N4R2 the
# in-package quad PSRAM uses only SPICS1 = IO26; IO33..IO37 (SPIIO4..7/SPIDQS) are consumed by the
# OCTAL PSRAM of R8 parts only (ESP-IDF GPIO guide for ESP32-S3; module datasheet footnote VERIFY).
SPARE_GPIO = ("IO34", "IO35", "IO36", "IO37", "RXD0/IO44")

# BQ25100 programming (VERIFY constants against SLUSBW6):
#   I_CHG     = K_ISET / R_ISET,          K_ISET      = 230 A*ohm  -> 9.1k  => 25.3 mA (~0.85C of 30 mAh)
#   I_PRETERM = K_PRETERM / R_PRETERM,    K_PRETERM   = 11.5 A*ohm -> 11.5k => 1.0 mA termination
R_ISET = "9.1k"
R_PRETERM = "11.5k"
# TPS62840: output selected by an E96 resistor from VSET to GND (16 codes, 1.8..3.3 V; GND = 1.8 V).
# SLVSE12 Table 1 "Output voltage setting": 3.3 V <- 267 kOhm (also the value in TI's 3.3 V efficiency
# figure). Read from distributor copies of the datasheet, not the TI PDF itself — re-check once.
R_VSET = "267k"
# Battery divider: 1 M / 1 M + 100 nF. 4.2 V / 2 M = 2.1 uA permanent drain (100k/100k was 21 uA, i.e.
# ~80 % of the 25 uA stage-1 standby budget in hardware/power-budget.txt). The 100 nF holds the node
# for the ADC sample bursts (8 reads) so the 500 k source impedance does not matter.
R_DIVIDER = "1M"

# --------------------------------------------------------------------------- #
# Footprint shorthands (KiCad 7/8 library names; 'mcring:' = custom footprint)
# --------------------------------------------------------------------------- #
R0402 = "Resistor_SMD:R_0402_1005Metric"
C0402 = "Capacitor_SMD:C_0402_1005Metric"
C0603 = "Capacitor_SMD:C_0603_1608Metric"
C1206 = "Capacitor_SMD:C_1206_3216Metric"
SOT23 = "Package_TO_SOT_SMD:SOT-23"
SOD523 = "Diode_SMD:D_SOD-523"
TP = "TestPoint:TestPoint_Pad_D1.0mm"
# Wire pads (custom 'mcring' footprints): sizes/pitches match hardware/pcb/board_params.json
# "wire_pads_bottom_mm" (J1a/J1b and PAD1w/PAD2w 1.5 mm, BZ1a/BZ1b 1.2 mm, 2.0 mm pitch).
PAD2x15 = "mcring:PAD_Wire_2x1.5mm_P2.0mm"
PAD2x12 = "mcring:PAD_Wire_2x1.2mm_P2.0mm"
PAD1x15 = "mcring:PAD_Wire_1x1.5mm"

PASSIVE_PINS = {"1": "1", "2": "2"}


def R(ref, value, mpn, desc, sheet):
    return Part(ref, value, R0402, mpn=mpn, pins=PASSIVE_PINS, description=desc,
                manufacturer="Yageo", sheet=sheet)


def C(ref, value, fp, mpn, desc, sheet):
    return Part(ref, value, fp, mpn=mpn, pins=PASSIVE_PINS, description=desc,
                manufacturer="Murata", sheet=sheet)


def TPAD(ref, name, sheet):
    return Part(ref, f"TP_{name}", TP, mpn="", pins={"1": "1"}, description=f"test pad {name}", sheet=sheet)


# Yageo RC0402FR-07 part number helper
def rc(v):
    return f"RC0402FR-07{v}L"


def build() -> Netlist:
    nl = Netlist("mcring_v1", source="hardware/electrical/mcring_v1.py")
    nl.declare_power_nets("GND", "3V3", "VBAT", "CHG_PAD", "CHG_IN", "CAM_3V3", "CAM_2V8", "CAM_1V2", "VLED")

    # ------------------------------------------------------------------ MCU
    # ESP32-S3-MINI-1U pin table (VERIFY against esp32-s3-mini-1_mini-1u_datasheet_en.pdf,
    # Table "Pin Definitions"). 65 pads: 1-45 perimeter, 46-65 thermal/ground pads.
    # IO26 = SPICS1 = chip select of the in-package quad PSRAM on the N4R2 -> NC.  IO33..IO37 are
    # only taken by OCTAL PSRAM (R8 parts), so they are ordinary GPIOs here: IO33 = LED_PWR_EN,
    # IO34..IO37 spare.  IO45/IO46 are strapping pins -> left floating (internal defaults).
    u1_pins = {"1": "GND", "2": "GND", "3": "3V3"}
    for i, io in enumerate(range(0, 22)):           # pins 4..25 = IO0..IO21
        u1_pins[str(4 + i)] = f"IO{io}"
    u1_pins["26"] = "IO26"
    for i, io in enumerate(range(33, 43)):          # pins 27..36 = IO33..IO42
        u1_pins[str(27 + i)] = f"IO{io}"
    u1_pins["37"] = "TXD0/IO43"
    u1_pins["38"] = "RXD0/IO44"
    u1_pins["39"] = "IO45"
    u1_pins["40"] = "IO46"
    u1_pins["41"] = "IO47"
    u1_pins["42"] = "IO48"
    u1_pins["43"] = "GND"
    u1_pins["44"] = "GND"
    u1_pins["45"] = "EN"
    for p in range(46, 66):
        u1_pins[str(p)] = "GND"
    u1_gnd = {p for p, n in u1_pins.items() if n == "GND"}
    u1_spare = {p for p, n in u1_pins.items() if n in SPARE_GPIO}
    nl.add(Part("U1", "ESP32-S3-MINI-1U-N4R2", "RF_Module:ESP32-S3-MINI-1U",
                mpn="ESP32-S3-MINI-1U-N4R2", manufacturer="Espressif",
                pins=u1_pins, power_pins=u1_gnd | {"3"},
                nc_pins={"26", "39", "40"}, spare_pins=u1_spare,
                description="Wi-Fi/BLE module, 4 MB flash + 2 MB quad PSRAM, u.FL (mates with ANT1); pin table VERIFY",
                is_ic=True, sheet="MCU"))
    # The u.FL flex antenna. The module's u.FL receptacle is not a pad, so ANT1 is an off-board BOM
    # line whose RF node is a deliberate single-node net (waived below). Size/placement: README §5.
    nl.add(Part("ANT1", "2.4 GHz flex antenna, MHF1", "offboard:Antenna_Flex_34.9x9mm_MHF1",
                mpn="146153-0050", manufacturer="Molex", pins={"1": "RF"}, offboard=True,
                fields={"Alt MPN": "FXP70.07.0053A (Taoglas, 53 mm cable; outline VERIFY)"},
                description="2.4 GHz flex dipole 34.9 x 9 x 0.1 mm, 50 mm MHF1 (u.FL) pigtail -> U1 u.FL "
                            "(mated plug 2.9 mm tall = board_params top_max_height). Route down the back wall "
                            "/ along the band, >= 5 mm from cell and LRA; size vs the band is a fit check",
                sheet="MCU"))
    nl.add(R("R1", "10k", rc("10K"), "EN pull-up", "MCU"))
    nl.add(C("C6", "1u", C0402, "GRM155R61A105KE15", "EN RC (reset delay)", "MCU"))
    nl.add(R("R2", "10k", rc("10K"), "IO0 boot strap pull-up", "MCU"))
    nl.add(C("C4", "10u", C0603, "GRM188R60J106ME47", "module 3V3 decoupling", "MCU"))
    nl.add(C("C5", "100n", C0402, "GRM155R71C104KA88", "module 3V3 decoupling", "MCU"))
    nl.add(R("R3", "4.7k", rc("4K7"), "I2C SDA pull-up", "MCU"))
    nl.add(R("R4", "4.7k", rc("4K7"), "I2C SCL pull-up", "MCU"))
    nl.add(R("R17", "100k", rc("100K"), "CAM_PWR_EN pull-down (camera off in sleep/boot)", "MCU"))
    nl.add(R("R18", "4.7k", rc("4K7"), "LED_PWR_EN pull-down: LED rail off while IO33 floats (reset, download, deep "
                                        "sleep); 4.7k keeps the ON pin < 0.35 V even against a ~45k internal pull-up", "MCU"))
    nl.add(TPAD("TP1", "IO0", "MCU"))
    nl.add(TPAD("TP2", "EN", "MCU"))
    nl.add(TPAD("TP3", "USB_DM", "MCU"))
    nl.add(TPAD("TP4", "USB_DP", "MCU"))
    nl.add(TPAD("TP5", "GND", "MCU"))
    nl.add(TPAD("TP6", "3V3", "MCU"))
    nl.add(Part("SW2", "B3U-1000P", "mcring:SW_Omron_B3U-1000P", mpn="B3U-1000P", manufacturer="Omron",
                pins={"1": "1", "2": "2"}, description="optional IO0 boot button (top-actuated), DNP",
                dnp=True, sheet="MCU"))

    for p in sorted(u1_gnd, key=int):          # sorted: keeps the export byte-stable between runs
        nl.connect("GND", "U1", p)
    nl.connect("3V3", "U1", "3")
    nl.connect_many("3V3", ("C4", "1"), ("C5", "1"), ("R1", "1"), ("R2", "1"), ("R3", "1"), ("R4", "1"), ("TP6", "1"))
    nl.connect_many("GND", ("C4", "2"), ("C5", "2"), ("C6", "2"), ("TP5", "1"), ("R17", "2"), ("R18", "2"), ("SW2", "2"))
    nl.connect_many("MCU_EN", ("U1", "EN"), ("R1", "2"), ("C6", "1"), ("TP2", "1"))
    nl.connect_many("IO0", ("U1", "IO0"), ("R2", "2"), ("TP1", "1"), ("SW2", "1"))
    nl.connect_many("USB_DM", ("U1", "IO19"), ("TP3", "1"))
    nl.connect_many("USB_DP", ("U1", "IO20"), ("TP4", "1"))
    nl.connect_many("SDA", ("U1", "IO5"), ("R3", "2"))
    nl.connect_many("SCL", ("U1", "IO6"), ("R4", "2"))
    nl.connect_many("CAM_PWR_EN", ("U1", "IO21"), ("R17", "1"))
    nl.connect_many("LED_PWR_EN", ("U1", f"IO{GPIO['LED_PWR_EN']}"), ("R18", "1"))
    nl.connect("ANT_RF", "ANT1", "RF")

    # ---------------------------------------------------------------- Power
    # Cell: two 1.5 mm wire pads on the board (floorplan J1a/J1b); the 4.25 mm-tall JST SH header of the
    # earlier netlist fits neither side of the board (top 2.9 / bottom 1.15 mm). The cell is BT1 (off-board).
    nl.add(Part("J1", "BAT pads", PAD2x15, pins={"1": "BAT+", "2": "BAT-"},
                description="two 1.5 mm wire pads, 2.0 mm pitch, bottom side, for the cell leads (cell = BT1)",
                sheet="Power"))
    nl.add(Part("BT1", "301012 LiPo 30 mAh", "offboard:Cell_301012_3x10x12mm", mpn="301012 (30 mAh, with PCM)",
                manufacturer="generic — see hardware/bom/stage1-ring.csv", pins={"1": "+", "2": "-"}, offboard=True,
                description="3 x 10 x 12 mm LiPo cell with PCM, 1C max charge; leads soldered to J1 (last step)",
                sheet="Power"))
    # Charging pads: the inner-band contacts (CP1/CP2, off-board) are wired to two 1.5 mm pads on the board
    # (PAD1/PAD2 = floorplan PAD1w/PAD2w). PAD1 is also the bring-up VBUS entry point (README §4).
    nl.add(Part("PAD1", "CHG+ pad", PAD1x15, pins={"1": "PAD"},
                description="1.5 mm wire pad (bottom) -> CP1 inner-band contact (+5 V pogo); bring-up VBUS entry",
                sheet="Power"))
    nl.add(Part("PAD2", "CHG- pad", PAD1x15, pins={"1": "PAD"},
                description="1.5 mm wire pad (bottom) -> CP2 inner-band contact (GND return)", sheet="Power"))
    for ref, net_desc in (("CP1", "+5 V from the pogo cradle"), ("CP2", "GND return")):
        nl.add(Part(ref, "charging contact 3x2 mm ENIG", "offboard:Pad_ENIG_3x2mm", pins={"1": "PAD"}, offboard=True,
                    manufacturer="PCB coupon or brass insert", mpn="",
                    description=f"inner-band pogo contact, 3 x 2 mm ENIG, flush, >= 3 mm from the other pad; "
                                f"{net_desc}; wire to {'PAD1' if ref == 'CP1' else 'PAD2'}", sheet="Power"))
    # Charging input protection: D3 (series Schottky) blocks a ring seated the wrong way round in a 2-pin
    # cradle (CHG_PAD = -5 V would otherwise forward-bias a unidirectional TVS and drive the BQ25100 IN to
    # -0.7 V, abs. min -0.3 V); D2 is therefore the BIDIRECTIONAL 5 V TVS so it does not conduct at -5 V.
    nl.add(Part("D2", "PESD5V0S1BB", SOD523, mpn="PESD5V0S1BB,115", manufacturer="Nexperia",
                pins={"1": "1", "2": "2"},
                description="bidirectional 5 V TVS on the charging pad (symmetric, no polarity); was PESD5V0S1UB",
                sheet="Power"))
    nl.add(Part("D3", "PMEG2005EB", SOD523, mpn="PMEG2005EB,115", manufacturer="Nexperia",
                pins={"1": "K", "2": "A"},
                description="series Schottky CHG_PAD -> CHG_IN: reverse-polarity block for the pogo pads "
                            "(~0.25 V at 25 mA; VIN to U7 >= 4.5 V from a 4.75 V cradle); pin order VERIFY",
                sheet="Power"))
    # BQ25100 DSBGA-6 ball map VERIFY (SLUSBW6). The BQ25100 has PRE_TERM (no TS pin);
    # the BQ25101 is the TS variant with fixed 10 % termination.
    nl.add(Part("U7", "BQ25100AYFPR", "mcring:BQ25100_DSBGA-6_YFP", mpn="BQ25100AYFPR", manufacturer="TI",
                pins={"A1": "IN", "A2": "OUT", "B1": "nCHG", "B2": "PRE_TERM", "C1": "ISET", "C2": "VSS"},
                power_pins={"A1", "A2", "C2"}, is_ic=True,
                description="Li-ion charger 10-250 mA, 1 mA termination; ball map VERIFY", sheet="Power"))
    nl.add(C("C7", "1u", C0402, "GRM155R61A105KE15", "charger IN", "Power"))
    nl.add(C("C8", "1u", C0402, "GRM155R61A105KE15", "charger OUT / VBAT", "Power"))
    nl.add(R("R10", R_ISET, rc("9K1"), "ISET: 230/9.1k = 25 mA (VERIFY K_ISET)", "Power"))
    nl.add(R("R11", R_PRETERM, rc("11K5"), "PRE_TERM: 11.5/11.5k = 1 mA (VERIFY K_PRETERM)", "Power"))
    nl.add(R("R19", "100k", rc("100K"), f"nCHG open-drain pull-up (IO{GPIO['nCHG']} input + TP7; 33 uA only while charging)",
             "Power"))
    nl.add(TPAD("TP7", "nCHG", "Power"))
    nl.add(TPAD("TP8", "VBAT", "Power"))
    # TPS62840 in SOT-583 (DLC): pin numbers VERIFY (SLVSE12 pin configuration).
    nl.add(Part("U8", "TPS62840DLCR", "Package_TO_SOT_SMD:SOT-583-8", mpn="TPS62840DLCR", manufacturer="TI",
                pins={"1": "SW", "2": "GND", "3": "VIN", "4": "EN", "5": "STOP", "6": "MODE", "7": "VSET", "8": "VOS"},
                power_pins={"2", "3"}, is_ic=True,
                description="750 mA buck, 60 nA IQ, Vout set by VSET resistor (3.3 V code); pins VERIFY",
                sheet="Power"))
    nl.add(Part("L1", "2.2uH", "Inductor_SMD:L_0806_2016Metric", mpn="DFE201610E-2R2M=P2", manufacturer="Murata",
                pins=PASSIVE_PINS, description="buck inductor 2.0x1.6x1.0 mm", sheet="Power"))
    nl.add(C("C1", "10u", C0603, "GRM188R60J106ME47", "buck input", "Power"))
    nl.add(C("C2", "10u", C0603, "GRM188R60J106ME47", "buck output", "Power"))
    nl.add(C("C3", "100u", C1206, "GRM31CR60J107ME39", "3V3 bulk for 300-370 mA capture/radio peaks", "Power"))
    nl.add(R("R12", R_VSET, rc("267K"), "TPS62840 VSET -> GND: 267 kOhm (E96) = 3.3 V code, SLVSE12 Table 1 (1 %)", "Power"))
    nl.add(R("R8", R_DIVIDER, rc("1M"), "battery divider top (1 M/1 M: 2.1 uA at 4.2 V)", "Power"))
    nl.add(R("R9", R_DIVIDER, rc("1M"), "battery divider bottom (BATTERY_DIVIDER = 2.0 unchanged)", "Power"))
    nl.add(C("C23", "100n", C0402, "GRM155R71C104KA88", "battery sense hold capacitor (ADC sample bursts)", "Power"))

    nl.connect_many("VBAT", ("J1", "BAT+"), ("BT1", "+"), ("U7", "OUT"), ("C8", "1"), ("U8", "VIN"), ("U8", "EN"),
                    ("C1", "1"), ("TP8", "1"), ("R8", "1"))
    nl.connect_many("GND", ("J1", "BAT-"), ("BT1", "-"), ("PAD2", "1"), ("CP2", "1"), ("D2", "2"), ("U7", "VSS"),
                    ("C7", "2"), ("C8", "2"),
                    ("R10", "2"), ("R11", "2"), ("U8", "GND"), ("U8", "STOP"), ("U8", "MODE"), ("C1", "2"),
                    ("C2", "2"), ("C3", "2"), ("R12", "2"), ("R9", "2"), ("C23", "2"))
    nl.connect_many("CHG_PAD", ("PAD1", "1"), ("CP1", "1"), ("D2", "1"), ("D3", "A"))
    nl.connect_many("CHG_IN", ("D3", "K"), ("U7", "IN"), ("C7", "1"))
    nl.connect_many("ISET", ("U7", "ISET"), ("R10", "1"))
    nl.connect_many("PRETERM", ("U7", "PRE_TERM"), ("R11", "1"))
    nl.connect_many("nCHG", ("U7", "nCHG"), ("R19", "2"), ("TP7", "1"), ("U1", f"IO{GPIO['nCHG']}"))
    nl.connect("3V3", "R19", "1")
    nl.connect_many("SW_NODE", ("U8", "SW"), ("L1", "1"))
    nl.connect_many("3V3", ("L1", "2"), ("U8", "VOS"), ("C2", "1"), ("C3", "1"))
    nl.connect_many("VSET", ("U8", "VSET"), ("R12", "1"))
    nl.connect_many("BAT_SENSE", ("R8", "2"), ("R9", "1"), ("C23", "1"), ("U1", "IO1"))

    # --------------------------------------------------------------- Camera
    # 24-pin 0.5 mm FPC, ESP32-CAM / Arducam M0031 OV2640 pin order (VERIFY on the purchased
    # module: a one-position offset variant exists where pin 1 = AGND and pin 24 = NC).
    fpc = {"1": "NC", "2": "AGND", "3": "SIOD", "4": "AVDD", "5": "SIOC", "6": "RESET", "7": "VSYNC",
           "8": "PWDN", "9": "HREF", "10": "DVDD", "11": "DOVDD", "12": "Y9", "13": "XCLK", "14": "Y8",
           "15": "DGND", "16": "Y7", "17": "PCLK", "18": "Y6", "19": "Y2", "20": "Y5", "21": "Y3",
           "22": "Y4", "23": "Y1", "24": "Y0"}
    # Connector: BOTTOM-contact back-flip horizontal, as hardware/bom/stage1-ring.csv and board_params.json
    # (fpc_connector_mm) assume — the flex's contacts face the board, the lens faces away. The KiCad
    # FH12-24S-0.5SH footprint is the industry-standard 24-pin 0.5 mm back-flip land pattern the F32R
    # series copies (24 pads + 2 mounting pads); confirm the land pattern against the F32R drawing.
    nl.add(Part("FPC1", "FPC-24-0.5mm-bottom", "Connector_FFC-FPC:Hirose_FH12-24S-0.5SH_1x24-1MP_P0.50mm_Horizontal",
                mpn="F32R-1A7H1-11024", manufacturer="XKB Connectivity (LCSC)",
                fields={"Alt MPN": "FH12-24S-0.5SH(55) (Hirose) — confirm BOTTOM contact before substituting"},
                pins=fpc, power_pins={"2", "4", "10", "11", "15"}, nc_pins={"1", "23", "24"},
                description="OV2640 24-pin 0.5 mm FPC, bottom-contact back-flip, horizontal, 2.0 mm tall "
                            "(Arducam M0031 pin order VERIFY)", sheet="Camera"))
    # TPS22916 DSBGA-4 ball map VERIFY (A1 VIN, A2 VOUT, B1 ON, B2 GND).
    def tps22916(ref, desc):
        return Part(ref, "TPS22916CYFPR", "mcring:TPS22916_DSBGA-4_YFP", mpn="TPS22916CYFPR", manufacturer="TI",
                    pins={"A1": "VIN", "A2": "VOUT", "B1": "ON", "B2": "GND"}, power_pins={"A1", "B2"},
                    is_ic=True, description=desc, sheet="Camera" if ref == "U2" else "Outputs")
    nl.add(tps22916("U2", "camera rail load switch (3V3 -> CAM_3V3); ball map VERIFY"))
    nl.add(Part("U3", "XC6206P282MR", SOT23, mpn="XC6206P282MR", manufacturer="Torex",
                pins={"1": "VSS", "2": "VOUT", "3": "VIN"}, power_pins={"1", "3"}, is_ic=True,
                description="2.8 V LDO for OV2640 AVDD", sheet="Camera"))
    nl.add(Part("U4", "XC6206P122MR", SOT23, mpn="XC6206P122MR", manufacturer="Torex",
                pins={"1": "VSS", "2": "VOUT", "3": "VIN"}, power_pins={"1", "3"}, is_ic=True,
                description="1.2 V LDO for OV2640 DVDD (DNP if the module regulates DVDD itself)",
                sheet="Camera"))
    nl.add(C("C9", "1u", C0402, "GRM155R61A105KE15", "U2 VIN local", "Camera"))
    nl.add(C("C10", "1u", C0402, "GRM155R61A105KE15", "CAM_3V3 (DOVDD) at U2 out", "Camera"))
    nl.add(C("C24", "100n", C0402, "GRM155R71C104KA88", "DOVDD at FPC", "Camera"))
    nl.add(C("C11", "1u", C0402, "GRM155R61A105KE15", "CAM_2V8 (AVDD)", "Camera"))
    nl.add(C("C13", "100n", C0402, "GRM155R71C104KA88", "AVDD at FPC", "Camera"))
    nl.add(C("C12", "1u", C0402, "GRM155R61A105KE15", "CAM_1V2 (DVDD)", "Camera"))
    nl.add(R("R5", "4.7k", rc("4K7"), "SCCB SIOD pull-up (to the switched rail)", "Camera"))
    nl.add(R("R6", "4.7k", rc("4K7"), "SCCB SIOC pull-up (to the switched rail)", "Camera"))
    nl.add(R("R16", "10k", rc("10K"), "camera RESET pull-up", "Camera"))
    nl.add(C("C14", "100n", C0402, "GRM155R71C104KA88", "camera RESET power-on delay", "Camera"))

    nl.connect_many("3V3", ("U2", "VIN"), ("C9", "1"))
    nl.connect_many("GND", ("U2", "GND"), ("C9", "2"), ("C10", "2"), ("C24", "2"), ("C11", "2"), ("C13", "2"),
                    ("C12", "2"), ("C14", "2"), ("U3", "VSS"), ("U4", "VSS"),
                    ("FPC1", "AGND"), ("FPC1", "DGND"), ("FPC1", "PWDN"))
    nl.connect("CAM_PWR_EN", "U2", "ON")
    nl.connect_many("CAM_3V3", ("U2", "VOUT"), ("C10", "1"), ("C24", "1"), ("U3", "VIN"), ("U4", "VIN"),
                    ("FPC1", "DOVDD"), ("R5", "1"), ("R6", "1"), ("R16", "1"))
    nl.connect_many("CAM_2V8", ("U3", "VOUT"), ("C11", "1"), ("C13", "1"), ("FPC1", "AVDD"))
    nl.connect_many("CAM_1V2", ("U4", "VOUT"), ("C12", "1"), ("FPC1", "DVDD"))
    nl.connect_many("CAM_RESET", ("FPC1", "RESET"), ("R16", "2"), ("C14", "1"))
    nl.connect_many("CAM_SIOD", ("FPC1", "SIOD"), ("R5", "2"), ("U1", f"IO{GPIO['CAM_SIOD']}"))
    nl.connect_many("CAM_SIOC", ("FPC1", "SIOC"), ("R6", "2"), ("U1", f"IO{GPIO['CAM_SIOC']}"))
    for sig in ("XCLK", "VSYNC", "HREF", "PCLK", "Y2", "Y3", "Y4", "Y5", "Y6", "Y7", "Y8", "Y9"):
        nl.connect_many(f"CAM_{sig}", ("FPC1", sig), ("U1", f"IO{GPIO['CAM_' + sig]}"))

    # ------------------------------------------------------- Sensors + Haptics
    # DRV2605L VSSOP-10 pin numbers VERIFY (SLOS854): 1 REG 2 SCL 3 SDA 4 IN/TRIG 5 EN 6 VDD 7 GND 8 OUT- 9 OUT+ 10 NC
    # EN is tied to 3V3 (as on the stage-0 Adafruit breakout): with EN low the DRV2605L is in shutdown and
    # only ACKs on I2C — no register reads/writes (datasheet "Operation with EN control") — so a GPIO-driven
    # EN that the firmware holds low until after drv2605_init() made the part "not found". Idle power is the
    # register STANDBY bit (drv2605_standby(), default state at power-up): < 4 uA.
    nl.add(Part("U5", "DRV2605LDGS", "Package_SO:VSSOP-10_3x3mm_P0.5mm", mpn="DRV2605LDGSR", manufacturer="TI",
                pins={"1": "REG", "2": "SCL", "3": "SDA", "4": "IN/TRIG", "5": "EN", "6": "VDD", "7": "GND",
                      "8": "OUT-", "9": "OUT+", "10": "NC"},
                power_pins={"6", "7"}, nc_pins={"10"}, is_ic=True,
                description="haptic driver, I2C 0x5A, LRA closed loop, EN tied to 3V3 (standby via I2C); pin numbers VERIFY",
                sheet="Sensors"))
    nl.add(C("C15", "1u", C0402, "GRM155R61A105KE15", "DRV2605L VDD", "Sensors"))
    nl.add(C("C16", "1u", C0402, "GRM155R61A105KE15", "DRV2605L REG", "Sensors"))
    nl.add(Part("M1", "LRA0825BC-0167F", "mcring:LRA_8mm_2pad", mpn="LRA0825BC-0167F", manufacturer="INEED",
                pins={"1": "+", "2": "-"},
                description="8 x 2.5 mm coin LRA, 240 Hz, 1.25 Vrms max (set RATED_V/OD_CLAMP for 1.25 Vrms @ 240 Hz, "
                            "docs/07-build-guide.md §1.8); leads to two bottom-side pads (floorplan M1a/M1b)",
                sheet="Sensors"))
    # LIS2DW12 LGA-12 pin numbers VERIFY (DS12303 Table 2); pins 5-8 all tie to GND regardless.
    nl.add(Part("U6", "LIS2DW12TR", "Package_LGA:LGA-12_2x2mm_P0.5mm", mpn="LIS2DW12TR", manufacturer="ST",
                pins={"1": "SCL/SPC", "2": "CS", "3": "SA0/SDO", "4": "SDA/SDI/SDO", "5": "RES", "6": "GND",
                      "7": "GND", "8": "GND", "9": "VDD", "10": "VDD_IO", "11": "INT2", "12": "INT1"},
                power_pins={"6", "7", "8", "9", "10"}, nc_pins={"11"}, is_ic=True,
                description="accelerometer, I2C 0x18 (SA0=GND), CS=VDD_IO for I2C; pins VERIFY",
                sheet="Sensors"))
    nl.add(C("C17", "100n", C0402, "GRM155R71C104KA88", "LIS2DW12 VDD", "Sensors"))
    nl.add(C("C18", "100n", C0402, "GRM155R71C104KA88", "LIS2DW12 VDD_IO", "Sensors"))
    # TDK T3902 PDM mic pad numbers VERIFY (T3902 datasheet "pin description").
    nl.add(Part("MK1", "T3902", "mcring:MIC_TDK_T3902_3.5x2.65mm", mpn="T3902", manufacturer="TDK InvenSense",
                pins={"1": "VDD", "2": "GND", "3": "CLK", "4": "DATA", "5": "SELECT", "6": "GND"},
                power_pins={"1", "2", "6"}, is_ic=True,
                description="PDM microphone, bottom port (0.5 mm hole); pad numbers VERIFY", sheet="Sensors"))
    nl.add(C("C19", "100n", C0402, "GRM155R71C104KA88", "mic VDD", "Sensors"))
    nl.add(Part("SW1", "B3U-3000P", "mcring:SW_Omron_B3U-3000P", mpn="B3U-3000P", manufacturer="Omron",
                pins={"1": "1", "2": "2"}, description="side-actuated tactile switch 3.0x2.5x1.2 mm",
                sheet="Sensors"))
    nl.add(C("C22", "100n", C0402, "GRM155R71C104KA88", "button debounce/ESD", "Sensors"))
    nl.add(Part("TPAD1", "TOUCH", "mcring:PAD_Touch_3x4mm", pins={"1": "PAD"},
                description="3 x 4 mm copper touch pad on the top face (ESP32-S3 touch T8)", sheet="Sensors"))
    nl.add(R("R13", "1k", rc("1K"), "touch pad series", "Sensors"))

    nl.connect_many("3V3", ("U5", "VDD"), ("U5", "EN"), ("C15", "1"), ("U6", "VDD"), ("U6", "VDD_IO"), ("U6", "CS"),
                    ("C17", "1"), ("C18", "1"), ("MK1", "VDD"), ("C19", "1"))
    nl.connect_many("GND", ("U5", "GND"), ("U5", "IN/TRIG"), ("C15", "2"), ("C16", "2"),
                    ("U6", "5"), ("U6", "6"), ("U6", "7"), ("U6", "8"), ("U6", "SA0/SDO"), ("C17", "2"), ("C18", "2"),
                    ("MK1", "2"), ("MK1", "6"), ("MK1", "SELECT"), ("C19", "2"), ("SW1", "2"), ("C22", "2"))
    nl.connect_many("SDA", ("U5", "SDA"), ("U6", "SDA/SDI/SDO"))
    nl.connect_many("SCL", ("U5", "SCL"), ("U6", "SCL/SPC"))
    nl.connect_many("DRV_REG", ("U5", "REG"), ("C16", "1"))
    nl.connect_many("LRA_P", ("U5", "OUT+"), ("M1", "+"))
    nl.connect_many("LRA_N", ("U5", "OUT-"), ("M1", "-"))
    nl.connect_many("IMU_INT1", ("U6", "INT1"), ("U1", f"IO{GPIO['IMU_INT1']}"))
    nl.connect_many("PDM_CLK", ("MK1", "CLK"), ("U1", f"IO{GPIO['PDM_CLK']}"))
    nl.connect_many("PDM_DATA", ("MK1", "DATA"), ("U1", f"IO{GPIO['PDM_DATA']}"))
    nl.connect_many("BUTTON", ("SW1", "1"), ("C22", "1"), ("U1", f"IO{GPIO['BUTTON']}"))
    nl.connect_many("TOUCH", ("R13", "1"), ("U1", f"IO{GPIO['TOUCH']}"))
    nl.connect_many("TOUCH_PAD", ("R13", "2"), ("TPAD1", "1"))

    # ------------------------------------------------------ Outputs + Connectors
    # WS2812 rail: 3V3 -> U9 -> VLED (was VBAT). With VLED = VBAT the LED's VIH = 0.7*VDD reaches 2.94 V at
    # 4.2 V, above the ESP32-S3's VOH(min) = 0.8*3.3 = 2.64 V, and a LiPo sits at 3.6-3.9 V (below the LED's
    # 3.7 V minimum) for most of its charge anyway. At 3.3 V the data interface is in spec (VIH 2.31 V); VDD
    # is below the 3.7 V datasheet minimum at all times — a known, commonly used operating point for the
    # WS2812B (reduced blue/green headroom): bench-check, else fit a 3.3 V-rated 2020 part on the same pads.
    nl.add(tps22916("U9", "WS2812 supply gate (3V3 -> VLED), kills ~0.6-1 mA LED idle current; ON = IO33"))
    nl.add(C("C21", "1u", C0402, "GRM155R61A105KE15", "VLED at U9 out", "Outputs"))
    # WS2812B-2020 pad order VERIFY (1 VDD, 2 DOUT, 3 GND, 4 DIN per Worldsemi drawing).
    nl.add(Part("D1", "WS2812B-2020", "LED_SMD:LED_WS2812B-2020_PLCC4_2.0x2.0mm", mpn="WS2812B-2020",
                manufacturer="Worldsemi", pins={"1": "VDD", "2": "DOUT", "3": "GND", "4": "DIN"},
                power_pins={"1", "3"}, nc_pins={"2"}, is_ic=True,
                description="RGB LED under the white-resin window, VLED = 3.3 V (below the 3.7 V datasheet min: "
                            "bench VERIFY; alt. 3.3 V-rated 2020 RGB per hardware/bom/stage1-ring.csv); pad order VERIFY",
                sheet="Outputs"))
    nl.add(R("R7", "1k", rc("1K"), "WS2812 data series: limits the ROM TXD0 boot chatter back-feed into DIN while "
                                   "VLED is off to ~2.7 mA (was 100 R = 27 mA pulses)", "Outputs"))
    nl.add(C("C20", "100n", C0402, "GRM155R71C104KA88", "WS2812 VDD", "Outputs"))
    # Piezo: two 1.2 mm wire pads on the board (floorplan BZ1a/BZ1b); the 9 x 9 x 1.9 mm element itself is
    # PZ1, off-board and optional — the current enclosure has no pocket for it.
    nl.add(Part("BZ1", "PIEZO pads", PAD2x12, pins={"1": "DRV", "2": "GND"},
                description="two 1.2 mm wire pads, 2.0 mm pitch, bottom side, for the optional piezo element PZ1",
                sheet="Outputs"))
    nl.add(Part("PZ1", "PKMCS0909E4000-R1", "offboard:Piezo_9x9x1.9mm", mpn="PKMCS0909E4000-R1",
                manufacturer="Murata", pins={"1": "+", "2": "-"}, offboard=True, dnp=True,
                description="4 kHz piezo sounder 9 x 9 x 1.9 mm (LTB) — optional; fit only if the enclosure gets a "
                            "9 x 9 x 2 pocket (none in the current CAD); any 2-wire piezo element also works",
                sheet="Outputs"))
    nl.add(R("R15", "100", rc("100R"), "piezo drive series", "Outputs"))
    nl.add(Part("Q1", "AO3400A", SOT23, mpn="AO3400A", manufacturer="Alpha & Omega",
                pins={"1": "G", "2": "S", "3": "D"}, description="aux low-side N-MOSFET (air-puff driver enable / any load)",
                sheet="Outputs"))
    nl.add(R("R14", "100k", rc("100K"), "aux gate pull-down", "Outputs"))
    nl.add(Part("J2", "AUX", "mcring:PAD_Aux_1x2", pins={"1": "VBAT", "2": "DRAIN"},
                description="aux actuator pads: VBAT + open-drain return (Q1)", sheet="Outputs"))

    nl.connect("VBAT", "J2", "VBAT")
    nl.connect("3V3", "U9", "VIN")           # C2/C3 (10 u + 100 u) sit on the same net next to the buck
    nl.connect_many("GND", ("U9", "GND"), ("C21", "2"), ("C20", "2"), ("D1", "GND"), ("BZ1", "GND"), ("PZ1", "-"),
                    ("Q1", "S"), ("R14", "2"))
    nl.connect("LED_PWR_EN", "U9", "ON")
    nl.connect_many("VLED", ("U9", "VOUT"), ("C21", "1"), ("C20", "1"), ("D1", "VDD"))
    nl.connect_many("RGB_DATA", ("U1", "TXD0/IO43"), ("R7", "1"))
    nl.connect_many("RGB_DIN", ("R7", "2"), ("D1", "DIN"))
    nl.connect_many("BUZZER", ("U1", f"IO{GPIO['BUZZER']}"), ("R15", "1"))
    nl.connect_many("BUZZ_DRV", ("R15", "2"), ("BZ1", "DRV"), ("PZ1", "+"))
    nl.connect_many("AUX_EN", ("U1", f"IO{GPIO['AUX_EN']}"), ("Q1", "G"), ("R14", "1"))
    nl.connect_many("AUX_DRAIN", ("Q1", "D"), ("J2", "DRAIN"))
    return nl


# ERC waivers: substring of the warning -> why it is intentional.
ERC_WAIVERS = {
    "net ANT_RF has 1 node": "ANT1's RF lead mates with the u.FL receptacle on the ESP32-S3-MINI-1U module, "
                             "which is not one of the module's 65 pads, so the net has no second node",
}


def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    nl = build()
    nl.export_kicad_netlist(os.path.join(OUT, "mcring_v1.net"))
    nl.export_bom_csv(os.path.join(OUT, "mcring_v1_bom.csv"))
    nl.export_markdown(os.path.join(OUT, "mcring_v1_nets.md"), title="mcring v1 (stage 1)")
    warns = nl.export_erc_markdown(os.path.join(OUT, "erc.md"), ERC_WAIVERS, title="mcring v1 (stage 1)")
    st = nl.stats()
    print(f"parts={st['parts']} (populated {st['parts_populated']}, off-board {st['parts_offboard']}) "
          f"pins={st['pins']} nets={st['nets']} nodes={st['nodes']} power_nets={st['power_nets']}")
    unexplained = [w for w in warns if not any(k in w.message for k in ERC_WAIVERS)]
    print(f"ERC: {len(warns)} warning(s), {len(unexplained)} unexplained")
    for w in warns:
        print("  ", w)
    # GPIO usage summary
    u1 = nl.parts["U1"]
    used = {}
    for (ref, pn), net in nl._pin_net.items():
        if ref == "U1" and u1.pins[pn].startswith(("IO", "TXD0", "RXD0")):
            used[u1.pins[pn]] = net
    spare = [n for pn, n in u1.pins.items() if pn in u1.spare_pins]
    open_ = [n for pn, n in u1.pins.items() if n.startswith(("IO", "TXD0", "RXD0"))
             and n not in used and pn not in u1.nc_pins and pn not in u1.spare_pins]
    print(f"GPIO used: {len(used)}; spare (firmware -1): {spare}; unaccounted: {open_}")
    # consistency with firmware/ring-esp32s3/src/config.h BOARD_MCRING_V1 (pin numbers only)
    expect = {"BAT_SENSE": "IO1", "BUTTON": "IO2", "nCHG": "IO3", "BUZZER": "IO4", "SDA": "IO5", "SCL": "IO6",
              "IMU_INT1": "IO7", "TOUCH": "IO8", "AUX_EN": "IO9", "CAM_PWR_EN": "IO21", "RGB_DATA": "TXD0/IO43",
              "LED_PWR_EN": "IO33"}
    bad = [f"{net}: {pin}" for net, pin in expect.items() if used.get(pin) != net]
    if bad:
        print("GPIO/net mismatch versus config.h:", bad)
    return 1 if (unexplained or bad or open_) else 0


if __name__ == "__main__":
    sys.exit(main())
