# hardware/pcb — stage-1 floorplan and stage-0 bench wiring

Pure-Python SVG/PNG generators (no KiCad / OpenSCAD needed; `cairosvg` renders the PNGs).

| File | What |
|---|---|
| `floorplan.py` | stage-1 board floorplan: placement of every part of `hardware/electrical/out/mcring_v1_nets.md` on a 2-layer 0.6 mm board, zones, routing corridors, critical nets; runs placement checks (overlaps, edge clearance, heights, zones, test pads on top, touch-contact height) and refuses to draw if one fails |
| `board_params.json` | **the numbers the enclosure is generated from** — board size, part heights, switch/LED/mic/module/touch positions, stack (incl. the 3.4 mm cell pocket), camera-pod inputs (floor relief, head clearance, FPC fold) and the derived z levels, antenna cavity, switch slot, touch electrode/contact, test-pad positions, every placed part with its centre and size. The CAD reads it; `hardware/cad/fit_report.md` is the as-built check |
| `floorplan.md` | the same placement as tables, keep-outs, layer usage, route rules, FPC pin order, stack, deviations |
| `out/floorplan_top.svg/.png` | to-scale top side (module, FPC connector, switch, LED, touch landing + lid-foil outline, bulk cap, the 8 test pads) |
| `out/floorplan_bottom.svg/.png` | to-scale bottom side **seen from below (mirrored)** — all small ICs, passives, wire pads |
| `out/stackup.svg/.png` | vertical stack skin → band → cell (+ pocket slack) → PCB → parts → lid with running totals, and the camera-pod side section |
| `wiring_stage0.py` | stage-0 bench wiring diagram for the Seeed XIAO ESP32S3 Sense |
| `wiring_stage0.md` | connection table, parts and the check-before-power-on list |
| `out/wiring_stage0.svg/.png` | the diagram |
| `svgkit.py` | tiny SVG writer shared by both scripts |

Regenerate: `python3 floorplan.py && python3 wiring_stage0.py` (Python ≥ 3.10, `pip install cairosvg`).

## Coordinate convention used by `board_params.json`

Origin = the board's **front-left corner seen from the top**. `x` runs along the finger from the front
edge (camera / FPC connector, x = 0) to the back edge (antenna / u.FL, x = `board_length_mm`); `y` runs
across the finger from the left edge (switch, y = 0) to the right edge (y = `board_width_mm`). Heights are
measured from the board surface of the side the part is on. The bottom drawing is mirrored so it looks like
the real board turned over; the JSON uses un-mirrored coordinates for both sides.

## Key numbers (stage 1)

* Board **26.5 × 18.0 × 0.6 mm**, r 1.5, 2 layers. Module ESP32-S3-MINI-1U at (18.8, 9.0), u.FL end flush with the back edge.
* Top parts ≤ 2.9 mm (mated u.FL plug; module shield 2.4), bottom parts ≤ 1.15 mm.
* Switch on the **left** edge at x = 8.0; LED (8.1, 10.0); touch landing (8.1, 5.6); mic port (8.1, 15.85) — the T3902 is bottom-port and
  sits on the **bottom** side with its port through the board and a lid hole above.
* **Touch electrode on the lid**: a 4 × 5 mm copper foil on the lid underside (0.8 mm resin over it), reached from the 3 × 4 TPAD1 landing
  by a conductive-foam / spring contact compressed from 3.6 to 3.2 mm — a bare pad on the board would be 4 mm behind the touch surface.
* **All 8 test pads on the top side**: IO0, GND, D−, D+, EN, 3V3 in a column at x = 10.15 just in front of the module row (1.5 mm pitch),
  VBAT and nCHG at x = 5.2 beside FPC1 — flash, probe and bench-power with the board seated in the bay.
* Signet top 11.1 mm above the skin with the cell in its 3.4 mm pocket under the board (7.7 mm with the cell in the band's palm-side thick zone).
* Camera pod: lens axis 6.25 mm above the skin (head 0.3 above the pod floor at 1.7), 8.3 mm interior depth in front of the board edge,
  Ø4.6 bore, roof 12.7 (1.6 above the lid). Bay interior extends 2 mm behind the board for the u.FL pigtail and flex antenna.
* No antenna copper keep-out on the board (the MINI-1U has no PCB antenna); the flex antenna stays ≥ 5 mm from the cell, LRA and metal.

See `floorplan.md` §9 for deviations from the task text and the earlier notes (mic side, battery pads instead of the JST SH, 8 test pads, heights).
