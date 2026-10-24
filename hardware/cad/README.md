# hardware/cad — stage-1 ring enclosure (CadQuery)

The only mechanical CAD in the project right now: a **printable stage-1 "signet" ring** generated from the
PCB floorplan numbers in `hardware/pcb/board_params.json`. It replaces the old OpenSCAD concept
(`hardware/enclosure/mcring_stage1.scad`, deleted).

| File | What |
|---|---|
| `mcring_stage1.py` | parametric model (band, bay, ledges, snap lid, camera pod, cell + LRA pockets, LED window, mic port, switch slot, charging-pad windows + wire grooves) with placeholder solids, fit check, mass/envelope, exports |
| `fit_report.md` | generated: stack, intersection volumes, wall probes, envelope, mass |
| `out/mcring_stage1_shell.stl` | **print file 1** — band + signet bay + camera pod (one part) |
| `out/mcring_stage1_lid.stl` | **print file 2** — rebated lid with detent beads |
| `out/mcring_stage1_assembly.step` | shell + lid + placeholders (PCB, module, camera, cell, LRA, switch, LED, mic, FPC1) as one compound |
| `out/view_top.png/.svg`, `out/view_front.png/.svg`, `out/view_section.png/.svg` | sanity views: top, front along the camera axis, section through the camera axis (Y = 0) |

## Regenerate

```bash
python3 hardware/cad/mcring_stage1.py                 # default inner_d 20.0, lens 4.6
python3 hardware/cad/mcring_stage1.py --inner-d 18.3  # US 8
python3 hardware/cad/mcring_stage1.py --lens-d 3.5    # HM01B0 lensed module instead of the OV2640 head
python3 hardware/cad/mcring_stage1.py --no-step --no-views   # quick fit check only (~3 s)
```

Needs Python ≥ 3.10, `cadquery` (2.8 tested) and `cairosvg`. The script exits 1 if any placeholder intersects the
shell, the lid or another placeholder, or if a wall probe is below its minimum — it did catch one error during
development (a mirrored u.FL placeholder sitting inside the back wall). Everything else in `default_params()` is a
plain dict you can edit (band width, wall, clearances, pocket positions, lid rebate, pad angle ...).

## Coordinates

X runs along the finger, **+X toward the fingertip = camera / front**; Y across the finger (the switch is on the −Y
side); Z up, Z = 0 on the finger axis, skin top at Z = inner_d / 2. Board coordinates from `board_params.json`
(x from the front edge, y from the switch edge) map as `X = L/2 − x`, `Y = y − W/2` — the board is centred on the
ring axis along the finger, so the 26.5 mm board overhangs the 12 mm band by ~7 mm front and back.

## Parameters

| `inner_d` | US ring size (finger Ø + 0.2 mm comfort) |
|---|---|
| 17.5 | 7 (17.3) |
| 18.3 | 8 (18.1) |
| 19.1 | 9 (18.9) |
| **20.0** | **10 (19.8) — default** |
| 20.8 | 11 (20.6) |
| 21.6 | 12 (21.4) |

Other defaults: band 12.0 wide, wall 1.2; bay = board + 0.3 clearance per side + 1.2 walls → 29.5 × 21.0 outer,
corner r 3.0; lid 1.2 thick in a 0.5 mm rebate with 0.15 clearance and a Ø0.5 detent bead on each long edge;
lens bore Ø4.6; cell pocket 10.4 × 12.4 × 3.4 (cell 10 along X, 12 across) centred 2.8 mm toward the antenna end;
LRA pocket Ø8.4 × 2.9 at (X 7.8, Y 3.5) under the mic side of the board; pad windows 4 × 3 at ±25° from the bottom;
switch slot 3.4 × 1.6; mic port Ø0.8; touch dimple 4 × 5 × 0.4 (0.8 mm resin over the pad).

## Stack (from `board_params.json`, Z above the finger skin)

| level | mm |
|---|---|
| band wall under the cell pocket / pod floor | 1.20 |
| sub-board floor (cell pocket top) — wall under the bay 4.6 | 4.60 |
| board bottom on the ledges | 6.10 |
| board top | 6.70 |
| lens axis | 5.50 |
| lid underside (2.9 top parts + 0.3) | 9.90 |
| lid top = camera pod roof | **11.10** |

0.4 mm taller than the floorplan's 10.7: the 3.4 mm pocket (cell 3.0 + 0.4) sits on the 1.2 mm wall and the
0.35 mm cell-to-parts clearance of the floorplan stack is kept on top of it. The side effect is welcome: the pod roof
(head 8.5 + 1.2 wall) ends up flush with the lid instead of 0.55 mm above it. Set `cell_pocket` to 3.0 deep to get the
10.7 stack back (cell flush with the floor).

Envelope: band OD 22.4 (23.8 across the two pad-wire ribs), signet 29.5 × 21.0, 37.8 mm long including the pod,
11.1 mm above the skin. Mass ≈ 6.5 g resin + 5.2 g parts ≈ **11.7 g** (`fit_report.md`).

## Print settings

* SLA, white or translucent resin (the LED shines through the 1.2 mm lid; translucent lets the whole bay glow).
  0.05 mm layers.
* **Shell**: bay opening up, finger axis horizontal. Supports under the camera pod, under the signet's overhangs
  (the flat shoulders beside the finger bore) and inside the bore if your printer needs them; keep the lid rebate and
  the bay interior support-free. The 0.7 mm rebate rim and the 0.4 mm rim under the detent groove are the thinnest
  features — print the shell in a tough resin, not a brittle standard one, if you want the detent to survive.
* **Lid**: flat, beads up, light supports under the plate or print directly on the build plate and sand the elephant foot
  off the rebate faces (0.15 mm clearance is all you have).
* FDM is possible (0.4 nozzle, 0.12 layers) but the Ø0.8 mic port, the 0.5 detent and the 0.7 rim will not come out;
  drill the port and glue the lid.

## After printing — check

1. **Lens bore** Ø4.6 is clear and round (ream with a 4.5 mm drill shank); the OV2640 head slides into the pod from
   the bay side (opening 9.2 × 8.7) until the barrel face touches the front wall. If you prefer the lens flush with the
   pod face, push the Ø4.5 barrel 1.2 mm into the bore — the 8.3 mm pod depth leaves room for the FPC loop either way.
2. **Lid snap**: the lid drops into the rebate with ~0.15 mm play and the beads click into the grooves; sand the beads if
   it binds, add a drop of glue or tape for the final build (resin detents are a light click, not a latch).
3. **Cell pocket**: the 3 × 10 × 12 mm 301012 cell drops in with 0.2 mm on each side; its tabs lie in the 3 × 0.8 mm
   channel toward the J1 pads (−Y side); the sub-board floor must sit ≥ 0.35 mm under the bottom-side parts
   (board on the front and back ledges, bottom parts ≤ 1.15 mm).
4. Board on the ledges (front 1.0 mm wide in the two gaps between bottom parts, back 3.2 mm under the test pads):
   board top 0.6 mm above the ledge; switch plunger centred in the 3.4 × 1.6 slot; mic port straight above the
   T3902 at (8.1, 15.85); LED ring over D1.
5. Charging-pad windows open through the band at ±25°; the wire grooves on the outside of the band (X +2.5 and
   −4.5) run into the slanted channels that surface under the board near the PAD1w/PAD2w pads — thread the wires
   before fitting the cell. Fill the grooves with resin/epoxy afterwards.
6. Antenna: route the u.FL pigtail / flex antenna down the inside of the back wall (5 mm behind the board edge is
   kept free of metal, cell and LRA).

## What the placeholders assume

OV2640 head 8.5 × 8.5 × 1.3 + Ø4.5 × 4.5 barrel; ESP32-S3-MINI-1U 15.4 × 15.4 × 2.4 with a 2.5 × 2.5 × 2.9 mated
u.FL at the back-left; 301012 cell 3 × 10 × 12; INEED LRA0825BC Ø8 × 2.5; Omron B3U-3000P 3.0 × 2.5 × 1.2 with a
plunger reaching the wall slot; WS2812B-2020 2 × 2 × 0.9; TDK T3902 3.5 × 2.65 × 0.98 on the bottom; FPC1 4 × 16 × 2.0.
All are axis-aligned boxes/cylinders — good enough for clearance, not for the exact part outlines.
