# 8. Mechanical CAD and 3D printing

The stage-1 enclosure is a program: `hardware/cad/mcring_stage1.py` (1 000 lines of CadQuery) reads `hardware/pcb/board_params.json`, builds a shell, a lid and a switch key, drops placeholder solids for every part into them, runs a fit check that refuses to export if anything intersects or a wall is too thin, and writes three STLs, a STEP assembly, five sanity views and `fit_report.md`. A ring size change is `--inner-d 18.3`; a camera change is `--lens-d 3.5`; dropping the speaker is `--no-speaker`. This chapter teaches enough solid modelling to read and change that file, enough tolerance thinking to trust its clearances, and enough resin-printing practice to turn `out/mcring_stage1_shell.stl` into a ring that closes. Read it next to `hardware/cad/README.md`, `fit_report.md` and `out/view_section.png`.

Every external resource in the "Learn it" tables is linked, and `docs/fundamentals/_links_making.json` records how each link was checked (a search result, or the project's own README, GitHub profile or package-registry metadata). Links marked *(root)* point at a home page and the "Why this one" column says where to go from there; rows marked *(this repo)* point at files in this repository.

## 8.1 Parametric solid modelling: B-rep, booleans, fillets, and CAD as code

**Why it matters in mcring.** Every shape in `mcring_stage1.py` is a box or a cylinder, moved, fused, cut or intersected: `build_shell()` fuses a band cylinder, a rounded slab, a pod block and two ribs, then *cuts* the bay, the lid rebate, the detent grooves, the cell and LRA pockets, the lens bore, the switch slot and the wire channels out of it. Parameters live in one dict (`default_params()`: `band_wall 1.2`, `bay_clear 0.3`, `lid_clear 0.15`, `cell_pocket (10.4, 12.4, 3.4)` …) and the board-derived numbers come from the JSON, so the enclosure regenerates when the floorplan moves a part. The repo deliberately replaced an OpenSCAD concept with CadQuery so the same model could export STEP for a viewer and run a geometric fit check (`hardware/enclosure/README.md`).

**The concepts.** A *solid* in a CAD kernel is a **boundary representation (B-rep)**: faces (surfaces with trimmed boundaries), edges and vertices, with topology that says which faces share which edges. **Booleans** combine solids — union/*fuse*, difference/*cut*, intersection/*intersect* — and are the whole vocabulary of this model; they are robust on simple analytic shapes (planes, cylinders, spheres) and fragile where faces are tangent or coincident, which is why the code offsets by 0.01 mm in places (`z_cut_top = z_top + lcl`, `box(..., self.z_lid_bot + 0.01)`) and wraps fillets in `try_fillet()` that keeps the sharp edge if the kernel refuses. A **fillet** rounds an edge with a given radius and can fail when the radius exceeds half the adjoining face's width; a **chamfer** bevels it. *Parametric* means the geometry is a function of named numbers and the history is re-executed on change — in a GUI CAD that history is a feature tree; here it is Python, so the "tree" is the order of statements and the parameters are a dict. **Code-CAD** (CadQuery, build123d, OpenSCAD) trades sketch-and-drag convenience for exact numbers, diffs, loops (`for sy in (+1, -1)` builds both detent grooves) and tests; it suits enclosures around a PCB whose coordinates already live in a JSON. File formats: **STEP** carries the B-rep (exact cylinders, editable in any CAD; the `assembly.step` here) and **STL** is a triangle mesh (what printers want; no dimensions, no faces, the 0.05 mm layer slicer re-slices it). Mesh resolution is a tolerance you set at export; a Ø4.6 bore exported coarsely becomes a polygon whose inscribed circle is smaller than 4.6. *Open CASCADE* (OCCT) is the kernel under CadQuery and FreeCAD; its error messages are what `try_fillet` catches.

**Learn it.**

| Resource | Type | Time | Why this one |
|---|---|---|---|
| [CadQuery documentation](https://cadquery.readthedocs.io/) *(root)* | docs | 2 h | *Quickstart* → *Concepts* (workplanes, stack, selectors, B-rep terms) → *Examples*; the mental model of this file |
| [CadQuery on GitHub](https://github.com/CadQuery/cadquery) | code | 20 min | The project home: install notes for the exact `cadquery` version `hardware/cad/README.md` pins (2.8), issue tracker for kernel quirks like refused fillets |
| [FreeCAD wiki: Workbenches](https://wiki.freecad.org/Workbenches) (*Part* and *Part Design*) | docs | 1–2 h | Same OCCT kernel as CadQuery with a GUI: if you have never used a feature-tree CAD, do *Getting started* and the *Part Design* pages first — sketches, pads, pockets, booleans and fillets in a GUI make the code version obvious; then open `out/mcring_stage1_assembly.step` in FreeCAD to inspect faces and measure |
| [OpenSCAD cheat sheet](https://openscad.org/cheatsheet/) | reference | 15 min | The code-CAD dialect the project left; one page shows how `union/difference/intersection` map onto `fuse/cut/intersect` |

**Check yourself.**

1. The band is `cyl_x(R + wall, −band_w/2, band_w/2, 0, 0)` and the bore is cut later as a cylinder of radius `R`. With `inner_d 20.0` and `band_wall 1.2`, what is the band's outer diameter, and why does the README quote 23.8 mm "across the pad-wire rib"?
2. `rbox()` fillets `edges("|Z")` with radius `r`. Which edges are those on a box, and what happens if `r` is larger than half the shorter footprint side?
3. Why does the lid cut extend to `z_top + lid_clear` rather than exactly `z_top`?
4. STL versus STEP: which one would you send to a machinist for a stage-2 aluminium shell, and why can a STEP of this model still be wrong for them?

<details><summary>Answers</summary>

1. OD = 20.0 + 2 × 1.2 = 22.4 mm. The two charging-pad wire ribs stand `pad_rib_h` = 0.7 mm proud of the band on the −Y side, so the envelope across them is 22.4 + 2 × 0.7 = 23.8 mm.
2. The four vertical edges (parallel to Z). A fillet whose radius exceeds half the side consumes the whole face; OCCT refuses and `try_fillet` prints "skipped" and leaves the box sharp — the slab's `slab_fillet` was reduced from 1.5 to 1.0 for the related reason that the wire channels needed the corner.
3. So the cutter passes clean through the top face: a boolean whose face is exactly coplanar with the solid's face leaves a zero-thickness skin or fails. The 0.15 mm overshoot is the same `lid_clear` value reused as a safe margin.
4. STEP: it carries exact faces, dimensions and tolerance-able features. It can still mislead because the model holds *printing* allowances (0.5 mm bore relief, 0.15 mm lid clearance, 0.2 mm pocket clearances) tuned for resin, not the fits a machined part needs.

</details>

## 8.2 Reading `mcring_stage1.py`: CadQuery idioms and the coordinate arithmetic

**Why it matters in mcring.** The file has two coordinate systems and a vertical stack you must be able to compute in your head. Board frame (`board_params.json`): `x` from the front/camera edge along the finger, `y` from the left/switch edge across it. World frame: `X` along the finger, **+X toward the fingertip**, `Y` across (switch side −Y), `Z` up with `Z = 0` on the finger axis and the skin at `Z = inner_d/2`. The two helpers `bx(x) = L/2 − x` and `by(y) = y − W/2` map one onto the other. The stack in `Model.__init__` is pure addition: `z_pocket_bot = R + band_wall`, `z_floor = z_pocket_bot + cell_pocket[2]`, `z_board_bot = z_floor + cell_clearance + bottom_max_height`, and so on up to `z_top`.

**The concepts.** CadQuery has two layers. The *fluent* `Workplane` API chains operations on a stack of objects: `cq.Workplane("XY").box(l, w, h, centered=(True, True, False)).edges("|Z").fillet(r).val()` makes a box with its base on the plane, selects its vertical edges with a **selector string** (`"|Z"` parallel to Z, `"<Z"` the lowest face/edges, `">Y"` the highest in Y), fillets them and returns the raw shape with `.val()`. The *direct* API builds shapes without a stack: `cq.Solid.makeBox(dx, dy, dz, origin)`, `cq.Solid.makeCylinder(r, h, origin, direction)`, then `.translate(cq.Vector(...))`, `.fuse()`, `.cut()`, `.intersect()`, `.clean()` (merges coplanar faces after booleans) and `.Volume()`, `.BoundingBox()`. This file uses the direct API almost everywhere because it is explicit about coordinates — `box(x0, x1, y0, y1, z0, z1)` and `cyl_x/cyl_y/cyl_z(r, a0, a1, …)` are one-line wrappers so every call reads as absolute millimetres. `u_slot_y()` shows the sketch route when a shape is not a primitive: a `Workplane("XZ")` polyline with a `threePointArc`, closed and `extrude(d/2, both=True)` to a prism, then translated. Mapping between the frames is the thing to practise: the module centre at board (18.8, 9.0) is world (26.5/2 − 18.8, 9.0 − 18.0/2) = (−5.55, 0); the camera FPC connector at board x = 2.5 is world X = +10.75 (toward the fingertip, correct — the camera is at the front); the switch at board y = 0 is Y = −9.0 (the −Y side). The stack with the defaults: 10.0 (skin) + 1.2 = 11.2 pocket floor; + 3.4 = 14.6 sub-board floor; + 0.35 + 1.15 = 16.1 board bottom; + 0.6 = 16.7 board top; + 2.9 + 0.3 = 19.9 lid underside; + 1.2 = 21.1 lid top — i.e. 11.1 mm above the skin, the number in every README. The pod repeats the trick from the bottom: floor = skin + 0.5 relief + 1.2 wall = 1.7 above the skin; head bottom at + 0.3; lens axis = head bottom + 8.5/2 = 6.25; ceiling = head top + 1.0 fold; roof = ceiling + 1.2 = 12.7. When the floorplan's JSON disagrees with the computed geometry the code *prints a NOTE* rather than silently trusting either — a pattern worth copying.

**Learn it.**

| Resource | Type | Time | Why this one |
|---|---|---|---|
| [CadQuery documentation](https://cadquery.readthedocs.io/) *(root)* | docs | 2 h | *API Reference* → `Workplane`, `Shape`/`Solid`, `Selectors` pages: every call in `mcring_stage1.py` is defined there (`edges("|Z")`, `makeCylinder`, `intersect`, `Volume`) |
| [CQ-editor on GitHub](https://github.com/CadQuery/CQ-editor) | tool | 30 min | A GUI that runs a CadQuery script and shows the result with a 3D view and object inspector; load the model and click faces to read coordinates |
| `hardware/cad/mcring_stage1.py` `Model.__init__` and `build_lid()` (this repo) | code | 1 h | Read these two with a calculator: the first is the z-stack, the second is a 40-line, fully commented example of fuse/cut on a real part |
| `hardware/pcb/board_params.json` + `hardware/pcb/README.md` "Coordinate convention" (this repo) | reference | 20 min | The source of every board-frame number and the sentence that defines `X = L/2 − x, Y = y − W/2` |
| [build123d documentation](https://build123d.readthedocs.io/en/latest/index.html) (the newer CadQuery-family library) | docs | 1 h | Same kernel, more explicit algebra of solids (`+`, `−`, `&`); reading its concepts page makes CadQuery's stack model less magical |
| Python 3 docs: [`argparse`](https://docs.python.org/3/library/argparse.html) and [`json`](https://docs.python.org/3/library/json.html) | docs | 30 min | The CLI (`--inner-d`, `--no-speaker`, `--report`) and the JSON reading are plain standard library; know them to add a parameter |

**Check yourself.**

1. Convert the speaker centre board (18.45, 20.0, −3.2 from the board top) to world coordinates with `inner_d 20.0` and check it against the README's "X −5.2, Y +11.0, Z 3.5 above the skin".
2. Which selector string would pick the *top* face of a box for a fillet, and which the edges parallel to X?
3. You change `cell_pocket` to (10.4, 12.4, 5.4) for a 5 mm 501012 cell. Recompute the lid top above the skin.
4. `u_slot_y()` extrudes a 2-D profile drawn on `Workplane("XZ")`. In which world axis does the extrusion go, and why is that the right axis for a speaker disc "standing in the XZ plane"?

<details><summary>Answers</summary>

1. X = 26.5/2 − 18.45 = −5.2; Y = 20.0 − 9.0 = +11.0; Z = z_board_top + (−3.2) = 16.7 − 3.2 = 13.5 world, i.e. 13.5 − 10.0 = 3.5 above the skin. All three match.
2. `faces(">Z")` for the top face; `edges("|X")` for edges parallel to X.
3. Pocket depth grows by 2.0 mm and everything above moves with it: 11.1 + 2.0 = 13.1 mm above the skin (`z_floor` is `z_pocket_bot + cell_pocket[2]`, the rest is unchanged).
4. The "XZ" workplane's normal is Y, so `extrude()` sweeps along ±Y — exactly the speaker's axis (grille normal +Y); `both=True` centres the prism on the plane and the final `translate` moves it to (y0 + y1)/2.

</details>

## 8.3 Tolerances, clearances and fits: what each 0.15, 0.2, 0.3 and 0.5 in the model is for

**Why it matters in mcring.** The model is a catalogue of allowances: board edge → bay wall **0.3 mm per side** (`bay_clear`), lid → rebate **0.15 mm** (`lid_clear`), cell → pocket **0.2 mm per side** (10.4 × 12.4 pocket for a 10 × 12 cell) plus 0.4 mm of depth slack, LRA Ø8 in a Ø8.4 pocket, OV2640 head **0.3 mm** to the pod floor and 0.35 to each wall, lens barrel Ø4.5 in a Ø4.6 bore (0.05 mm radial — "ream with a 4.5 mm drill shank"), speaker Ø10 in a Ø10.4 U-slot, the 0.5 mm `bore_relief` that lifts every overhang off the skin, the key's 0.3 mm travel. `fit_report.md` lists the as-built clearances against their minimums and `hardware/cad/README.md` carries the open items: "a 301012 *with PCM* is longer than 12 mm at the tab end — model the pocket from the cell drawing before the final print".

**The concepts.** A *nominal* dimension is what you draw; a *tolerance* is how far the real part may deviate; *clearance* is the designed gap between two nominals so that, with both parts at their worst tolerances, they still fit (and, for a slide or a snap, still function). Three kinds of fit: **clearance** (always a gap — the board in the bay, the cell in the pocket), **transition** (may touch — the lid in its rebate at 0.15 mm, the lens barrel in a reamed bore), **interference** (always presses — nothing here, because resin cracks; glue does that job). A resin printer's accuracy is typically ±0.1 to ±0.2 mm on a part this size plus a systematic error (over-cure widens positives and shrinks holes; "elephant foot" flares the first layers against the build plate), so a 0.15 mm clearance is at the edge of what you can rely on and the README says to *sand the elephant foot off the rebate faces*; 0.2–0.3 mm is a comfortable drop-in fit; 0.5 mm is "never touches". *Stack-up*: tolerances add. Worst case, the board (±0.1 on a 26.5 mm outline from the fab) in a bay printed ±0.15 leaves 0.3 − 0.1 − 0.15 = 0.05 mm per side — still positive, so the board drops in; statistically (root-sum-square: √(0.1² + 0.15²) ≈ 0.18) it almost always has 0.1 mm or more. Depth stacks matter as much as widths: the sub-board floor must stay 0.35 mm under the bottom parts (`cell_clearance`), and a 1.15 mm part on a 0.6 mm board on ledges printed 0.1 mm high eats a third of that. *Holes shrink*: a printed Ø4.6 comes out ≈ 4.4–4.5 because resin cures slightly past the laser's edge and small holes trap uncured resin; print oversize and finish with a drill shank or reamer to the fit you want (4.5 mm for a snug barrel) — the same logic as the 0.8 mm mic hole and 0.9 mm wire channels "passed with a drill". *Datums*: dimension from the surfaces that actually locate the part — here the finger axis (`Z = 0`) and the board ledges — not from arbitrary edges, so a size change moves everything consistently.

**Learn it.**

| Resource | Type | Time | Why this one |
|---|---|---|---|
| [Formlabs](https://formlabs.com/) *(root)* | docs | 1.5 h | Support → *Design specs for 3D models* (minimum clearances, hole and wall sizes per resin), the blog's *Engineering fit* article (clearance / transition / interference with the numbers SLA actually holds) and the tolerance white papers; the printer-side half of every number in `default_params()` |
| `hardware/cad/fit_report.md` (this repo) | report | 20 min | Read the "Clearances" table once: each row is a nominal minus a minimum, and the names tell you what would collide first |
| `hardware/cad/README.md`, the clearance notes and open items (this repo) | reference | 20 min | Where each 0.15 / 0.2 / 0.3 / 0.5 came from, which were measured on a print and which are still guesses ("model the pocket from the cell drawing before the final print") — and the instruction to measure your own printer's offset on a test coupon before trusting 0.15 mm |

**Check yourself.**

1. The lid is `Li_tot + 2·rebate − 2·clearance` long. With a 0.15 mm clearance and a printer that over-sizes positives by 0.1 mm and under-sizes cavities by 0.1 mm, how much room is left on each side, and what does the README tell you to do about it?
2. A 301012 cell with a PCM measures 10.0 × 13.2 × 3.1 mm. Which pocket numbers change, and does the board still clear it?
3. Why print the lens bore at Ø4.6 and ream to 4.5 instead of printing 4.5?
4. Worst-case versus RSS: the bay has 0.3 mm per side; board outline ±0.1, printed cavity ±0.15, resin shrinkage −0.05 systematic. Compute both.

<details><summary>Answers</summary>

1. 0.15 − 0.1 − 0.1 = −0.05 mm: the lid would not go in. Hence "sand the elephant foot off the rebate faces, 0.15 mm is all the clearance there is", and the alternative is measuring your printer's offset on a test coupon and raising `lid_clear` to 0.2–0.25.
2. Pocket across (Y) from 12.4 to 13.6 (0.2 per side); depth from 3.4 to 3.5 (3.1 + 0.4 slack), which lifts the whole stack by 0.1 mm — the fit check still passes if the pocket fits inside the slab's `head_drop` region, which is the check to run. The lead channel (3 × 0.8) must also be re-positioned for the PCM's tabs.
3. Printed holes come out small and slightly non-round, and the layer surface is rough; a drill shank turned by hand in a 4.6 hole removes 0.05 mm of skin and leaves a round, smooth 4.5 — a transition fit you cannot print directly.
4. Worst case: 0.3 − 0.1 − 0.15 − 0.05 = 0.0 mm (just fits). RSS of the random terms √(0.1² + 0.15²) = 0.18, minus the systematic 0.05: 0.3 − 0.05 − 0.18 = 0.07 mm typical margin per side. Comfortable only after you have measured the systematic term.

</details>

## 8.4 Walls, holes and orientation: designing for SLA (and what FDM cannot do)

**Why it matters in mcring.** The wall rule is 1.2 mm (`band_wall`, `bay_wall`, `lid_t`, pod wall), and the fit check *probes* it with line samples at ~25 named places (floor under the cell pocket, band wall at 100°, bay long wall rim at the lid groove, pod side wall at lens height …). The README lists the deliberately thinner features: the 0.7 mm rebate rim and the 0.4 mm rim under the detent groove, the 0.7 mm wall around the switch counterbore, the first ~1.3 mm of each wire channel, 0.8 mm of resin over the touch electrode, the 1.0 mm grille plate with five Ø1.0 holes; and the smallest openings: Ø0.8 mic port in a Ø1.8 tube, Ø0.5 detent beads, Ø0.9 wire channels, 0.5 mm counterbore depth. Print orientation is prescribed (shell: bay up, finger axis horizontal; lid: beads up, tube up; key: cap down) and FDM is allowed for the shell only, "drill the ports and the grille, glue the lid; the key will not print".

**The concepts.** *SLA/MSLA* cures a photopolymer layer by layer (0.05 mm here) with a laser or an LCD; resolution is tens of microns in XY, so Ø0.8 holes and 0.5 mm beads are printable, but three physics limits set the rules. **Minimum wall**: below ~1 mm an unsupported resin wall warps during printing and cracks in post-cure; 1.2 mm is a safe general wall for a tough resin, 0.7 mm only for short, supported features (the counterbore wall, the rebate rim), 0.4 mm only as a rim that is backed by something (the detent groove's rim sits on the wall). **Small holes close**: uncured resin is viscous and light scatters, so holes under ~1 mm print undersize or skinned over — print them anyway and clear with a drill (0.8, 0.9, 1.0 mm). **Cups and suction**: a closed cavity facing the build plate traps resin and air (a "cup"), and the peel force of each layer can tear a thin wall; the bay opening *up* and the U-slot opening upward drain by design, and the lead groove is "a vertical slot that drains into the bay". **Supports** touch the part and leave nubs, so they go where a mark does not matter (under the pod, under the signet shoulders, under the speaker bump) and never on the rebate, the pod lip or inside the bay; the lid can print flat on the plate instead, at the cost of the elephant foot. **Orientation** also sets which surfaces are smooth (facing up or down) and which show layer lines (vertical), and which thin features are self-supporting: the grille is a *vertical* 1.0 mm plate with horizontal Ø1.0 holes in the prescribed orientation, which SLA handles. *FDM* lays a 0.4 mm nozzle's bead in 0.12–0.2 mm layers: nothing thinner than ~0.8 mm (two beads) is solid, holes under ~1.5 mm are ragged, a Ø0.5 bead or a 0.3 mm key standoff cannot exist, overhangs beyond ~45° droop — so the shell prints, the details do not. *Material*: a standard SLA resin is brittle (the detent rim snaps on the second opening); a *tough* or *durable* resin (ABS-like elongation) survives the click; translucent lets the LED glow through 1.2 mm; white diffuses it into a soft dot. Over-curing yellows and embrittles both.

**Learn it.**

| Resource | Type | Time | Why this one |
|---|---|---|---|
| [Formlabs](https://formlabs.com/) *(root)* | docs | 1.5 h | Support articles *Design specs for 3D models* (walls, holes, embossed detail, drain holes), *Orientation* and *Supports*; the clearest SLA design rules with numbers |
| [Teaching Tech: 3D printer calibration](https://teachingtechyt.github.io/calibration.html) (FDM) | interactive | 30 min | If you do print the shell on FDM: browser-based dimensional, flow and retraction calibration generators, so a 1.2 mm wall is 1.2 mm and a Ø1.0 hole is round |
| `hardware/cad/mcring_stage1.py` `fit_check()` probes (this repo) | code | 30 min | The list of line probes *is* the wall-thickness design review; read the names and minimums to see which walls were judged critical |

**Check yourself.**

1. The grille plate is 1.0 mm with five Ø1.0 holes on a Ø5 ring (plus the centre). What minimum plate is left between neighbouring ring holes, and how does the fit check know?
2. Why is the shell printed with the bay opening up although that puts supports under the camera pod?
3. The mic tube is Ø1.8 OD with a Ø0.8 bore, 3.2 mm long, hanging under the lid. Is its 0.5 mm wall acceptable, and what makes it so?
4. Explain why the key "will not print" on FDM but the shell will, in two sentences with numbers.

<details><summary>Answers</summary>

1. Chord between adjacent holes on a Ø5 ring (90° apart): 2 × 2.5 × sin 45° = 3.54 mm centre-to-centre, minus 1.0 mm of hole = 2.54 mm of plate; centre hole to a ring hole: 2.5 − 1.0 = 1.5 mm. The check is the probe "grille plate 1.0" plus the rule "≥ 1.0 mm of plate between the holes" the README quotes.
2. Cavities must face up to drain and avoid suction; the bay, the U-slot and the lead groove all open upward in that orientation, and the rebate, lid lip and bay interior stay support-free. The pod's underside is an outside surface where support nubs can be sanded.
3. Yes: it is short, round (a tube is stiff for its wall), printed vertically (tube up) and bonded to the lid along its full top edge; the 1.2 mm rule is for free walls under load. The bore will still need the 0.8 mm drill.
4. FDM lays 0.4 mm beads: the key's 0.33 mm flange, 0.3 mm standoff and 3.2 × 1.4 pin are below or at one bead, and the Ø0.5 beads and Ø0.8 port vanish. The shell's walls (1.2 mm = three beads) and pockets (≥ 3 mm) are inside FDM's range, so it prints with the small holes drilled afterwards.

</details>

## 8.5 Lids, detents, snaps and printed buttons

**Why it matters in mcring.** The lid sits in a 0.5 mm rebate with 0.15 mm clearance, its front edge slides under the pod roof's 1.0 mm **lip**, and two Ø0.5 **detent beads** along its long edges click into grooves (r = bead + 0.05) with "only 0.1 mm of engagement — a light locating click; a drop of glue or tape is the real retention". The **key** is a flange (4.4 × 2.6 × 0.33) that sits in a 4.6 × 2.8 × 0.5 counterbore inside the wall, a 3.2 × 1.4 pin through the 3.4 × 1.6 slot, and a 4.4 × 2.6 × 0.6 cap standing 0.3 mm off the wall — the travel — "the flange keeps the key from falling out, the cap from falling in; the plunger touches the flange's inner face". With the speaker the lid also grows a tab and a boss that hold the driver down with 0.2 mm of play for a foam pad (`build_lid()`).

**The concepts.** A *detent* locates; a *snap* retains. Both work by elastic deflection of a feature that returns to shape. For a **cantilever snap** of length L, thickness t and deflection y, the maximum strain is ε ≈ 1.5·y·t/L² (rectangular section); a tough resin tolerates ~2–5 % strain repeatedly, a standard resin under 1 %. Here nothing is a cantilever: the lid plate itself bows a little so its beads can ride over the groove edges — with a 0.1 mm engagement over a ~17 mm wide plate the strain is tiny and the click is weak, which is why glue is the retention and the detent is a *locator*. A **rebate** (step) does three jobs: it sets the lid flush, it hides the gap from the side, and it gives a face for silicone sealing (`docs/07` §2.7 "a thin bead of neutral-cure silicone on the rebate faces"); a **lip** over one edge replaces a second snap and defines the sequence (front edge in first, then press the back). Design rules for printed moving parts: give every sliding pair ≥ 0.2 mm, round the edges that must ride over something, make the flexing member long and thin rather than short and thick (strain falls with L²), and keep features that must align within one print (the lid's beads and the shell's grooves are generated from the same parameters, so they move together when `lid_t` changes). A **printed button** needs three things the key has: a captured flange so it cannot fall out of the device, a cap that cannot pass through the slot, and a travel set by a standoff equal to the switch's actuation distance (the B3U-3000P's plunger needs ~0.3 mm); fit it from the inside before the board closes the wall. *Sealing* against hand-washing is a separate problem from retention: the mic port, LED and touch dimple are in the lid for a reason (one gasket plane), the wire grooves are filled with resin, and anything that must move (the LRA, the switch) is never potted.

**Learn it.**

| Resource | Type | Time | Why this one |
|---|---|---|---|
| [Formlabs](https://formlabs.com/) *(root)* | docs | 45 min | Blog → *How to design snap-fit joints for 3D printing* and *Design for assembly*: cantilever length / thickness / deflection numbers for printed parts, the ε ≈ 1.5·y·t/L² rule in practice, and which resins survive repeated clicks |
| Omron B3U-3000P datasheet, via the DigiKey product page linked in `hardware/bom/stage1-ring.csv` (this repo) | datasheet | 15 min | Actuation force and travel, plunger protrusion and the recommended actuator — the numbers `switch_slot`, `standoff` and the counterbore encode |
| `hardware/cad/mcring_stage1.py` `build_key()` and the lid detent lines of `build_lid()` (this repo) | code | 30 min | Thirty lines each; change `bead_r` or `standoff`, regenerate, and watch the fit check's "key cap stand-off" and "rim at the lid groove" rows react |

**Check yourself.**

1. The detent groove radius is `bead_r + 0.05` and the bead engages 0.1 mm. If you raise `bead_r` to 0.4 for a firmer click, which probe in `fit_check()` is the first to fail and why?
2. Treat one long edge of the lid as a cantilever 8.5 mm long (half the width) and 1.2 mm thick that must deflect 0.1 mm to pass the groove edge. Estimate the strain and say whether a standard resin survives it.
3. The key's cap stands 0.3 mm off the signet side. What happens to the switch if that standoff prints at 0.1 mm, and at 0.6 mm?
4. Why does the front of the lid use a lip and not a third bead?

<details><summary>Answers</summary>

1. "bay long wall rim at the lid groove" (minimum 0.35): the 0.5 mm rebate leaves a 0.7 mm rim of the 1.2 mm wall, and the groove (radius `bead_r` + 0.05) is cut into that rim's inner face. Today 0.7 − 0.30 = 0.40 mm remains (the README's "0.4 mm rim under the detent groove"); with `bead_r` = 0.4 the groove radius is 0.45 and only 0.25 mm of rim is left — below the 0.35 minimum, so the build exits 1 before writing STLs.
2. ε ≈ 1.5 × 0.1 × 1.2 / 8.5² ≈ 0.0025 = 0.25 %. Even a brittle standard resin tolerates that once; the README's warning about the detent is about the thin *rim* chipping, not the lid plate.
3. At 0.1 mm the key bottoms on the wall before the switch's full travel — a dead or mushy button. At 0.6 mm the cap protrudes 1.2 mm, snags on things and the plunger is pressed only after 0.6 mm of free play; the switch still works but feels loose.
4. The pod roof is already there above the lid's front edge; a lip is a zero-cost, strong retention that also closes the pod slot against light and dust, and it fixes the assembly order (front in first). A third bead would need a groove in the pod wall, the thinnest-walled region.

</details>

## 8.6 Fit checks: in the model and on the bench

**Why it matters in mcring.** `fit_check()` is the reason the model is code. It builds axis-aligned placeholders for the PCB, module, camera head and folded FPC, cell, LRA, switch and key, LED, mic, FPC connector, bottom and top parts, antenna, pigtail and speaker, then asserts that every placeholder-vs-shell, placeholder-vs-lid and placeholder-vs-placeholder `intersect().Volume()` is 0, that a list of named clearances (head to floor 0.3, FPC fold 1.0, u.FL plug to lid 0.3, speaker to antenna 5.0 …) meets its minimum, that each wall **probe** — the volume of a thin cylinder along a line through the shell divided by πr² — is at least the required thickness, and that the finger-contact scan shows the bore touching only where the band is. `main()` exits 1 on any failure and the STLs are not written. `fit_report.md` is the human-readable copy; `hardware/cad/README.md` "After printing — check" is the bench version of the same list.

**The concepts.** A fit check is a set of *invariants* on the geometry, run automatically, so that a parameter change (ring size, a taller part, a deeper pocket) cannot silently break the assembly. Three kinds are cheap in a B-rep kernel. **Intersection volume**: `A.intersect(B).Volume()` is zero when solids do not overlap; it catches a part that pokes through a wall or two parts that collide, and it is exact, not visual. **Clearance**: bounding boxes or face positions give the gap between two features (`cam.zmin − pod_z_floor`); compare with the minimum you chose in 8.3. **Material probes**: there is no cheap "minimum wall thickness everywhere" query, so the model samples the thickness along chosen lines — the line's intersection with the shell is a cylinder whose volume/area is the thickness crossed. Its limit is honesty: "a list of line probes, not a global thickness analysis", so the list must be curated where walls are thin (the README's known-thin spots). *Placeholders* are boxes and cylinders — good for clearance, wrong for exact outlines (the OV2640 head "is still marked unverified"), so the second half of the check is physical. On the bench: calipers on the printed bay length and width versus the model (26.5 + 0.6 = 27.1 nominal interior), a pin gauge or drill shank in the bore, the bare board dropped onto the ledges (0.3 mm play per side, board top 0.6 above the ledge), the cell and LRA in their pockets (0.2 mm per side, LRA 0.2 below floor level), the camera head slid in from the bay until the barrel sits 0.4 mm into the bore, the lid slid under the lip and pressed down, the key's travel felt. *Test coupons*: before the whole shell, print only the lid-and-rebate corner or the key-and-slot wall — a 10-minute print that measures your printer's offsets for `lid_clear` and `switch_slot`. *Close the loop*: a measured deviation becomes a parameter change and a regenerated model, never a sanded part you cannot reproduce.

**Learn it.**

| Resource | Type | Time | Why this one |
|---|---|---|---|
| [CadQuery documentation](https://cadquery.readthedocs.io/) *(root)* | docs | 45 min | *Assemblies* and the `Shape` API (`intersect`, `Volume`, `BoundingBox`) — the primitives the fit check is built from; assemblies also give constraint-based placement if the placeholders ever need it |
| `hardware/cad/mcring_stage1.py` `fit_check()`, `probe()`, `contact_scan()` (this repo) | code | 45 min | 150 lines that implement everything above; add one probe for a wall you worry about and watch it appear in `fit_report.md` |
| [DigiKey Maker: Oura Ring Teardown (Gen 3 and 2)](https://www.digikey.com/en/maker/projects/oura-ring-teardown-gen-3-and-2/2c005e01f82d429398e78f49591793cc) | article | 30 min | A production ring opened up: how little clearance a potted rigid-flex needs, and what stage 2 will have to fit-check instead of a bay and a lid |

**Check yourself.**

1. `probe()` returns `intersect(c).Volume() / (π r²)` for a thin cylinder along the probe line. Why divide by the area, and what does the result mean if the line crosses two walls with a gap between them?
2. The "u.FL plug top → lid underside" clearance must be ≥ 0.3. Compute it from the stack with the 2.9 mm mated plug.
3. The contact scan steps along X at Z just below the skin and records where the shell touches. Which parameters decide its result, and what should it show?
4. Your first print measures the bay 27.0 mm long inside instead of 27.1. Which parameter do you change, by how much, and what else moves when you do?

<details><summary>Answers</summary>

1. The intersection is a cylinder segment per wall crossed, so volume/area is the *total* material length along the line, not the thickness of either wall. A probe across two walls reports their sum; the probes are therefore placed to cross one wall each.
2. Board top 6.7 + 2.9 = 9.6 above the skin; lid underside 9.9; clearance 0.3 — exactly the `lid_clearance` in `stack_mm`, which is why the row exists: a taller plug or thicker board fails it first.
3. `inner_d`, `band_w`, `bore_relief` and the chamfer cones: the scan should find contact only over X −8.0 .. +5.5 (the band plus the 2 mm of cell-pocket floor) and none under the signet or the pod, where the bore is opened by 0.5 mm.
4. The cavity under-sized by 0.1 mm total means ~0.05 per side of resin growth: raise `bay_clear` from 0.3 to 0.35. The lid, rebate, pod position and signet outline all follow (`Li`, `Lo`, lid length derive from it), the signet grows 0.1 mm each way, and the fit check re-validates the wall probes.

</details>

## 8.7 Printing resin and post-processing

**Why it matters in mcring.** `docs/07` §2.5 and the CAD README agree on the recipe: SLA, white or translucent **tough** resin, 0.05 mm layers; wash 2 × 5 min in IPA (the second bath clean), dry, **remove supports before curing**, cure 10–15 min and not longer (over-curing yellows the resin and dims the LED through the lid); ream the lens bore with a 4.5 mm drill shank, clear the Ø0.8 mic hole down through the tube, pass a 0.9 mm drill through the wire channels, open the 3 × 3 pad windows, sand the elephant foot off the lid's rebate faces and the speaker boss, then fill the wire grooves with resin only after the wires are in.

**The concepts.** A resin print comes off the plate wet with uncured resin and mechanically green (partly cured, soft). **Washing** dissolves the surface resin in isopropyl alcohol (≥ 90 %) — two baths because the first becomes resin-laden and leaves a film; small holes and the bay corners need agitation or a syringe of clean IPA, and a part soaked too long swells and loses dimension. **Drying** fully before curing, or trapped IPA leaves a white haze and micro-cracks. **Support removal while green** leaves smaller nubs and avoids cracking the hardened part; flush cutters, then a sanding stick on the nub sites (pod underside, signet shoulders), never on the rebate or bore. **Post-cure** under UV (405 nm) finishes the polymerisation: strength and stiffness rise over the first 10–15 minutes, then the resin keeps absorbing UV and turns yellow and brittle — "not longer" is a mechanical as well as an optical instruction, and a translucent lid cured too long stops glowing. **Finishing**: the elephant foot is a 0.1–0.2 mm flare on the first layers; a few passes of 400-grit on the rebate faces restore the 0.15 mm clearance. Holes: print small, finish with a drill *shank* turned by hand (a drill's cutting edges chip resin) or a reamer for the bore; a 0.8 mm drill in a pin vice for the mic port; chase threads never — resin threads strip, use heat-set inserts or glue. **Resin choice**: "tough"/"durable" resins (higher elongation, lower modulus) survive the detent click and the switch counterbore wall; "standard" resins chip; translucent or white decides how the LED reads through 1.2 mm. **Safety**: liquid resin is a skin sensitiser and an irritant — nitrile gloves, eye protection, ventilation, cover the work surface; cured resin is inert; IPA is flammable and should not be run through an ultrasonic cleaner without a cooling check; uncured resin and dirty IPA are cured in sunlight before disposal, not poured away. **Hollowing** does not apply to a part this small, but the same logic (trapped resin) is why the bay opens upward.

**Learn it.**

| Resource | Type | Time | Why this one |
|---|---|---|---|
| [Formlabs](https://formlabs.com/) *(root)* | docs | 1.5 h | Support → *Washing*, *Post-curing* (times and temperatures per resin), *Removing supports* and *Resin safety*; Materials → the *Tough* and *Durable* resin pages (elongation, modulus, recommended post-cure — compare with a standard resin's numbers); the procedure `docs/07` §2.5 condenses |
| `docs/07-build-guide.md` §2.5 "Enclosure print and post-processing" (this repo) | procedure | 20 min | The project's wash / dry / de-support / cure recipe with its times, and the reaming and drilling steps for every small feature, in build order |
| `hardware/cad/README.md` "Print settings" and "After printing — check" (this repo) | procedure | 15 min | The project's own print and finishing checklist, feature by feature (0.7 mm rims, Ø0.8 port, 4.6 bore, grille holes) |

**Check yourself.**

1. The lid came out of the cure cycle yellow and the LED is barely visible through it. Which step went wrong and what does it imply for the lid's mechanical behaviour?
2. Why remove supports *before* the post-cure, and which two surfaces of the shell must never carry a support?
3. A 4.6 mm bore measures 4.42 mm after cure. Describe the finishing step and the fit you are aiming for with the 4.5 mm barrel.
4. The wire grooves on the −Y rib are filled with resin "only after the wires are in" and the filled grooves "face the palm". What does the fill do, and why cure it in place rather than print a closed channel?

<details><summary>Answers</summary>

1. Over-curing (longer than 10–15 min, or a hot cure). The same over-exposure that yellows the resin embrittles it: expect the Ø0.5 beads and the 0.4 mm rim under the groove to chip at the first click.
2. Green resin is soft, so supports snap off cleanly with small nubs and without cracking the part; after curing they are hard and tear chunks out. Never on the lid rebate faces (the 0.15 mm fit) or the pod-roof lip (it must be smooth for the lid to slide under).
3. Turn a 4.5 mm drill *shank* (or a 4.5 reamer) by hand through the bore, removing ~0.04 mm of radius of cured skin until the shank passes with light friction: a transition fit that holds the barrel centred without stressing the resin.
4. It locks and strain-relieves the two 30 AWG wires, closes the groove flush so the palm feels a smooth band, and seals the channel entrances. A closed Ø0.9 tunnel 10+ mm long would neither drain nor thread (the README: "an enclosed tunnel this size would not print clean or thread").

</details>

## 8.8 Ring sizing and ergonomics

**Why it matters in mcring.** `inner_d` is the single parameter a wearer cares about: the README's table maps US sizes to it (7 → 17.5, 8 → 18.3, 9 → 19.1, **10 → 20.0 (default)**, 11 → 20.8, 12 → 21.6; finger Ø + 0.2 mm comfort), the band is 12 mm wide, the bore touches the finger only over the band plus 2 mm (X −8.0 .. +5.5) and is opened 0.5 mm elsewhere, and the shell is 39.8 mm long including the pod and antenna cavity — "worn with the band against the knuckle the pod front sits ~17 mm toward the PIP joint — try it on a hand before printing in volume". Mass ≈ 13.5 g with the speaker, 12.2 g without; the signet is 11.1 mm tall, the pod 12.7. Stage 2 targets an 8 mm band ≤ 3 mm thick with a 4–5 mm camera pod (`docs/03` §3.4).

**The concepts.** Ring sizes are inner *circumference* systems in disguise: the US scale is linear in diameter, ID(mm) ≈ 0.8128 × size + 11.63 (size 10 → 19.76 mm, size 8 → 18.13 — the table's 19.8 and 18.1), each full size being 0.81 mm of diameter or 2.55 mm of circumference; the ISO/European scale simply *is* the circumference in millimetres (a US 10 ≈ EU 62). Fingers are not round (oval, wider than tall), swell by a size or more with heat, exercise and time of day, and have a knuckle larger than the base, so a ring must pass the knuckle (size up) yet not spin at the base (size down) — the 0.2 mm comfort allowance is a compromise and a wide band (12 mm here, versus 7–8 mm for Oura-class rings) needs ~half a size more because it contacts more skin. *Where the ring sits* decides what the camera sees: a signet on the index finger's proximal phalanx points along the finger; the pod must clear the PIP joint when the finger bends, which is the 17 mm concern — a 39.8 mm shell on a ~45 mm proximal phalanx leaves little. *Comfort rules* from jewellery and wearables: inner edges chamfered or rounded (the 0.5 mm chamfer cones joining the two bore radii), no edges across the finger, mass under ~10 g preferred for all-day wear (commercial smart rings are 3–6 g; this prototype's 13.5 g is a bench number), and the thick side (the signet) on top of the hand where it does not press into the neighbouring finger — hence the speaker bump's asymmetry warning ("if it rubs, `--no-speaker` or move the pocket"). *Measuring*: a strip of paper around the base of the finger at the end of a warm day, read as circumference, divided by π for the diameter; or a set of plastic sizer rings; print the band alone (`--no-step --no-views` for a 13 s fit check and a 20-minute print) in two neighbouring sizes before committing the full shell. *Anthropometry* exists for this: published hand dimension tables give finger circumference percentiles by sex and population, so a two-size run (US 8 and 10, say) covers most adults.

**Learn it.**

| Resource | Type | Time | Why this one |
|---|---|---|---|
| [DigiKey Maker: Oura Ring Teardown (Gen 3 and 2)](https://www.digikey.com/en/maker/projects/oura-ring-teardown-gen-3-and-2/2c005e01f82d429398e78f49591793cc) | article | 30 min | What a shipping ring's band width, thickness and mass are, and how the electronics curve to follow the finger — the stage-2 target in pictures |
| [Grepow: smart ring batteries (curved cells)](https://www.grepow.com/wearables/smart-ring.html) | vendor | 15 min | The dimensions of the curved cells that set an 8 mm × ≤ 3 mm band at stage 2 |
| [Memfault Interrupt: Smart Ring Development (Part 2) — Hardware Design](https://interrupt.memfault.com/blog/smart-ring-development-part-2) | article | 30 min | Sizing, flex-circuit wrap and potting of a ring from a team that built one |

**Check yourself.**

1. A finger measures 62 mm around at the base. What US size and `inner_d` would you print, and what does the 12 mm band change?
2. Compute the ring's bore circumference at `inner_d 20.0` and the length of a 31 mm wire antenna laid along the band as a fraction of it.
3. The proximal phalanx of an index finger is ~45 mm long on an average adult hand. With the band 12 mm wide centred at X = 0 and the pod front at X ≈ +23 (bay half-length 13.55 + 8.3 interior + 1.2 wall), how far is the pod front from the knuckle when the band's back face rests against it, how much phalanx is left before the PIP joint, and what two design changes does the README offer?
4. Mass: the shell is ≈ 6.8 g of resin without the speaker at 1.15 g/cm³. What resin volume is that, and what would the same shell weigh in PA12 nylon (≈ 1.01 g/cm³) or aluminium (2.7 g/cm³)?

<details><summary>Answers</summary>

1. 62 / π = 19.7 mm → US 10 (19.76) → `inner_d 20.0` with the 0.2 comfort. A 12 mm band grips more skin, so if the finger is close to the knuckle size go to 20.8 (US 11) and test both.
2. π × 20.0 = 62.8 mm; 31 / 62.8 ≈ half the circumference — the monopole lies along one side of the band, well clear of the cell pocket on the other.
3. The band spans X −6 .. +6, so the pod front at +23 is 17 mm beyond the band's front face — the README's "~17 mm toward the PIP joint". With the band's back face (X = −6) against the knuckle the pod front is 29 mm from it, leaving 45 − 29 ≈ 16 mm of phalanx before the PIP, less on a smaller hand. Options offered: a shorter board, or a pod that points sideways.
4. 6.8 / 1.15 ≈ 5.9 cm³. PA12: 5.9 × 1.01 ≈ 6.0 g; aluminium: 5.9 × 2.7 ≈ 16 g (before any wall-thickness reduction a metal would allow).

</details>
