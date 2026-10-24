"""
mcring_v1.py — electrical design of the stage-1 "mcring v1" ring board.

Single rigid 2-layer 0.6 mm board in the signet bay, ESP32-S3-MINI-1U-N4R2 with the
u.FL end pointing away from the camera.  Nets follow firmware/ring-esp32s3/src/config.h
(BOARD_MCRING_V1) after the IO19/IO20 native-USB conflict was resolved:

    PIN_CAM_PWR  19 -> 21   (RTC GPIO, no boot-time activity, hold-capable in deep sleep)
    PIN_RGB      20 -> 43   (TXD0; ROM boot chatter only glitches a power-gated LED)
    IO44 (RXD0)  -> LED_PWR_EN, second TPS22916 gating the WS2812 (new; firmware TODO)
    IO19/IO20    -> native USB D-/D+ test pads

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
    "BAT_SENSE": 1, "BUTTON": 2, "HAPTIC_EN": 3, "BUZZER": 4,
    "SDA": 5, "SCL": 6, "IMU_INT1": 7, "TOUCH": 8, "AUX_EN": 9,
    "CAM_PWR_EN": 21,     # was 19 (USB D-)
    "RGB_DATA": 43,       # was 20 (USB D+)
    "LED_PWR_EN": 44,     # new: WS2812 supply gate (firmware PIN_RGB_PWR to be added)
    "USB_DM": 19, "USB_DP": 20,
    "IO0": 0,
}

# BQ25100 programming (VERIFY constants against SLUSBW6):
#   I_CHG     = K_ISET / R_ISET,          K_ISET      = 230 A*ohm  -> 9.1k  => 25.3 mA (~0.85C of 30 mAh)
#   I_PRETERM = K_PRETERM / R_PRETERM,    K_PRETERM   = 11.5 A*ohm -> 11.5k => 1.0 mA termination
R_ISET = "9.1k"
R_PRETERM = "11.5k"
# TPS62840: output selected by a resistor on VSET (16 codes, 1.8..3.3 V). The 3.3 V code
# resistor value must be read from SLVSE12 Table "Output voltage setting" — VERIFY.
R_VSET = "VSET-3V3"

# --------------------------------------------------------------------------- #
# Footprint shorthands (KiCad 7/8 library names; 'mcring:' = custom footprint)
# --------------------------------------------------------------------------- #
R0402 = "Resistor_SMD:R_0402_1005Metric"
C0402 = "Capacitor_SMD:C_0402_1005Metric"
C0603 = "Capacitor_SMD:C_0603_1608Metric"
C1206 = "Capacitor_SMD:C_1206_3216Metric"
SOT23 = "Package_TO_SOT_SMD:SOT-23"
TP = "TestPoint:TestPoint_Pad_D1.0mm"

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
    nl.declare_power_nets("GND", "3V3", "VBAT", "CHG_IN", "CAM_3V3", "CAM_2V8", "CAM_1V2", "VLED")

    # ------------------------------------------------------------------ MCU
    # ESP32-S3-MINI-1U pin table (VERIFY against esp32-s3-mini-1_mini-1u_datasheet_en.pdf,
    # Table "Pin Definitions"). 65 pads: 1-45 perimeter, 46-65 thermal/ground pads.
    # IO26 and IO33..IO37 are routed to the in-package flash/PSRAM on the N4R2 (and R8)
    # variants -> NC.  IO45/IO46 are strapping pins -> left floating (internal defaults).
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
    nl.add(Part("U1", "ESP32-S3-MINI-1U-N4R2", "RF_Module:ESP32-S3-MINI-1U",
                mpn="ESP32-S3-MINI-1U-N4R2", manufacturer="Espressif",
                pins=u1_pins, power_pins=u1_gnd | {"3"},
                nc_pins={"26", "27", "28", "29", "30", "31", "39", "40"},
                description="Wi-Fi/BLE module, 4 MB flash + 2 MB PSRAM, u.FL; pin table VERIFY",
                is_ic=True, sheet="MCU"))
    nl.add(R("R1", "10k", rc("10K"), "EN pull-up", "MCU"))
    nl.add(C("C6", "1u", C0402, "GRM155R61A105KE15", "EN RC (reset delay)", "MCU"))
    nl.add(R("R2", "10k", rc("10K"), "IO0 boot strap pull-up", "MCU"))
    nl.add(C("C4", "10u", C0603, "GRM188R60J106ME47", "module 3V3 decoupling", "MCU"))
    nl.add(C("C5", "100n", C0402, "GRM155R71C104KA88", "module 3V3 decoupling", "MCU"))
    nl.add(R("R3", "4.7k", rc("4K7"), "I2C SDA pull-up", "MCU"))
    nl.add(R("R4", "4.7k", rc("4K7"), "I2C SCL pull-up", "MCU"))
    nl.add(R("R17", "100k", rc("100K"), "CAM_PWR_EN pull-down (camera off in sleep/boot)", "MCU"))
    nl.add(R("R18", "4.7k", rc("4K7"), "LED_PWR_EN pull-down (beats the RXD0 reset pull-up)", "MCU"))
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
    nl.connect_many("LED_PWR_EN", ("U1", "RXD0/IO44"), ("R18", "1"))

    # ---------------------------------------------------------------- Power
    nl.add(Part("J1", "BM02B-SRSS-TB", "Connector_JST:JST_SH_BM02B-SRSS-TB_1x02-1MP_P1.00mm_Vertical",
                mpn="BM02B-SRSS-TB(LF)(SN)", manufacturer="JST", pins={"1": "BAT+", "2": "BAT-"},
                description="301012 LiPo 30 mAh with PCM, JST SH 1.0 mm", sheet="Power"))
    nl.add(Part("PAD1", "CHG+", "mcring:PAD_Charge_3.0x2.0mm", pins={"1": "PAD"},
                description="charging pad (+5 V from pogo cradle), ENIG, inner band", sheet="Power"))
    nl.add(Part("PAD2", "CHG-", "mcring:PAD_Charge_3.0x2.0mm", pins={"1": "PAD"},
                description="charging pad (GND return)", sheet="Power"))
    nl.add(Part("D2", "PESD5V0S1UB", "Diode_SMD:D_SOD-523", mpn="PESD5V0S1UB,115", manufacturer="Nexperia",
                pins={"1": "K", "2": "A"}, description="TVS on the charging pad (pin order VERIFY)", sheet="Power"))
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
    nl.add(R("R19", "100k", rc("100K"), "nCHG open-drain pull-up (test pad only)", "Power"))
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
    nl.add(R("R12", R_VSET, "RC0402FR-07xxxL", "TPS62840 VSET resistor, 3.3 V code (VERIFY table)", "Power"))
    nl.add(R("R8", "100k", rc("100K"), "battery divider top", "Power"))
    nl.add(R("R9", "100k", rc("100K"), "battery divider bottom", "Power"))
    nl.add(C("C23", "100n", C0402, "GRM155R71C104KA88", "battery sense filter", "Power"))

    nl.connect_many("VBAT", ("J1", "BAT+"), ("U7", "OUT"), ("C8", "1"), ("U8", "VIN"), ("U8", "EN"),
                    ("C1", "1"), ("TP8", "1"), ("R8", "1"))
    nl.connect_many("GND", ("J1", "BAT-"), ("PAD2", "1"), ("D2", "A"), ("U7", "VSS"), ("C7", "2"), ("C8", "2"),
                    ("R10", "2"), ("R11", "2"), ("U8", "GND"), ("U8", "STOP"), ("U8", "MODE"), ("C1", "2"),
                    ("C2", "2"), ("C3", "2"), ("R12", "2"), ("R9", "2"), ("C23", "2"))
    nl.connect_many("CHG_IN", ("PAD1", "1"), ("D2", "K"), ("U7", "IN"), ("C7", "1"))
    nl.connect_many("ISET", ("U7", "ISET"), ("R10", "1"))
    nl.connect_many("PRETERM", ("U7", "PRE_TERM"), ("R11", "1"))
    nl.connect_many("nCHG", ("U7", "nCHG"), ("R19", "2"), ("TP7", "1"))
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
    nl.add(Part("FPC1", "FPC-24-0.5mm", "Connector_FFC-FPC:Hirose_FH12-24S-0.5SH_1x24-1MP_P0.50mm_Horizontal",
                mpn="FH12-24S-0.5SH(55) / F32R-1A7H1-11024", manufacturer="Hirose / generic",
                pins=fpc, power_pins={"2", "4", "10", "11", "15"}, nc_pins={"1", "23", "24"},
                description="OV2640 24-pin 0.5 mm FPC head (Arducam M0031 pin order VERIFY)", sheet="Camera"))
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
    nl.add(Part("U5", "DRV2605LDGS", "Package_SO:VSSOP-10_3x3mm_P0.5mm", mpn="DRV2605LDGSR", manufacturer="TI",
                pins={"1": "REG", "2": "SCL", "3": "SDA", "4": "IN/TRIG", "5": "EN", "6": "VDD", "7": "GND",
                      "8": "OUT-", "9": "OUT+", "10": "NC"},
                power_pins={"6", "7"}, nc_pins={"10"}, is_ic=True,
                description="haptic driver, I2C 0x5A, LRA closed loop; pin numbers VERIFY", sheet="Sensors"))
    nl.add(C("C15", "1u", C0402, "GRM155R61A105KE15", "DRV2605L VDD", "Sensors"))
    nl.add(C("C16", "1u", C0402, "GRM155R61A105KE15", "DRV2605L REG", "Sensors"))
    nl.add(Part("M1", "LRA0825BC-0167F", "mcring:LRA_8mm_2pad", mpn="LRA0825BC-0167F", manufacturer="INEED",
                pins={"1": "+", "2": "-"}, description="8 x 2.5 mm LRA, ~170 Hz, 2 solder pads/leads",
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

    nl.connect_many("3V3", ("U5", "VDD"), ("C15", "1"), ("U6", "VDD"), ("U6", "VDD_IO"), ("U6", "CS"),
                    ("C17", "1"), ("C18", "1"), ("MK1", "VDD"), ("C19", "1"))
    nl.connect_many("GND", ("U5", "GND"), ("U5", "IN/TRIG"), ("C15", "2"), ("C16", "2"),
                    ("U6", "5"), ("U6", "6"), ("U6", "7"), ("U6", "8"), ("U6", "SA0/SDO"), ("C17", "2"), ("C18", "2"),
                    ("MK1", "2"), ("MK1", "6"), ("MK1", "SELECT"), ("C19", "2"), ("SW1", "2"), ("C22", "2"))
    nl.connect_many("SDA", ("U5", "SDA"), ("U6", "SDA/SDI/SDO"))
    nl.connect_many("SCL", ("U5", "SCL"), ("U6", "SCL/SPC"))
    nl.connect_many("DRV_REG", ("U5", "REG"), ("C16", "1"))
    nl.connect_many("HAPTIC_EN", ("U5", "EN"), ("U1", f"IO{GPIO['HAPTIC_EN']}"))
    nl.connect_many("LRA_P", ("U5", "OUT+"), ("M1", "+"))
    nl.connect_many("LRA_N", ("U5", "OUT-"), ("M1", "-"))
    nl.connect_many("IMU_INT1", ("U6", "INT1"), ("U1", f"IO{GPIO['IMU_INT1']}"))
    nl.connect_many("PDM_CLK", ("MK1", "CLK"), ("U1", f"IO{GPIO['PDM_CLK']}"))
    nl.connect_many("PDM_DATA", ("MK1", "DATA"), ("U1", f"IO{GPIO['PDM_DATA']}"))
    nl.connect_many("BUTTON", ("SW1", "1"), ("C22", "1"), ("U1", f"IO{GPIO['BUTTON']}"))
    nl.connect_many("TOUCH", ("R13", "1"), ("U1", f"IO{GPIO['TOUCH']}"))
    nl.connect_many("TOUCH_PAD", ("R13", "2"), ("TPAD1", "1"))

    # ------------------------------------------------------ Outputs + Connectors
    nl.add(tps22916("U9", "WS2812 supply gate (VBAT -> VLED), kills ~0.6-1 mA LED idle current"))
    nl.add(C("C21", "1u", C0402, "GRM155R61A105KE15", "VLED at U9 out", "Outputs"))
    # WS2812B-2020 pad order VERIFY (1 VDD, 2 DOUT, 3 GND, 4 DIN per Worldsemi drawing).
    nl.add(Part("D1", "WS2812B-2020", "LED_SMD:LED_WS2812B-2020_PLCC4_2.0x2.0mm", mpn="WS2812B-2020",
                manufacturer="Worldsemi", pins={"1": "VDD", "2": "DOUT", "3": "GND", "4": "DIN"},
                power_pins={"1", "3"}, nc_pins={"2"}, is_ic=True,
                description="RGB LED under the white-resin window; pad order VERIFY", sheet="Outputs"))
    nl.add(R("R7", "100", rc("100R"), "WS2812 data series", "Outputs"))
    nl.add(C("C20", "100n", C0402, "GRM155R71C104KA88", "WS2812 VDD", "Outputs"))
    nl.add(Part("BZ1", "PKMCS0909E4000-R1", "mcring:Murata_PKMCS0909_9x9mm", mpn="PKMCS0909E4000-R1",
                manufacturer="Murata", pins={"1": "1", "2": "2"},
                description="4 kHz piezo sounder 9x9x1.9 mm (LTB) — or 2 pads for any piezo", sheet="Outputs"))
    nl.add(R("R15", "100", rc("100R"), "piezo drive series", "Outputs"))
    nl.add(Part("Q1", "AO3400A", SOT23, mpn="AO3400A", manufacturer="Alpha & Omega",
                pins={"1": "G", "2": "S", "3": "D"}, description="aux low-side N-MOSFET (air-puff driver enable / any load)",
                sheet="Outputs"))
    nl.add(R("R14", "100k", rc("100K"), "aux gate pull-down", "Outputs"))
    nl.add(Part("J2", "AUX", "mcring:PAD_Aux_1x2", pins={"1": "VBAT", "2": "DRAIN"},
                description="aux actuator pads: VBAT + open-drain return (Q1)", sheet="Outputs"))

    nl.connect_many("VBAT", ("U9", "VIN"), ("J2", "VBAT"))
    nl.connect_many("GND", ("U9", "GND"), ("C21", "2"), ("C20", "2"), ("D1", "GND"), ("BZ1", "2"),
                    ("Q1", "S"), ("R14", "2"))
    nl.connect("LED_PWR_EN", "U9", "ON")
    nl.connect_many("VLED", ("U9", "VOUT"), ("C21", "1"), ("C20", "1"), ("D1", "VDD"))
    nl.connect_many("RGB_DATA", ("U1", "TXD0/IO43"), ("R7", "1"))
    nl.connect_many("RGB_DIN", ("R7", "2"), ("D1", "DIN"))
    nl.connect_many("BUZZER", ("U1", f"IO{GPIO['BUZZER']}"), ("R15", "1"))
    nl.connect_many("BUZZ_DRV", ("R15", "2"), ("BZ1", "1"))
    nl.connect_many("AUX_EN", ("U1", f"IO{GPIO['AUX_EN']}"), ("Q1", "G"), ("R14", "1"))
    nl.connect_many("AUX_DRAIN", ("Q1", "D"), ("J2", "DRAIN"))
    return nl


# ERC waivers: substring of the warning -> why it is intentional.
ERC_WAIVERS = {
    # (none expected; kept for future use)
}


def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    nl = build()
    nl.export_kicad_netlist(os.path.join(OUT, "mcring_v1.net"))
    nl.export_bom_csv(os.path.join(OUT, "mcring_v1_bom.csv"))
    nl.export_markdown(os.path.join(OUT, "mcring_v1_nets.md"), title="mcring v1 (stage 1)")
    warns = nl.export_erc_markdown(os.path.join(OUT, "erc.md"), ERC_WAIVERS, title="mcring v1 (stage 1)")
    st = nl.stats()
    print(f"parts={st['parts']} (populated {st['parts_populated']}) pins={st['pins']} nets={st['nets']} "
          f"nodes={st['nodes']} power_nets={st['power_nets']}")
    unexplained = [w for w in warns if not any(k in w.message for k in ERC_WAIVERS)]
    print(f"ERC: {len(warns)} warning(s), {len(unexplained)} unexplained")
    for w in warns:
        print("  ", w)
    # GPIO usage summary
    used = {}
    for (ref, pn), net in nl._pin_net.items():
        if ref == "U1" and nl.parts["U1"].pins[pn].startswith(("IO", "TXD0", "RXD0")):
            used[nl.parts["U1"].pins[pn]] = net
    free = [n for pn, n in nl.parts["U1"].pins.items() if n.startswith(("IO", "TXD0", "RXD0"))
            and n not in used and pn not in nl.parts["U1"].nc_pins]
    print(f"GPIO used: {len(used)}; free exposed non-NC GPIO: {free}")
    return 1 if unexplained else 0


if __name__ == "__main__":
    sys.exit(main())
