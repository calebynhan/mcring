# Build helpers

Small, standard-library-only helpers referenced from `docs/07-build-guide.md`.

| File | What |
|---|---|
| `tuning_calc.py` | calculators used during bring-up: DRV2605L `RATED_VOLTAGE`/`OD_CLAMP` registers for a given LRA (and decoding the firmware defaults), LIS2DW12 `TAP_THS` ↔ g and `INT_DUR` timing, battery-divider drain (100 k stage 0 / 1 M stage 1), the stage-1 **deep-sleep budget** by IMU wake mode (`sleep`, with days-per-charge), the charging-pad / pogo-pin geometry from the CAD's `pad_angle` (`pads`), the **on-ring speaker budget** — energy per spoken answer and answers per charge, and why the amp rail is gated (`speaker`) — and, for the optional silent mode, Morse/Farnsworth unit lengths (`morse`). `python3 docs/build-helpers/tuning_calc.py -h` |

Numbers these produce are starting points; the guide says where each one is checked on hardware
(`sleep` → §2.4 PPK2 in series with the cell, `speaker` → §1.10 / §2.4 meter during
`mcring say … --ring-speaker`, `drv2605` → §1.8 autocal, `tap` → §1.9 / §2.10 false-positive log,
`pads` → §2.8 cradle).
