# Enclosure

The stage-1 enclosure now lives in **`hardware/cad/`** as a parametric CadQuery model generated from the PCB
floorplan (`hardware/pcb/board_params.json`): band, signet bay with board ledges and a rebated detent lid, forward
camera pod with the Ø4.6 lens bore, cell and LRA pockets, LED window, mic port, side-switch slot, inner-band
charging-pad windows with wire grooves, placeholder solids and an automatic fit check.

```bash
python3 hardware/cad/mcring_stage1.py            # -> hardware/cad/out/*.stl, *.step, views; hardware/cad/fit_report.md
python3 hardware/cad/mcring_stage1.py --inner-d 18.3   # US 8; see hardware/cad/README.md for the size table
```

The earlier OpenSCAD concept (`mcring_stage1.scad`, 26 × 12 bay) was removed: the ESP32-S3-MINI-1U + 24-pin FPC
connector set the board at 26.5 × 18.0 mm, so the bay, the stack and the cell position all changed.

Stage 2 (Oura-size) will not be printed around a rigid board; it will be a potted rigid-flex inside a machined or
printed shell — see `docs/04-feasibility-and-risks.md`.
