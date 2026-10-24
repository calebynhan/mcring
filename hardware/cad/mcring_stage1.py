#!/usr/bin/env python3
"""mcring stage-1 ring enclosure — parametric CadQuery model.

Reads  hardware/pcb/board_params.json  (board size, part positions, stack, pod) and builds
  * the printable SHELL  (band + signet bay + camera pod, one SLA part)
  * the printable LID    (rebated plate with a detent bead, Ø0.8 mic port, LED window, touch dimple)
  * PLACEHOLDER solids   (PCB, ESP32-S3-MINI-1U, OV2640 head + barrel, cell, LRA, switch, LED, mic, FPC1)
then runs a programmatic fit check (pairwise intersections must be 0, wall probes), prints the
envelope and a mass estimate, writes fit_report.md and exports STL / STEP / SVG+PNG views.

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
COMPONENT_MASS_G = {"module": 1.5, "cell": 0.9, "LRA": 1.2, "PCB": 0.5, "camera": 0.6, "misc": 0.5}


# ----------------------------------------------------------------------------------------------
# parameters
# ----------------------------------------------------------------------------------------------
def default_params():
    return dict(
        inner_d=20.0,          # finger diameter (US 10 ≈ 19.8 + comfort)
        band_w=12.0,           # band width along the finger
        band_wall=1.2,         # band wall, also the floor under the cell pocket and the pod
        head_drop=3.0,         # the signet slab reaches down to Z = R - head_drop beside the finger
        bay_clear=0.3,         # board edge -> bay interior wall
        bay_wall=1.2,          # bay wall
        lid_t=1.2,             # lid plate
        lid_clear=0.15,        # lid -> rebate
        lid_rebate=0.5,        # rebate width in the wall top (lid rests on it, 1.2 deep)
        bead_r=0.25,           # detent bead on the lid's long edges (groove r = bead_r + 0.05)
        cell=(10.0, 12.0, 3.0),    # 301012 cell placed 10 along X, 12 across (Y), 3 thick
        cell_pocket=(10.4, 12.4, 3.4),
        cell_cx=-2.8,          # pocket centre along the finger (negative = toward the antenna end)
        lra_d=8.0, lra_h=2.5, lra_pocket_clear=0.2, lra_pocket_depth=2.9,
        lra_xy=(7.8, 3.5),     # LRA pocket centre (under the mic / away from the touch pad)
        lens_d=4.6,            # lens bore (OV2640 barrel 4.5)
        pod_bottom_drop=1.5,   # pod block bottom at Z = R - pod_bottom_drop
        switch_slot=(3.4, 1.6),
        pad_window=(4.0, 3.0), # charging pad window: 4 along X, 3 around the band
        pad_angle=25.0,        # ± from the bottom
        pad_rib_w=1.8, pad_rib_h=0.7, pad_groove_w=0.9, pad_groove_d=0.5,
        led_mark_d=3.0,        # engraved ring marking the LED window (wall stays lid_t over the LED)
        touch_dimple=(4.0, 5.0, 0.4),
        mic_hole_d=0.8,
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
        # vertical stack (absolute Z)
        self.z_pocket_bot = R + p["band_wall"]
        self.z_floor = self.z_pocket_bot + p["cell_pocket"][2]
        self.z_board_bot = self.z_floor + st["cell_clearance"] + bp["bottom_max_height_mm"]
        self.z_board_top = self.z_board_bot + self.T
        self.z_lid_bot = self.z_board_top + bp["top_max_height_mm"] + st["lid_clearance"]
        self.z_top = self.z_lid_bot + p["lid_t"]
        self.z_slab0 = R - p["head_drop"]
        # bay footprint
        c, w = p["bay_clear"], p["bay_wall"]
        self.Li, self.Wi = self.L + 2 * c, self.W + 2 * c
        self.Lo, self.Wo = self.Li + 2 * w, self.Wi + 2 * w
        self.ri = bp["corner_radius_mm"] + c
        self.ro = self.ri + w
        # camera pod (in front of the bay, +X)
        self.pod_depth_int = pod["interior_depth_from_board_edge"]
        self.pod_wi = pod["interior_width"]
        self.pod_wall = pod["wall"]
        self.pod_x_in0 = self.Li / 2                      # bay interior front wall
        self.pod_x_in1 = self.pod_x_in0 + self.pod_depth_int
        self.pod_x_out = self.pod_x_in1 + self.pod_wall
        self.pod_z_floor = R + p["band_wall"]
        self.pod_z_ceil = self.z_lid_bot
        self.lens_z = R + pod["lens_axis_z"]
        self.z_pod_bot = R - p["pod_bottom_drop"]
        # misc
        self.sw_x = self.bx(bp["switch_offset_mm"])
        self.led = (self.bx(bp["led_xy_mm"][0]), self.by(bp["led_xy_mm"][1]))
        self.mic = (self.bx(bp["mic_xy_mm"][0]), self.by(bp["mic_xy_mm"][1]))
        self.tpad = (self.bx(bp["touchpad_xy_mm"][0]), self.by(bp["touchpad_xy_mm"][1]))
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
        # 2. signet slab (bay body), fillet on the outer vertical edges = ro, soft bottom edge
        slab = rbox(self.Lo, self.Wo, self.z_top - self.z_slab0, self.ro, 0, 0, self.z_slab0)
        slab = try_fillet(slab, "<Z", 1.5, "slab bottom")
        # 3. camera pod block
        pod_x0 = self.Lo / 2 - 0.75
        pod_l = self.pod_x_out - pod_x0
        pod_w = self.pod_wi + 2 * self.pod_wall
        pod = rbox(pod_l, pod_w, self.z_top - self.z_pod_bot, 1.5, pod_x0 + pod_l / 2, 0, self.z_pod_bot)
        pod = try_fillet(pod, "<Z", 1.0, "pod bottom")
        # 4. charging-pad wire ribs on the outside of the band (one per pad, both end on the -Y side)
        r0, r1 = R + wall, R + wall + p["pad_rib_h"]
        self.rib_x = (+2.5, -4.5)          # rib / groove centre along X (A: -Y pad, B: +Y pad)
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
        # bay cavity + lid rebate
        cuts.append(rbox(self.Li, self.Wi, self.z_top - self.z_floor + 1, self.ri, 0, 0, self.z_floor))
        reb = p["lid_rebate"]
        cuts.append(rbox(self.Li + 2 * reb, self.Wi + 2 * reb, p["lid_t"] + 1, self.ri + reb, 0, 0, self.z_lid_bot))
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
        # camera pod interior (also opens the bay front wall for the FPC) and the lens bore
        cuts.append(box(self.pod_x_in0 - 0.01, self.pod_x_in1, -self.pod_wi / 2, self.pod_wi / 2, self.pod_z_floor, self.pod_z_ceil))
        cuts.append(cyl_x(p["lens_d"] / 2, self.pod_x_in1 - 0.5, self.pod_x_out + 1, 0, self.lens_z))
        # side-switch slot through the left (-Y) wall
        sl, sh = p["switch_slot"]
        yw = -(self.Wi / 2)
        sz = self.z_board_top + 0.6
        cuts.append(box(self.sw_x - sl / 2, self.sw_x + sl / 2, yw - self.p["bay_wall"] - 1, yw + 0.3, sz - sh / 2, sz + sh / 2))
        # charging-pad windows through the inner band, ±pad_angle from the bottom
        pw = p["pad_window"]
        win_x = (self.rib_x[0], self.rib_x[1])
        for ang, wx in ((-p["pad_angle"], win_x[0]), (+p["pad_angle"], win_x[1])):
            b = cq.Solid.makeBox(pw[0], pw[1], 4.0, V(wx - pw[0] / 2, -pw[1] / 2, -(R + 3.0)))
            cuts.append(b.rotate(V(0, 0, 0), V(1, 0, 0), ang))
        # wire grooves in the ribs + slanted channels through the slab into the sub-board cavity
        gr0, gr1 = r1 - p["pad_groove_d"], r1 + 0.5
        for wx, phi_end in ((self.rib_x[0], phiA), (self.rib_x[1], phiB)):
            cuts.append(sector_x(gr0, gr1, self.phi_slab - 6, phi_end, wx - p["pad_groove_w"] / 2, wx + p["pad_groove_w"] / 2))
            ph = math.radians(self.phi_slab - 3)
            rm = (gr0 + r1) / 2
            p0 = (wx, -rm * math.sin(ph), rm * math.cos(ph))
            p1 = (wx, -(self.Wi / 2 - 0.8), self.z_floor + 0.4)
            cuts.append(cyl_between(0.5, p0, p1))
        # finger bore with 0.5 mm chamfers on every exposed inner edge
        cuts.append(cyl_x(R, -40, 40, 0, 0))
        ch = 0.5
        cone = lambda x, d: cq.Solid.makeCone(R + ch, R, ch, V(x, 0, 0), V(d, 0, 0))
        cuts.append(cone(-self.Lo / 2, +1))                                       # slab back face
        cuts.append(cone(self.pod_x_out, -1))                                     # pod front face
        cuts.append(cone(self.Lo / 2, -1).intersect(box(0, 30, -30, -pod_w / 2, -30, 30)))   # slab front face
        cuts.append(cone(self.Lo / 2, -1).intersect(box(0, 30, pod_w / 2, 30, -30, 30)))
        for sx in (+1, -1):                                                       # band faces (below the slab)
            cuts.append(cone(sx * p["band_w"] / 2, -sx).intersect(box(-30, 30, -30, 30, -30, self.z_slab0 - 0.01)))

        shell = body
        for c_ in cuts:
            shell = shell.cut(c_)
        shell = shell.clean()

        # ---- board ledges (added after the cavity cut): front (two blocks clear of the bottom parts), back (full width)
        zb = self.z_board_bot
        f0, f1 = self.bx(0.7), self.Li / 2 + 0.01
        ledges = [
            box(f0, f1, -self.Wi / 2 - 0.01, self.by(2.6), self.z_floor - 0.01, zb),
            box(f0, f1, self.by(8.4), self.Wi / 2 + 0.01, self.z_floor - 0.01, zb),
            box(-self.Li / 2 - 0.01, self.bx(23.6), -self.Wi / 2 - 0.01, self.Wi / 2 + 0.01, self.z_floor - 0.01, zb),
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
        l, w = self.Li + 2 * reb - 2 * cl, self.Wi + 2 * reb - 2 * cl
        lid = rbox(l, w, p["lid_t"], self.ri + reb - cl, 0, 0, self.z_lid_bot)
        gz = self.z_lid_bot + p["lid_t"] / 2
        for sy in (+1, -1):
            lid = lid.fuse(cyl_x(p["bead_r"], -9.0, 9.0, sy * w / 2, gz))
        # mic port straight above the T3902 port
        lid = lid.cut(cyl_z(p["mic_hole_d"] / 2, self.z_lid_bot - 1, self.z_top + 1, *self.mic))
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
        ufl = box(self.bx(self.L - 0.2), self.bx(self.L - 0.2) + 2.5, self.by(3.2), self.by(5.7), zt, zt + bp["ufl_mated_height_mm"])
        ph["module"] = mod.fuse(ufl).clean()
        pod = bp["pod_mm"]
        hs, ht, bl, bd = pod["head_square"], pod["head_thickness"], pod["barrel_length"], pod["lens_barrel_d"]
        x_barrel_front = self.pod_x_in1 - 0.1
        barrel = cyl_x(bd / 2, x_barrel_front - bl, x_barrel_front, 0, self.lens_z)
        head = box(x_barrel_front - bl - ht, x_barrel_front - bl, -hs / 2, hs / 2, self.lens_z - hs / 2, self.lens_z + hs / 2)
        ph["camera"] = head.fuse(barrel).clean()
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
        ph["LED"] = box(self.led[0] - 1, self.led[0] + 1, self.led[1] - 1, self.led[1] + 1, zt, zt + 0.9)
        ph["mic"] = box(self.mic[0] - 2.65 / 2, self.mic[0] + 2.65 / 2, self.mic[1] - 3.5 / 2, self.mic[1] + 3.5 / 2, zb - 0.98, zb)
        fc = bp["fpc_connector_mm"]
        ph["FPC1"] = box(self.bx(fc["x1"]), self.bx(fc["x0"]), self.by(fc["y0"]), self.by(fc["y1"]), zt, zt + fc["height"])
        self.placeholders = ph
        return ph

    # ------------------------------------------------------------------ checks
    def probe(self, p0, p1):
        """material thickness of the shell along the segment p0 -> p1 (thin cylinder intersection)."""
        r = 0.02
        c = cyl_between(r, p0, p1)
        return self.shell.intersect(c).Volume() / (math.pi * r * r)

    def fit_check(self):
        print("fit check ...")
        res = {"shell": {}, "lid": {}, "pairs": {}, "probes": []}
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
        rib_a = self.rib_x[0]
        probes = [
            ("floor under the cell pocket (X=cell centre, Y=0)", (cx, 0, R - 0.5), (cx, 0, self.z_pocket_bot + 0.5), 1.2),
            ("floor under the LRA pocket (centre)", (lx, ly, R - 1), (lx, ly, zf - p["lra_pocket_depth"] + 0.3), 1.2),
            ("band wall at the bottom (X=0)", (0, 0, -R - 2), (0, 0, -R + 0.5), 1.2),
            ("band wall at 100 deg, beside the ribs (X=0)", (0, -(R - 0.5) * math.sin(phi), (R - 0.5) * math.cos(phi)),
             (0, -(R + 3) * math.sin(phi), (R + 3) * math.cos(phi)), 1.2),
            ("band + rib under the pad-wire groove A (100 deg)", (rib_a, -(R - 0.5) * math.sin(phi), (R - 0.5) * math.cos(phi)),
             (rib_a, -(R + 3) * math.sin(phi), (R + 3) * math.cos(phi)), 1.2),
            ("bay long wall (X=0, Z=board top+1)", (0, self.Wi / 2 - 1, self.z_board_top + 1), (0, self.Wo / 2 + 1, self.z_board_top + 1), 1.2),
            ("bay long wall rim at the lid groove (X=0)", (0, self.Wi / 2 - 1, self.z_lid_bot + p["lid_t"] / 2), (0, self.Wo / 2 + 1, self.z_lid_bot + p["lid_t"] / 2), 0.35),
            ("bay long wall rim beyond the groove (X=12)", (12, self.Wi / 2 - 1, self.z_lid_bot + p["lid_t"] / 2), (12, self.Wo / 2 + 1, self.z_lid_bot + p["lid_t"] / 2), 0.6),
            ("bay back wall (Y=0, Z=board top+1)", (-self.Li / 2 + 1, 0, self.z_board_top + 1), (-self.Lo / 2 - 1, 0, self.z_board_top + 1), 1.2),
            ("bay front wall beside the pod opening (Y=7)", (self.Li / 2 - 1, 7, self.z_board_top + 1), (self.Lo / 2 + 1, 7, self.z_board_top + 1), 1.2),
            ("pod side wall (X=18, lens height)", (18, self.pod_wi / 2 - 1, self.lens_z), (18, self.pod_wi / 2 + 3, self.lens_z), 1.2),
            ("pod front wall beside the lens bore (Y=3.5)", (self.pod_x_in1 - 1, 3.5, self.lens_z), (self.pod_x_out + 1, 3.5, self.lens_z), 1.2),
            ("pod floor (X=18, Y=0)", (18, 0, R - 1), (18, 0, self.pod_z_floor + 0.5), 1.2),
            ("pod roof (X=18, Y=0)", (18, 0, self.pod_z_ceil - 0.5), (18, 0, self.z_top + 1), 1.2),
            ("wall between the cell pocket and the LRA pocket", (cx + p["cell_pocket"][0] / 2 - 0.5, 2, zf - 1.5), (lx - p["lra_d"] / 2 - p["lra_pocket_clear"] + 0.5, 2, zf - 1.5), 0.8),
            ("left wall above the switch slot (X=switch)", (self.sw_x, -self.Wi / 2 + 0.5, self.z_board_top + 0.6 + 0.8 + 0.2), (self.sw_x, -self.Wo / 2 - 1, self.z_board_top + 0.6 + 0.8 + 0.2), 1.2),
        ]
        for name, a, b, want in probes:
            t = self.probe(a, b)
            res["probes"].append((name, t, want, t + 1e-3 >= want))
        self.fit = res
        return res

    def envelope(self):
        bb = self.shell.BoundingBox()
        band_od = 2 * (self.R + self.p["band_wall"])
        return dict(
            bbox=(bb.xmin, bb.xmax, bb.ymin, bb.ymax, bb.zmin, bb.zmax),
            band_od=band_od, band_od_at_ribs=band_od + 2 * self.p["pad_rib_h"],
            height_above_skin=self.z_top - self.R, lid_top_z=self.z_top,
            bay_footprint=(self.Lo, self.Wo), length_with_pod=self.pod_x_out + self.Lo / 2,
            signet_width=self.Wo,
        )

    def mass(self):
        vs, vl = self.shell.Volume(), self.lid.Volume()
        resin = (vs + vl) / 1000.0 * RESIN_G_PER_CC
        comp = sum(COMPONENT_MASS_G.values())
        return dict(shell_cc=vs / 1000, lid_cc=vl / 1000, resin_g=resin, components_g=comp, total_g=resin + comp)


# ----------------------------------------------------------------------------------------------
# report + exports
# ----------------------------------------------------------------------------------------------
def write_report(m, path, args):
    f = m.fit
    env, mass = m.envelope(), m.mass()
    ok_int = all(v < 1e-6 for v in f["shell"].values()) and all(v < 1e-6 for v in f["lid"].values()) \
        and all(v < 1e-6 for v in f["pairs"].values()) and f["lid_vs_shell"] < 1e-6
    ok_probe = all(p[3] for p in f["probes"])
    L = []
    L.append("# mcring stage-1 enclosure — fit report\n")
    L.append(f"Generated by `mcring_stage1.py` from `hardware/pcb/board_params.json` "
             f"(inner_d = {m.p['inner_d']} mm, lens_d = {m.p['lens_d']} mm). "
             f"Result: **{'PASS' if ok_int and ok_probe else 'FAIL'}** "
             f"(intersections {'all 0' if ok_int else 'NON-ZERO'}, wall probes {'ok' if ok_probe else 'BELOW MINIMUM'}).\n")
    L.append("## Stack (Z above the finger skin, mm)\n")
    R = m.R
    L.append("| level | z |\n|---|---|")
    for n, z in [("pocket / pod floor (band wall)", m.z_pocket_bot), ("sub-board floor (cell pocket top)", m.z_floor),
                 ("board bottom (ledges)", m.z_board_bot), ("board top", m.z_board_top), ("lens axis", m.lens_z),
                 ("lid underside", m.z_lid_bot), ("lid top = pod roof", m.z_top)]:
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
    L.append("## Wall probes (material thickness along a line through the shell, mm)\n")
    L.append("| where | measured | minimum | ok |\n|---|---|---|---|")
    for name, t, want, ok in f["probes"]:
        L.append(f"| {name} | {t:.2f} | {want:.2f} | {'yes' if ok else 'NO'} |")
    L.append("")
    L.append("## Envelope\n")
    bb = env["bbox"]
    L.append(f"* bounding box (X along the finger, Y across, Z up): {bb[0]:.1f}..{bb[1]:.1f} × {bb[2]:.1f}..{bb[3]:.1f} × {bb[4]:.1f}..{bb[5]:.1f} mm "
             f"→ {bb[1]-bb[0]:.1f} × {bb[3]-bb[2]:.1f} × {bb[5]-bb[4]:.1f} mm")
    L.append(f"* band OD {env['band_od']:.1f} mm (inner {m.p['inner_d']:.1f}, wall {m.p['band_wall']:.1f}); {env['band_od_at_ribs']:.1f} across the pad-wire ribs")
    L.append(f"* signet (bay) footprint {env['bay_footprint'][0]:.1f} × {env['bay_footprint'][1]:.1f} mm, height above the skin {env['height_above_skin']:.2f} mm "
             f"(lid top), {env['length_with_pod']:.1f} mm long along the finger including the camera pod")
    L.append("")
    L.append("## Mass estimate\n")
    L.append(f"* shell {mass['shell_cc']:.2f} cm³ + lid {mass['lid_cc']:.2f} cm³ of resin at {RESIN_G_PER_CC} g/cm³ = **{mass['resin_g']:.1f} g**")
    L.append(f"* components {mass['components_g']:.1f} g ({', '.join(f'{k} {v}' for k, v in COMPONENT_MASS_G.items())})")
    L.append(f"* **total ≈ {mass['total_g']:.1f} g**")
    L.append("")
    with open(path, "w") as fh:
        fh.write("\n".join(L))
    return ok_int and ok_probe


def export_all(m, out, views=True, step=True):
    os.makedirs(out, exist_ok=True)
    print("exporting ...")
    cq.exporters.export(cq.Workplane().add(m.shell), os.path.join(out, "mcring_stage1_shell.stl"), exportType="STL", tolerance=0.02, angularTolerance=0.15)
    cq.exporters.export(cq.Workplane().add(m.lid), os.path.join(out, "mcring_stage1_lid.stl"), exportType="STL", tolerance=0.02, angularTolerance=0.15)
    parts = [m.shell, m.lid] + list(m.placeholders.values())
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
            ("view_section", section, "section through the camera axis (Y = 0): bore, head + barrel, cell pocket, board, module, lid"),
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
    m.build_placeholders()
    f = m.fit_check()
    ok = write_report(m, os.path.join(HERE, "fit_report.md"), args)
    env, mass = m.envelope(), m.mass()
    print(f"placeholder∩shell: " + ", ".join(f"{k}={v:.3f}" for k, v in f["shell"].items()))
    print(f"placeholder∩lid:   " + ", ".join(f"{k}={v:.3f}" for k, v in f["lid"].items()))
    bad = [(k, v) for k, v in f["pairs"].items() if v > 1e-6]
    print(f"pairs non-zero: {bad if bad else 'none'};  lid∩shell = {f['lid_vs_shell']:.4f}")
    for name, t, want, okp in f["probes"]:
        print(f"  probe {'ok ' if okp else 'LOW'} {t:5.2f} >= {want:4.2f}  {name}")
    print(f"envelope: band OD {env['band_od']:.1f}, height above skin {env['height_above_skin']:.2f}, bay {env['bay_footprint'][0]:.1f} x {env['bay_footprint'][1]:.1f}, "
          f"length incl. pod {env['length_with_pod']:.1f}")
    print(f"mass: resin {mass['resin_g']:.1f} g + components {mass['components_g']:.1f} g = {mass['total_g']:.1f} g")
    export_all(m, args.out, views=not args.no_views, step=not args.no_step)
    print(f"{'FIT CHECK PASS' if ok else 'FIT CHECK FAIL'}  ({time.time() - t0:.1f} s)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
