#!/usr/bin/env python3
"""mcring stage-1 ring enclosure — parametric CadQuery model.

Reads  hardware/pcb/board_params.json  (board size, part positions, stack, pod, antenna cavity) and builds
  * the printable SHELL  (band + signet bay + camera pod, one SLA part)
  * the printable LID    (rebated plate with a detent bead, Ø0.8 mic port + tube, LED window, touch dimple)
  * the printable KEY    (side-switch button: flange + pin + cap)
  * PLACEHOLDER solids   (PCB, ESP32-S3-MINI-1U, OV2640 head + barrel + folded FPC, cell, LRA, switch, LED,
                          mic, FPC1, bottom-side parts, flex antenna + u.FL pigtail)
then runs a programmatic fit check (pairwise intersections must be 0, clearances, wall probes, finger-contact
scan), prints the envelope and a mass estimate, writes fit_report.md and exports STL / STEP / SVG+PNG views.

World frame (mm):  X along the finger, +X toward the fingertip (camera / front);
                   Y across the finger, +Y = board +y (switch edge is -Y);
                   Z up (top of the hand), Z = 0 on the finger axis.  Skin top at Z = inner_d/2.
Board frame (board_params.json): bx from the front edge (0) to the back (L); by from the left (switch) edge.
    X = L/2 - bx,  Y = by - W/2   (board centred on the ring axis along the finger).

Run:  python3 hardware/cad/mcring_stage1.py [--inner-d 20.0] [--lens-d 4.6] [--no-views] [--no-step]
"""
import argparse
import json
import math
import os
import sys
import time

import cadquery as cq

HERE = os.path.dirname(os.path.abspath(__file__))
PARAMS_JSON = os.path.normpath(os.path.join(HERE, "..", "pcb", "board_params.json"))
OUT_DIR = os.path.join(HERE, "out")

RESIN_G_PER_CC = 1.15
COMPONENT_MASS_G = {"module": 1.5, "cell": 0.9, "LRA": 1.2, "PCB": 0.5, "camera": 0.6, "antenna": 0.2, "misc": 0.5}


# ----------------------------------------------------------------------------------------------
# parameters
# ----------------------------------------------------------------------------------------------
def default_params():
    return dict(
        inner_d=20.0,          # finger diameter (US 10 ≈ 19.8 + comfort)
        band_w=12.0,           # band width along the finger
        band_wall=1.2,         # band wall, also the floor under the cell pocket and the pod
        bore_relief=0.5,       # the bore is opened by this much (R + relief) under the signet overhangs so that
                               # only the band (+ the cell-pocket floor) touches the finger; JSON pod_mm overrides
        head_drop=3.0,         # the signet slab reaches down to Z = R - head_drop beside the finger
        slab_fillet=1.0,       # fillet on the slab's bottom edges (was 1.5: the wire channels need the corner)
        bay_clear=0.3,         # board edge -> bay interior wall
        bay_wall=1.2,          # bay wall
        ant_depth=2.0,         # antenna cavity behind the board's back edge (JSON antenna_cavity_mm overrides)
        lid_t=1.2,             # lid plate
        lid_clear=0.15,        # lid -> rebate
        lid_rebate=0.5,        # rebate width in the wall top (lid rests on it, 1.2 deep)
        lid_lip=1.0,           # the pod roof overhangs the lid's front edge by this much (closes the pod slot)
        bead_r=0.25,           # detent bead on the lid's long edges (groove r = bead_r + 0.05); glue-assisted
        cell=(10.0, 12.0, 3.0),    # 301012 cell placed 10 along X, 12 across (Y), 3 thick
        cell_pocket=(10.4, 12.4, 3.4),
        cell_cx=-2.8,          # pocket centre along the finger (negative = toward the antenna end)
        lra_d=8.0, lra_h=2.5, lra_pocket_clear=0.2, lra_pocket_depth=2.9,
        lra_xy=(7.8, 3.5),     # LRA pocket centre (under the mic / away from the touch pad)
        lens_d=4.6,            # lens bore (OV2640 barrel 4.5)
        pod_bottom_drop=1.5,   # pod block bottom at Z = R - pod_bottom_drop (the relieved bore shapes it)
        head_clear=0.3,        # OV2640 head -> pod floor / side walls (JSON pod_mm overrides)
        fpc_fold=1.0,          # room above the head for the 180 deg fold of the camera FPC (JSON overrides)
        pod_corner_r=0.5,      # fillet of the pod interior's front vertical corners (keeps the corner wall >= 1.2)
        switch_slot=(3.4, 1.6),
        switch_bore=(4.6, 2.8, 0.5),   # counterbore from the inside for the key flange: X, Z, depth
        key=dict(flange=(4.4, 2.6, 0.33), pin=(3.2, 1.4), standoff=0.3, cap=(4.4, 2.6, 0.6)),
        pad_window=(3.0, 3.0), # charging pad window: 3 along X, 3 around the band
        pad_angle=25.0,        # ± from the bottom
        rib_x=(-1.5, -3.5),    # rib / groove / channel centres along X (A: -Y pad, B: +Y pad); next to PAD1w/PAD2w
        pad_rib_w=2.0, pad_rib_h=0.7, pad_groove_w=0.9, pad_groove_d=0.5,
        wire_r=0.45,           # wire channel radius (30 AWG wire-wrap / PTFE wire, <= 0.7 mm OD)
        led_mark_d=3.0,        # engraved ring marking the LED window (wall stays lid_t over the LED)
        touch_dimple=(4.0, 5.0, 0.4),
        mic_hole_d=0.8,
        mic_tube_od=1.8,       # tube under the lid hole down to the board (closes the bay off the mic port)
        mic_tube_gap=0.3,      # tube end -> board top (foam / adhesive gasket)
        antenna=(15.0, 5.0, 0.25),   # flex PCB antenna placeholder (Y, Z, X) glued to the back wall
        pigtail_d=0.9,         # u.FL pigtail (U.FL-LP-040, Ø0.81 cable)
    )


def load_board_params(path=PARAMS_JSON):
    with open(path) as f:
        return json.load(f)


# ----------------------------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------------------------
def V(x, y, z):
    return cq.Vector(x, y, z)


def rbox(l, w, h, r, x=0.0, y=0.0, z0=0.0):
    """rounded-corner box (vertical edges filleted r), footprint l x w centred on (x, y), from z0 up h."""
    wp = cq.Workplane("XY").box(l, w, h, centered=(True, True, False))
    if r > 0:
        wp = wp.edges("|Z").fillet(r)
    return wp.val().translate(V(x, y, z0))


def box(x0, x1, y0, y1, z0, z1):
    return cq.Solid.makeBox(x1 - x0, y1 - y0, z1 - z0, V(x0, y0, z0))


def cyl_x(r, x0, x1, y, z):
    return cq.Solid.makeCylinder(r, x1 - x0, V(x0, y, z), V(1, 0, 0))


def cyl_z(r, z0, z1, x, y):
    return cq.Solid.makeCylinder(r, z1 - z0, V(x, y, z0), V(0, 0, 1))


def cyl_between(r, p0, p1):
    d = V(*p1) - V(*p0)
    return cq.Solid.makeCylinder(r, d.Length, V(*p0), d.normalized())


def sector_x(r_in, r_out, phi0, phi1, x0, x1):
    """annular sector about the X axis; phi measured from +Z toward -Y (degrees), phi1 > phi0."""
    ring = cyl_x(r_out, x0, x1, 0, 0).cut(cyl_x(r_in, x0 - 1, x1 + 1, 0, 0))
    big = r_out * 3
    pts = [(0.0, 0.0)]
    n = max(2, int((phi1 - phi0) / 10) + 1)
    for i in range(n + 1):
        ph = math.radians(phi0 + (phi1 - phi0) * i / n)
        pts.append((-big * math.sin(ph), big * math.cos(ph)))
    wedge = cq.Workplane("YZ").polyline(pts).close().extrude(x1 - x0).val().translate(V(x0, 0, 0))
    return ring.intersect(wedge)


def fuse_all(shapes):
    s = shapes[0]
    for t in shapes[1:]:
        s = s.fuse(t)
    return s.clean()


def try_fillet(shape, selector, r, what):
    try:
        return cq.Workplane().add(shape).edges(selector).fillet(r).val()
    except Exception as e:  # OCC may refuse; keep the sharp edge rather than fail the build
        print(f"  (fillet {what} r={r} skipped: {type(e).__name__})")
        return shape


# ----------------------------------------------------------------------------------------------
# geometry
# ----------------------------------------------------------------------------------------------
class Model:
    def __init__(self, p, bp):
        self.p, self.bp = p, bp
        R = p["inner_d"] / 2.0
        self.R = R
        self.L, self.W, self.T = bp["board_length_mm"], bp["board_width_mm"], bp["board_thickness_mm"]
        st, pod = bp["stack_mm"], bp["pod_mm"]
        self.skin = R
        # enclosure allowances that live in board_params.json when the floorplan wrote them
        self.relief = pod.get("floor_relief_above_skin", p["bore_relief"])
        self.head_clear = pod.get("head_clearance", p["head_clear"])
        self.fpc_fold = pod.get("fpc_fold_above_head", p["fpc_fold"])
        self.ant_depth = bp.get("antenna_cavity_mm", {}).get("depth_behind_board_edge", p["ant_depth"])
        # vertical stack (absolute Z)
        self.z_pocket_bot = R + p["band_wall"]
        self.z_floor = self.z_pocket_bot + p["cell_pocket"][2]
        self.z_board_bot = self.z_floor + st["cell_clearance"] + bp["bottom_max_height_mm"]
        self.z_board_top = self.z_board_bot + self.T
        self.z_lid_bot = self.z_board_top + bp["top_max_height_mm"] + st["lid_clearance"]
        self.z_top = self.z_lid_bot + p["lid_t"]
        self.z_slab0 = R - p["head_drop"]
        # bay footprint: board + clearance + walls, plus the antenna cavity behind the board's back edge
        c, w = p["bay_clear"], p["bay_wall"]
        self.Li, self.Wi = self.L + 2 * c, self.W + 2 * c
        self.Lo, self.Wo = self.Li + 2 * w, self.Wi + 2 * w
        self.x_back_in = -self.Li / 2 - self.ant_depth      # bay interior back wall
        self.x_back_out = self.x_back_in - w                # slab back face
        self.Li_tot, self.Lo_tot = self.Li + self.ant_depth, self.Lo + self.ant_depth
        self.ri = bp["corner_radius_mm"] + c
        self.ro = self.ri + w
        # camera pod (in front of the bay, +X); the head stands on the pod floor with head_clear, the FPC folds above it
        self.pod_depth_int = pod["interior_depth_from_board_edge"]
        self.pod_wi = pod["interior_width"]
        self.pod_wall = pod["wall"]
        self.hs, self.ht, self.bl, self.bd = pod["head_square"], pod["head_thickness"], pod["barrel_length"], pod["lens_barrel_d"]
        self.pod_x_in0 = self.Li / 2                      # bay interior front wall
        self.pod_x_in1 = self.pod_x_in0 + self.pod_depth_int
        self.pod_x_out = self.pod_x_in1 + self.pod_wall
        self.pod_z_floor = R + self.relief + p["band_wall"]
        self.head_z0 = self.pod_z_floor + self.head_clear
        self.head_z1 = self.head_z0 + self.hs
        self.lens_z = self.head_z0 + self.hs / 2
        self.pod_z_ceil = self.head_z1 + self.fpc_fold
        self.z_pod_roof = self.pod_z_ceil + self.pod_wall
        self.z_pod_bot = R - p["pod_bottom_drop"]
        if abs(self.lens_z - R - pod["lens_axis_z"]) > 0.01:
            print(f"  NOTE board_params pod_mm.lens_axis_z = {pod['lens_axis_z']} but the pod geometry gives "
                  f"{self.lens_z - R:.2f} (floor {self.pod_z_floor - R:.2f} + {self.head_clear} clearance + {self.hs / 2})")
        # misc
        self.sw_x = self.bx(bp["switch_offset_mm"])
        self.sw_z = self.z_board_top + 0.6
        self.led = (self.bx(bp["led_xy_mm"][0]), self.by(bp["led_xy_mm"][1]))
        self.mic = (self.bx(bp["mic_xy_mm"][0]), self.by(bp["mic_xy_mm"][1]))
        self.tpad = (self.bx(bp["touchpad_xy_mm"][0]), self.by(bp["touchpad_xy_mm"][1]))
        self.rib_x = tuple(p["rib_x"])
        self.placeholders = {}

    # board -> world
    def bx(self, bx):
        return self.L / 2 - bx

    def by(self, by):
        return by - self.W / 2

    # ------------------------------------------------------------------ shell
    def build_shell(self):
        p, R = self.p, self.R
        wall = p["band_wall"]
        print("building shell ...")
        # 1. band
        band = cyl_x(R + wall, -p["band_w"] / 2, p["band_w"] / 2, 0, 0)
        # 2. signet slab (bay body incl. the antenna cavity), fillet on the outer vertical edges = ro, soft bottom edge
        slab = rbox(self.Lo_tot, self.Wo, self.z_top - self.z_slab0, self.ro, -self.ant_depth / 2, 0, self.z_slab0)
        slab = try_fillet(slab, "<Z", p["slab_fillet"], "slab bottom")
        # 3. camera pod block; its roof is taller than the lid and reaches back over the lid's front edge (lid_lip)
        reb, lcl = p["lid_rebate"], p["lid_clear"]
        pod_x0 = self.Li / 2 + reb - lcl - p["lid_lip"]
        pod_l = self.pod_x_out - pod_x0
        pod_w = self.pod_wi + 2 * self.pod_wall
        self.pod_w = pod_w
        pod = rbox(pod_l, pod_w, self.z_pod_roof - self.z_pod_bot, 1.5, pod_x0 + pod_l / 2, 0, self.z_pod_bot)
        pod = try_fillet(pod, "<Z", 1.0, "pod bottom")
        # 4. charging-pad wire ribs on the outside of the band (one per pad, both run down the -Y side; B goes
        #    round the bottom to the +Y window). The two ribs touch and print as one 4 mm wide rib.
        r0, r1 = R + wall, R + wall + p["pad_rib_h"]
        phiA = 180 - p["pad_angle"]        # -Y pad, 25 deg from the bottom
        phiB = 180 + p["pad_angle"]        # +Y pad
        half_win = math.degrees((p["pad_window"][1] / 2) / R)
        self.phi_slab = math.degrees(math.acos(self.z_slab0 / r1))   # where the rib meets the slab
        ribs = [
            sector_x(r0 - 0.05, r1, self.phi_slab - 4, phiA - half_win + 2, self.rib_x[0] - p["pad_rib_w"] / 2, self.rib_x[0] + p["pad_rib_w"] / 2),
            sector_x(r0 - 0.05, r1, self.phi_slab - 4, phiB - half_win + 2, self.rib_x[1] - p["pad_rib_w"] / 2, self.rib_x[1] + p["pad_rib_w"] / 2),
        ]
        body = fuse_all([band, slab, pod] + ribs)

        # ---- cuts
        cuts = []
        # bay cavity (board + antenna cavity) + lid rebate; both stop lid_clear above the wall tops so the pod's
        # roof lip over the lid survives
        z_cut_top = self.z_top + lcl
        cuts.append(rbox(self.Li_tot, self.Wi, z_cut_top - self.z_floor, self.ri, -self.ant_depth / 2, 0, self.z_floor))
        cuts.append(rbox(self.Li_tot + 2 * reb, self.Wi + 2 * reb, z_cut_top - self.z_lid_bot, self.ri + reb, -self.ant_depth / 2, 0, self.z_lid_bot))
        # lid detent grooves in the rebate faces
        gz = self.z_lid_bot + p["lid_t"] / 2
        for sy in (+1, -1):
            cuts.append(cyl_x(p["bead_r"] + 0.05, -9.5, 9.5, sy * (self.Wi / 2 + reb), gz))
        # cell pocket (recess in the sub-board floor) and its lead channel toward the J1 pads (-Y side)
        cl, cw, ch = p["cell_pocket"]
        cx = p["cell_cx"]
        cuts.append(box(cx - cl / 2, cx + cl / 2, -cw / 2, cw / 2, self.z_floor - ch, self.z_floor + 0.5))
        j1y = self.by(self.bp["wire_pads_bottom_mm"]["J1a"][1])
        cuts.append(box(cx - 1.5, cx + 1.5, j1y - 0.6, -cw / 2 + 0.5, self.z_floor - 0.8, self.z_floor + 0.5))
        # LRA pocket
        lx, ly = p["lra_xy"]
        cuts.append(cyl_z(p["lra_d"] / 2 + p["lra_pocket_clear"], self.z_floor - p["lra_pocket_depth"], self.z_floor + 0.5, lx, ly))
        # camera pod interior (also opens the bay front wall for the head + FPC neck) and the lens bore;
        # the front vertical corners are filleted so the wall stays >= 1.2 inside the r 1.5 outer corner
        pod_int = box(self.pod_x_in0 - 0.01, self.pod_x_in1, -self.pod_wi / 2, self.pod_wi / 2, self.pod_z_floor, self.pod_z_ceil)
        pod_int = try_fillet(pod_int, "|Z and >X", p["pod_corner_r"], "pod interior front corners")
        cuts.append(pod_int)
        cuts.append(cyl_x(p["lens_d"] / 2, self.pod_x_in1 - 0.5, self.pod_x_out + 1, 0, self.lens_z))
        # side-switch slot through the left (-Y) wall + counterbore from the inside for the key's flange
        sl, sh = p["switch_slot"]
        yw = -(self.Wi / 2)
        sz = self.sw_z
        cuts.append(box(self.sw_x - sl / 2, self.sw_x + sl / 2, yw - self.p["bay_wall"] - 1, yw + 0.3, sz - sh / 2, sz + sh / 2))
        bl_, bh_, bd_ = p["switch_bore"]
        cuts.append(box(self.sw_x - bl_ / 2, self.sw_x + bl_ / 2, yw - bd_, yw + 0.3, sz - bh_ / 2, sz + bh_ / 2))
        # charging-pad windows through the inner band, ±pad_angle from the bottom
        pw = p["pad_window"]
        for ang, wx in ((-p["pad_angle"], self.rib_x[0]), (+p["pad_angle"], self.rib_x[1])):
            b = cq.Solid.makeBox(pw[0], pw[1], 4.0, V(wx - pw[0] / 2, -pw[1] / 2, -(R + 3.0)))
            cuts.append(b.rotate(V(0, 0, 0), V(1, 0, 0), ang))
        # wire grooves in the ribs + slanted channels through the slab into the sub-board cavity.
        # The channel starts in the groove at the slab's bottom corner and climbs steeply enough to keep
        # >= 1.2 mm to the slab's outer face / bottom fillet from ~1.3 mm above the slab bottom upward.
        gr0, gr1 = r1 - p["pad_groove_d"], r1 + 0.5
        self.chan = {}
        for wx, phi_end in ((self.rib_x[0], phiA), (self.rib_x[1], phiB)):
            cuts.append(sector_x(gr0, gr1, self.phi_slab - 6, phi_end, wx - p["pad_groove_w"] / 2, wx + p["pad_groove_w"] / 2))
            p0 = (wx, -8.75, self.z_slab0 + 0.4)
            p1 = (wx, -(self.Wi / 2 - 1.0), self.z_floor + 0.4)
            self.chan[wx] = (p0, p1)
            cuts.append(cyl_between(p["wire_r"], p0, p1))
        # finger bore: radius R where the ring is meant to touch the finger (the band plus the cell-pocket
        # floor behind it), R + relief under the signet overhangs and the pod so they clear the skin; 0.5 mm
        # chamfer cones join the two radii and soften the band faces.
        rr = R + self.relief
        xb0 = min(-p["band_w"] / 2, cx - cl / 2)             # back end of the contact zone (cell pocket floor)
        xb1 = p["band_w"] / 2 - 0.5
        self.bore_x = (xb0, xb1)
        chf = 0.5
        cuts.append(cyl_x(R, xb0, xb1, 0, 0))
        cuts.append(cyl_x(rr, -40, xb0 - chf + 0.01, 0, 0))
        cuts.append(cyl_x(rr, xb1 + chf - 0.01, 40, 0, 0))
        cone = lambda x, d: cq.Solid.makeCone(R + chf, R, chf, V(x, 0, 0), V(d, 0, 0))   # R+chf at x -> R at x + d*chf
        cuts.append(cone(xb0 - chf, +1))                                          # back of the contact zone (inside the slab)
        cuts.append(cone(xb1 + chf, -1))                                          # band front face / slab transition
        cuts.append(cone(self.pod_x_out, -1))                                     # pod front face
        cuts.append(cone(self.x_back_out, +1))                                    # slab back face
        cuts.append(cone(-p["band_w"] / 2, +1).intersect(box(-30, 30, -30, 30, -30, self.z_slab0 - 0.01)))   # band back face
        cuts.append(cone(self.Lo / 2, -1).intersect(box(0, 30, -30, -pod_w / 2, -30, 30)))   # slab front faces beside the pod
        cuts.append(cone(self.Lo / 2, -1).intersect(box(0, 30, pod_w / 2, 30, -30, 30)))

        shell = body
        for c_ in cuts:
            shell = shell.cut(c_)
        shell = shell.clean()
        # soften the edge where the slab's flat underside meets the bore (134 deg edge along the full slab)
        yb = math.sqrt(max(rr * rr - self.z_slab0 ** 2, 0.0))
        sel = cq.selectors.BoxSelector((-40, -yb - 0.9, self.z_slab0 - 0.1), (40, yb + 0.9, self.z_slab0 + 0.1))
        long_edges = [e for e in cq.Workplane().add(shell).edges(sel).vals() if e.Length() > 3.0]
        for r_, how in ((0.6, "fillet"), (0.4, "fillet"), (0.4, "chamfer")):
            try:
                wp = cq.Workplane().add(shell).newObject(long_edges)
                shell = (wp.fillet(r_) if how == "fillet" else wp.chamfer(r_)).val()
                print(f"  slab underside / bore edge: {how} r={r_} on {len(long_edges)} edges")
                break
            except Exception as e:
                print(f"  ({how} slab underside / bore edge r={r_} skipped: {type(e).__name__})")

        # ---- board ledges (added after the cavity cut): front (two blocks clear of the bottom parts), back (full width)
        zb = self.z_board_bot
        f0, f1 = self.bx(0.7), self.Li / 2 + 0.01
        ledges = [
            box(f0, f1, -self.Wi / 2 - 0.01, self.by(2.6), self.z_floor - 0.01, zb),
            box(f0, f1, self.by(8.4), self.Wi / 2 + 0.01, self.z_floor - 0.01, zb),
            box(-self.Li / 2, self.bx(23.6), -self.Wi / 2 - 0.01, self.Wi / 2 + 0.01, self.z_floor - 0.01, zb),
        ]
        self.ledges = ledges
        shell = fuse_all([shell] + ledges)
        self.shell = shell
        return shell

    # ------------------------------------------------------------------ lid
    def build_lid(self):
        p = self.p
        print("building lid ...")
        reb, cl = p["lid_rebate"], p["lid_clear"]
        l, w = self.Li_tot + 2 * reb - 2 * cl, self.Wi + 2 * reb - 2 * cl
        lid = rbox(l, w, p["lid_t"], self.ri + reb - cl, -self.ant_depth / 2, 0, self.z_lid_bot)
        gz = self.z_lid_bot + p["lid_t"] / 2
        for sy in (+1, -1):
            lid = lid.fuse(cyl_x(p["bead_r"], -9.0, 9.0, sy * w / 2, gz))
        # mic port straight above the T3902 port, with a tube down to the board so the mic does not listen to
        # the bay and the hole does not open the bay to dust (a 0.3 mm foam/adhesive ring seals the tube end)
        self.mic_tube_z0 = self.z_board_top + p["mic_tube_gap"]
        lid = lid.fuse(cyl_z(p["mic_tube_od"] / 2, self.mic_tube_z0, self.z_lid_bot + 0.01, *self.mic))
        lid = lid.cut(cyl_z(p["mic_hole_d"] / 2, self.mic_tube_z0 - 1, self.z_top + 1, *self.mic))
        # LED window: the lid stays lid_t thick over led_xy; a 0.15 mm engraved ring marks it
        ring = cyl_z(p["led_mark_d"] / 2 + 0.3, self.z_top - 0.15, self.z_top + 1, *self.led).cut(
            cyl_z(p["led_mark_d"] / 2 - 0.3, self.z_top - 1, self.z_top + 2, *self.led))
        lid = lid.cut(ring)
        # touch dimple: thin (<= 1.0 mm) dielectric over the touch pad + tactile marker
        tdx, tdy, tdd = p["touch_dimple"]
        lid = lid.cut(box(self.tpad[0] - tdx / 2, self.tpad[0] + tdx / 2, self.tpad[1] - tdy / 2, self.tpad[1] + tdy / 2,
                          self.z_top - tdd, self.z_top + 1))
        self.lid = lid.clean()
        return self.lid

    # ------------------------------------------------------------------ switch key (third printed part)
    def build_key(self):
        """Button for the B3U-3000P: flange inside the wall counterbore, pin through the slot, cap outside.
        The flange keeps it from falling out, the cap from falling in; the plunger touches the flange's inner face."""
        p = self.p
        print("building key ...")
        k = p["key"]
        yw = -(self.Wi / 2)                        # bay wall inner face
        yo = -(self.Wo / 2)                        # outer face
        y_in = yw - 0.1 - 0.02                     # flange inner face: just outboard of the plunger tip (yw - 0.1)
        fl, fh, ft = k["flange"]
        y_fl_out = y_in - ft
        pl, ph = k["pin"]
        y_cap_in = yo - k["standoff"]
        cl_, chh, ct = k["cap"]
        sx, sz = self.sw_x, self.sw_z
        flange = box(sx - fl / 2, sx + fl / 2, y_fl_out, y_in, sz - fh / 2, sz + fh / 2)
        pin = box(sx - pl / 2, sx + pl / 2, y_cap_in - 0.01, y_fl_out + 0.01, sz - ph / 2, sz + ph / 2)
        cap = box(sx - cl_ / 2, sx + cl_ / 2, y_cap_in - ct, y_cap_in, sz - chh / 2, sz + chh / 2)
        cap = try_fillet(cap, "|Y", 0.6, "key cap")
        self.key = fuse_all([flange, pin, cap])
        self.key_cap_in = y_cap_in
        self.key_travel = k["standoff"]
        return self.key

    # ------------------------------------------------------------------ placeholders
    def build_placeholders(self):
        p, bp = self.p, self.bp
        print("building placeholders ...")
        ph = {}
        zb, zt = self.z_board_bot, self.z_board_top
        ph["PCB"] = rbox(self.L, self.W, self.T, bp["corner_radius_mm"], 0, 0, zb)
        mx, my = bp["module_xy_mm"]
        ms = bp["module_size_mm"]
        mod = box(self.bx(mx) - ms[0] / 2, self.bx(mx) + ms[0] / 2, self.by(my) - ms[1] / 2, self.by(my) + ms[1] / 2, zt, zt + ms[2])
        ufl_x0, ufl_y = self.bx(self.L - 0.2), (self.by(3.2) + self.by(5.7)) / 2
        ufl = box(ufl_x0, ufl_x0 + 2.5, self.by(3.2), self.by(5.7), zt, zt + bp["ufl_mated_height_mm"])
        ph["module"] = mod.fuse(ufl).clean()
        # OV2640 head + barrel; the 24-pin flex leaves the head's top edge, folds 180 deg back down behind the head,
        # turns 90 deg at the board and runs into FPC1 (bottom-contact) from the front
        hs, ht, bl, bd = self.hs, self.ht, self.bl, self.bd
        x_barrel_front = self.pod_x_in1 - 0.1
        x_head_back = x_barrel_front - bl - ht
        barrel = cyl_x(bd / 2, x_barrel_front - bl, x_barrel_front, 0, self.lens_z)
        head = box(x_head_back, x_barrel_front - bl, -hs / 2, hs / 2, self.head_z0, self.head_z1)
        ph["camera"] = head.fuse(barrel).clean()
        fc = bp["fpc_connector_mm"]
        ph["FPC1"] = box(self.bx(fc["x1"]), self.bx(fc["x0"]), self.by(fc["y0"]), self.by(fc["y1"]), zt, zt + fc["height"])
        t_fpc, w_neck, w_end = 0.2, hs, 12.5          # flex 0.2 thick, neck as wide as the head, 24 x 0.5 mm contact end
        z_run = zt + 0.3                               # contact plane of a 0.5 mm bottom-contact connector
        fold_r = (self.fpc_fold - 0.2 - t_fpc) / 2     # 180 deg fold centreline radius (0.3 for fpc_fold 1.0)
        x_down = x_head_back - 2 * fold_r - t_fpc      # vertical run behind the head
        x_mouth = self.bx(fc["x0"]) + 0.01             # FPC1 mouth (front face)
        fold = box(x_down, x_head_back + t_fpc, -w_neck / 2, w_neck / 2, self.head_z1, self.head_z1 + 2 * fold_r + t_fpc)
        down = box(x_down, x_down + t_fpc, -w_neck / 2, w_neck / 2, z_run + 0.8, self.head_z1 + 0.01)
        bend = box(x_down - 0.8, x_down + t_fpc, -w_neck / 2, w_neck / 2, z_run, z_run + 0.8 + 0.01)
        x_end1 = self.pod_x_in0 - 0.1                  # the wide stiffened end stays inside the bay
        run = box(x_end1 - 0.01, x_down - 0.8 + 0.01, -w_neck / 2, w_neck / 2, z_run, z_run + t_fpc)
        end = box(x_mouth, x_end1, -w_end / 2, w_end / 2, z_run - 0.05, z_run + 0.3)
        ph["camera_FPC"] = fuse_all([fold, down, bend, run, end])
        self.fpc_path = dict(x_down=x_down, fold_top=self.head_z1 + 2 * fold_r + t_fpc, z_run=z_run, x_end1=x_end1)
        cl, cw, ch = p["cell"]
        cx = p["cell_cx"]
        ph["cell"] = box(cx - cl / 2, cx + cl / 2, -cw / 2, cw / 2, self.z_pocket_bot + 0.2, self.z_pocket_bot + 0.2 + ch)
        lx, ly = p["lra_xy"]
        ph["LRA"] = cyl_z(p["lra_d"] / 2, self.z_floor - p["lra_pocket_depth"] + 0.2, self.z_floor - p["lra_pocket_depth"] + 0.2 + p["lra_h"], lx, ly)
        sx, sy = bp["switch_xy_mm"]
        sb = bp["switch_body_mm"]
        sw = box(self.bx(sx) - sb[0] / 2, self.bx(sx) + sb[0] / 2, self.by(sy) - sb[1] / 2, self.by(sy) + sb[1] / 2, zt, zt + sb[2])
        plunger = box(self.sw_x - 0.6, self.sw_x + 0.6, -self.Wi / 2 - 0.1, self.by(sy) - sb[1] / 2 + 0.05, zt + 0.3, zt + 0.9)
        ph["switch"] = sw.fuse(plunger).clean()
        ph["key"] = self.key
        ph["LED"] = box(self.led[0] - 1, self.led[0] + 1, self.led[1] - 1, self.led[1] + 1, zt, zt + 0.9)
        ph["mic"] = box(self.mic[0] - 2.65 / 2, self.mic[0] + 2.65 / 2, self.mic[1] - 3.5 / 2, self.mic[1] + 3.5 / 2, zb - 0.98, zb)
        # every bottom-side part from the floorplan (the 1.15 mm envelope, checked against ledges and pockets)
        bottoms = [box(self.bx(q["cx"]) - q["w"] / 2, self.bx(q["cx"]) + q["w"] / 2, self.by(q["cy"]) - q["h"] / 2,
                       self.by(q["cy"]) + q["h"] / 2, zb - q["height"], zb)
                   for q in bp["parts"] if q["side"] == "bottom" and q["height"] > 0 and q["ref"] != "MK1"]
        ph["bottom_parts"] = fuse_all(bottoms)
        # every other top-side part from the floorplan (C3, R7, the touch contact block, test pads ...): must clear the
        # lid, its mic tube and the camera flex
        modelled = {"U1", "FPC1", "SW1", "D1"}
        tops = [box(self.bx(q["cx"]) - q["w"] / 2, self.bx(q["cx"]) + q["w"] / 2, self.by(q["cy"]) - q["h"] / 2,
                    self.by(q["cy"]) + q["h"] / 2, zt, zt + min(q["height"], self.z_lid_bot - zt - 0.01))
                for q in bp["parts"] if q["side"] == "top" and q["height"] > 0 and q["ref"] not in modelled]
        if tops:
            ph["top_parts"] = fuse_all(tops)
        # 2.4 GHz flex antenna glued to the back wall + u.FL pigtail leaving the plug toward -X and turning down
        ay, az, at = p["antenna"]
        ph["antenna"] = box(self.x_back_in + 0.05, self.x_back_in + 0.05 + at, -ay / 2, ay / 2, self.z_floor + 0.1, self.z_floor + 0.1 + az)
        pr = p["pigtail_d"] / 2
        z_pig = zt + 1.7                                 # cable axis of the mated plug
        x_turn = self.bx(mx) - ms[0] / 2 - 1.05            # downward run, ~1 mm behind the board edge
        x_mod_back = self.bx(mx) - ms[0] / 2                  # module back face (= board back edge)
        pig = cyl_x(pr, x_turn, x_mod_back - 0.01, ufl_y, z_pig)
        pig = pig.fuse(cq.Solid.makeSphere(pr, V(x_turn, ufl_y, z_pig)))
        pig = pig.fuse(cyl_z(pr, self.z_floor + 0.6, z_pig, x_turn, ufl_y))
        ph["pigtail"] = pig.clean()
        self.placeholders = ph
        return ph

    # ------------------------------------------------------------------ checks
    def probe(self, p0, p1, shape=None):
        """material thickness of the shell (or `shape`) along the segment p0 -> p1 (thin cylinder intersection)."""
        r = 0.02
        c = cyl_between(r, p0, p1)
        return (shape or self.shell).intersect(c).Volume() / (math.pi * r * r)

    def contact_scan(self, step=0.5):
        """X range over which the shell touches the nominal finger (radius R) along the top (Y=0) and bottom."""
        R = self.R
        out = {}
        for name, zc in (("top", R), ("bottom", -R)):
            xs = []
            x = -40.0
            while x <= 40.0:
                if self.probe((x, 0, zc - 0.15), (x, 0, zc + 0.15)) > 0.05:
                    xs.append(x)
                x += step
            out[name] = (min(xs), max(xs)) if xs else None
        return out

    def fit_check(self):
        print("fit check ...")
        res = {"shell": {}, "lid": {}, "pairs": {}, "probes": [], "clearances": []}
        names = list(self.placeholders)
        for n in names:
            s = self.placeholders[n]
            res["shell"][n] = s.intersect(self.shell).Volume()
            res["lid"][n] = s.intersect(self.lid).Volume()
        for i, a in enumerate(names):
            for b in names[i + 1:]:
                res["pairs"][(a, b)] = self.placeholders[a].intersect(self.placeholders[b]).Volume()
        res["lid_vs_shell"] = self.lid.intersect(self.shell).Volume()
        R, p = self.R, self.p
        cx = p["cell_cx"]
        lx, ly = p["lra_xy"]
        zf = self.z_floor
        phi = math.radians(100)
        sx, sz = self.sw_x, self.sw_z
        bh_ = p["switch_bore"][1]
        # explicit clearances (mm, must be >= minimum)
        cam = self.placeholders["camera"].BoundingBox()
        fpc = self.placeholders["camera_FPC"].BoundingBox()
        mod = self.placeholders["module"].BoundingBox()
        key = self.key.BoundingBox()
        res["clearances"] = [
            ("OV2640 head bottom -> pod floor", cam.zmin - self.pod_z_floor, self.head_clear),
            ("OV2640 head top -> pod ceiling (FPC fold space)", self.pod_z_ceil - cam.zmax, self.fpc_fold),
            ("OV2640 head side -> pod side wall", self.pod_wi / 2 - cam.ymax, self.head_clear),
            ("FPC fold top -> pod ceiling", self.pod_z_ceil - fpc.zmax, 0.15),
            ("FPC vertical run behind the head -> bay interior front wall", self.fpc_path["x_down"] - self.pod_x_in0, 0.3),
            ("FPC wide contact end -> bay front wall", self.pod_x_in0 - self.fpc_path["x_end1"], 0.05),
            ("module/u.FL back face -> antenna cavity back wall", mod.xmin - self.x_back_in, self.ant_depth - 0.05),
            ("u.FL plug top -> lid underside", self.z_lid_bot - mod.zmax, 0.3),
            ("switch key cap stand-off from the signet side (button travel)", -self.Wo / 2 - self.key_cap_in, 0.25),
            ("switch key flange inner face -> plunger tip (gap)", (-self.Wi / 2 - 0.1) - key.ymax, 0.0),
        ]
        probes = [
            ("floor under the cell pocket (X=cell centre, Y=0)", (cx, 0, R - 0.5), (cx, 0, self.z_pocket_bot + 0.5), 1.2),
            ("floor under the cell pocket's back end (X=pocket back+0.3, Y=0)", (cx - p["cell_pocket"][0] / 2 + 0.3, 0, R - 0.5), (cx - p["cell_pocket"][0] / 2 + 0.3, 0, self.z_pocket_bot + 0.5), 1.2),
            ("floor under the LRA pocket (centre)", (lx, ly, R - 1), (lx, ly, zf - p["lra_pocket_depth"] + 0.3), 1.2),
            ("band wall at the bottom (X=0)", (0, 0, -R - 2), (0, 0, -R + 0.5), 1.2),
            ("band wall at 100 deg, beside the ribs (X=2)", (2, -(R - 0.5) * math.sin(phi), (R - 0.5) * math.cos(phi)),
             (2, -(R + 3) * math.sin(phi), (R + 3) * math.cos(phi)), 1.2),
            ("band + rib under the pad-wire groove A (100 deg)", (self.rib_x[0], -(R - 0.5) * math.sin(phi), (R - 0.5) * math.cos(phi)),
             (self.rib_x[0], -(R + 3) * math.sin(phi), (R + 3) * math.cos(phi)), 1.2),
            ("bay long wall (X=0, Z=board top+1)", (0, self.Wi / 2 - 1, self.z_board_top + 1), (0, self.Wo / 2 + 1, self.z_board_top + 1), 1.2),
            ("bay long wall rim at the lid groove (X=0)", (0, self.Wi / 2 - 1, self.z_lid_bot + p["lid_t"] / 2), (0, self.Wo / 2 + 1, self.z_lid_bot + p["lid_t"] / 2), 0.35),
            ("bay long wall rim beyond the groove (X=12)", (12, self.Wi / 2 - 1, self.z_lid_bot + p["lid_t"] / 2), (12, self.Wo / 2 + 1, self.z_lid_bot + p["lid_t"] / 2), 0.6),
            ("bay back wall behind the antenna cavity (Y=0, Z=board top+1)", (self.x_back_in + 1, 0, self.z_board_top + 1), (self.x_back_out - 1, 0, self.z_board_top + 1), 1.2),
            ("bay front wall beside the pod opening (Y=7)", (self.Li / 2 - 1, 7, self.z_board_top + 1), (self.Lo / 2 + 1, 7, self.z_board_top + 1), 1.2),
            ("pod side wall (X=18, lens height)", (18, self.pod_wi / 2 - 1, self.lens_z), (18, self.pod_wi / 2 + 3, self.lens_z), 1.2),
            ("pod front wall beside the lens bore (Y=3.5)", (self.pod_x_in1 - 1, 3.5, self.lens_z), (self.pod_x_out + 1, 3.5, self.lens_z), 1.2),
            ("pod front corner, diagonal (+Y, lens height)", (self.pod_x_in1 - 0.3, self.pod_wi / 2 - 0.3, self.lens_z), (self.pod_x_in1 + 2.5, self.pod_wi / 2 + 2.5, self.lens_z), 1.2),
            ("pod front corner, diagonal (-Y, lens height)", (self.pod_x_in1 - 0.3, -self.pod_wi / 2 + 0.3, self.lens_z), (self.pod_x_in1 + 2.5, -self.pod_wi / 2 - 2.5, self.lens_z), 1.2),
            ("pod floor (X=18, Y=0)", (18, 0, R - 1), (18, 0, self.pod_z_floor + 0.5), 1.2),
            ("pod roof (X=18, Y=0)", (18, 0, self.pod_z_ceil - 0.5), (18, 0, self.z_pod_roof + 1), 1.2),
            ("pod roof lip over the lid's front edge (X=lid edge+0.07, Y=0)", (self.Li / 2 + p["lid_rebate"] - p["lid_clear"] + 0.07, 0, self.z_lid_bot - 0.5), (self.Li / 2 + p["lid_rebate"] - p["lid_clear"] + 0.07, 0, self.z_pod_roof + 1), 1.2),
            ("pod roof lip + lid, vertical (X=lid edge-0.5, Y=0)", (self.Li / 2 + p["lid_rebate"] - p["lid_clear"] - 0.5, 0, self.z_lid_bot - 0.5), (self.Li / 2 + p["lid_rebate"] - p["lid_clear"] - 0.5, 0, self.z_pod_roof + 1), 1.2),
            ("wall between the cell pocket and the LRA pocket", (cx + p["cell_pocket"][0] / 2 - 0.5, 2, zf - 1.5), (lx - p["lra_d"] / 2 - p["lra_pocket_clear"] + 0.5, 2, zf - 1.5), 0.8),
            ("left wall above the switch counterbore (X=switch)", (sx, -self.Wi / 2 + 0.5, sz + bh_ / 2 + 0.3), (sx, -self.Wo / 2 - 1, sz + bh_ / 2 + 0.3), 1.2),
            ("left wall at the switch counterbore, beside the slot", (sx + 1.9, -self.Wi / 2 + 0.5, sz), (sx + 1.9, -self.Wo / 2 - 1, sz), p["bay_wall"] - p["switch_bore"][2]),
            ("lid: mic tube wall, through the tube (lid part)", (self.mic[0], self.mic[1] - 2, self.z_lid_bot - 1), (self.mic[0], self.mic[1] + 2, self.z_lid_bot - 1), 0.9, "lid"),
        ]
        # band faces through both pad windows: the band must still be closed 0.5 mm inside each face
        rad = lambda r, a: (r * math.sin(a), -r * math.cos(a))     # (Y, Z) of the window box's point at radius r
        for ang in (-p["pad_angle"], +p["pad_angle"]):
            a = math.radians(ang)
            for xf in (-p["band_w"] / 2 + 0.7, p["band_w"] / 2 - 0.7):
                probes.append((f"band wall at the face X={xf:+.1f} through the {ang:+.0f} deg pad window angle",
                               (xf, *rad(R - 0.5, a)), (xf, *rad(R + 3, a)), 1.2))
        # skin around both wire channels: toward the slab's outer face (-Y), down (-Z) and diagonally into the
        # bottom fillet, from 1.5 mm above the slab bottom (where the channel has left the open groove) upward
        for wx, (p0, p1) in self.chan.items():
            d = V(*p1) - V(*p0)
            for z in (self.z_slab0 + 2.0, self.z_slab0 + 3.0, self.z_slab0 + 4.5, self.z_slab0 + 6.5):
                t = (z - p0[2]) / d.z
                q = V(*p0) + d * t
                probes.append((f"skin beside wire channel X={wx:+.1f} toward -Y (outer face) at Z={z - R:+.1f}", (q.x, q.y, q.z), (q.x, q.y - 4, q.z), 1.2))
                probes.append((f"skin beside wire channel X={wx:+.1f} diagonal (-Y,-Z, bottom fillet) at Z={z - R:+.1f}", (q.x, q.y, q.z), (q.x, q.y - 3, q.z - 3), 1.2))
                probes.append((f"skin beside wire channel X={wx:+.1f} toward +Y (cell pocket) at Z={z - R:+.1f}", (q.x, q.y, q.z), (q.x, q.y + 4, q.z), 1.2))
        for pr_ in probes:
            name, a, b, want = pr_[:4]
            t = self.probe(a, b, self.lid if len(pr_) > 4 and pr_[4] == "lid" else None)
            res["probes"].append((name, t, want, t + 1e-3 >= want))
        # openings that must be open (material 0): pad windows
        opens = []
        for ang, wx in ((-p["pad_angle"], self.rib_x[0]), (+p["pad_angle"], self.rib_x[1])):
            a = math.radians(ang)
            opens.append((f"pad window {'A (-Y)' if ang < 0 else 'B (+Y)'} open at X={wx:+.1f}", (wx, *rad(R - 0.5, a)), (wx, *rad(R + 3, a))))
        for name, a, b in opens:
            t = self.probe(a, b)
            res["probes"].append((name + " (must be 0)", t, 0.0, t < 0.01))
        res["contact"] = self.contact_scan()
        self.fit = res
        return res

    def envelope(self):
        bb = self.shell.BoundingBox()
        band_od = 2 * (self.R + self.p["band_wall"])
        return dict(
            bbox=(bb.xmin, bb.xmax, bb.ymin, bb.ymax, bb.zmin, bb.zmax),
            band_od=band_od, band_od_at_ribs=band_od + 2 * self.p["pad_rib_h"],
            height_above_skin=self.z_top - self.R, pod_above_skin=self.z_pod_roof - self.R, lid_top_z=self.z_top,
            bay_footprint=(self.Lo_tot, self.Wo), length_with_pod=self.pod_x_out - self.x_back_out,
            signet_width=self.Wo,
        )

    def mass(self):
        vs, vl, vk = self.shell.Volume(), self.lid.Volume(), self.key.Volume()
        resin = (vs + vl + vk) / 1000.0 * RESIN_G_PER_CC
        comp = sum(COMPONENT_MASS_G.values())
        return dict(shell_cc=vs / 1000, lid_cc=vl / 1000, key_cc=vk / 1000, resin_g=resin, components_g=comp, total_g=resin + comp)


# ----------------------------------------------------------------------------------------------
# report + exports
# ----------------------------------------------------------------------------------------------
def write_report(m, path, args):
    f = m.fit
    env, mass = m.envelope(), m.mass()
    ok_int = all(v < 1e-6 for v in f["shell"].values()) and all(v < 1e-6 for v in f["lid"].values()) \
        and all(v < 1e-6 for v in f["pairs"].values()) and f["lid_vs_shell"] < 1e-6
    ok_probe = all(p[3] for p in f["probes"])
    ok_clear = all(v + 1e-3 >= want for _, v, want in f["clearances"])
    ok = ok_int and ok_probe and ok_clear
    L = []
    L.append("# mcring stage-1 enclosure — fit report\n")
    L.append(f"Generated by `mcring_stage1.py` from `hardware/pcb/board_params.json` "
             f"(inner_d = {m.p['inner_d']} mm, lens_d = {m.p['lens_d']} mm). "
             f"Result: **{'PASS' if ok else 'FAIL'}** "
             f"(intersections {'all 0' if ok_int else 'NON-ZERO'}, clearances {'ok' if ok_clear else 'BELOW MINIMUM'}, "
             f"wall probes {'ok' if ok_probe else 'BELOW MINIMUM'}).\n")
    L.append("The wall probes are line samples at the places listed below, not a global thickness analysis. Known spots "
             "thinner than the 1.2 mm wall rule, by design: the 0.4 / 0.7 mm rebate rim under the lid detent groove, the "
             "0.7 mm wall around the switch key's counterbore, the first ~1.3 mm of each wire channel where it leaves the "
             "open groove at the slab's bottom corner, and the 0.8 mm resin over the touch pad.\n")
    L.append("## Stack (Z above the finger skin, mm)\n")
    R = m.R
    L.append("| level | z |\n|---|---|")
    for n, z in [("pocket floor (band wall)", m.z_pocket_bot), ("sub-board floor (cell pocket top)", m.z_floor),
                 ("board bottom (ledges)", m.z_board_bot), ("board top", m.z_board_top),
                 ("lid underside", m.z_lid_bot), ("lid top", m.z_top),
                 (f"pod underside (bore relief {m.relief})", R + m.relief), ("pod floor", m.pod_z_floor),
                 ("OV2640 head bottom / top", None), ("lens axis", m.lens_z),
                 ("pod ceiling (head top + FPC fold)", m.pod_z_ceil), ("pod roof top", m.z_pod_roof)]:
        if z is None:
            L.append(f"| {n} | {m.head_z0 - R:.2f} / {m.head_z1 - R:.2f} |")
        else:
            L.append(f"| {n} | {z - R:.2f} |")
    L.append("")
    L.append("## Placeholder vs shell / lid intersection volumes (mm³, must be 0)\n")
    L.append("| placeholder | ∩ shell | ∩ lid |\n|---|---|---|")
    for n in f["shell"]:
        L.append(f"| {n} | {f['shell'][n]:.4f} | {f['lid'][n]:.4f} |")
    L.append(f"| lid ∩ shell | {f['lid_vs_shell']:.4f} | — |")
    L.append("")
    L.append("## Placeholder pairs (mm³, must be 0)\n")
    L.append("| a | b | ∩ |\n|---|---|---|")
    for (a, b), v in f["pairs"].items():
        L.append(f"| {a} | {b} | {v:.4f} |")
    L.append("")
    L.append("## Clearances (mm, must be >= minimum)\n")
    L.append("| what | measured | minimum | ok |\n|---|---|---|---|")
    for name, v, want in f["clearances"]:
        L.append(f"| {name} | {v:.2f} | {want:.2f} | {'yes' if v + 1e-3 >= want else 'NO'} |")
    L.append("")
    L.append("## Wall probes (material thickness along a line through the shell, mm)\n")
    L.append("| where | measured | minimum | ok |\n|---|---|---|---|")
    for name, t, want, okp in f["probes"]:
        L.append(f"| {name} | {t:.2f} | {want:.2f} | {'yes' if okp else 'NO'} |")
    L.append("")
    L.append("## Finger contact\n")
    c = f["contact"]
    top, bot = c["top"], c["bottom"]
    L.append(f"* the shell touches the nominal finger (Ø{m.p['inner_d']}) along the top (Y = 0) only for X {top[0]:.1f}..{top[1]:.1f} "
             f"({top[1] - top[0]:.1f} mm: the {m.p['band_w']:.0f} mm band plus the cell-pocket floor behind it) and along the bottom for "
             f"X {bot[0]:.1f}..{bot[1]:.1f} ({bot[1] - bot[0]:.1f} mm); the signet overhangs and the camera pod are relieved "
             f"{m.relief} mm above the skin line.")
    L.append(f"* the shell is {env['length_with_pod']:.1f} mm long along the finger; worn with the band against the knuckle, the pod "
             f"front sits {m.pod_x_out - m.p['band_w'] / 2:.1f} mm beyond the band's front face toward the PIP joint — check on a hand.")
    L.append("")
    L.append("## Envelope\n")
    bb = env["bbox"]
    L.append(f"* bounding box (X along the finger, Y across, Z up): {bb[0]:.1f}..{bb[1]:.1f} × {bb[2]:.1f}..{bb[3]:.1f} × {bb[4]:.1f}..{bb[5]:.1f} mm "
             f"→ {bb[1]-bb[0]:.1f} × {bb[3]-bb[2]:.1f} × {bb[5]-bb[4]:.1f} mm")
    L.append(f"* band OD {env['band_od']:.1f} mm (inner {m.p['inner_d']:.1f}, wall {m.p['band_wall']:.1f}); {env['band_od_at_ribs']:.1f} across the pad-wire rib")
    L.append(f"* signet (bay) footprint {env['bay_footprint'][0]:.1f} × {env['bay_footprint'][1]:.1f} mm (incl. the {m.ant_depth:.1f} mm antenna cavity), "
             f"lid top {env['height_above_skin']:.2f} mm above the skin, pod roof {env['pod_above_skin']:.2f} mm, "
             f"{env['length_with_pod']:.1f} mm long along the finger including the camera pod")
    L.append("")
    L.append("## Mass estimate\n")
    L.append(f"* shell {mass['shell_cc']:.2f} cm³ + lid {mass['lid_cc']:.2f} cm³ + key {mass['key_cc']:.3f} cm³ of resin at {RESIN_G_PER_CC} g/cm³ = **{mass['resin_g']:.1f} g**")
    L.append(f"* components {mass['components_g']:.1f} g ({', '.join(f'{k} {v}' for k, v in COMPONENT_MASS_G.items())})")
    L.append(f"* **total ≈ {mass['total_g']:.1f} g**")
    L.append("")
    with open(path, "w") as fh:
        fh.write("\n".join(L))
    return ok


def export_all(m, out, views=True, step=True):
    os.makedirs(out, exist_ok=True)
    print("exporting ...")
    cq.exporters.export(cq.Workplane().add(m.shell), os.path.join(out, "mcring_stage1_shell.stl"), exportType="STL", tolerance=0.02, angularTolerance=0.15)
    cq.exporters.export(cq.Workplane().add(m.lid), os.path.join(out, "mcring_stage1_lid.stl"), exportType="STL", tolerance=0.02, angularTolerance=0.15)
    cq.exporters.export(cq.Workplane().add(m.key), os.path.join(out, "mcring_stage1_key.stl"), exportType="STL", tolerance=0.02, angularTolerance=0.15)
    parts = [m.shell, m.lid] + [v for k, v in m.placeholders.items()]
    comp = cq.Compound.makeCompound(parts)
    if step:
        cq.exporters.export(cq.Workplane().add(comp), os.path.join(out, "mcring_stage1_assembly.step"), exportType="STEP")
    if views:
        import cairosvg
        # The SVG exporter chooses the in-plane axes itself, so every view is rotated into a top view
        # (image right = +X', image up = +Y') before projecting along +Z'.
        O, X, Y, Z = V(0, 0, 0), V(1, 0, 0), V(0, 1, 0), V(0, 0, 1)
        front = comp.rotate(O, Y, -90).rotate(O, Z, -90)                 # viewer at +X: right = +Y, up = +Z
        half = comp.intersect(box(-60, 60, 0, 60, -60, 60))               # keep Y > 0, look from -Y at the Y = 0 cut
        section = half.rotate(O, X, -90)                                  # right = +X (pod), up = +Z
        views_ = [
            ("view_top", comp, "top view: lid with mic port, LED ring and touch dimple; pod at +X (right), switch side at -Y (bottom)"),
            ("view_front", front, "front view along the camera axis: lens bore, pod, signet over the band, Z up"),
            ("view_section", section, "section through the camera axis (Y = 0): bore, head + barrel + folded FPC, cell pocket, board, module, antenna cavity, lid"),
        ]
        for name, shape, _ in views_:
            svg = os.path.join(out, f"{name}.svg")
            cq.exporters.export(cq.Workplane().add(shape), svg, exportType="SVG",
                                opt={"projectionDir": (0, 0, 1), "width": 900, "height": 700, "showHidden": False,
                                     "strokeWidth": 0.4, "marginLeft": 20, "marginTop": 20, "showAxes": False})
            cairosvg.svg2png(url=svg, write_to=os.path.join(out, f"{name}.png"), output_width=1400, background_color="white")


# ----------------------------------------------------------------------------------------------
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--inner-d", type=float, default=None, help="finger diameter, mm (default 20.0)")
    ap.add_argument("--lens-d", type=float, default=None, help="lens bore, mm (default 4.6; 3.5 for the HM01B0 module)")
    ap.add_argument("--params", default=PARAMS_JSON)
    ap.add_argument("--out", default=OUT_DIR)
    ap.add_argument("--no-views", action="store_true")
    ap.add_argument("--no-step", action="store_true")
    args = ap.parse_args(argv)
    p = default_params()
    if args.inner_d:
        p["inner_d"] = args.inner_d
    if args.lens_d:
        p["lens_d"] = args.lens_d
    bp = load_board_params(args.params)
    t0 = time.time()
    m = Model(p, bp)
    m.build_shell()
    m.build_lid()
    m.build_key()
    m.build_placeholders()
    f = m.fit_check()
    ok = write_report(m, os.path.join(HERE, "fit_report.md"), args)
    env, mass = m.envelope(), m.mass()
    print(f"placeholder∩shell: " + ", ".join(f"{k}={v:.3f}" for k, v in f["shell"].items()))
    print(f"placeholder∩lid:   " + ", ".join(f"{k}={v:.3f}" for k, v in f["lid"].items()))
    bad = [(k, v) for k, v in f["pairs"].items() if v > 1e-6]
    print(f"pairs non-zero: {bad if bad else 'none'};  lid∩shell = {f['lid_vs_shell']:.4f}")
    for name, v, want in f["clearances"]:
        print(f"  clear {'ok ' if v + 1e-3 >= want else 'LOW'} {v:5.2f} >= {want:5.2f}  {name}")
    for name, t, want, okp in f["probes"]:
        print(f"  probe {'ok ' if okp else 'LOW'} {t:5.2f} >= {want:4.2f}  {name}")
    c = f["contact"]
    print(f"finger contact: top X {c['top']}, bottom X {c['bottom']}")
    print(f"envelope: band OD {env['band_od']:.1f}, lid top {env['height_above_skin']:.2f} / pod roof {env['pod_above_skin']:.2f} above skin, "
          f"bay {env['bay_footprint'][0]:.1f} x {env['bay_footprint'][1]:.1f}, length incl. pod {env['length_with_pod']:.1f}")
    print(f"mass: resin {mass['resin_g']:.1f} g + components {mass['components_g']:.1f} g = {mass['total_g']:.1f} g")
    export_all(m, args.out, views=not args.no_views, step=not args.no_step)
    print(f"{'FIT CHECK PASS' if ok else 'FIT CHECK FAIL'}  ({time.time() - t0:.1f} s)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
