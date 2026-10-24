# hardware/cad — stage-1 ring enclosure (CadQuery)

The only mechanical CAD in the project right now: a **printable stage-1 "signet" ring** generated from the
PCB floorplan numbers in `hardware/pcb/board_params.json`. It replaces the old OpenSCAD concept
(`hardware/enclosure/mcring_stage1.scad`, deleted).

| File | What |
|---|---|
| `mcring_stage1.py` | parametric model (band, bay + antenna cavity, ledges, snap lid with a pod lip, camera pod, cell + LRA pockets, LED window, mic port + tube, switch slot + key, charging-pad windows + wire grooves/channels, **optional speaker pocket** in the +Y wall with its grille, lead groove and lid tab) with placeholder solids, fit check, mass/envelope, exports |
| `fit_report.md` | generated: stack, speaker section, intersection volumes, clearances, wall probes, finger-contact scan, envelope, mass |
| `out/mcring_stage1_shell.stl` | **print file 1** — band + signet bay + camera pod + speaker bump (one part) |
| `out/mcring_stage1_lid.stl` | **print file 2** — rebated lid with detent beads, the mic tube and the speaker tab + boss |
| `out/mcring_stage1_key.stl` | **print file 3** — side-switch button (flange + pin + cap) |
| `out/mcring_stage1_assembly.step` | shell + lid + placeholders (PCB, module, camera head + folded FPC, cell, LRA, switch + key, LED, mic, FPC1, top/bottom parts, antenna, pigtail, speaker LS1) as one compound |
| `out/view_top.png/.svg`, `out/view_front.png/.svg`, `out/view_section.png/.svg` | sanity views: top, front along the camera axis, section through the camera axis (Y = 0) |
| `out/view_right.png/.svg`, `out/view_section_speaker.png/.svg` | speaker views (only with the speaker): the +Y side with the grille, section through the speaker axis (X = −5.2) |

## Regenerate

```bash
python3 hardware/cad/mcring_stage1.py                 # default inner_d 20.0, lens 4.6, speaker pocket (speaker_mm in the JSON)
python3 hardware/cad/mcring_stage1.py --inner-d 18.3  # US 8
python3 hardware/cad/mcring_stage1.py --lens-d 3.5    # HM01B0 lensed module instead of the OV2640 head
python3 hardware/cad/mcring_stage1.py --no-speaker    # ring without the speaker pocket / bump / lid tab (the pre-speaker shell)
python3 hardware/cad/mcring_stage1.py --no-step --no-views   # quick fit check only (~13 s)
python3 hardware/cad/mcring_stage1.py --out /tmp/x --report /tmp/x/fit.md   # a scratch build that leaves out/ and fit_report.md alone
```

Needs Python ≥ 3.10, `cadquery` (2.8 tested) and `cairosvg`. The script exits 1 if any placeholder intersects the
shell, the lid or another placeholder, if a clearance (head, FPC fold, antenna cavity, key travel, speaker ↔ antenna /
cell / lid boss) is below its minimum, or if a wall probe is below its minimum. Everything in `default_params()` is a
plain dict you can edit (band width, wall, clearances, pocket positions, lid rebate, pad angle, speaker grille ...);
the pod, antenna and speaker numbers are read from `board_params.json` (`pod_mm.floor_relief_above_skin /
head_clearance / fpc_fold_above_head`, `antenna_cavity_mm.depth_behind_board_edge`, `speaker_mm.diameter / thickness
/ centre_board_xyz_mm / pocket_clearance / grille_wall`) with the same defaults in the script.

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
4 × 5 × 0.4 (0.8 mm resin over the lid electrode); speaker pocket Ø10.4 × 3.2 deep (speaker Ø10 × 2.9 + 0.2 radial /
0.1 + 0.2 axial) in a 3.15 mm bump on the +Y wall, 5 × Ø1.0 grille holes through a 1.0 mm plate, 6 × 1.0 lead groove,
lid tab 1.2 thick + boss 0.2 above the speaker (see "Speaker" below).

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
| speaker pocket bottom (1.3 above the slab bottom at −3.0) | −1.70 |
| speaker axis (`speaker_mm`: 3.2 below the board top) / rim top | 3.50 / 8.50 |
| lid boss underside over the speaker / slot top = bump shelf | 8.70 / 9.90 |

0.4 mm taller than the floorplan's original 10.7: the 3.4 mm pocket (cell 3.0 + 0.4) sits on the 1.2 mm wall and the
0.35 mm cell-to-parts clearance of the floorplan stack is kept on top of it. The camera pod is 1.6 mm taller than the
lid: the head alone needs 8.5 + 2 × 0.3 between the pod floor (1.2 mm wall over the 0.5 mm bore relief) and the
ceiling, and the 24-pin flex needs ~1 mm above the head to fold back down behind it (see "Camera FPC" below).
`board_params.json` `stack_mm` / `pod_mm` carry these as-built numbers.

Envelope: band OD 22.4 (23.8 across the pad-wire rib), signet 31.5 × 21.0 — **24.15 wide across the speaker bump**
(X −11.6..1.2 on the +Y side only), 39.8 mm long along the finger including the pod and the antenna cavity, lid 11.1 /
pod roof 12.7 mm above the skin. Mass ≈ 7.1 g resin + 6.4 g parts ≈ **13.5 g** with the speaker (`fit_report.md`);
6.8 g + 5.4 g ≈ 12.2 g with `--no-speaker`.

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

## Speaker (optional, `speaker_mm`)

The optional on-ring speaker — a Ø10 × 2.9 mm 8 Ω micro speaker (PUI AS01008MR-2-R class, netlist LS1, driven by the
MAX98357A U10 through the SPK1a/SPK1b wire pads on the board's bottom) — stands **vertically in the signet's right
(+Y) wall**, the side away from the switch, grille facing +Y. `board_params.json` → `speaker_mm` is the source of the
numbers (the floorplan pass chose the place: the left wall is taken by the switch key and the pad-wire channels and
would put the magnet 0.7 mm from the antenna plane, the band wall has the finger behind it): centre board
(18.45, 20.0, −3.2 from the board top) = world X −5.2, Y +11.0, 3.5 mm above the skin; disc in the XZ plane.

* **Pocket**: a U-slot Ø10.4 (0.2 mm radial clearance) about the speaker axis, straight walls above the axis up to the
  lid underside, 3.2 mm deep along Y (0.1 behind the speaker's back face, 0.2 in front of it) — the speaker **drops in
  from the top** before the lid goes on. X −10.4..0, Y 9.45..12.65, bottom 1.3 mm above the slab bottom.
* **Bump**: the +Y wall grows 3.15 mm (12.8 mm long: pocket + two 1.2 mm end walls, X −11.6..1.2, full slab height,
  vertical corners r 1.0, bottom edge r 0.6). Its top is cut down to the lid underside (a shelf at 9.9 above the skin)
  and the 0.7 mm rebate rim is interrupted over that length. The signet is 24.15 wide there, asymmetric toward the
  adjacent finger on the +Y side — try it on; if it rubs, `--no-speaker` or move the pocket (`speaker_mm`).
* **Grille**: 5 × Ø1.0 holes (centre + 4 on a Ø5 ring at 45°) through the 1.0 mm +Y plate, 3.9 mm² open. The
  pattern is `spk_grille` in `default_params()` (hole Ø, ring radius, count); the plate thickness is
  `speaker_mm.grille_wall`. If the printed ring sounds muffled, open it up (more holes or three 0.8 × 6 slots) — the
  fit check only asks for ≥ 1.0 mm of plate between the holes.
* **Back volume**: above the sub-board floor (4.6) the slot's back is open to the bay over its full width, so the
  lidded bay (~1.4 cm³ minus parts, closed by the lid, the key and the epoxy-filled wire grooves) is the back volume —
  far larger than any sealed pocket this size could be. Below the floor the pocket is a recess in the solid slab with a
  **lead groove** 6 wide × 1.0 deep in its back wall (Y 8.45..9.45, from 1 mm above the pocket bottom up to the floor),
  so terminals in the lower half of the disc have room for the solder blobs and the leads. The sealed alternative in
  `speaker_mm.back_volume` (a 1.2 mm back wall with a wire slot + vents, bump 4.3) is not modelled.
* **Leads**: two 30 AWG wires soldered to the speaker's back terminals **before** it goes in; rotate the speaker so the
  terminals face the sub-board cavity (just above floor level, i.e. between 3 and 1 o'clock when seen from +Y) and the
  leads run straight −Y under the board's +Y edge (board edge at Y 9.0, wall at 9.3, cavity 4.6..6.1 above the skin)
  to SPK1a/SPK1b at board (18.8 / 20.8, 16.85) = 1.45 mm inside the board edge: ≈ 2–3 mm of wire, allow 6. Terminals
  lower down use the lead groove. Thread the leads before the board goes onto the ledges.
* **Lid**: a tab X −11.3..0.9 × Y 9.65..13.5 (1.2 thick, 0.15 inside the bump face, 0.3 from its end walls) rests on
  the shelf and closes the slot; a boss X −10.1..−0.3 × Y 9.75..12.35 under it fills the slot down to 0.2 mm above the
  speaker rim — the lid holds the speaker, a 0.5 mm foam pad on the boss or a drop of silicone takes up the play. The
  +Y detent groove only works over X 1.2..9.5 (8.3 mm) with the speaker; the −Y side is unchanged.
* **Fit check**: placeholder `speaker` (Ø10 × 2.9 disc) must not intersect the shell, the lid or any part; 3-D gap to
  the flex antenna ≥ 5.0 (5.45 as placed — the NdFeB magnet is "other metal" for the antenna rule), to the cell ≥ 2
  (3.55), to the LRA (4.49); probes: grille plate 1.0, slab under the pocket 1.3, end walls 1.2, bump bottom corner
  diagonal 1.35, slab between the pocket's back wall and the cell pocket 2.25 (through the lead groove) / 3.75 beside
  it, lid tab 1.2 / tab + boss 2.4; openness: grille centre hole, lead path to SPK1a/b, slot up to the lid, lead groove.

## Print settings

* SLA, white or translucent resin (the LED shines through the 1.2 mm lid; translucent lets the whole bay glow).
  0.05 mm layers. Print the shell in a tough resin, not a brittle standard one, if you want the detent and the switch
  counterbore wall to survive.
* **Shell**: bay opening up, finger axis horizontal. Supports under the camera pod, under the signet's overhangs
  (the flat shoulders beside the finger bore), under the speaker bump's underside and inside the bore if your printer
  needs them; keep the lid rebate, the pod-roof lip, the bay interior and the speaker slot support-free. In this
  orientation the speaker grille is a **vertical** 1.0 mm plate on the +Y side (the right wall, opposite the switch)
  with five horizontal Ø1.0 holes — they print clean in SLA, ream them with a 1.0 mm drill if resin closes them; the
  U-slot opens upward (no trapped resin) and the lead groove is a vertical slot that drains into the bay. The thinnest
  features: the 0.7 mm rebate rim, the 0.4 mm rim under the detent groove, the 0.7 mm wall around the switch
  counterbore, the first ~1.3 mm of each wire channel where it leaves the open groove at the slab's bottom corner, and
  the 1.0 mm grille plate. Everything else is ≥ 1.2 mm where the fit check probes it (it is a list of line probes, not
  a global thickness analysis).
* **Lid**: beads up, mic tube up, speaker tab flat and its boss up (the boss stands 1.2 mm below the plate like a
  short mic tube); light supports under the plate or print directly on the build plate and sand the elephant foot off
  the rebate faces and the boss (0.15 mm clearance in the rebate, 0.3 in the slot).
* **Key**: cap down on the build plate, no supports.
* FDM is possible (0.4 nozzle, 0.12 layers) but the Ø0.8 mic port, the 0.5 detent, the 0.7 rims, the Ø1.0 grille holes
  and the key will not come out; drill the ports and the grille and glue the lid.

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
7. **Speaker** (if fitted): the Ø10 × 2.9 disc drops into the U-slot in the +Y wall from the top with 0.2 mm all round
   and seats in the semicircle (its back face 0.1 mm off the pocket's back wall below the floor, its front 0.2 mm off
   the grille plate); the five grille holes are clear; the slot's back is open to the bay above the floor and the
   6 × 1.0 lead groove is open below it. Solder the two leads first, drop the speaker in with the terminals toward the
   bay (just above floor level), lead the wires under the board edge to SPK1a/b, then the board, then the lid — its
   boss should end 0.2 mm above the speaker rim (add a foam pad or a drop of silicone). The speaker's magnet is 5.45 mm
   from the antenna placeholder; keep the antenna glued where the model puts it. **Open item**: the PUI drawing
   (terminal position, max thickness 2.9 from a distributor listing, venting) sets the final pocket depth and whether
   the lead groove is needed.

## What the placeholders assume

OV2640 head 8.5 × 8.5 × 1.3 + Ø4.5 × 4.5 barrel with a 0.2 mm thick flex (8.5 wide neck, 12.5 wide contact end); ESP32-S3-
MINI-1U 15.4 × 15.4 × 2.4 with a 2.5 × 2.5 × 2.9 mated u.FL at the back-left; 301012 cell 3 × 10 × 12 (no PCM); INEED
LRA0825BC Ø8 × 2.5; Omron B3U-3000P 3.0 × 2.5 × 1.2 with a plunger reaching 0.1 mm past the wall's inner face; WS2812B-
2020 2 × 2 × 0.9; TDK T3902 3.5 × 2.65 × 0.98 on the bottom; FPC1 4 × 16 × 2.0; every other top- and bottom-side part
from `board_params.json` as a box; flex antenna 15 × 5 × 0.25; pigtail Ø0.9; speaker LS1 a plain Ø10 × 2.9 disc (no
terminal tabs, no port bump — PUI AS01008MR-2-R max outline). All are axis-aligned boxes/cylinders — good enough for
clearance, not for the exact part outlines. The 8.5 mm head size is still marked unverified in
`docs/research/01-camera-modules.md`.
