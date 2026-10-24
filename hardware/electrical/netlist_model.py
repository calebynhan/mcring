"""
netlist_model.py — a tiny, dependency-free schematic/netlist model for mcring.

KiCad and SKiDL are not available in the design sandbox, so the stage-1 board is
described as Python objects and exported to:

  * the KiCad netlist S-expression format (pcbnew: File > Import Netlist),
  * a grouped BOM CSV with manufacturer part numbers,
  * a per-net Markdown listing,
  * an ERC report (unconnected pins, single-node nets, power pins on
    non-power nets, IC supply pins without a decoupling capacitor on their net).

Usage sketch::

    nl = Netlist("mcring_v1")
    nl.add(Part("R1", "10k", "Resistor_SMD:R_0402_1005Metric",
                mpn="RC0402FR-0710KL", pins={"1": "1", "2": "2"}))
    nl.connect("3V3", "R1", "1")        # by pin number
    nl.connect("EN",  "R1", "2")
    nl.connect("3V3", "U1", "3V3")      # or by (unique) pin name
    nl.export_kicad_netlist("out/mcring_v1.net")

Only the Python standard library is used.
"""
from __future__ import annotations

import csv
import datetime as _dt
import hashlib
import re
import uuid
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Set, Tuple

__all__ = ["Part", "Net", "Netlist", "ERCWarning"]


# --------------------------------------------------------------------------- #
# Data model
# --------------------------------------------------------------------------- #
@dataclass
class Part:
    """One schematic component.

    pins       : {pin_number: pin_name}; pin numbers are strings ("1", "A1", ...).
    power_pins : pin numbers that are supply/ground pins. ERC requires them to sit
                 on a power-named net and (for ICs) to have a capacitor on the net.
    nc_pins    : pin numbers that may legitimately be left unconnected.
    is_ic      : enables the "supply pin needs a capacitor" check.
    dnp        : do-not-populate (still exported; marked in the BOM).
    """
    ref: str
    value: str
    footprint: str
    mpn: str = ""
    pins: Dict[str, str] = field(default_factory=dict)
    power_pins: Set[str] = field(default_factory=set)
    nc_pins: Set[str] = field(default_factory=set)
    description: str = ""
    is_ic: bool = False
    dnp: bool = False
    manufacturer: str = ""
    fields: Dict[str, str] = field(default_factory=dict)
    sheet: str = ""          # schematic sheet name (for the SVG renderer)

    def __post_init__(self) -> None:
        self.pins = OrderedDict((str(k), str(v)) for k, v in self.pins.items())
        self.power_pins = {str(p) for p in self.power_pins}
        self.nc_pins = {str(p) for p in self.nc_pins}
        unknown = (self.power_pins | self.nc_pins) - set(self.pins)
        if unknown:
            raise ValueError(f"{self.ref}: power/nc pins not in pin table: {sorted(unknown)}")

    # pin lookup by number or by unique name
    def resolve_pin(self, pin: str) -> str:
        pin = str(pin)
        if pin in self.pins:
            return pin
        matches = [n for n, name in self.pins.items() if name == pin]
        if len(matches) == 1:
            return matches[0]
        if not matches:
            raise KeyError(f"{self.ref}: no pin number or name '{pin}'")
        raise KeyError(f"{self.ref}: pin name '{pin}' is not unique ({matches}); use the number")

    @property
    def prefix(self) -> str:
        return re.match(r"[A-Za-z_]+", self.ref).group(0)

    @property
    def is_capacitor(self) -> bool:
        return self.prefix == "C"


@dataclass
class Net:
    name: str
    is_power: bool = False
    nodes: List[Tuple[str, str]] = field(default_factory=list)  # (ref, pin_number)

    def add(self, ref: str, pin: str) -> None:
        if (ref, pin) not in self.nodes:
            self.nodes.append((ref, pin))

    @property
    def is_ground(self) -> bool:
        return bool(re.match(r"^(A|D|P)?GND\d*$", self.name))


@dataclass
class ERCWarning:
    kind: str
    message: str

    def __str__(self) -> str:
        return f"[{self.kind}] {self.message}"


# --------------------------------------------------------------------------- #
# Netlist
# --------------------------------------------------------------------------- #
class Netlist:
    #: nets whose name matches are treated as power nets for ERC
    POWER_NET_RE = re.compile(r"^(?:(?:A|D|P)?GND\d*|VBAT|VBUS|VSYS|VIN|VLED|VDD\w*|V\d+V\d*|\d+V\d+|"
                              r"[A-Z0-9]+_\d+V\d+|CHG_IN|\+\w+)$")

    def __init__(self, name: str, source: str = "", tool: str = "mcring netlist_model 0.1") -> None:
        self.name = name
        self.source = source or f"{name}.py"
        self.tool = tool
        self.parts: "OrderedDict[str, Part]" = OrderedDict()
        self.nets: "OrderedDict[str, Net]" = OrderedDict()
        self._pin_net: Dict[Tuple[str, str], str] = {}
        self.extra_power_nets: Set[str] = set()

    # ---- building ---------------------------------------------------------- #
    def add(self, part: Part) -> Part:
        if part.ref in self.parts:
            raise ValueError(f"duplicate reference {part.ref}")
        self.parts[part.ref] = part
        return part

    def add_parts(self, parts: Iterable[Part]) -> None:
        for p in parts:
            self.add(p)

    def net(self, name: str) -> Net:
        if name not in self.nets:
            is_power = bool(self.POWER_NET_RE.match(name)) or name in self.extra_power_nets
            self.nets[name] = Net(name, is_power=is_power)
        return self.nets[name]

    def declare_power_nets(self, *names: str) -> None:
        for n in names:
            self.extra_power_nets.add(n)
            self.net(n).is_power = True

    def connect(self, net_name: str, ref: str, pin: str) -> None:
        """Attach part `ref` pin `pin` (number or unique name) to net `net_name`."""
        if ref not in self.parts:
            raise KeyError(f"unknown part {ref}")
        part = self.parts[ref]
        pn = part.resolve_pin(pin)
        key = (ref, pn)
        if key in self._pin_net and self._pin_net[key] != net_name:
            raise ValueError(f"{ref}.{pn} ({part.pins[pn]}) already on net {self._pin_net[key]}, "
                             f"cannot also join {net_name}")
        self.net(net_name).add(ref, pn)
        self._pin_net[key] = net_name

    def connect_many(self, net_name: str, *nodes: Tuple[str, str]) -> None:
        for ref, pin in nodes:
            self.connect(net_name, ref, pin)

    def net_of(self, ref: str, pin: str) -> Optional[str]:
        return self._pin_net.get((ref, self.parts[ref].resolve_pin(pin)))

    # ---- stats ------------------------------------------------------------- #
    def stats(self) -> Dict[str, int]:
        n_pins = sum(len(p.pins) for p in self.parts.values())
        n_nodes = sum(len(n.nodes) for n in self.nets.values())
        return {
            "parts": len(self.parts),
            "parts_populated": sum(1 for p in self.parts.values() if not p.dnp),
            "pins": n_pins,
            "nets": len(self.nets),
            "nodes": n_nodes,
            "power_nets": sum(1 for n in self.nets.values() if n.is_power),
        }

    # ---- ERC --------------------------------------------------------------- #
    def erc(self) -> List[ERCWarning]:
        warns: List[ERCWarning] = []
        # 1. unconnected non-NC pins, and NC pins that are connected (info)
        for p in self.parts.values():
            for pn, name in p.pins.items():
                connected = (p.ref, pn) in self._pin_net
                if not connected and pn not in p.nc_pins:
                    warns.append(ERCWarning("unconnected", f"{p.ref}.{pn} ({name}) is not connected"))
                if connected and pn in p.nc_pins:
                    warns.append(ERCWarning("nc-connected",
                                            f"{p.ref}.{pn} ({name}) is marked NC but is on net "
                                            f"{self._pin_net[(p.ref, pn)]}"))
        # 2. single-node nets
        for n in self.nets.values():
            if len(n.nodes) < 2:
                warns.append(ERCWarning("single-node", f"net {n.name} has {len(n.nodes)} node(s): {n.nodes}"))
        # 3. power pins on non-power nets
        for p in self.parts.values():
            for pn in sorted(p.power_pins):
                nn = self._pin_net.get((p.ref, pn))
                if nn is None:
                    continue  # already reported as unconnected
                if not self.nets[nn].is_power:
                    warns.append(ERCWarning("power-pin",
                                            f"{p.ref}.{pn} ({p.pins[pn]}) is a power pin on non-power net {nn}"))
        # 4. IC supply pins without a capacitor on their net (ground nets excluded)
        for p in self.parts.values():
            if not p.is_ic:
                continue
            for pn in sorted(p.power_pins):
                nn = self._pin_net.get((p.ref, pn))
                if nn is None:
                    continue
                net = self.nets[nn]
                if net.is_ground:
                    continue
                has_cap = any(self.parts[r].is_capacitor and not self.parts[r].dnp for r, _ in net.nodes)
                if not has_cap:
                    warns.append(ERCWarning("no-decoupling",
                                            f"{p.ref}.{pn} ({p.pins[pn]}) supply net {nn} has no capacitor"))
        return warns

    # ---- exports ----------------------------------------------------------- #
    @staticmethod
    def _q(s: str) -> str:
        s = str(s).replace("\\", "\\\\").replace('"', '\\"')
        return f'"{s}"'

    def _tstamp(self, key: str) -> str:
        return str(uuid.UUID(hashlib.md5(f"{self.name}:{key}".encode()).hexdigest()))

    def _pintype(self, part: Part, pn: str) -> str:
        if pn in part.power_pins:
            return "power_in"
        if pn in part.nc_pins:
            return "no_connect"
        return "passive" if not part.is_ic else "bidirectional"

    def export_kicad_netlist(self, path: str) -> str:
        """Write a KiCad (version 'E') netlist that pcbnew imports via File > Import Netlist."""
        q = self._q
        now = _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        out: List[str] = []
        out.append('(export (version "E")')
        out.append(f'  (design (source {q(self.source)}) (date {q(now)}) (tool {q(self.tool)})')
        out.append(f'    (sheet (number "1") (name "/") (tstamps "/")'
                   f' (title_block (title {q(self.name)}) (company "mcring") (rev "v1") (date {q(now[:10])}))))')
        out.append('  (components')
        for p in self.parts.values():
            out.append(f'    (comp (ref {q(p.ref)})')
            out.append(f'      (value {q(p.value)})')
            out.append(f'      (footprint {q(p.footprint)})')
            if p.description:
                out.append(f'      (description {q(p.description)})')
            flds = OrderedDict()
            if p.mpn:
                flds["MPN"] = p.mpn
            if p.manufacturer:
                flds["Manufacturer"] = p.manufacturer
            if p.sheet:
                flds["Sheet"] = p.sheet
            flds.update(p.fields)
            if flds:
                out.append('      (fields')
                for k, v in flds.items():
                    out.append(f'        (field (name {q(k)}) {q(v)})')
                out.append('      )')
            out.append(f'      (libsource (lib "mcring") (part {q(p.value)}) (description {q(p.description)}))')
            out.append(f'      (property (name "Sheetname") (value "Root"))')
            out.append(f'      (property (name "Sheetfile") (value {q(self.name + ".kicad_sch")}))')
            if p.dnp:
                out.append('      (property (name "dnp"))')
            out.append(f'      (sheetpath (names "/") (tstamps "/"))')
            out.append(f'      (tstamps {q(self._tstamp(p.ref))}))')
        out.append('  )')
        out.append('  (libparts)')
        out.append('  (libraries)')
        out.append('  (nets')
        code = 0
        for n in self.nets.values():
            code += 1
            out.append(f'    (net (code {q(code)}) (name {q(n.name)})')
            for ref, pn in n.nodes:
                part = self.parts[ref]
                out.append(f'      (node (ref {q(ref)}) (pin {q(pn)}) (pinfunction {q(part.pins[pn])})'
                           f' (pintype {q(self._pintype(part, pn))}))')
            out.append('    )')
        out.append('  )')
        out.append(')')
        text = "\n".join(out) + "\n"
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return text

    def export_bom_csv(self, path: str) -> List[dict]:
        """Grouped by value + footprint (+ MPN); DNP parts are grouped separately and marked."""
        groups: "OrderedDict[tuple, dict]" = OrderedDict()
        for p in self.parts.values():
            key = (p.value, p.footprint, p.mpn, p.dnp)
            g = groups.setdefault(key, {"qty": 0, "refs": [], "value": p.value, "footprint": p.footprint,
                                        "mpn": p.mpn, "manufacturer": p.manufacturer,
                                        "descriptions": [], "dnp": "DNP" if p.dnp else ""})
            g["qty"] += 1
            g["refs"].append(p.ref)
            if p.description and p.description not in g["descriptions"]:
                g["descriptions"].append(p.description)
        rows = []
        for g in groups.values():
            if len(g["descriptions"]) == 1:
                desc = g["descriptions"][0]
            elif g["descriptions"]:
                desc = f"{g['qty']}x {g['value']} {_pkg(g['footprint'])}: " + "; ".join(g["descriptions"])
            else:
                desc = ""
            rows.append({"Qty": g["qty"], "Refs": " ".join(sorted(g["refs"], key=_natkey)),
                         "Value": g["value"], "Footprint": g["footprint"], "MPN": g["mpn"],
                         "Manufacturer": g["manufacturer"], "Description": desc, "DNP": g["dnp"]})
        rows.sort(key=lambda r: (r["DNP"] != "", _natkey(r["Refs"].split()[0])))
        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        return rows

    def export_markdown(self, path: str, title: str = "") -> str:
        st = self.stats()
        lines = [f"# {title or self.name} — net listing", "",
                 f"{st['parts']} parts ({st['parts_populated']} populated), {st['pins']} pins, "
                 f"{st['nets']} nets, {st['nodes']} nodes, {st['power_nets']} power nets.", "",
                 "## Nets", "", "| Net | Power | Nodes | Connections |", "|---|---|---|---|"]
        for n in sorted(self.nets.values(), key=lambda n: (not n.is_power, _natkey(n.name))):
            conns = ", ".join(f"{ref}.{pn} ({self.parts[ref].pins[pn]})" for ref, pn in n.nodes)
            lines.append(f"| `{n.name}` | {'yes' if n.is_power else ''} | {len(n.nodes)} | {conns} |")
        lines += ["", "## Parts", "", "| Ref | Value | MPN | Footprint | Pins | Sheet |", "|---|---|---|---|---|---|"]
        for p in sorted(self.parts.values(), key=lambda p: _natkey(p.ref)):
            lines.append(f"| {p.ref}{' (DNP)' if p.dnp else ''} | {p.value} | {p.mpn} | `{p.footprint}` | "
                         f"{len(p.pins)} | {p.sheet} |")
        lines += ["", "## Pin-by-pin", ""]
        for p in sorted(self.parts.values(), key=lambda p: _natkey(p.ref)):
            if len(p.pins) < 3:
                continue
            lines += [f"### {p.ref} — {p.value}", "", "| Pin | Name | Net |", "|---|---|---|"]
            for pn, name in p.pins.items():
                nn = self._pin_net.get((p.ref, pn))
                lines.append(f"| {pn} | {name} | {nn if nn else ('NC' if pn in p.nc_pins else '**open**')} |")
            lines.append("")
        text = "\n".join(lines) + "\n"
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return text

    def export_erc_markdown(self, path: str, waivers: Optional[Dict[str, str]] = None,
                            title: str = "") -> List[ERCWarning]:
        """Write erc.md. `waivers` maps a substring of a warning message to an explanation."""
        waivers = waivers or {}
        warns = self.erc()
        st = self.stats()
        unexplained, explained = [], []
        for w in warns:
            why = next((v for k, v in waivers.items() if k in w.message), None)
            (explained if why else unexplained).append((w, why))
        lines = [f"# {title or self.name} — ERC", "",
                 f"Checked {st['parts']} parts / {st['pins']} pins / {st['nets']} nets / {st['nodes']} nodes.", "",
                 f"* {len(warns)} warning(s) total, {len(unexplained)} unexplained, {len(explained)} explained.", ""]
        lines.append("**Result: CLEAN**" if not unexplained else "**Result: WARNINGS — see below**")
        lines.append("")
        if unexplained:
            lines += ["## Unexplained warnings", ""]
            lines += [f"* {w}" for w, _ in unexplained]
            lines.append("")
        if explained:
            lines += ["## Explained (intentional) warnings", "", "| Warning | Why it is intentional |", "|---|---|"]
            lines += [f"| {w} | {why} |" for w, why in explained]
            lines.append("")
        lines += ["## Checks performed", "",
                  "1. every pin not marked NC is on a net;",
                  "2. no net has fewer than two nodes;",
                  "3. every pin declared as a power pin sits on a power-named net;",
                  "4. every IC supply pin (non-ground) has at least one populated capacitor on its net;",
                  "5. (while building) no pin is on two nets, every NC pin that is connected is reported.", ""]
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
        return warns


def _pkg(footprint: str) -> str:
    """'Capacitor_SMD:C_0402_1005Metric' -> '0402'."""
    m = re.search(r"_(\d{4})_\d{4}Metric", footprint)
    return m.group(1) if m else footprint.split(":")[-1]


def _natkey(s: str):
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", s)]


def _selftest() -> None:
    """`python3 netlist_model.py` — builds a deliberately faulty netlist and checks every ERC kind fires."""
    nl = Netlist("selftest")
    nl.add(Part("U1", "IC", "X:Y", pins={"1": "VDD", "2": "GND", "3": "OUT", "4": "NC"},
                power_pins={"1", "2"}, nc_pins={"4"}, is_ic=True))
    nl.add(Part("R1", "10k", "X:R", pins={"1": "1", "2": "2"}))
    nl.add(Part("C1", "100n", "X:C", pins={"1": "1", "2": "2"}))
    nl.connect("3V3", "U1", "VDD")          # power net, no capacitor on it   -> no-decoupling
    nl.connect("SIGNAL_X", "U1", "GND")     # power pin on a signal net        -> power-pin
    nl.connect("SIGNAL_X", "R1", "1")
    nl.connect("OUT", "U1", "3")            # single node                      -> single-node
    nl.connect("GND", "C1", "2")
    nl.connect("GND", "U1", "4")            # NC pin connected                 -> nc-connected
    # R1.2 and C1.1 left open                                                  -> unconnected
    kinds = {w.kind for w in nl.erc()}
    expected = {"no-decoupling", "power-pin", "single-node", "nc-connected", "unconnected"}
    assert kinds == expected, f"ERC self-test: got {kinds}, expected {expected}"
    try:
        nl.connect("OTHER", "U1", "3")
        raise AssertionError("double connection not refused")
    except ValueError:
        pass
    print(f"netlist_model self-test OK: {len(nl.erc())} warnings of kinds {sorted(kinds)}")


if __name__ == "__main__":
    _selftest()
