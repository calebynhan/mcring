#!/usr/bin/env python3
"""mcring stage-1 ring enclosure — parametric CadQuery model.

Reads  hardware/pcb/board_params.json  (board size, part positions, stack, pod, antenna cavity, speaker, plug-in
connectors + edge notches, cell lead channel, floor wire groove, front-ledge gap) and builds
  * the printable SHELL  (band + signet bay + camera pod + the optional speaker pocket in the +Y wall, one SLA part)
  * the printable LID    (rebated plate with a detent bead, Ø0.8 mic port + tube, LED window, touch dimple, and the
                          tab + boss that close the speaker slot)
  * the printable KEY    (side-switch button: flange + pin + cap)
  * PLACEHOLDER solids   (PCB, ESP32-S3-MINI-1U, OV2640 head + barrel + folded FPC, cell, LRA, switch, LED,
                          mic, FPC1, bottom-side parts, top-side parts incl. the four Pico-EZmate headers and their
                          mated plugs over the edge notches, flex antenna + u.FL pigtail, speaker LS1)
then runs a programmatic fit check (pairwise intersections must be 0, clearances, wall probes, finger-contact
scan), prints the envelope and a mass estimate, writes fit_report.md and exports STL / STEP / SVG+PNG views.

World frame (mm):  X along the finger, +X toward the fingertip (camera / front);
                   Y across the finger, +Y = board +y (switch edge is -Y);
                   Z up (top of the hand), Z = 0 on the finger axis.  Skin top at Z = inner_d/2.
Board frame (board_params.json): bx from the front edge (0) to the back (L); by from the left (switch) edge.
    X = L/2 - bx,  Y = by - W/2   (board centred on the ring axis along the finger).

Run:  python3 hardware/cad/mcring_stage1.py [--inner-d 20.0] [--lens-d 4.6] [--no-speaker] [--no-views] [--no-step]
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
COMPONENT_MASS_G = {"module": 1.5, "cell": 0.9, "LRA": 1.2, "PCB": 0.6, "camera": 0.6, "antenna": 0.2, "connectors+pigtails": 0.4, "misc": 0.5}


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
        rib_x=(-1.5, -3.5),    # rib / groove / channel centres along X (A: -Y pad, B: +Y pad); the channels surface
                               # beside the -Y wall at board x 14.75 / 16.75, where the floor groove to J3 starts
        pad_rib_w=2.0, pad_rib_h=0.7, pad_groove_w=1.1, pad_groove_d=0.5,
        wire_r=0.55,           # wire channel radius: Ø1.1 for the 28 AWG Pico-EZmate pigtail (<= 1.0 mm OD); JSON
                               # pad_wire_channel_d_mm overrides
        front_ledge_gap=(2.6, 8.4),   # board y range left open between the two front ledges (JSON front_ledge_gap_y_mm overrides)
        cell_lead_channel=(3.0, 0.8), # cell-tab channel from the pocket edge to the wall: width (X), depth; JSON overrides
        floor_groove=True,     # cut the charging-wire groove in the sub-board floor when the JSON describes one
        led_mark_d=3.0,        # engraved ring marking the LED window (wall stays lid_t over the LED)
        touch_dimple=(4.0, 5.0, 0.4),
        mic_hole_d=0.8,
        mic_tube_od=1.8,       # tube under the lid hole down to the board (closes the bay off the mic port)
        mic_tube_gap=0.3,      # tube end -> board top (foam / adhesive gasket)
        antenna=(15.0, 5.0, 0.25),   # flex PCB antenna placeholder (Y, Z, X) glued to the back wall
        pigtail_d=0.9,         # u.FL pigtail (U.FL-LP-040, Ø0.81 cable)
        # optional on-ring speaker: WHAT and WHERE come from board_params.json speaker_mm (Ø, thickness, centre,
        # pocket clearance, grille wall); these are the pocket's print details
        speaker=True,          # build the pocket when speaker_mm exists (--no-speaker turns it off)
        spk_depth_slack=0.3,   # pocket depth = speaker thickness + this
        spk_back_seat=0.1,     # of which: behind the back face (the rest, 0.2, in front of the diaphragm)
        spk_grille=dict(hole_d=1.0, ring_r=2.5, n=4),   # centre hole + n holes on a ring, through the grille plate
        spk_lead_groove=(6.0, 1.0),   # lead relief in the pocket's back wall below the sub-board floor: width (X), depth (-Y)
        spk_bump_r=1.0,        # vertical outer corners of the wall bump (<= 1.2 keeps the end walls >= the grille wall)
        spk_bump_bottom_r=0.6, # bottom edge of the bump (<= 0.6 keeps the diagonal at the pocket's front-bottom edge >= 1.2)
        spk_tab_clear=0.3,     # lid tab -> bump end walls (X); its outer face keeps lid_clear to the bump face
        spk_boss_clear=(0.3, 0.3),   # lid boss -> slot walls (X, Y)
        spk_boss_gap=0.2,      # lid boss underside -> speaker rim
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


def cyl_y(r, y0, y1, x, z):
    return cq.Solid.makeCylinder(r, y1 - y0, V(x, y0, z), V(0, 1, 0))


def cyl_z(r, z0, z1, x, y):
    return cq.Solid.makeCylinder(r, z1 - z0, V(x, y, z0), V(0, 0, 1))


def u_slot_y(r, x, zc, z_top, y0, y1):
    """U-shaped slot along Y (a drop-in pocket for a disc standing in the XZ plane): semicircle of radius r below the
    axis (x, zc), straight walls from the axis up to z_top; from y0 to y1."""
    prof = (cq.Workplane("XZ").moveTo(x - r, zc).lineTo(x - r, z_top).lineTo(x + r, z_top).lineTo(x + r, zc)
            .threePointArc((x, zc - r), (x - r, zc)).close())
    return prof.extrude((y1 - y0) / 2, both=True).val().translate(V(0, (y0 + y1) / 2, 0))


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
        # design-for-assembly inputs (floorplan.py writes them; older JSONs fall back to the script defaults)
        self.wire_r = bp.get("pad_wire_channel_d_mm", 2 * p["wire_r"]) / 2
        self.ledge_gap = tuple(bp.get("front_ledge_gap_y_mm", p["front_ledge_gap"]))
        self.conns = bp.get("connectors_top_mm", {})          # ref -> header/plug/notch geometry (board frame)
        self.cell_tab_edge = bp.get("cell_tab_edge", "-y")
        self.cell_chan = bp.get("cell_lead_channel_mm")
        self.groove = bp.get("floor_wire_groove_mm") if p["floor_groove"] else None
        self.notch_probe_pts = {}
        # optional speaker (speaker_mm): a Ø d x t disc standing in the +Y (right) signet wall, grille facing +Y.
        # The pocket is a U-slot (semicircle below the speaker axis, straight walls above it up to the lid's underside) so
        # the speaker drops in from the top before the lid goes on; the lid's tab + boss close the slot.
        self.spk = None
        sp = bp.get("speaker_mm")
        if p["speaker"] and sp:
            if sp.get("location", "signet_right_wall") != "signet_right_wall" or sp.get("grille_normal_board", [0, 1, 0]) != [0, 1, 0]:
                raise SystemExit(f"speaker_mm: only location 'signet_right_wall' with grille normal +y is modelled "
                                 f"(got {sp.get('location')!r}, {sp.get('grille_normal_board')!r})")
            d, t = sp["diameter"], sp["thickness"]
            cl_ = sp.get("pocket_clearance", 0.2)
            gw = sp.get("grille_wall", 1.0)
            cxb, cyb, czb = sp["centre_board_xyz_mm"]
            X, Y, Z = self.bx(cxb), self.by(cyb), self.z_board_top + czb
            rp = d / 2 + cl_
            y_back = Y - t / 2 - p["spk_back_seat"]
            y_front = y_back + t + p["spk_depth_slack"]
            y_out = y_front + gw
            self.spk = dict(d=d, t=t, cl=cl_, gw=gw, X=X, Y=Y, Z=Z, rp=rp, depth=y_front - y_back,
                            y_back=y_back, y_front=y_front, y_out=y_out, x0=X - rp, x1=X + rp,
                            bx0=X - rp - p["bay_wall"], bx1=X + rp + p["bay_wall"], bump=y_out - self.Wo / 2,
                            z_bot=Z - rp, mass=sp.get("mass_g", 1.0), part=sp.get("part", "10 mm 8 ohm micro speaker"),
                            board=(cxb, cyb, czb))
            s = self.spk
            if abs(s["bump"] - sp.get("signet_right_face_bump_mm", s["bump"])) > 0.01:
                print(f"  NOTE board_params speaker_mm.signet_right_face_bump_mm = {sp['signet_right_face_bump_mm']} but the pocket "
                      f"geometry gives {s['bump']:.2f} (seat {p['spk_back_seat']} + {t} + {p['spk_depth_slack'] - p['spk_back_seat']:.1f} + grille {gw})")
            if s["z_bot"] - self.z_slab0 < p["bay_wall"] - 1e-6:
                print(f"  NOTE speaker pocket bottom is only {s['z_bot'] - self.z_slab0:.2f} above the slab bottom (< {p['bay_wall']})")
            if s["bx0"] < self.x_back_out + self.ro or s["bx1"] > self.Lo / 2 - self.ro:
                print(f"  NOTE speaker bump X {s['bx0']:.1f}..{s['bx1']:.1f} runs into the slab's rounded corners")
            if Z + d / 2 + p["spk_boss_gap"] > self.z_lid_bot - 1e-6:
                print(f"  NOTE speaker top {Z + d / 2:.2f} is too close to the lid underside {self.z_lid_bot:.2f} for the lid boss")

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
        # 2b. speaker bump: the +Y wall grows by `bump` over the pocket + its two end walls, full slab height (its top is
        #     lowered to the lid underside later). It reaches slab_fillet into the slab so its own flat bottom replaces
        #     the slab's bottom fillet over this length; its outer vertical corners and bottom edge get small fillets.
        if self.spk:
            s = self.spk
            y_in = self.Wo / 2 - p["slab_fillet"]
            bump = rbox(s["bx1"] - s["bx0"], s["y_out"] - y_in, self.z_top - self.z_slab0, p["spk_bump_r"],
                        (s["bx0"] + s["bx1"]) / 2, (y_in + s["y_out"]) / 2, self.z_slab0)
            bump = try_fillet(bump, "<Z", p["spk_bump_bottom_r"], "speaker bump bottom")
            slab = slab.fuse(bump).clean()
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
        # cell pocket (recess in the sub-board floor) and its lead channel: with the tabs toward +Y (design for
        # assembly) the channel runs from the pocket's +Y edge to the bay wall under the J1 header, where the cell's
        # pigtail climbs the wall gap / edge notch; the legacy -Y layout ran it to the J1a wire pad
        cl, cw, ch = p["cell_pocket"]
        cx = p["cell_cx"]
        cuts.append(box(cx - cl / 2, cx + cl / 2, -cw / 2, cw / 2, self.z_floor - ch, self.z_floor + 0.5))
        if self.cell_tab_edge == "+y" and self.cell_chan:
            ccw, ccd = self.cell_chan.get("width", p["cell_lead_channel"][0]), self.cell_chan.get("depth", p["cell_lead_channel"][1])
            ccx = self.bx(self.cell_chan["at_board_x"])
            self.cell_chan_box = (ccx - ccw / 2, ccx + ccw / 2, cw / 2 - 0.5, self.Wi / 2 + 0.01, self.z_floor - ccd, self.z_floor + 0.5)
            cuts.append(box(*self.cell_chan_box))
        else:
            j1y = self.by(self.bp["wire_pads_bottom_mm"]["J1a"][1])
            self.cell_chan_box = (cx - 1.5, cx + 1.5, j1y - 0.6, -cw / 2 + 0.5, self.z_floor - 0.8, self.z_floor + 0.5)
            cuts.append(box(*self.cell_chan_box))
        # charging-wire groove in the sub-board floor (floorplan floor_wire_groove_mm): axis-aligned legs, each a box
        # width x depth below the floor; the corner squares come free from the overlapping boxes
        self.groove_boxes = []
        if self.groove:
            gw, gd = self.groove["width"], self.groove["depth"]
            pts = [(self.bx(x), self.by(y)) for x, y in self.groove["path"]]
            for (xa, ya), (xb, yb) in zip(pts, pts[1:]):
                b = (min(xa, xb) - gw / 2, max(xa, xb) + gw / 2, min(ya, yb) - gw / 2, max(ya, yb) + gw / 2,
                     self.z_floor - gd, self.z_floor + 0.5)
                self.groove_boxes.append(b)
                cuts.append(box(*b))
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
            cuts.append(cyl_between(self.wire_r, p0, p1))
        # speaker pocket in the +Y wall bump (speaker_mm): a U-slot Ø(d + 2 cl) about the speaker axis (along Y), straight
        # above the axis up to the lid underside so the speaker drops in from the top; depth t + 0.3. Above the sub-board
        # floor the slot's back is open to the bay (the lidded bay is the back volume and the leads pass straight through
        # to the SPK1 pads under the board); below the floor the pocket is a recess in the solid slab with a lead groove.
        # A grille of Ø1.0 holes goes through the +Y plate; the bump's top is cut down to the lid underside (shelf) so the
        # lid's tab + boss close the slot and hold the speaker.
        if self.spk:
            s = self.spk
            zf = self.z_floor
            pocket = u_slot_y(s["rp"], s["X"], s["Z"], self.z_lid_bot + 0.01, s["y_back"], s["y_front"])
            back = u_slot_y(s["rp"], s["X"], s["Z"], self.z_lid_bot + 0.01, self.Wi / 2 - 0.1, s["y_back"] + 0.01)
            back = back.intersect(box(-60, 60, -60, 60, zf, 60))
            cuts.append(pocket.fuse(back).clean())
            gwid, gdep = p["spk_lead_groove"]
            self.spk_groove = (s["X"] - gwid / 2, s["X"] + gwid / 2, s["y_back"] - gdep, s["z_bot"] + 1.0)
            cuts.append(box(self.spk_groove[0], self.spk_groove[1], self.spk_groove[2], s["y_back"] + 0.01, self.spk_groove[3], zf + 0.5))
            g = p["spk_grille"]
            self.spk_holes = [(s["X"], s["Z"])] + [
                (s["X"] + g["ring_r"] * math.cos(math.radians(45 + 360.0 * i / g["n"])),
                 s["Z"] + g["ring_r"] * math.sin(math.radians(45 + 360.0 * i / g["n"]))) for i in range(g["n"])]
            for hx, hz in self.spk_holes:
                cuts.append(cyl_y(g["hole_d"] / 2, s["y_front"] - 0.5, s["y_out"] + 1, hx, hz))
            cuts.append(box(s["bx0"] - 0.01, s["bx1"] + 0.01, self.Wi / 2 - 0.01, s["y_out"] + 1, self.z_lid_bot, self.z_top + 1))
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
            box(f0, f1, -self.Wi / 2 - 0.01, self.by(self.ledge_gap[0]), self.z_floor - 0.01, zb),
            box(f0, f1, self.by(self.ledge_gap[1]), self.Wi / 2 + 0.01, self.z_floor - 0.01, zb),
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
        # speaker: a tab over the +Y wall bump (it rests on the bump's shelf at the lid underside, lid_clear inside the
        # bump's face, spk_tab_clear from its end walls) and a boss under the tab that fills the slot above the speaker
        # (spk_boss_gap above its rim) - the lid closes the pocket and keeps the speaker down; no fourth printed part
        if self.spk:
            s = self.spk
            tc = p["spk_tab_clear"]
            y_tab_in = w / 2 - 1.0                       # 1 mm inside the lid plate (fused away)
            y_tab_out = s["y_out"] - cl
            tab = rbox(s["bx1"] - s["bx0"] - 2 * tc, y_tab_out - y_tab_in, p["lid_t"], max(p["spk_bump_r"] - cl - 0.15, 0.3),
                       (s["bx0"] + s["bx1"]) / 2, (y_tab_in + y_tab_out) / 2, self.z_lid_bot)
            bcx, bcy = p["spk_boss_clear"]
            self.spk_boss_z0 = s["Z"] + s["d"] / 2 + p["spk_boss_gap"]
            boss = box(s["x0"] + bcx, s["x1"] - bcx, s["y_back"] + bcy, s["y_front"] - bcy, self.spk_boss_z0, self.z_lid_bot + 0.01)
            self.spk_boss = (s["x0"] + bcx, s["x1"] - bcx, s["y_back"] + bcy, s["y_front"] - bcy)
            self.spk_tab = (s["bx0"] + tc, s["bx1"] - tc, y_tab_out)
            lid = lid.fuse(tab).fuse(boss)
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
        # the mated Pico-EZmate plug + the wire bend over each edge notch: from the header's +y end to just inside the
        # bay wall (the pigtail turns down there), mated height tall — must clear the lid, the mic tube and the wall
        plugs = []
        for ref, c in self.conns.items():
            pm = c["plug_mm"]
            plugs.append(box(self.bx(pm["x1"]), self.bx(pm["x0"]), self.by(pm["y0"]), min(self.by(pm["y1"]), self.Wi / 2 - 0.05),
                             zt, zt + pm["height"]))
        if plugs:
            ph["plugs"] = fuse_all(plugs)
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
        # optional speaker LS1: a Ø d x t disc standing in the +Y wall pocket (axis along Y, grille side +Y)
        if self.spk:
            s = self.spk
            ph["speaker"] = cyl_y(s["d"] / 2, s["Y"] - s["t"] / 2, s["Y"] + s["t"] / 2, s["X"], s["Z"])
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
        # the +Y long-wall probes move clear of the speaker pocket (X -10.4..0) when the speaker is built
        xw = 3.0 if self.spk else 0.0
        probes = [
            ("floor under the cell pocket (X=cell centre, Y=0)", (cx, 0, R - 0.5), (cx, 0, self.z_pocket_bot + 0.5), 1.2),
            ("floor under the cell pocket's back end (X=pocket back+0.3, Y=0)", (cx - p["cell_pocket"][0] / 2 + 0.3, 0, R - 0.5), (cx - p["cell_pocket"][0] / 2 + 0.3, 0, self.z_pocket_bot + 0.5), 1.2),
            ("floor under the LRA pocket (centre)", (lx, ly, R - 1), (lx, ly, zf - p["lra_pocket_depth"] + 0.3), 1.2),
            ("band wall at the bottom (X=0)", (0, 0, -R - 2), (0, 0, -R + 0.5), 1.2),
            ("band wall at 100 deg, beside the ribs (X=2)", (2, -(R - 0.5) * math.sin(phi), (R - 0.5) * math.cos(phi)),
             (2, -(R + 3) * math.sin(phi), (R + 3) * math.cos(phi)), 1.2),
            ("band + rib under the pad-wire groove A (100 deg)", (self.rib_x[0], -(R - 0.5) * math.sin(phi), (R - 0.5) * math.cos(phi)),
             (self.rib_x[0], -(R + 3) * math.sin(phi), (R + 3) * math.cos(phi)), 1.2),
            (f"bay long wall (+Y, X={xw:.0f}, Z=board top+1)", (xw, self.Wi / 2 - 1, self.z_board_top + 1), (xw, self.Wo / 2 + 1, self.z_board_top + 1), 1.2),
            (f"bay long wall rim at the lid groove (+Y, X={xw:.0f})", (xw, self.Wi / 2 - 1, self.z_lid_bot + p["lid_t"] / 2), (xw, self.Wo / 2 + 1, self.z_lid_bot + p["lid_t"] / 2), 0.35),
            ("bay long wall (-Y, X=0, Z=board top+1)", (0, -self.Wi / 2 + 1, self.z_board_top + 1), (0, -self.Wo / 2 - 1, self.z_board_top + 1), 1.2),
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
        # openings that must be open (material 0): pad windows
        opens = []
        for ang, wx in ((-p["pad_angle"], self.rib_x[0]), (+p["pad_angle"], self.rib_x[1])):
            a = math.radians(ang)
            opens.append((f"pad window {'A (-Y)' if ang < 0 else 'B (+Y)'} open at X={wx:+.1f}", (wx, *rad(R - 0.5, a)), (wx, *rad(R + 3, a))))
        # speaker pocket: clearances to the metal parts (antenna keep-out, cell), the pocket's own clearances, the walls
        # around the pocket (grille plate, end walls, floor, back wall to the cell pocket, bump corner), the lid tab + boss,
        # and the openings that must be open (grille holes, lead path to the SPK1 pads, slot up to the lid)
        if self.spk:
            s = self.spk
            spk = self.placeholders["speaker"].BoundingBox()
            ab = lambda bb: ((bb.xmin, bb.xmax), (bb.ymin, bb.ymax), (bb.zmin, bb.zmax))
            gap = lambda a, b: math.sqrt(sum(max(0.0, lo2 - hi1, lo1 - hi2) ** 2 for (lo1, hi1), (lo2, hi2) in zip(a, b)))
            keepout = self.bp.get("antenna_keepout_beyond_edge_mm", 5.0)
            gx, gz_, gy = s["X"], s["Z"], s["Y"]
            yb, yf, yo = s["y_back"], s["y_front"], s["y_out"]
            self.spk_antenna_gap = gap(ab(spk), ab(self.placeholders["antenna"].BoundingBox()))
            res["clearances"] += [
                ("speaker LS1 (NdFeB magnet) -> flex antenna, 3-D gap (metal keep-out)", self.spk_antenna_gap, keepout),
                ("speaker LS1 -> u.FL pigtail, 3-D gap", gap(ab(spk), ab(self.placeholders["pigtail"].BoundingBox())), keepout),
                ("speaker LS1 -> cell, 3-D gap (through the slab wall)", gap(ab(spk), ab(self.placeholders["cell"].BoundingBox())), 2.0),
                ("speaker LS1 -> LRA, 3-D gap", gap(ab(spk), ab(self.placeholders["LRA"].BoundingBox())), 2.0),
                ("speaker rim -> pocket wall (radial)", s["rp"] - s["d"] / 2, 0.15),
                ("speaker back face -> pocket back wall (below the floor)", spk.ymin - yb, 0.05),
                ("speaker front -> grille plate", yf - spk.ymax, 0.15),
                ("speaker top -> lid boss underside", self.spk_boss_z0 - spk.zmax, 0.15),
                ("lid boss -> slot end walls (X)", min(self.spk_boss[0] - s["x0"], s["x1"] - self.spk_boss[1]), 0.2),
                ("lid boss -> slot back / grille plate (Y)", min(self.spk_boss[2] - yb, yf - self.spk_boss[3]), 0.2),
                ("lid tab -> bump end walls (X)", min(self.spk_tab[0] - s["bx0"], s["bx1"] - self.spk_tab[1]), 0.2),
                ("lid tab outer face -> bump face (Y)", yo - self.spk_tab[2], p["lid_clear"] - 0.01),
            ]
            cw_ = p["cell_pocket"][1]
            probes += [
                (f"speaker grille plate between the holes (X=spk, Z=spk+2.5)", (gx, yf - 0.5, gz_ + 2.5), (gx, yo + 1, gz_ + 2.5), s["gw"]),
                (f"speaker grille plate between the holes (X=spk+3.5, Z=spk)", (gx + 3.5, yf - 0.5, gz_), (gx + 3.5, yo + 1, gz_), s["gw"]),
                ("slab under the speaker pocket (X=spk, Y=spk)", (gx, gy, self.z_slab0 - 1), (gx, gy, s["z_bot"] + 0.5), 1.2),
                ("bump end wall at the pocket's front (+X) end, speaker axis height", (s["x1"] - 0.5, gy, gz_), (s["x1"] + 2.5, gy, gz_), 1.2),
                ("bump end wall at the pocket's back (-X) end, speaker axis height", (s["x0"] + 0.5, gy, gz_), (s["x0"] - 2.5, gy, gz_), 1.2),
                ("bump end wall at the pocket's back (-X) end, slot top (Z=lid underside-0.5)", (s["x0"] + 0.5, gy, self.z_lid_bot - 0.5), (s["x0"] - 2.5, gy, self.z_lid_bot - 0.5), 1.2),
                ("bump bottom-front corner, diagonal from the pocket's front-bottom edge (X=spk)", (gx, yf - 0.3, s["z_bot"] + 0.3), (gx, yf + 2.7, s["z_bot"] - 2.7), 1.2),
                ("slab between the speaker pocket back and the cell pocket, through the lead groove (X=spk, Z=floor-1.5)", (gx, cw_ / 2 - 0.5, zf - 1.5), (gx, yb + 0.5, zf - 1.5), 1.2),
                ("slab between the speaker pocket back and the cell pocket, beside the groove (X=spk-4, Z=floor-1.5)", (gx - 4, cw_ / 2 - 0.5, zf - 1.5), (gx - 4, yb + 0.5, zf - 1.5), 1.2),
                ("slab behind the lead groove's bottom (X=spk, Y=spk back, Z=groove bottom-0.5 .. slab bottom)", (gx, (yb + self.spk_groove[2]) / 2, self.spk_groove[3] + 0.3), (gx, (yb + self.spk_groove[2]) / 2, self.z_slab0 - 1), 1.2),
                ("lid: tab + boss over the speaker (X=spk, Y=spk) (lid part)", (gx, gy, self.spk_boss_z0 - 0.5), (gx, gy, self.z_top + 1), 1.2, "lid"),
                ("lid: tab over the bump shelf (X=spk, Y=bump face-0.5) (lid part)", (gx, yo - 0.5, self.z_lid_bot - 0.5), (gx, yo - 0.5, self.z_top + 1), 1.2, "lid"),
            ]
            if "J5" in self.conns:
                n = self.conns["J5"]["notch"]
                px, py = self.bx(n["cx"]), self.Wi / 2 - 0.15
                opens.append(("speaker lead path: pocket back above the floor -> cavity under the J5 notch", (gx, gy - s['t'] / 2 - 0.05, zf + 0.7), (px, py, zf + 0.7)))
            else:
                pads = self.bp["wire_pads_bottom_mm"]
                for pad in ("SPK1a", "SPK1b"):
                    px, py = self.bx(pads[pad][0]), self.by(pads[pad][1])
                    opens.append((f"speaker lead path: pocket back above the floor -> {pad} under the board", (gx, gy - s['t'] / 2 - 0.05, zf + 0.7), (px, py, self.z_board_bot - 0.1)))
        # plug-in connectors: each pigtail drops from the header's plug, past the board edge (0.3 bay clearance + the
        # edge notch), into the sub-board cavity — the wall gap must be open from above the board to the floor
        for ref, c in self.conns.items():
            n = c["notch"]
            px, py = self.bx(n["cx"]), self.Wi / 2 - 0.15
            self.notch_probe_pts[ref] = (px, py)
            opens.append((f"{ref} pigtail drop beside the right board edge (notch at board x {n['cx']}): plug height -> floor", (px, py, self.z_board_top + c["mated_height"]), (px, py, zf + 0.2)))
        if self.cell_tab_edge == "+y" and self.cell_chan:
            b = self.cell_chan_box
            opens.append(("cell lead channel open from the pocket's +Y edge to the wall (under J1)", ((b[0] + b[1]) / 2, b[2] + 0.2, zf - 0.4), ((b[0] + b[1]) / 2, b[3] - 0.3, zf - 0.4)))
            probes.append(("floor under the cell lead channel (X=J1, Y=channel mid)", ((b[0] + b[1]) / 2, (b[2] + b[3]) / 2, zf - self.cell_chan.get("depth", 0.8) - 0.05), ((b[0] + b[1]) / 2, (b[2] + b[3]) / 2, self.z_slab0 - 1), 1.2))
        if self.groove:
            gd = self.groove["depth"]
            for i, b in enumerate(self.groove_boxes):
                xm, ym = (b[0] + b[1]) / 2, (b[2] + b[3]) / 2
                along_x = (b[1] - b[0]) > (b[3] - b[2])
                a0 = (b[0] + 0.3, ym, zf - gd / 2) if along_x else (xm, b[2] + 0.3, zf - gd / 2)
                a1 = (b[1] - 0.3, ym, zf - gd / 2) if along_x else (xm, b[3] - 0.3, zf - gd / 2)
                opens.append((f"floor wire groove leg {i + 1} open along its length", a0, a1))
                probes.append((f"floor under wire groove leg {i + 1} (mid-leg, down to the bore / slab bottom)", (xm, ym, zf - gd - 0.05), (xm, ym, self.R - 0.5 if abs(ym) < self.R - 1 else self.z_slab0 - 1), 1.2))
            opens.append(("speaker grille centre hole open (X=spk, Z=spk)", (gx, yf - 0.5, gz_), (gx, yo + 1, gz_)))
            opens.append(("speaker slot open from the speaker rim up to the lid underside (X=spk, Y=spk)", (gx, gy, spk.zmax + 0.05), (gx, gy, self.z_lid_bot - 0.05)))
            opens.append(("speaker lead groove open at the floor (X=spk, Y=groove centre)", (gx, (yb + self.spk_groove[2]) / 2, self.spk_groove[3] + 0.5), (gx, (yb + self.spk_groove[2]) / 2, zf + 0.3)))
        for pr_ in probes:
            name, a, b, want = pr_[:4]
            t = self.probe(a, b, self.lid if len(pr_) > 4 and pr_[4] == "lid" else None)
            res["probes"].append((name, t, want, t + 1e-3 >= want))
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
            signet_width=self.Wo, signet_width_at_speaker=(self.Wo + self.spk["bump"]) if self.spk else self.Wo,
        )

    def charging_wire_runs(self):
        """Length of each W2 wire from its band window to the J3 plug, along the modelled path and with no slack:
        the rib groove round the band (window centre -> where the slab channel starts), the slanted Ø1.1 channel
        through the slab, the floor groove (channel exit -> first leg -> the rest of the path to the J3 notch) and
        the climb from the groove bottom up the notch to the top of the mated header. Needs build_shell()."""
        if not (self.groove and self.chan):
            return {}
        p = self.p
        rg = self.R + p["band_wall"] + p["pad_rib_h"] - p["pad_groove_d"] / 2      # rib-groove centre radius
        path = [tuple(q) for q in self.groove["path"]]
        poly = lambda pts: sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))
        hdr = self.conns.get(self.groove.get("feeds", "J3"), {}).get("mated_height", 1.55)
        rise = (self.z_board_top + hdr) - (self.z_floor - self.groove["depth"])
        runs = {}
        for (wx, phi_end), name in zip(((self.rib_x[0], 180 - p["pad_angle"]), (self.rib_x[1], 180 + p["pad_angle"])),
                                       ("-Y pad (rib A)", "+Y pad (rib B, round the bottom)")):
            p0, p1 = self.chan[wx]
            phi0 = math.degrees(math.atan2(-p0[1], p0[2]))                          # channel start, from +Z
            arc = rg * math.radians(phi_end - phi0)
            chan = math.dist(p0, p1)
            ex, ey = self.L / 2 - wx, p1[1] + self.W / 2                            # channel exit in board xy
            floor = abs(path[0][1] - ey) + abs(ex - path[1][0]) + poly(path[1:])
            runs[name] = dict(arc=arc, channel=chan, floor=floor, rise=rise, total=arc + chan + floor + rise)
        return runs

    def component_masses(self):
        m = dict(COMPONENT_MASS_G)
        if self.spk:
            m["speaker"] = self.spk["mass"]
        return m

    def mass(self):
        vs, vl, vk = self.shell.Volume(), self.lid.Volume(), self.key.Volume()
        resin = (vs + vl + vk) / 1000.0 * RESIN_G_PER_CC
        comp = sum(self.component_masses().values())
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
             "open groove at the slab's bottom corner, the floor beside the charging-wire groove where it skims the cell- and LRA-pocket rims, "
             + (f"the 0.8 mm resin over the touch pad, and the {m.spk['gw']:.1f} mm speaker grille plate (the pocket's +Y face, "
                f"{len(m.spk_holes)} × Ø{m.p['spk_grille']['hole_d']:.1f} holes)." if m.spk else "and the 0.8 mm resin over the touch pad.") + "\n")
    L.append("## Stack (Z above the finger skin, mm)\n")
    R = m.R
    L.append("| level | z |\n|---|---|")
    rows = [("pocket floor (band wall)", m.z_pocket_bot), ("sub-board floor (cell pocket top)", m.z_floor),
            ("board bottom (ledges)", m.z_board_bot), ("board top", m.z_board_top),
            ("lid underside", m.z_lid_bot), ("lid top", m.z_top),
            (f"pod underside (bore relief {m.relief})", R + m.relief), ("pod floor", m.pod_z_floor),
            ("OV2640 head bottom / top", None), ("lens axis", m.lens_z),
            ("pod ceiling (head top + FPC fold)", m.pod_z_ceil), ("pod roof top", m.z_pod_roof)]
    if m.spk:
        s = m.spk
        rows += [("speaker pocket bottom (slab bottom + 1.3)", s["z_bot"]), ("speaker axis", s["Z"]),
                 ("speaker rim top / lid boss underside", (s["Z"] + s["d"] / 2, m.spk_boss_z0)),
                 ("speaker slot top = bump shelf = lid underside", m.z_lid_bot)]
    for n, z in rows:
        if z is None:
            L.append(f"| {n} | {m.head_z0 - R:.2f} / {m.head_z1 - R:.2f} |")
        elif isinstance(z, tuple):
            L.append(f"| {n} | {z[0] - R:.2f} / {z[1] - R:.2f} |")
        else:
            L.append(f"| {n} | {z - R:.2f} |")
    L.append("")
    if m.spk:
        s = m.spk
        g = m.p["spk_grille"]
        open_area = len(m.spk_holes) * math.pi * (g["hole_d"] / 2) ** 2
        lead = []
        if "J5" in m.conns:
            px, py = m.notch_probe_pts["J5"]
            lead.append(math.dist((s["X"], s["Y"] - s["t"] / 2, m.z_floor + 0.7), (px, py, m.z_floor + 0.7)))
        L.append("## Speaker LS1 (optional, `speaker_mm`)\n")
        L.append(f"* part: {s['part']}; placeholder Ø{s['d']:.1f} × {s['t']:.1f} mm disc standing in the XZ plane, axis along Y, "
                 f"centre board ({s['board'][0]}, {s['board'][1]}, {s['board'][2]} from the board top) = world X {s['X']:.2f}, Y {s['Y']:.2f}, "
                 f"Z {s['Z'] - R:.2f} above the skin; rim Z {s['Z'] - s['d'] / 2 - R:.2f}..{s['Z'] + s['d'] / 2 - R:.2f} above the skin, "
                 f"back face Y {s['Y'] - s['t'] / 2:.2f} ({s['Y'] - s['t'] / 2 - m.Wi / 2:+.2f} from the bay's inner wall plane), front face Y {s['Y'] + s['t'] / 2:.2f}")
        L.append(f"* pocket: U-slot Ø{2 * s['rp']:.1f} ({s['cl']:.1f} radial clearance) about the axis, straight walls above the axis up to the lid "
                 f"underside (drop-in from the top), depth {s['depth']:.1f} along Y ({m.p['spk_back_seat']:.1f} behind the back face, "
                 f"{s['depth'] - s['t'] - m.p['spk_back_seat']:.1f} in front); X {s['x0']:.1f}..{s['x1']:.1f}, Y {s['y_back']:.2f}..{s['y_front']:.2f}, "
                 f"bottom {s['z_bot'] - R:.2f} above the skin ({s['z_bot'] - m.z_slab0:.1f} above the slab bottom)")
        L.append(f"* +Y wall bump: {s['bump']:.2f} mm over X {s['bx0']:.1f}..{s['bx1']:.1f} ({s['bx1'] - s['bx0']:.1f} long = pocket + two "
                 f"{m.p['bay_wall']:.1f} end walls), full slab height, top cut down to the lid underside (shelf); the signet is "
                 f"{m.Wo + s['bump']:.2f} wide there (asymmetric: +Y side only); outer corners r {m.p['spk_bump_r']}, bottom edge r {m.p['spk_bump_bottom_r']}")
        L.append(f"* grille: {len(m.spk_holes)} × Ø{g['hole_d']:.1f} holes (centre + {g['n']} on a Ø{2 * g['ring_r']:.0f} ring at 45°) through the "
                 f"{s['gw']:.1f} mm +Y plate = {open_area:.1f} mm² open ({100 * open_area / (math.pi * (s['d'] / 2) ** 2):.0f} % of the Ø{s['d']:.0f} disc)")
        L.append(f"* back volume: above the sub-board floor ({m.z_floor - R:.2f}) the slot's back is open to the bay over its full width, so the "
                 f"lidded bay (~1.4 cm³ minus parts) is the back volume and the terminals/leads pass straight through; below the floor the pocket is a "
                 f"recess in the solid slab with a lead groove {m.p['spk_lead_groove'][0]:.0f} wide × {m.p['spk_lead_groove'][1]:.1f} deep in its "
                 f"back wall (Y {m.spk_groove[2]:.2f}..{s['y_back']:.2f}, Z {m.spk_groove[3] - R:.1f}..floor) for terminals in the lower half of the disc")
        if lead:
            L.append(f"* leads: the speaker's pigtail (two 28 AWG wires ending in a Pico-EZmate plug) leaves the back terminals into the sub-board "
                     f"cavity (Z {m.z_floor - R:.1f}..{m.z_board_bot - R:.1f} above the skin, under the board's +Y edge), runs ≈ {lead[0]:.1f} mm to the "
                     f"J5 edge notch at board x {m.conns['J5']['notch']['cx']} and climbs the wall gap to the J5 header on the board top (allow 10 mm)")
        L.append(f"* lid: tab X {m.spk_tab[0]:.1f}..{m.spk_tab[1]:.1f} × Y {(m.Wi + 2 * m.p['lid_rebate'] - 2 * m.p['lid_clear']) / 2:.2f}..{m.spk_tab[2]:.2f} "
                 f"({m.p['lid_t']:.1f} thick, {s['y_out'] - m.spk_tab[2]:.2f} inside the bump face, {m.spk_tab[0] - s['bx0']:.1f} from the bump's end walls) rests on the shelf; "
                 f"boss X {m.spk_boss[0]:.1f}..{m.spk_boss[1]:.1f} × Y {m.spk_boss[2]:.2f}..{m.spk_boss[3]:.2f} under it fills the slot down to "
                 f"{m.spk_boss_z0 - R:.2f} above the skin = {m.spk_boss_z0 - s['Z'] - s['d'] / 2:.1f} mm above the speaker rim (the lid holds the speaker; "
                 f"a foam pad or a drop of glue takes up the play). The +Y detent groove is interrupted over the bump (X {s['bx0']:.1f}..{s['bx1']:.1f}).")
        L.append(f"* antenna: 3-D gap speaker ↔ flex antenna placeholder {m.spk_antenna_gap:.2f} mm (keep-out {m.bp.get('antenna_keepout_beyond_edge_mm', 5.0):.1f}); "
                 f"mass +{s['mass']:.1f} g speaker")
        L.append("")
    if m.conns:
        L.append("## Plug-in connectors (`connectors_top_mm`, `edge_notches_mm`)\n")
        L.append("The owner solders nothing: the cell, the charging-pad pigtail, the LRA and the speaker plug into four Molex Pico-EZmate "
                 "headers on the board TOP (right strip), and each pigtail drops through a notch in the board's right edge into the "
                 "sub-board cavity. Checked here: the mated plug + wire bend (placeholder `plugs`) clears the lid, the mic tube and the wall; "
                 "the wall gap beside each notch is open from plug height to the floor; the cell lead channel and the charging-wire floor groove "
                 "are open along their length and keep >= 1.2 mm of floor under them.\n")
        L.append("| header | feeds | header centre (board x, y) | notch (board x, right edge) | plug/bend envelope (world X, Y, Z) | wire path |\n|---|---|---|---|---|---|")
        paths = {
            "J1": f"cell tabs toward +Y, 3 x 0.8 lead channel from the pocket's +Y edge to the wall at X {m.cell_chan_box[0] + 1.5:.2f}" if m.cell_tab_edge == "+y" else "cell lead channel (-Y)",
            "J3": (f"two Ø{2 * m.wire_r:.1f} channels from the band ribs surface beside the -Y wall, then the {m.groove['width']} x {m.groove['depth']} floor groove "
                   f"({len(m.groove_boxes)} legs) to the notch") if m.groove else "floor groove not modelled",
            "J4": f"LRA pocket at X {m.p['lra_xy'][0]}, Y {m.p['lra_xy'][1]} -> +Y under the board edge -> notch",
            "J5": "speaker pocket (right wall, back open to the bay above the floor) -> cavity -> notch",
        }
        for ref, c in m.conns.items():
            pm = c["plug_mm"]
            L.append(f"| {ref} ({c['short']}) | {c['feeds']} | {c['cx']}, {c['cy']} | x {c['notch']['cx']}, {c['notch']['w']} x {c['notch']['d']} | "
                     f"X {m.bx(pm['x1']):.2f}..{m.bx(pm['x0']):.2f}, Y {m.by(pm['y0']):.2f}..{min(m.by(pm['y1']), m.Wi / 2 - 0.05):.2f}, Z {m.z_board_top - R:.2f}..{m.z_board_top + pm['height'] - R:.2f} above the skin | {paths.get(ref, '')} |")
        L.append("")
        runs = m.charging_wire_runs()
        if runs:
            longest = max(r["total"] for r in runs.values())
            cut = 5 * math.ceil((longest + 10) / 5)
            L.append("**Charging pigtail (W2) wire runs** along the modelled path, window centre → mated J3 plug, no slack "
                     "(band rib groove + slab channel + floor groove + climb up the notch to the header top):\n")
            for name, r in runs.items():
                L.append(f"* {name}: {r['arc']:.1f} + {r['channel']:.1f} + {r['floor']:.1f} + {r['rise']:.1f} = **{r['total']:.1f} mm**")
            L.append(f"\nCut W2 to **≥ {cut} mm per wire** (longest run + 10 mm for the bend into the plug and the trim at the window). "
                     "Half of a 100 mm 36920-0201 (≈ 50 mm) does not reach; half of a 300 mm 36920-0203 (≈ 150 mm) does.\n")
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
    L.append(f"* signet (bay) footprint {env['bay_footprint'][0]:.1f} × {env['bay_footprint'][1]:.1f} mm (incl. the {m.ant_depth:.1f} mm antenna cavity)"
             + (f", {env['signet_width_at_speaker']:.2f} wide across the speaker bump (X {m.spk['bx0']:.1f}..{m.spk['bx1']:.1f}, +Y side)" if m.spk else "")
             + f", lid top {env['height_above_skin']:.2f} mm above the skin, pod roof {env['pod_above_skin']:.2f} mm, "
             f"{env['length_with_pod']:.1f} mm long along the finger including the camera pod")
    L.append("")
    L.append("## Mass estimate\n")
    L.append(f"* shell {mass['shell_cc']:.2f} cm³ + lid {mass['lid_cc']:.2f} cm³ + key {mass['key_cc']:.3f} cm³ of resin at {RESIN_G_PER_CC} g/cm³ = **{mass['resin_g']:.1f} g**")
    L.append(f"* components {mass['components_g']:.1f} g ({', '.join(f'{k} {v}' for k, v in m.component_masses().items())})")
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
        if m.spk:
            right = comp.rotate(O, X, 90).rotate(O, Z, 180)                 # viewer at +Y: right = -X (pod on the left), up = +Z
            spk_half = comp.intersect(box(-60, m.spk["X"], -60, 60, -60, 60))   # keep X < speaker axis, look from +X at the cut
            spk_section = spk_half.rotate(O, Y, -90).rotate(O, Z, -90)      # right = +Y (speaker side), up = +Z
            views_ += [
                ("view_right", right, "right view (+Y, the speaker side): wall bump with the grille holes, lid tab, band and pad-wire ribs beyond"),
                ("view_section_speaker", spk_section, "section through the speaker axis (X = speaker): U-pocket, speaker, grille plate, lead groove, lid tab + boss, cell pocket, board, module"),
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
    ap.add_argument("--report", default=os.path.join(HERE, "fit_report.md"), help="where to write the fit report")
    ap.add_argument("--no-speaker", action="store_true", help="build the ring without the optional speaker pocket / lid tab")
    ap.add_argument("--no-views", action="store_true")
    ap.add_argument("--no-step", action="store_true")
    args = ap.parse_args(argv)
    p = default_params()
    if args.inner_d:
        p["inner_d"] = args.inner_d
    if args.lens_d:
        p["lens_d"] = args.lens_d
    if args.no_speaker:
        p["speaker"] = False
    bp = load_board_params(args.params)
    if p["speaker"] and "speaker_mm" not in bp:
        print("  NOTE board_params.json has no speaker_mm: building without the speaker pocket")
    t0 = time.time()
    m = Model(p, bp)
    m.build_shell()
    m.build_lid()
    m.build_key()
    m.build_placeholders()
    f = m.fit_check()
    ok = write_report(m, args.report, args)
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
          f"bay {env['bay_footprint'][0]:.1f} x {env['bay_footprint'][1]:.1f}, length incl. pod {env['length_with_pod']:.1f}"
          + (f", {env['signet_width_at_speaker']:.2f} wide at the speaker bump" if m.spk else ""))
    if m.spk:
        s = m.spk
        print(f"speaker: Ø{s['d']} x {s['t']} at X {s['X']:.2f} Y {s['Y']:.2f} Z {s['Z'] - m.R:.2f} above skin; pocket Ø{2 * s['rp']:.1f} x {s['depth']:.1f} deep, "
              f"X {s['x0']:.1f}..{s['x1']:.1f}, bump {s['bump']:.2f} over X {s['bx0']:.1f}..{s['bx1']:.1f}; {len(m.spk_holes)} grille holes Ø{p['spk_grille']['hole_d']}; "
              f"antenna gap {m.spk_antenna_gap:.2f}")
    print(f"mass: resin {mass['resin_g']:.1f} g + components {mass['components_g']:.1f} g = {mass['total_g']:.1f} g")
    export_all(m, args.out, views=not args.no_views, step=not args.no_step)
    print(f"{'FIT CHECK PASS' if ok else 'FIT CHECK FAIL'}  ({time.time() - t0:.1f} s)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
