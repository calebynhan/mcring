# hardware/cad — stage-1 ring enclosure (CadQuery)

The only mechanical CAD in the project right now: a **printable stage-1 "signet" ring** generated from the
PCB floorplan numbers in `hardware/pcb/board_params.json`. It replaces the old OpenSCAD concept
(`hardware/enclosure/mcring_stage1.scad`, deleted).

| File | What |
|---|---|
| `mcring_stage1.py` | parametric model (band, bay + antenna cavity, ledges, snap lid with a pod lip, camera pod, cell + LRA pockets, LED window, mic port + tube, switch slot + key, charging-pad windows + wire grooves/channels) with placeholder solids, fit check, mass/envelope, exports |
| `fit_report.md` | generated: stack, intersection volumes, clearances, wall probes, finger-contact scan, envelope, mass |
| `out/mcring_stage1_shell.stl` | **print file 1** — band + signet bay + camera pod (one part) |
| `out/mcring_stage1_lid.stl` | **print file 2** — rebated lid with detent beads and the mic tube |
| `out/mcring_stage1_key.stl` | **print file 3** — side-switch button (flange + pin + cap) |
| `out/mcring_stage1_assembly.step` | shell + lid + placeholders (PCB, module, camera head + folded FPC, cell, LRA, switch + key, LED, mic, FPC1, top/bottom parts, antenna, pigtail) as one compound |
| `out/view_top.png/.svg`, `out/view_front.png/.svg`, `out/view_section.png/.svg` | sanity views: top, front along the camera axis, section through the camera axis (Y = 0) |

## Regenerate

```bash
python3 hardware/cad/mcring_stage1.py                 # default inner_d 20.0, lens 4.6
python3 hardware/cad/mcring_stage1.py --inner-d 18.3  # US 8
python3 hardware/cad/mcring_stage1.py --lens-d 3.5    # HM01B0 lensed module instead of the OV2640 head
python3 hardware/cad/mcring_stage1.py --no-step --no-views   # quick fit check only (~12 s)
```

Needs Python ≥ 3.10, `cadquery` (2.8 tested) and `cairosvg`. The script exits 1 if any placeholder intersects the
shell, the lid or another placeholder, if a clearance (head, FPC fold, antenna cavity, key travel) is below its minimum,
or if a wall probe is below its minimum. Everything in `default_params()` is a plain dict you can edit (band width,
wall, clearances, pocket positions, lid rebate, pad angle ...); the pod and antenna allowances are read from
`board_params.json` (`pod_mm.floor_relief_above_skin / head_clearance / fpc_fold_above_head`,
`antenna_cavity_mm.depth_behind_board_edge`) with the same defaults in the script.

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

Other defaults: band 12.0 wide, wall 1.2; bay = board + 0.3 clearance per side + 1.2 walls, plus a 2.0 mm antenna
cavity behind the board's back edge → signet 31.5 × 21.0 outer, corner r 3.0; lid 1.2 thick in a 0.5 mm rebate with
0.15 clearance, a Ø0.5 detent bead on each long edge and a 1.0 mm pod-roof lip over its front edge; lens bore Ø4.6;
cell pocket 10.4 × 12.4 × 3.4 (cell 10 along X, 12 across) centred 2.8 mm toward the antenna end; LRA pocket Ø8.4 × 2.9 at
(X 7.8, Y 3.5) under the mic side of the board; pad windows 3 × 3 at ±25° from the bottom; one 4 mm wide rib on the
−Y side carrying two 0.9 mm grooves (X −1.5 and −3.5) that turn into Ø0.9 channels through the slab; switch slot
3.4 × 1.6 with a 4.6 × 2.8 × 0.5 counterbore inside for the key's flange; mic port Ø0.8 in a Ø1.8 tube; touch dimple
4 × 5 × 0.4 (0.8 mm resin over the lid electrode).

## Stack (Z above the finger skin, mm)

| level | mm |
|---|---|
| cell-pocket floor (band wall) | 1.20 |
| sub-board floor (cell pocket top) — wall under the bay 4.6 | 4.60 |
| board bottom on the ledges | 6.10 |
| board top | 6.70 |
| lid underside (2.9 top parts + 0.3) | 9.90 |
| lid top | **11.10** |
| pod underside (bore relief) / pod floor | 0.50 / 1.70 |
| OV2640 head bottom / top (8.5 mm, 0.3 clearance each side) | 2.00 / 10.50 |
| lens axis | 6.25 |
| pod ceiling (head top + 1.0 for the FPC fold) | 11.50 |
| pod roof top | **12.70** |

0.4 mm taller than the floorplan's original 10.7: the 3.4 mm pocket (cell 3.0 + 0.4) sits on the 1.2 mm wall and the
0.35 mm cell-to-parts clearance of the floorplan stack is kept on top of it. The camera pod is 1.6 mm taller than the
lid: the head alone needs 8.5 + 2 × 0.3 between the pod floor (1.2 mm wall over the 0.5 mm bore relief) and the
ceiling, and the 24-pin flex needs ~1 mm above the head to fold back down behind it (see "Camera FPC" below).
`board_params.json` `stack_mm` / `pod_mm` carry these as-built numbers.

Envelope: band OD 22.4 (23.8 across the pad-wire rib), signet 31.5 × 21.0, 39.8 mm long along the finger including
the pod and the antenna cavity, lid 11.1 / pod roof 12.7 mm above the skin. Mass ≈ 6.8 g resin + 5.4 g parts ≈
**12.2 g** (`fit_report.md`).

## Finger contact

The bore is Ø`inner_d` only where the ring is meant to touch the finger: the 12 mm band plus the 2 mm of cell-pocket
floor behind it (X −8.0 .. +5.5, 13.5 mm along the top of the finger, 11 mm + chamfers along the bottom). Under the rest
of the signet and under the camera pod the bore is opened by 0.5 mm (`bore_relief`) so the overhangs clear the skin;
0.5 mm chamfer cones join the two radii. The shell is still 39.8 mm long: worn with the band against the knuckle the
pod front sits ~17 mm beyond the band's front face toward the PIP joint — try it on a hand before printing in volume,
the alternative is a shorter board or a pod that points sideways.

## Camera FPC

The OV2640 head stands on the pod floor with its lens along +X; its 24-pin flex leaves the head's **top** edge, folds
180° back down behind the head (the 1.0 mm `fpc_fold_above_head`), runs down behind the head, turns 90° at board
top + 0.3 and enters FPC1 (bottom-contact, mouth at the board's front edge) from the front — contacts facing down,
as a bottom-contact connector needs. Path length ≈ 2 (fold) + 2.6 (down) + 1.3 (bend) + 5.1 (run incl. 4 mm in the
connector) ≈ **11 mm from the head's top edge to the contact end — verify on the purchased head** (the Arducam-style
21 × 12.5 mm module has ~12.5). The 12.5 mm wide stiffened contact end never enters the pod: only the 8.5 mm neck passes
the 9.2 × 9.8 pod opening. Assembly order: push the head from the bay into the pod until the barrel sits 0.4 mm into
the Ø4.6 bore, insert the flex into FPC1 with the board held above the bay, then lower the board onto the ledges — the
flex folds behind the head as the board goes down. The flex is in the fit check (`camera_FPC` placeholder: fold, down
run, bend, run and the wide end).

## Antenna

The bay interior extends 2.0 mm behind the board's back edge (`antenna_cavity_mm`), full width, from the sub-board
floor to the lid. A 2.4 GHz flex PCB antenna (placeholder 15 × 5 × 0.25 mm) is glued to the inside of the 1.2 mm back
wall; the u.FL pigtail (Ø0.81, U.FL-LP-040) leaves the plug toward the back and turns down ~1 mm behind the board edge
(placeholder `pigtail`). Nothing metal, no cell and no LRA in the cavity; beyond the wall is air, so the floorplan's
5 mm metal keep-out behind the module is met. Part choice is open: a short-cable flex antenna (most come with 50–100 mm
of cable, which does not fit — order a 30 mm version or re-terminate) or a 31 mm wire monopole on a cut pigtail laid
down the wall and along the band.

## Switch key

The B3U-3000P plunger ends ~1.1 mm inside the 1.2 mm wall, so a printed key passes the 3.4 × 1.6 slot: a 4.4 × 2.6 × 0.33
flange sits in a 4.6 × 2.8 × 0.5 counterbore cut from the inside of the wall (0.7 mm of wall remains around the slot
there), a 3.2 × 1.4 pin goes through the slot, and a 4.4 × 2.6 × 0.6 cap stands 0.3 mm off the signet side (= the
travel) and protrudes 0.9 mm. The flange keeps the key from falling out, the cap from falling in; the plunger touches
the flange's inner face. Fit the key from the inside before the board goes in.

## Print settings

* SLA, white or translucent resin (the LED shines through the 1.2 mm lid; translucent lets the whole bay glow).
  0.05 mm layers. Print the shell in a tough resin, not a brittle standard one, if you want the detent and the switch
  counterbore wall to survive.
* **Shell**: bay opening up, finger axis horizontal. Supports under the camera pod, under the signet's overhangs
  (the flat shoulders beside the finger bore) and inside the bore if your printer needs them; keep the lid rebate, the
  pod-roof lip and the bay interior support-free. The thinnest features: the 0.7 mm rebate rim, the 0.4 mm rim under the
  detent groove, the 0.7 mm wall around the switch counterbore, and the first ~1.3 mm of each wire channel where it
  leaves the open groove at the slab's bottom corner. Everything else is ≥ 1.2 mm where the fit check probes it (it is
  a list of line probes, not a global thickness analysis).
* **Lid**: beads up, mic tube up, light supports under the plate or print directly on the build plate and sand the
  elephant foot off the rebate faces (0.15 mm clearance is all you have).
* **Key**: cap down on the build plate, no supports.
* FDM is possible (0.4 nozzle, 0.12 layers) but the Ø0.8 mic port, the 0.5 detent, the 0.7 rims and the key will not come
  out; drill the port and glue the lid.

## After printing — check

1. **Lens bore** Ø4.6 is clear and round (ream with a 4.5 mm drill shank); the OV2640 head slides into the pod from
   the bay side (opening 9.2 × 9.8) until the barrel sits 0.4 mm into the bore. The head has 0.3 mm to the floor and
   0.35 mm to each side wall; the 1.0 mm above it is for the flex fold, not for a taller head.
2. **Lid**: slide its front edge under the pod-roof lip, then press the back down until the beads click into the
   grooves. The bead engagement is only 0.1 mm — the detent is a light click that locates the lid, the lip holds the
   front edge, and a drop of glue or tape is the real retention for the final build.
3. **Cell pocket**: the 3 × 10 × 12 mm 301012 cell drops in with 0.2 mm on each side; its tabs lie in the 3 × 0.8 mm
   channel toward the J1 pads (−Y side); the sub-board floor must sit ≥ 0.35 mm under the bottom-side parts
   (board on the front and back ledges, bottom parts ≤ 1.15 mm). **Open item**: a 301012 *with PCM* is longer than
   12 mm at the tab end — model the pocket from the cell drawing before the final print.
4. Board on the ledges (front 1.0 mm wide in the two gaps between bottom parts, back 3.2 mm under the test pads):
   board top 0.6 mm above the ledge; switch plunger on the key's flange; mic tube over the T3902 port at (8.1, 15.85)
   with a 0.3 mm foam/adhesive ring between the tube end and the board; LED ring over D1.
5. Charging-pad windows (3 × 3) open through the band at ±25°; the two grooves on the −Y rib (X −1.5 and −3.5) run into
   Ø0.9 channels that surface under the board at Y ≈ −8.3, 0.65 mm (channel B, X −3.5, +Y window → PAD1w CHG+) and
   2.7 / 4.7 mm (channel A, X −1.5, −Y window → PAD2w CHG−, running along the board edge) from the pads — thread the
   wires before fitting the cell. Fill the grooves with resin/epoxy afterwards (they face the palm; an enclosed tunnel
   this size would not print clean or thread).
6. Antenna: glue the flex antenna to the inside of the back wall in the 2 mm cavity, route the pigtail down behind the
   board edge; keep both away from the cell and the LRA.

## What the placeholders assume

OV2640 head 8.5 × 8.5 × 1.3 + Ø4.5 × 4.5 barrel with a 0.2 mm thick flex (8.5 wide neck, 12.5 wide contact end); ESP32-S3-
MINI-1U 15.4 × 15.4 × 2.4 with a 2.5 × 2.5 × 2.9 mated u.FL at the back-left; 301012 cell 3 × 10 × 12 (no PCM); INEED
LRA0825BC Ø8 × 2.5; Omron B3U-3000P 3.0 × 2.5 × 1.2 with a plunger reaching 0.1 mm past the wall's inner face; WS2812B-
2020 2 × 2 × 0.9; TDK T3902 3.5 × 2.65 × 0.98 on the bottom; FPC1 4 × 16 × 2.0; every other top- and bottom-side part
from `board_params.json` as a box; flex antenna 15 × 5 × 0.25; pigtail Ø0.9. All are axis-aligned boxes/cylinders —
good enough for clearance, not for the exact part outlines. The 8.5 mm head size is still marked unverified in
`docs/research/01-camera-modules.md`.
