# 5. Roadmap

## Stage 0 — bench proof (now → 2 weeks)

- [x] Protocol spec, shared codecs (C / Python / TS) with cross-tests
- [x] ESP32-S3 firmware for XIAO ESP32S3 Sense (capture, transfer, triggers, Morse player, audio, sleep)
- [x] Backend (Claude vision + structured output + Morse + optional TTS + sessions)
- [x] Desktop companion (bleak) incl. no-hardware `ask` mode
- [x] Phone companion (Expo dev client, BLE, TTS)
- [ ] **Order the stage-0 BOM** (`hardware/bom/stage0-devkit.csv`)
- [ ] Flash, pair with the CLI, first photo over BLE; record throughput in `docs/benchmarks.md`
- [ ] Measure current with a shunt/PPK2 during capture + transfer; update `hardware/power_budget.py`
- [ ] Tune JPEG quality/size vs. answer quality (QVGA q12 vs VGA q15)
- [ ] Tune Morse WPM/Farnsworth and haptic strength on a real LRA
- [ ] Prebuild the app on a phone; confirm iOS MTU/PHY behaviour

## Stage 1 — oversized wearable ring (1–3 months)

- [ ] Decide ESP32-S3-MINI-1U (keep firmware) vs. nRF52840 (future-proof) for the ring board
- [ ] Schematic + layout from `hardware/schematic-notes.md` (KiCad), order 2-layer boards + assembly of the fine-pitch parts
- [ ] Print `hardware/enclosure/mcring_stage1.scad`; fit check with the OV2640 head and a 301012 cell
- [ ] Load-switched camera rail; verify <30 µA sleep
- [ ] Double-tap threshold tuning on-finger; false-positive log
- [ ] Optional: Murata microblower signet experiment on the aux channel
- [ ] One day of real use on 40 mAh

## Stage 2 — Oura-size (3–9 months, multi-spin)

- [ ] Finish `firmware/ring-nrf52840/src/camera_hal.c`: OV7670/OVM7692 bit-bang + baseline JPEG encoder; benchmark capture time on XIAO nRF52840 Sense
- [ ] Try HM01B0 1-bit mode through SPIS + PPI (lowest power path)
- [ ] Sample Grepow curved cells; BQ25100 charger board
- [ ] Rigid-flex layout (0.22/0.48 mm) around ISP1807 or nRF52840 WLCSP; printed antenna; OVM7692 pod
- [ ] Haptic: VG0640001D vs PowerHap + BOS1901 on-finger comparison
- [ ] Potting + shell; charging cradle
- [ ] Battery-life validation against `hardware/power-budget.txt`

## Software backlog (any stage)

- [ ] OTA firmware update over BLE
- [ ] Voice activity detection to end recordings early
- [ ] Phone-side on-device transcription (iOS Speech / Android SpeechRecognizer) to avoid a second cloud provider
- [ ] Morse "yes/no/digits" ultra-short mode and a per-user abbreviation dictionary
- [ ] Backend: rate limiting, per-device tokens, request logging opt-in
- [ ] Simulated ring (software peripheral) for CI of the companion apps
