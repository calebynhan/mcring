# 9. Fundamentals — what you need to know to build mcring

This is the course that goes with the project. Each chapter in `docs/fundamentals/` follows
the same shape: *why it matters in mcring* (with the exact files where the concept shows up),
*the concepts* worked on mcring's own numbers, *learn it* (videos, courses, interactive tools,
with time estimates), and *check yourself* (exercises with answers).

| Chapter | What you'll be able to do afterwards |
|---|---|
| [1. Electronics basics](fundamentals/01-electronics-basics.md) | Read the schematic sheets in `hardware/electrical/out/`, know why every pull-up and capacitor is there, pick a package you can solder |
| [2. Batteries and power budgets](fundamentals/02-batteries-and-power-budgets.md) | Redo `hardware/power_budget.py` by hand, explain the 1C rule that rules out the ESP32-S3 for stage 2, measure current correctly |
| [3. Microcontrollers and firmware](fundamentals/03-microcontrollers-and-firmware.md) | Read every file in `firmware/ring-esp32s3/src/`, change a pin, add a cue, understand the cooperative loop and deep sleep |
| [4. Bluetooth Low Energy](fundamentals/04-bluetooth-low-energy.md) | Explain `protocol/ble-gatt.md` end to end, predict transfer time on iPhone vs Android, debug with nRF Connect |
| [5. Cameras and images](fundamentals/05-cameras-and-images.md) | Choose resolution and JPEG quality on purpose, know what a 2.8 mm camera cube can and cannot see, estimate vision-token cost |
| [6. Audio and haptics](fundamentals/06-audio-and-haptics.md) | Follow the mic → ADPCM → BLE → speech-to-text path and the text-to-speech → ADPCM → I²S → speaker path; design haptic cues |
| [7. PCB design and assembly](fundamentals/07-pcb-design-and-assembly.md) | Turn `hardware/electrical/out/mcring_v1.net` + `hardware/pcb/floorplan.md` into a KiCad layout, order it, reflow it, bring it up |
| [8. Mechanical CAD and 3D printing](fundamentals/08-mechanical-cad-and-3d-printing.md) | Modify `hardware/cad/mcring_stage1.py`, re-run the fit check, print and finish the ring |
| [9. Software stack](fundamentals/09-software-stack.md) | Run and extend the backend, the phone app and the CLI; understand the Claude vision/structured-output calls and the STT/TTS loop |

## Suggested order (and how it lines up with the build)

You don't need all of this before touching hardware. The order below interleaves learning
with the stage-0 bring-up in `docs/07-build-guide.md` so every chapter pays off immediately.

| Week | Learn | Do (from docs/07) |
|---|---|---|
| 1 | Ch. 1 (electronics basics), Ch. 3 first half (GPIO, I²C, serial, PlatformIO) | Order the stage-0 parts; run the backend and `mcring talk --no-ring` with no hardware |
| 2 | Ch. 3 second half (state machine, sleep), Ch. 4 (BLE) | Flash the XIAO, first photo over BLE, first spoken answer |
| 3 | Ch. 6 (audio/haptics), Ch. 5 (cameras) | Add the LRA + DRV2605L, the accelerometer, the speaker; tune cues and tap threshold |
| 4 | Ch. 2 (power) | Battery test with a USB meter, fill in `docs/benchmarks.md` |
| 5–6 | Ch. 7 (PCB) | Lay out the stage-1 board in KiCad from the netlist and floorplan; order boards + stencils |
| 7 | Ch. 8 (CAD/printing) | Print the ring, fit-check with real parts, iterate the pocket dimensions |
| 8 | Ch. 9 (software) as needed | Stage-1 assembly and bring-up; app polish |

Total: roughly 40–60 hours of study spread over the build. If you only have time for three
chapters, do 2 (power), 4 (BLE) and 7 (PCB): they are where this project differs from a
generic ESP32 tutorial.

## How the chapters were put together

Each resource link was checked against a live web search before it was written down, and a
separate review pass re-checked every link and every repo path. Dead links are still possible
(videos get taken down); each chapter's `_links_*.json` file records what the link was verified
against so a broken one is easy to replace.

## Safety, up front

Three things in this project can hurt you or the parts, and the chapters repeat them:

1. **LiPo cells**: never short, puncture or charge above 1C; the tiny 30 mAh cells have no
   margin. Charge with the designed charger (BQ25100 at ≤ 35 mA) or the XIAO's on-board charger
   only, never a generic 500 mA module.
2. **Reflow and hot air**: 250 °C tools, flux fumes; work in a ventilated space.
3. **Lasers (v2 only)**: anything on a hand points at faces; see `docs/08-projection-v2.md`
   before buying a laser module.
