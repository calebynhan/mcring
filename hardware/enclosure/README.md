# Enclosure

`mcring_stage1.scad` — parametric OpenSCAD model of the stage-1 "oversized ring":
a 20 mm ID band (US ~10) with a 26 × 12 × 6.5 mm electronics bay on top, a forward-facing
camera pod with a 4.6 mm lens bore (OV2640 head) or 3.5 mm (HM01B0), a pocket in the
thick lower band for a 3 × 10 × 12 mm cell, an LED window, an Omron B3U side-button slot,
inner-band charging-pad windows and a snap lid.

```bash
openscad -o mcring_stage1.stl hardware/enclosure/mcring_stage1.scad
# tweak: -D inner_d=18.2 -D lens_d=3.5
```

Printing: SLA in white or translucent resin, 0.05 mm layers; the LED window is a 1.2 mm
wall that diffuses when the LED sits ≥ 1 mm behind it. For FDM use 0.4 mm nozzle, 0.12 mm
layers, bay opening up, supports under the pod.

Sizing: `inner_d` is the finger diameter (US size 7 = 17.3 mm, 9 = 18.9, 10 = 19.8, 11 = 20.6,
12 = 21.4). Add 0.2–0.3 mm for comfort.

Stage 2 (Oura-size) will not be printed around a rigid board; it will be a potted rigid-flex
inside a machined or printed shell — see `docs/04-feasibility-and-risks.md`.
