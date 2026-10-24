// mcring stage-1 enclosure — oversized ring for an ESP32-S3-MINI-1U class board,
// a 24-pin FPC camera head, an 8 mm LRA and a 30-40 mAh 3x10x12 mm cell.
//
// Print in white/translucent SLA resin (LED window) or in two colours on FDM.
// Parameters are in mm. Run with OpenSCAD 2021+: openscad -o ring.stl mcring_stage1.scad
//
// Layout (looking at the top "signet"):  camera lens points FORWARD along the finger
// (toward the fingertip) so a natural "point and tap" frames the object.

/* [Fit] */
inner_d      = 20.0;   // finger diameter (US size 10 ≈ 19.8 mm)
band_w       = 12.0;   // band width along the finger
band_t       = 3.2;    // band wall thickness (battery hides inside the thick zone)

/* [Signet / electronics bay] */
bay_l        = 26.0;   // along the finger-tangent direction
bay_w        = 12.0;   // across the finger
bay_h        = 6.5;    // height above the band outer surface
bay_wall     = 1.2;
corner_r     = 3.0;

/* [Camera pod] */
lens_d       = 4.6;    // OV2640 lens barrel ≈ 4.5 mm; HM01B0 module lens ≈ 3.5 mm
lens_z       = 3.4;    // lens axis height above band surface
pod_depth    = 7.0;    // how far the pod sticks forward past the bay

/* [Features] */
led_window_d = 3.0;
button_hole  = [3.2, 2.7];  // Omron B3U side-actuated
pad_slots    = true;        // charging pad windows on the inner band
cell_pocket  = [12.4, 3.4, 10.4]; // 301012 cell, oversized 0.4 mm (L, T, W)

$fn = 96;

module rounded_box(size, r) {
  hull() for (x = [r, size[0]-r], y = [r, size[1]-r]) translate([x, y, 0]) cylinder(r = r, h = size[2]);
}

module band() {
  difference() {
    cylinder(d = inner_d + 2*band_t, h = band_w, center = true);
    cylinder(d = inner_d, h = band_w + 2, center = true);
  }
}

module bay_outer() {
  translate([-bay_l/2, -bay_w/2, inner_d/2 + band_t - 1.0])
    rounded_box([bay_l, bay_w, bay_h + 1.0], corner_r);
}
module bay_inner() {
  translate([-bay_l/2 + bay_wall, -bay_w/2 + bay_wall, inner_d/2 + band_t - 0.6])
    rounded_box([bay_l - 2*bay_wall, bay_w - 2*bay_wall, bay_h + 2], corner_r - bay_wall);
}

module camera_pod() {
  // forward (+X) pod with a lens bore
  translate([bay_l/2 - 1, -bay_w/2 + 1.5, inner_d/2 + band_t - 1.0])
    rounded_box([pod_depth + 1, bay_w - 3, lens_z + lens_d/2 + 1.6], 1.5);
}
module camera_bore() {
  translate([bay_l/2 - 2, 0, inner_d/2 + band_t + lens_z]) rotate([0, 90, 0]) cylinder(d = lens_d, h = pod_depth + 4);
  // cavity for the camera head behind the lens (OV2640 head ≈ 8.5 x 8.5 x 5.5)
  translate([bay_l/2 - 9, -4.5, inner_d/2 + band_t - 0.5]) cube([8.5, 9, 6.2]);
}

module cell_pocket() {
  // pocket in the thick part of the band opposite the bay (bottom), tangent to the finger
  translate([-cell_pocket[0]/2, -cell_pocket[2]/2, -(inner_d/2 + band_t) + 0.6])
    cube([cell_pocket[0], cell_pocket[2], cell_pocket[1]]);
}

module side_features() {
  // LED window on top of the bay, near the back
  translate([-bay_l/2 + 5, 0, inner_d/2 + band_t + bay_h - 2]) cylinder(d = led_window_d, h = 5);
  // button hole on the left side (palm-opposite when worn on the right index finger)
  translate([-2, -bay_w/2 - 1, inner_d/2 + band_t + 2.0]) cube([button_hole[0], 3, button_hole[1]]);
  // wire/FPC channel from the bay down into the band
  translate([-6, -2.5, inner_d/2 - 0.5]) cube([12, 5, band_t + 1.5]);
  // charging pad windows on the inner surface
  if (pad_slots) for (a = [-25, 25]) rotate([0, a, 0]) translate([0, -1.5, -(inner_d/2) - 0.1]) cube([4, 3, band_t - 1.2]);
}

module ring() {
  difference() {
    union() {
      band();
      // thicker zone around the cell pocket
      intersection() {
        cylinder(d = inner_d + 2*band_t + 1.6, h = band_w, center = true);
        translate([-9, -band_w, -(inner_d/2 + band_t + 1)]) cube([18, 2*band_w, 5]);
      }
      bay_outer();
      camera_pod();
    }
    cylinder(d = inner_d, h = band_w + 4, center = true);
    bay_inner();
    camera_bore();
    cell_pocket();
    side_features();
  }
}

module lid() {
  // snap-fit lid for the bay (print separately); 0.15 mm clearance
  translate([0, 20, 0]) difference() {
    translate([-bay_l/2 + 0.15, -bay_w/2 + 0.15, 0]) rounded_box([bay_l - 0.3, bay_w - 0.3, 1.2], corner_r - 0.15);
    translate([-bay_l/2 + 5, 0, -1]) cylinder(d = led_window_d, h = 5);
  }
  translate([0, 20, 1.2]) translate([-bay_l/2 + bay_wall + 0.15, -bay_w/2 + bay_wall + 0.15, 0])
    rounded_box([bay_l - 2*bay_wall - 0.3, bay_w - 2*bay_wall - 0.3, 1.0], corner_r - bay_wall - 0.15);
}

// Orientation: finger axis = Y; +X = toward the fingertip; +Z = top of the hand.
rotate([90, 0, 0]) ring();
lid();
