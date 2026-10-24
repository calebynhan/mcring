# Build helpers

Small, standard-library-only helpers referenced from `docs/07-build-guide.md`.

| File | What |
|---|---|
| `tuning_calc.py` | calculators used during bring-up: DRV2605L `RATED_VOLTAGE`/`OD_CLAMP` registers for a given LRA (and decoding the firmware defaults), LIS2DW12 `TAP_THS` ↔ g and `INT_DUR` timing, battery-divider drain, Morse/Farnsworth unit lengths. `python3 docs/build-helpers/tuning_calc.py -h` |

Numbers these produce are starting points; the guide says where each one is checked on hardware.
