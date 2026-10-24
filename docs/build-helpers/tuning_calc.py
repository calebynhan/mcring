#!/usr/bin/env python3
"""Small calculators used by docs/07-build-guide.md (standard library only).

  python3 docs/build-helpers/tuning_calc.py drv2605 --vrms 1.25 --freq 240          # LRA -> RATED_VOLTAGE / OD_CLAMP
  python3 docs/build-helpers/tuning_calc.py drv2605 --decode 0x3E 0x8C --freq 235   # what the firmware defaults mean
  python3 docs/build-helpers/tuning_calc.py tap --g 0.75                            # g -> LIS2DW12 TAP_THS (FS = +/-2 g)
  python3 docs/build-helpers/tuning_calc.py tap --ths 9                             # TAP_THS -> g, plus INT_DUR timing
  python3 docs/build-helpers/tuning_calc.py divider --r1k 100 --r2k 100             # battery-sense divider drain (stage 0)
  python3 docs/build-helpers/tuning_calc.py divider --r1k 1000 --r2k 1000           # stage-1 board: R8/R9 = 1 M / 1 M
  python3 docs/build-helpers/tuning_calc.py sleep                                   # stage-1 deep-sleep budget, firmware as-is
  python3 docs/build-helpers/tuning_calc.py sleep --imu lp-wakeup --shots-per-day 30 # ... with the IMU low-power wake follow-up
  python3 docs/build-helpers/tuning_calc.py pads --inner-d 20 --angle 25            # charging-pad / pogo-pin geometry from the CAD
  python3 docs/build-helpers/tuning_calc.py morse --wpm 15 --overall 8              # unit lengths for Farnsworth timing

Formulas: TI DRV2605L datasheet (SLOS854) 8.5.2.1 "Rated voltage programming" and 8.5.2.2
"Overdrive voltage-clamp programming"; ST LIS2DW12 datasheet (DS12099) TAP_THS_* / INT_DUR and Table 3
current consumption (the IMU figures below are datasheet-class numbers, not measurements); sleep floor
items per hardware/electrical/README.md section 3; pad geometry per hardware/cad/mcring_stage1.py
default_params() (pad_angle, rib_x, pad_window). Verify against the datasheet revision you have before
trusting a register value on hardware, and against the PPK2 before trusting a current.
"""
from __future__ import annotations

import argparse
import math

T_SAMPLE_S = 300e-6          # DRV2605L default sample time (SAMPLE_TIME[1:0] = 11 -> 300 us)
T_BLANK_IDISS_S = 300e-6     # default blanking + current-dissipation time (added in the TI formula)
RATED_LSB_V = 20.58e-3
OD_CLAMP_LSB_V = 21.22e-3


def lra_rated_reg(vrms: float, f_hz: float) -> int:
    k = math.sqrt(1.0 - (4.0 * T_SAMPLE_S + T_BLANK_IDISS_S) * f_hz)
    return max(0, min(255, round(vrms * k / RATED_LSB_V)))


def lra_rated_vrms(reg: int, f_hz: float) -> float:
    k = math.sqrt(1.0 - (4.0 * T_SAMPLE_S + T_BLANK_IDISS_S) * f_hz)
    return reg * RATED_LSB_V / k


def od_clamp_reg(vpeak: float) -> int:
    return max(0, min(255, round(vpeak / OD_CLAMP_LSB_V)))


def cmd_drv2605(a: argparse.Namespace) -> None:
    if a.decode:
        rated, clamp = (int(x, 0) for x in a.decode)
        print(f"RATED_VOLTAGE 0x{rated:02X} -> {lra_rated_vrms(rated, a.freq):.2f} Vrms at {a.freq:.0f} Hz")
        print(f"OD_CLAMP      0x{clamp:02X} -> {clamp * OD_CLAMP_LSB_V:.2f} V peak")
        return
    if a.vrms is None:
        raise SystemExit("drv2605 needs --vrms (or --decode RATED OD_CLAMP)")
    vpeak = a.vpeak if a.vpeak is not None else a.vrms * math.sqrt(2.0) * 1.3   # 30 % overdrive default
    rated = lra_rated_reg(a.vrms, a.freq)
    clamp = od_clamp_reg(vpeak)
    print(f"LRA {a.vrms:.2f} Vrms @ {a.freq:.0f} Hz, overdrive clamp {vpeak:.2f} Vp")
    print(f"  REG_RATED_V (0x16) = 0x{rated:02X}   ({lra_rated_vrms(rated, a.freq):.2f} Vrms after rounding)")
    print(f"  REG_OD_CLAMP (0x17) = 0x{clamp:02X}   ({clamp * OD_CLAMP_LSB_V:.2f} Vp)")
    print("  firmware: edit wr(REG_RATED_V, ...) / wr(REG_OD_CLAMP, ...) in src/drv2605.cpp, rebuild, re-run autocal")


def cmd_tap(a: argparse.Namespace) -> None:
    lsb_g = a.fs / 32.0
    if a.g is not None:
        ths = max(1, min(31, round(a.g / lsb_g)))
        print(f"{a.g:.2f} g -> TAP_THS = {ths} (0x{ths:02X}); actual {ths * lsb_g:.3f} g at FS=+/-{a.fs:.0f} g (LSB {lsb_g*1000:.1f} mg)")
    if a.ths is not None:
        print(f"TAP_THS {a.ths} -> {a.ths * lsb_g:.3f} g at FS=+/-{a.fs:.0f} g")
    odr = a.odr
    lat, quiet, shock = a.latency, a.quiet, a.shock
    print(f"INT_DUR @ {odr:.0f} Hz: LATENCY={lat} -> {lat * 32 / odr * 1000:.0f} ms window for the 2nd tap, "
          f"QUIET={quiet} -> {quiet * 4 / odr * 1000:.0f} ms, SHOCK={shock} -> {shock * 8 / odr * 1000:.0f} ms"
          f"  (register value 0x{(lat << 4) | (quiet << 2) | shock:02X})")


def cmd_divider(a: argparse.Namespace) -> None:
    r1, r2 = a.r1k * 1e3, a.r2k * 1e3
    ratio = (r1 + r2) / r2
    for v in (4.2, 3.7, 3.3):
        i = v / (r1 + r2)
        print(f"VBAT {v:.1f} V -> ADC {v / ratio:.3f} V, drain {i * 1e6:.1f} uA ({i * 24 * 1e3:.3f} mAh/day)")
    print(f"BATTERY_DIVIDER = {ratio:.3f}  (config.h expects 2.0 for equal resistors)")


# LIS2DW12 current by mode (DS12099 Table 3 class values, uA). The firmware's imu_wake() writes CTRL1 = 0x74:
# ODR 400 Hz, high-performance mode - the only mode in which the double-tap engine is specified (>= 400 Hz),
# and the one that dominates the stage-1 sleep floor. Low-power modes stop at 200 Hz.
IMU_MODES = {
    "hp400":     (90.0, "CTRL1 0x74: 400 Hz high-performance, double-tap armed (firmware as-is)"),
    "lp1-200":   (10.0, "LP mode 1, 200 Hz: double-tap with INT_DUR rescaled (timing marginal)"),
    "lp1-100":   (6.5,  "LP mode 1, 100 Hz: wake-up/activity interrupt, re-arm 400 Hz tap after wake"),
    "lp-wakeup": (1.8,  "LP mode 1, 25 Hz: wake-up/activity interrupt, re-arm 400 Hz tap after wake"),
    "off":       (0.05, "power-down (no tap wake; button only)"),
}

# Everything else that stays powered on the mcring v1 board in deep sleep (uA, typical/max class values).
SLEEP_FIXED = [
    ("ESP32-S3-MINI-1U deep sleep (RTC + EXT0/EXT1 wake)", 8.0, "research 02: 7-8 uA"),
    ("DRV2605L standby (EN tied to 3V3, STANDBY bit set)", 4.0, "datasheet max; typ lower"),
    ("BQ25100 battery leakage, no input", 1.0, "OUT pin, cradle off"),
    ("TPS62840 quiescent", 0.06, "60 nA"),
    ("2 x TPS22916 off (camera, LED rails gated)", 0.02, "~10 nA each; rails at 0 V"),
]
MIC_SLEEP_UA = 5.0   # TDK T3902 with the PDM clock stopped ("sleep mode" class figure - verify on the datasheet / PPK2)
SHOT_UAH_DEFAULT = 153.6   # per-shot energy of the ESP32-S3 profile in hardware/power-budget.txt


def cmd_sleep(a: argparse.Namespace) -> None:
    imu_ua, imu_desc = IMU_MODES[a.imu]
    div_ua = a.vbat / (a.r1k * 1e3 + a.r2k * 1e3) * 1e6
    rows = [("LIS2DW12: " + imu_desc, imu_ua, "DS12099 Table 3 class")]
    rows += SLEEP_FIXED
    rows.append((f"battery divider {a.r1k:.0f}k / {a.r2k:.0f}k at {a.vbat:.1f} V (R8/R9 + C23)", div_ua, "V / (R1 + R2)"))
    if a.mic:
        rows.append(("TDK T3902 mic, PDM clock stopped", MIC_SLEEP_UA, "sleep-mode class figure, verify"))
    total = sum(r[1] for r in rows)
    w = max(len(r[0]) for r in rows)
    print(f"stage-1 deep-sleep budget (mcring v1, camera + LED rails gated, BLE off):")
    for name, ua, note in rows:
        print(f"  {name:<{w}}  {ua:7.2f} uA   {note}")
    print(f"  {'TOTAL':<{w}}  {total:7.2f} uA   -> {total * 24 / 1000:.2f} mAh/day")
    usable = a.battery * a.usable
    per_day = total * 24 / 1000 + a.shots_per_day * a.shot_uah / 1000
    print(f"  {a.battery:.0f} mAh cell, {a.usable:.0%} usable = {usable:.1f} mAh; {a.shots_per_day:.0f} shots/day x {a.shot_uah:.1f} uAh"
          f" -> {per_day:.2f} mAh/day -> {usable / per_day:.1f} days  (standby-only {usable / (total * 24 / 1000):.0f} days)")
    print("  acceptance: measure in series with the cell (PPK2), lid off, after 'I pwr: deep sleep'; lift INT1 / power the IMU down"
          " to split the IMU share out")


def cmd_pads(a: argparse.Namespace) -> None:
    R = a.inner_d / 2.0
    ang = math.radians(a.angle)
    chord = 2 * R * math.sin(ang)
    arc = 2 * R * ang
    y, z = R * math.sin(ang), R * math.cos(ang)
    print(f"charging pads on the inner band, +/-{a.angle:.0f} deg from the bottom, bore diameter {a.inner_d:.1f} mm (R = {R:.2f}):")
    print(f"  pad centres {chord:.2f} mm apart across the finger (chord), {arc:.2f} mm along the bore surface (arc)")
    print(f"  each pad centre: {y:.2f} mm off the ring's vertical mid-plane, {z:.2f} mm below the finger axis;"
          f" pogo-pin axis tilted {a.angle:.0f} deg from vertical, aimed at the axis")
    xa, xb = a.rib_x
    print(f"  along the finger (X from the band mid-plane, negative = toward the antenna end): -Y pad (CHG-, PAD2/CP2) at X {xa:+.1f},"
          f" +Y pad (CHG+, PAD1/CP1) at X {xb:+.1f} -> pins staggered {abs(xa - xb):.1f} mm")
    print(f"  windows {a.window:.0f} x {a.window:.0f} mm through the {a.wall:.1f} mm wall; the ENIG contact sits flush with the bore,"
          f" so the pin tip must reach R = {R:.1f} mm, i.e. {a.wall:.1f} mm inside the band's outer surface at that angle")


def cmd_morse(a: argparse.Namespace) -> None:
    unit = 1200.0 / a.wpm
    print(f"char {a.wpm} WPM -> unit {unit:.0f} ms: dot {unit:.0f} ms, dash {3 * unit:.0f} ms, intra-char gap {unit:.0f} ms")
    if a.overall and a.overall < a.wpm:
        # Farnsworth (ARRL): total time per PARIS word = 60/overall s; 31 units are character time
        word_s = 60.0 / a.overall
        char_s = 31 * unit / 1000.0
        gaps_s = word_s - char_s
        # 19 "gap units" per PARIS word: 4 inter-char gaps x 3 + 1 word gap x 7
        stretched_unit = gaps_s / 19.0
        print(f"overall {a.overall} WPM -> inter-char gap {3 * stretched_unit * 1000:.0f} ms, word gap {7 * stretched_unit * 1000:.0f} ms")
    print("LRA rise/fall is 20-40 ms: keep the dot >= 80 ms (char <= 15 WPM) or dots blur into dashes")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("drv2605"); s.set_defaults(fn=cmd_drv2605)
    s.add_argument("--vrms", type=float); s.add_argument("--freq", type=float, default=235.0)
    s.add_argument("--vpeak", type=float); s.add_argument("--decode", nargs=2, metavar=("RATED", "OD_CLAMP"))

    s = sub.add_parser("tap"); s.set_defaults(fn=cmd_tap)
    s.add_argument("--g", type=float); s.add_argument("--ths", type=int); s.add_argument("--fs", type=float, default=2.0)
    s.add_argument("--odr", type=float, default=400.0)
    s.add_argument("--latency", type=int, default=7); s.add_argument("--quiet", type=int, default=2); s.add_argument("--shock", type=int, default=2)

    s = sub.add_parser("divider"); s.set_defaults(fn=cmd_divider)
    s.add_argument("--r1k", type=float, default=100.0); s.add_argument("--r2k", type=float, default=100.0)

    s = sub.add_parser("sleep"); s.set_defaults(fn=cmd_sleep)
    s.add_argument("--imu", choices=sorted(IMU_MODES), default="hp400")
    s.add_argument("--r1k", type=float, default=1000.0); s.add_argument("--r2k", type=float, default=1000.0)
    s.add_argument("--vbat", type=float, default=3.8); s.add_argument("--no-mic", dest="mic", action="store_false")
    s.add_argument("--battery", type=float, default=30.0); s.add_argument("--usable", type=float, default=0.8)
    s.add_argument("--shots-per-day", type=float, default=30.0); s.add_argument("--shot-uah", type=float, default=SHOT_UAH_DEFAULT)

    s = sub.add_parser("pads"); s.set_defaults(fn=cmd_pads)
    s.add_argument("--inner-d", type=float, default=20.0); s.add_argument("--angle", type=float, default=25.0)
    s.add_argument("--rib-x", type=float, nargs=2, default=(-1.5, -3.5)); s.add_argument("--window", type=float, default=3.0)
    s.add_argument("--wall", type=float, default=1.2)

    s = sub.add_parser("morse"); s.set_defaults(fn=cmd_morse)
    s.add_argument("--wpm", type=int, default=15); s.add_argument("--overall", type=int, default=8)

    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
