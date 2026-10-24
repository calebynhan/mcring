# Enclosure

The stage-1 enclosure now lives in **`hardware/cad/`** as a parametric CadQuery model generated from the PCB
floorplan (`hardware/pcb/board_params.json`): band, signet bay with board ledges, an antenna cavity behind the board
and a rebated detent lid held at the front by the camera-pod roof, forward camera pod with the Ø4.6 lens bore and room
for the folded camera FPC, cell and LRA pockets, LED window, mic port with a tube to the board, side-switch slot with a
printed key, inner-band charging-pad windows with wire grooves, the **optional speaker pocket** (a Ø10 × 2.9 mm micro
speaker standing in a 3.15 mm bump on the right (+Y) wall behind a 5-hole grille, back open to the lidded bay, leads
to the SPK1 pads, closed and held by a tab + boss on the lid — `board_params.json` → `speaker_mm`), placeholder solids
and an automatic fit check (intersections, clearances incl. speaker ↔ antenna, wall probes, finger-contact scan).

```bash
python3 hardware/cad/mcring_stage1.py            # -> hardware/cad/out/*.stl (shell, lid, key), *.step, views; hardware/cad/fit_report.md
python3 hardware/cad/mcring_stage1.py --inner-d 18.3   # US 8; see hardware/cad/README.md for the size table
python3 hardware/cad/mcring_stage1.py --no-speaker     # the ring without the speaker pocket / bump / lid tab
```

The earlier OpenSCAD concept (`mcring_stage1.scad`, 26 × 12 bay) was removed: the ESP32-S3-MINI-1U + 24-pin FPC
connector set the board at 26.5 × 18.0 mm, so the bay, the stack and the cell position all changed.

Stage 2 (Oura-size) will not be printed around a rigid board; it will be a potted rigid-flex inside a machined or
printed shell — see `docs/04-feasibility-and-risks.md`.
