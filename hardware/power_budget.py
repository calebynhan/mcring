#!/usr/bin/env python3
"""Shots-per-charge estimator for the ring. Edit the PROFILES or pass --battery.

    python hardware/power_budget.py            # table for 20/40/100 mAh
    python hardware/power_budget.py --battery 16 --shots-per-day 40
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass


@dataclass
class Profile:
    name: str
    capture_s: float          # camera on + encode
    capture_ma: float
    transfer_s: float         # BLE radio busy
    transfer_ma: float
    feedback_s: float         # haptic/LED Morse playback
    feedback_ma: float
    standby_ua: float         # everything else, 24/7
    notes: str = ""

    def mah_per_shot(self) -> float:
        return (self.capture_s * self.capture_ma + self.transfer_s * self.transfer_ma
                + self.feedback_s * self.feedback_ma) / 3600.0

    def mah_per_day_standby(self) -> float:
        return self.standby_ua / 1000.0 * 24.0


PROFILES = [
    Profile("ESP32-S3 + OV2640, camera power-gated, BLE off in sleep (stage 1 best case)",
            capture_s=0.6, capture_ma=180, transfer_s=0.5, transfer_ma=90, feedback_s=10, feedback_ma=40,
            standby_ua=25, notes="deep sleep 7-8 uA + IMU 1 uA + regulator/charger leakage; wake on tap/button"),
    Profile("ESP32-S3 + OV2640, BLE connection kept alive (light sleep)",
            capture_s=0.6, capture_ma=180, transfer_s=0.5, transfer_ma=90, feedback_s=10, feedback_ma=40,
            standby_ua=380, notes="XIAO-class light sleep with BLE ~380 uA (third-party measurement)"),
    Profile("ESP32-S3 dev kit as-is (camera board not power-gated)",
            capture_s=0.6, capture_ma=180, transfer_s=0.5, transfer_ma=90, feedback_s=10, feedback_ma=40,
            standby_ua=3000, notes="measured ~3 mA deep sleep with the Sense camera board attached"),
    Profile("nRF52840 + HM01B0 160x120 mono, slow BLE connection maintained (stage 2 target)",
            capture_s=0.3, capture_ma=12, transfer_s=0.5, transfer_ma=8, feedback_s=10, feedback_ma=40,
            standby_ua=30, notes="radio 5 mA peaks; HM01B0 <2 mW; the 10 s haptic Morse reply (8 mm LRA ~75 mA at 50% duty) dominates per-shot energy"),
]


def report(batteries_mah: list[float], shots_per_day: float, usable: float = 0.8) -> None:
    for p in PROFILES:
        print(f"\n== {p.name}")
        print(f"   {p.notes}")
        print(f"   per shot: {p.mah_per_shot()*1000:.2f} µAh   standby: {p.mah_per_day_standby():.2f} mAh/day")
        print(f"   {'battery':>8} {'usable':>7} {'shots (no standby)':>19} {'days @ '+str(shots_per_day)+'/day':>16} {'standby-only days':>18}")
        for b in batteries_mah:
            u = b * usable
            shots = u / p.mah_per_shot()
            daily = p.mah_per_day_standby() + shots_per_day * p.mah_per_shot()
            print(f"   {b:>6.0f}mAh {u:>6.1f} {shots:>19.0f} {u/daily:>16.1f} {u/p.mah_per_day_standby():>18.1f}")
    print("\nPeak-current check: ESP32-S3 photo peaks 300-370 mA = 15-20C on a 1C-rated 16-22 mAh ring cell → not viable")
    print("without a large buffer capacitor; nRF52840 peaks ~15 mA ≈ 1C. See docs/research/02-mcu-radio-power.md §3.4.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--battery", type=float, nargs="*", default=[20, 40, 100])
    ap.add_argument("--shots-per-day", type=float, default=30)
    ap.add_argument("--usable", type=float, default=0.8)
    a = ap.parse_args()
    report(a.battery, a.shots_per_day, a.usable)
