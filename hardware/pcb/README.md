# hardware/pcb — stage-1 floorplan and stage-0 bench wiring

Pure-Python SVG/PNG generators (no KiCad / OpenSCAD needed; `cairosvg` renders the PNGs).

| File | What |
|---|---|
| `floorplan.py` | stage-1 board floorplan: placement of every part of `hardware/electrical/out/mcring_v1_nets.md` on a 2-layer 0.6 mm board, keep-outs, routing corridors, critical nets; runs placement checks (overlaps, edge clearance, heights, keep-outs) and refuses to draw if one fails |
| `board_params.json` | **the numbers the enclosure is generated from** — board size, part heights, switch/LED/mic/module/touch-pad positions, stack and camera-pod dimensions, every placed part with its centre and size |
| `floorplan.md` | the same placement as tables, keep-outs, layer usage, route rules, FPC pin order, stack, deviations |
| `out/floorplan_top.svg/.png` | to-scale top side (module, FPC connector, switch, LED, touch pad, bulk cap) |
| `out/floorplan_bottom.svg/.png` | to-scale bottom side **seen from below (mirrored)** — all small ICs, passives, wire pads, test pads |
| `out/stackup.svg/.png` | vertical stack skin → band → cell → PCB → parts → lid with running totals, and the camera-pod side section |
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
* Switch on the **left** edge at x = 8.0; LED (8.1, 10.0); touch pad (8.1, 5.6); mic port (8.1, 15.85) — the T3902 is bottom-port and
  sits on the **bottom** side with its port through the board and a lid hole above.
* Signet top ≈ 10.7 mm above the skin with the cell under the board (7.7 mm with the cell in the band's palm-side thick zone).
* Camera pod: lens axis 5.5 mm above the skin, 8.3 mm interior depth in front of the board edge, Ø4.7 bore.

See `floorplan.md` §9 for deviations from the task text and the earlier notes (mic side, battery pads instead of the JST SH, 8 test pads, heights).
