#!/usr/bin/env python3
"""export_cpl.py — pick-and-place (CPL) and assembler BOM for the stage-1 board, in JLCPCB's format.

Reads the placement data of `floorplan.py` (part centres, sides) and the design of
`hardware/electrical/mcring_v1.py` (values, MPNs, LCSC numbers, DNP / off-board flags) and writes, in out/:

  mcring_v1_cpl.csv       Designator, Mid X, Mid Y, Layer, Rotation      (JLCPCB "CPL" / PCBWay "centroid" file)
  mcring_v1_bom_jlc.csv   Comment, Designator, Footprint, LCSC Part #     (JLCPCB BOM; PCBWay reads the same columns)
  mcring_v1_pcba_notes.md what the two files assume, the sourcing status of every BOM line (LCSC / consign /
                          match-in-tool), the parts that are NOT placed (DNP, off-board, copper features) and the
                          joint / line counts the assembly quote is built from

Coordinates are the floorplan's: origin at the board's FRONT-LEFT corner seen from the top, X along the finger
(front edge = 0), Y across it (left/switch edge = 0), millimetres, both layers in the top view (what JLCPCB and
KiCad's position file expect for bottom-side parts). Set the layout tool's drill/place origin to that corner before
exporting Gerbers so the two agree. Rotation is 0 except for 0402s placed "along y" (90); the pin-1 orientation of
every IC and connector is fixed at layout — see the notes file.

Run:  python3 export_cpl.py        (exit 1 if the floorplan and the netlist disagree about which parts exist)
"""
from __future__ import annotations

import csv
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..", "electrical")))
import floorplan as fp  # noqa: E402
import mcring_v1 as design  # noqa: E402

OUT = os.path.join(HERE, "out")

# copper features of the floorplan that are not components (no CPL line, no BOM line)
COPPER_KINDS = {"pad", "tp", "copper"}
# netlist parts that are copper features on the board (bare pads) — not placed by the assembler
PAD_PARTS = {"BZ1": "two bare 1.2 mm pads (optional piezo, DNP)", "J2": "two bare 1.2 mm pads (aux bench experiment)",
             "TPAD1": "3 x 4 mm copper landing (touch)"}
# parts the LCSC/JLCPCB library does not stock -> the owner buys them and ships them to the assembler ("consigned")
CONSIGN = {
    "ESP32-S3-MINI-1U-N4R2": "not on LCSC (only the N8 without PSRAM and the MINI-1 PCB-antenna variant) — Mouser / DigiKey / Espressif store",
    "TPS22916CYFPR": "not on LCSC at the research snapshot (DigiKey 12-wk, Arrow) — order 3 + spares; or re-check live, TI stock moves",
    "78171-0002": "Molex Pico-EZmate — not on LCSC; DigiKey / Mouser / RS (4 + spares); the matching pigtails are owner-side parts",
}


def pkg(fpname: str) -> str:
    """KiCad footprint name -> the short package string JLCPCB's BOM tool matches on."""
    m = re.search(r"_(\d{4})_\d{4}Metric", fpname)
    if m:
        return m.group(1)
    table = {
        "Package_TO_SOT_SMD:SOT-23": "SOT-23",
        "Package_TO_SOT_SMD:SOT-583-8": "SOT-583-8",
        "Diode_SMD:D_SOD-523": "SOD-523",
        "Inductor_SMD:L_0806_2016Metric": "2016 (0806)",
        "RF_Module:ESP32-S3-MINI-1U": "ESP32-S3-MINI-1U (65 pads)",
        "Package_LGA:LGA-12_2x2mm_P0.5mm": "LGA-12 2x2 0.5 mm",
        "Package_SO:VSSOP-10_3x3mm_P0.5mm": "VSSOP-10 3x3",
        "Package_DFN_QFN:QFN-16-1EP_3x3mm_P0.5mm_EP1.7x1.7mm": "QFN-16 3x3 EP",
        "LED_SMD:LED_WS2812B-2020_PLCC4_2.0x2.0mm": "2020 PLCC4",
        "mcring:TPS22916_DSBGA-4_YFP": "DSBGA-4 0.4 mm (YFP)",
        "mcring:BQ25100_DSBGA-6_YFP": "DSBGA-6 0.4 mm (YFP)",
        "mcring:SW_Omron_B3U-3000P": "B3U-3000P side switch",
        "mcring:SW_Omron_B3U-1000P": "B3U-1000P",
        "mcring:MIC_TDK_T3902_3.5x2.65mm": "T3902 3.5x2.65 bottom port",
        "Connector_FFC-FPC:Hirose_FH12-24S-0.5SH_1x24-1MP_P0.50mm_Horizontal": "FH12-24 0.5 mm horizontal",
        "Connector_Molex:Molex_Pico-EZmate_78171-0002_1x02-1MP_P1.20mm_Vertical": "Pico-EZmate 1x2 vertical",
    }
    return table.get(fpname, fpname.split(":")[-1])


def rotation(p: fp.Part) -> float:
    return 90.0 if (p.kind == "passive" and p.h > p.w) else 0.0


def natkey(s: str):
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", s)]


def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    nl = design.build()
    placed = [p for p in fp.PARTS if p.kind not in COPPER_KINDS]
    on_board = {r: p for r, p in nl.parts.items() if not p.offboard and not p.dnp}
    dnp = {r: p for r, p in nl.parts.items() if p.dnp and not p.offboard}
    offboard = {r: p for r, p in nl.parts.items() if p.offboard}

    # ---- consistency between the two sources
    fp_refs = {p.ref for p in placed}
    problems = []
    for r in sorted(set(on_board) - fp_refs - set(PAD_PARTS) - {f"TP{i}" for i in range(1, 9)}, key=natkey):
        problems.append(f"{r} is a populated on-board part in the netlist but not placed in floorplan.py")
    for r in sorted(fp_refs - set(on_board), key=natkey):
        problems.append(f"{r} is placed in floorplan.py but is not a populated on-board part in the netlist")
    dup = [r for r in fp_refs if sum(q.ref == r for q in placed) > 1]
    if dup:
        problems.append(f"duplicate placements: {dup}")
    if problems:
        for m in problems:
            print("FAIL", m)
        return 1

    # ---- CPL
    cpl_path = os.path.join(OUT, "mcring_v1_cpl.csv")
    with open(cpl_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
        for p in sorted(placed, key=lambda q: natkey(q.ref)):
            w.writerow([p.ref, f"{p.cx:.3f}", f"{p.cy:.3f}", "Top" if p.side == "top" else "Bottom", f"{rotation(p):.0f}"])

    # ---- JLC BOM: one line per (value, footprint, MPN, LCSC)
    groups: dict[tuple, dict] = {}
    for p in sorted(placed, key=lambda q: natkey(q.ref)):
        part = on_board[p.ref]
        lcsc = part.fields.get("LCSC", "")
        comment = part.mpn if (part.prefix not in ("R", "C") and part.mpn) else part.value
        key = (comment, pkg(part.footprint), part.mpn, lcsc)
        g = groups.setdefault(key, {"refs": [], "part": part, "comment": comment, "footprint": pkg(part.footprint), "lcsc": lcsc})
        g["refs"].append(p.ref)
    bom_path = os.path.join(OUT, "mcring_v1_bom_jlc.csv")
    with open(bom_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["Comment", "Designator", "Footprint", "LCSC Part #"])
        for g in groups.values():
            w.writerow([g["comment"], ",".join(g["refs"]), g["footprint"], g["lcsc"]])

    # ---- sourcing status + counts
    def status(g) -> str:
        part = g["part"]
        if part.mpn in CONSIGN:
            return "CONSIGN — " + CONSIGN[part.mpn]
        if g["lcsc"]:
            note = design.LCSC.get(part.mpn, "")
            extra = note.split(" ", 1)[1] if " " in note else ""
            return f"LCSC {g['lcsc']}" + (f" ({extra})" if extra else "")
        if part.prefix in ("R", "C", "L", "D"):
            return "no C-number recorded — let the JLCPCB BOM tool match the value + package (basic part where one exists), or paste the MPN"
        return "no C-number recorded — search the MPN on LCSC at order time; if absent, consign"
    joints = sum(len(on_board[p.ref].pins) for p in placed)
    n_top = sum(p.side == "top" for p in placed)
    n_bot = sum(p.side == "bottom" for p in placed)
    n_consign = sum(1 for g in groups.values() if g["part"].mpn in CONSIGN)
    n_lcsc = sum(1 for g in groups.values() if g["lcsc"] and g["part"].mpn not in CONSIGN)
    n_blank = len(groups) - n_consign - n_lcsc
    notes = os.path.join(OUT, "mcring_v1_pcba_notes.md")
    L = ["# mcring v1 — PCBA files: what `mcring_v1_cpl.csv` and `mcring_v1_bom_jlc.csv` assume", "",
         "Generated by `hardware/pcb/export_cpl.py` from `floorplan.py` (positions) and `hardware/electrical/mcring_v1.py` "
         "(values, MPNs, LCSC numbers). How to use them: `docs/10-ordering-assembled-boards.md`.", "",
         "## Coordinate frame and rotation", "",
         f"* Origin = the board's front-left corner seen from the top; X along the finger (0 = camera/FPC edge, {fp.L} = antenna edge), "
         f"Y across it (0 = switch edge, {fp.W} = connector-notch edge); mm. Both layers in the top view (bottom parts are *not* mirrored).",
         "* Before exporting Gerbers from the layout tool, put its drill/place origin on that corner with the same axes, or regenerate the CPL "
         "from the tool (KiCad: File → Fabrication Outputs → Component Placement, then rename Ref/PosX/PosY/Rot/Side to "
         "Designator/Mid X/Mid Y/Rotation/Layer).",
         "* Rotation: 0 for every part except 0402s placed along y (90). The pin-1 orientation of the ICs, the module, FPC1 and the four "
         "Pico-EZmate headers is set at layout (each header's wire-exit end must face the right board edge / its notch, D1's DIN toward R7, "
         "D3's cathode toward U7, the mic's port over the board hole). JLCPCB re-orients polarised parts to their library footprint at "
         "DFM review — confirm every polarised part on their placement preview before approving.", "",
         "## Counts", "",
         f"* {len(placed)} placed parts ({n_top} top, {n_bot} bottom), {len(groups)} BOM lines, ≈ {joints} solder joints (pads of the placed parts, "
         f"incl. the module's 65).",
         f"* BOM lines with an LCSC number: {n_lcsc}; consigned (not stocked by LCSC): {n_consign}; no C-number recorded: {n_blank} "
         f"(generic passives the JLCPCB BOM tool matches on value + package).", "",
         "## Sourcing status per BOM line", "",
         "| Comment | Designators | Footprint | LCSC Part # | Status |", "|---|---|---|---|---|"]
    for g in groups.values():
        L.append(f"| {g['comment']} | {', '.join(g['refs'])} | {g['footprint']} | {g['lcsc'] or '—'} | {status(g)} |")
    L += ["", "## Not in the CPL / BOM", "",
          "### Copper features (no component)", ""]
    for r, why in PAD_PARTS.items():
        L.append(f"* {r}: {why}")
    L.append("* TP1–TP8: 1.0 mm test pads on the top side")
    L += ["", "### Do-not-populate", ""]
    for r, p in dnp.items():
        L.append(f"* {r} {p.value} ({p.mpn or 'no MPN'}): {p.description}")
    L.append("* U4 (XC6206P122MR, 1.2 V DVDD LDO) is populated in these files; make it DNP in the BOM upload if the purchased OV2640 head "
             "regulates DVDD itself (`hardware/electrical/README.md` §1 item 3)")
    L.append("* The optional speaker group U10/U11/C25/C26/R20–R24 is populated here; the J5 header stays either way")
    L += ["", "### Off-board (owner-supplied, plug in after delivery)", ""]
    for r, p in offboard.items():
        L.append(f"* {r} {p.value} ({p.mpn or 'no MPN'}): {p.description}")
    L += ["", "### Plug-in headers and notches", "",
          f"| Header | Centre (X, Y) | Feeds | Notch in the right edge |", "|---|---|---|---|"]
    for ref, cx, short, feeds, nets in fp.CONNECTORS:
        L.append(f"| {ref} ({short}) | {cx:.2f}, {fp.CONN_CY:.2f} | {feeds} | {fp.NOTCH['w']} × {fp.NOTCH['d']} mm centred on X = {cx:.2f}, Y = {fp.W} (board outline feature, no copper within 0.3 mm) |")
    with open(notes, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")
    print(f"wrote {os.path.relpath(cpl_path, HERE)} ({len(placed)} parts), {os.path.relpath(bom_path, HERE)} ({len(groups)} lines; "
          f"{n_lcsc} with LCSC #, {n_consign} consigned, {n_blank} to match), {os.path.relpath(notes, HERE)}; ≈ {joints} joints")
    return 0


if __name__ == "__main__":
    sys.exit(main())
