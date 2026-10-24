# 7. Build and integration guide

How to go from a box of parts to a working ring, one stage at a time, with a check at every
step. It assumes the repo as it is: `firmware/ring-esp32s3` (ESP32-S3, PlatformIO),
`backend/` (FastAPI), `tools/ring-cli` (the `mcring` desktop companion), `app/` (Expo phone
app) and the hardware files under `hardware/`. Requirements F1–F9 are in
`docs/01-vision-and-requirements.md`.

Conventions: every step says what you should **observe** and what to do **if not**. Serial
log lines are quoted as the firmware prints them (`[   millis] I tag: text`, see `src/log.h`).
CLI output is quoted from `tools/ring-cli/mcring_cli/*.py`.

Files produced by other steps of the hardware pass are referenced by path; if a path does not
exist yet, that step has not been run and the guide tells you what to fall back to:

| Path | Produced by | Used in |
|---|---|---|
| `hardware/pcb/out/wiring_stage0.png` | PCB/wiring step | §1.2 |
| `hardware/pcb/floorplan.md`, `hardware/pcb/board_params.json` | PCB floorplan step | §2.1, §2.6 |
| `hardware/electrical/out/mcring_v1.net`, `out/sch_*.png`, `out/erc.md` | electrical step (present) | §2.1, §2.3 |
| `hardware/cad/out/mcring_stage1_{shell,lid,key}.stl`, `hardware/cad/fit_report.md`, `hardware/cad/README.md` | enclosure CAD step (CadQuery, generated from `board_params.json`; the old OpenSCAD file is gone) | §2.5–2.8 |
| `docs/build-helpers/tuning_calc.py` | this guide (`sleep`, `pads`, `divider`, `drv2605`, `tap`, `morse` calculators) | §1.8, §1.9, §2.4, §2.8 |

---

## 0. Before any hardware: prove the AI loop on a photo (30 min)

```bash
git clone <repo> && cd mcring
python -m venv .venv && . .venv/bin/activate
pip install -r backend/requirements.txt -e tools/ring-cli     # requirements.txt pulls in python/mcring_core
cp backend/.env.example backend/.env                           # put your ANTHROPIC_API_KEY in it
(cd backend && uvicorn app.main:app --port 8000 &)
curl -s localhost:8000/v1/health
mcring ask ~/Pictures/any-photo.jpg -q "what is this and is it dangerous?" --speak --beep
```

**Observe:** `{"status":"ok","provider":"anthropic","model":"claude-opus-5-5","tts":"none"}` from
the health check; `mcring ask` prints `<subject>  [NN%]  via claude-opus-5-5 in NNNN ms`, the
`answer:` and `short:` lines, then plays the Morse pattern in the terminal (beeps with `--beep`),
and ends with `session: <id>`.

**If not:** `backend not reachable` → uvicorn is not up or the port differs (`--backend`).
HTTP 401 → `MCRING_API_TOKEN` is set in `.env` but you did not pass `--token`. 5xx → see §4.
No sound from `--speak` → the CLI tries `afplay`, `mpg123`, `ffplay`, then `say`/`espeak-ng`;
install one, or ignore (the text is printed anyway). Tests to run once: `docs/06-getting-started.md` §C.

---

## 1. Stage 0 — bench rig (XIAO ESP32S3 Sense)

### 1.1 Order list

From `hardware/bom/stage0-devkit.csv` (≈ $40–55):

| Qty | Part | Note |
|---|---|---|
| 1 | Seeed XIAO ESP32S3 **Sense** (with the camera expansion board) | some ship with OV3660 instead of OV2640; both work |
| 1 | Adafruit DRV2605L breakout (#2305) | EN is tied high on the breakout; I²C 0x5A |
| 1 | 8 mm coin LRA, ~235 Hz (PMD C08-005, Jameco 8 mm, or INEED LRA0825BC-0167F) | the INEED part is the stage-1 motor; buy it now and tune on it |
| 1 | LIS2DW12 breakout | 0x18 or 0x19, both auto-detected |
| 1 | 6 × 6 mm tactile switch | the only mandatory peripheral |
| 1 | 9–12 mm passive piezo | optional beeps |
| 1 | 100 mAh LiPo (Adafruit 1570) | plugs into the XIAO BAT+/BAT- pads |
| 2 | resistors for the battery divider | **use 100 kΩ/100 kΩ**, not 10 k: 10 k/10 k drains 210 µA, ten times the sleep budget (`python3 docs/build-helpers/tuning_calc.py divider --r1k 10 --r2k 10`) |
| — | breadboard, jumpers, USB-C data cable | |

Tools: multimeter, a **USB inline current meter** (any $10 one) or, much better, a Nordic PPK2
(source-meter mode, 1 µA resolution, needed for the sleep numbers). A phone is optional for
stage 0; the CLI does everything the app does.

### 1.2 Wiring

Reference diagram: `hardware/pcb/out/wiring_stage0.png`. The table is authoritative
(`src/config.h`, `BOARD_XIAO_ESP32S3_SENSE`):

| Signal | XIAO pin | GPIO | Part |
|---|---|---|---|
| Button → GND | D1 | 2 | tactile switch; internal pull-up; EXT0 wake |
| Haptic enable | D2 | 3 | leave unconnected with the Adafruit breakout (EN is high on-board); only used for a bare MOSFET/ERM |
| Buzzer | D3 | 4 | piezo to GND (optional) |
| I²C SDA / SCL | D4 / D5 | 5 / 6 | DRV2605L + LIS2DW12 (breakouts carry pull-ups) |
| IMU INT1 | D8 | 7 | LIS2DW12 INT1; EXT1 wake |
| Touch pad | D9 | 8 | a 3 × 4 mm copper scrap or bare wire (optional) |
| Aux | D10 | 9 | air-puff driver enable (optional) |
| Battery sense | A0 | 1 | centre of the 100 k/100 k divider from BAT+ |
| 3V3 / GND | 3V3 / GND | — | breakouts' VIN and GND |

Everything except the button is optional: missing I²C devices are detected at boot and the
matching status flags stay clear. Start with **the button only**; add parts in §1.8–1.10.

### 1.3 Flash

```bash
pip install platformio
cd firmware/ring-esp32s3
pio run -e xiao_esp32s3_sense -t upload
pio device monitor -b 115200
```

Boot/Reset dance (only if upload says `Failed to connect` or no port appears): hold **B**,
press and release **R**, release **B** → the XIAO is in download mode and enumerates as a
serial port; run the upload again; afterwards press **R** once (the firmware uses USB-CDC, so
the port disappears for a second and comes back).

**Observe** (first lines after reset; `W` lines are expected until the breakouts are wired):

```
[     150] I main: mcring fw 0.1.0 (xiao-esp32s3-sense)
[     152] I cfg: trig=03 q=12 fs=2 sleep=120s led=96 hap=100 wpm=15 ch=03
[     160] W imu: LIS2DW12 not found (who=...)
[     165] W drv: DRV2605L not found (status=...)
[     420] I cam: sensor PID=0x2640 detected          (0x3660 on OV3660 units)
[     430] I trig: touch baseline 23xxx
[     900] I ble: advertising as mcring-7a3f
```

then the on-board LED (GPIO21) blinks the `<SN>` pattern (`...-.`).

**If not:** no port at all → data cable / driver; on Linux add yourself to `dialout`.
Garbage at 115200 → the monitor opened before CDC re-enumerated; restart the monitor.
`E cam: esp_camera_init failed: 0x...` → the Sense board is not seated (push the two
board-to-board connectors home) or the ribbon between Sense board and camera is loose; `0x105`
(ESP_ERR_NOT_FOUND) or `0x20001` (ESP_ERR_CAMERA_NOT_DETECTED) is the classic "no sensor
answers on SCCB". A reboot loop with `Guru Meditation` right after the `cfg` line → PSRAM not
detected: confirm `board_build.arduino.memory_type = qio_opi` is still in `platformio.ini`
(the Sense needs OPI PSRAM).

### 1.4 Scan and connect

```bash
mcring scan                                   # 10 s scan
mcring send "SOS" --channels 1                # backend-free connection test: connect, blink, disconnect
mcring listen --backend http://localhost:8000 --speak --echo   # the real loop (backend from §0 must be up;
                                                              # listen checks /v1/health first and exits otherwise)
```

**Observe:** `scan` prints `AA:BB:CC:DD:EE:FF  mcring-7a3f  rssi=-55` (macOS shows a UUID instead
of the MAC). Both `send` and `listen` print `I mcring.ring: scanning for mcring* (10s)…`,
`connected; MTU 517` (Linux/BlueZ; macOS reports 185 or more) and a `status: idle
batt=0mV(255%) flags=0x02 ...` line (255 % = no divider fitted; `0x02` = camera_ok); `listen`
then says `listening — press the ring button (or Ctrl-C). 'c' + Enter captures from here.`
On the ring: `I ble: connected ...`, `I ble: MTU 517 -> chunk 510`, three `subscribe ... -> 1`
lines, and a short LED blink. Note that `listen` writes `morse_wpm` and `feedback_channels`
(its `--wpm`/`--channels` values) to the ring's NVS on every connect.

**If not:** `no ring found` → the ring deep-sleeps after **120 s** disconnected and idle
(`DEFAULT_IDLE_SLEEP_S`); press the button to wake it (that press also takes a photo, which is
queued) and scan again. For bench work disable sleep once connected: `mcring config
idle_sleep_s 0` (persisted in NVS). Bleak on Linux needs BlueZ ≥ 5.43 and `bluetooth.service`
running; on macOS grant the terminal Bluetooth permission the first time.

### 1.5 First photo

Press the button once (short press). **Observe** on the ring:

```
I cam: captured 320x240 JPEG, 11234 bytes (q=12)
I xfer: START id=1 type=1 len=11234 chunks=23 x 510
I xfer: ACK complete id=1 (1 rounds)
```

and in the CLI: `transfer 1 start: type=1 11234 bytes in 23 chunks of 510 (320x240)`,
`transfer 1 complete: 11234 bytes in 0.35s (31.3 kB/s)`, `saved captures/capture-....jpg`.
Open the JPEG. Capture latency (trigger → `captured`) should be 150–300 ms.

**If not:** `E main: capture failed (2)` → `MC_ERR_CAPTURE_FAILED`, usually a loose Sense
board or a frame < 100 bytes (sensor not streaming); re-seat and retry. `START` but no
`ACK complete` → see "transfer timeouts" in §4. `queue full, dropped an older capture` →
more than 3 captures while disconnected; connect and let them drain. A photo that is dark
or green → the 3 AEC warm-up frames were not enough in low light; add light or raise the
discard count in `camera_capture()`.

### 1.6 First LLM answer

With `mcring listen --backend http://localhost:8000 --speak --echo` running, press the button.
**Observe:** after the transfer the ring flashes once (the CLI sends a 300 ms `RGB` blue
flash before asking; on the mono LED that is a plain 300 ms blink), the CLI prints the
answer block from §0, speaks it, and then writes the Morse pattern to the ring:
`I fb: play 57 units @ 80 ms, ch=03 (11040 ms total)` on the ring, the pattern mirrored in
the terminal (`--echo`). Trigger → Morse start should be under 6 s (N2).

**If not:** `backend error: ...` in the CLI and `HH` (`........`) on the LED → the backend
returned an error; read its log (§4, "backend 401/413/503"). No Morse but a spoken answer →
`morse.units` empty because `short` reduced to nothing (unusual) or `--channels 0`.

### 1.7 First Morse on the LED

```bash
mcring send "SOS" --wpm 12 --channels 1          # LED only, 100 ms unit
mcring send "R TOXIC" --wpm 15 --overall-wpm 8   # default Farnsworth profile
```

Inside `listen`, `say HELLO` + Enter does the same through the running connection.
**Observe:** `I fb: play N units @ 100 ms, ch=01 (... ms total)`; dots 100 ms, dashes 300 ms,
inter-character gaps visibly longer than dashes (Farnsworth). Count the elements against
`protocol/morse.md`.

**If not:** nothing on the LED but the log line is there → `led_brightness` is 0 (`mcring
config led_brightness 96`). Pattern plays but far too fast → see §4 "Morse too fast".

### 1.8 Add the LRA + DRV2605L

Wire the breakout (VIN 3V3, GND, SDA D4, SCL D5; motor on the two screw/solder terminals).
Stick the LRA to something with mass (the breadboard, a coin) — a free-floating LRA cannot
auto-calibrate. Reset.

**Observe:** `I drv: DRV2605L ready (LRA)` then `I drv: autocal ok (status 0xe0)`; the
`<SN>` boot blink now comes with a haptic tick; `mcring send "SOS" --channels 2` buzzes.
Status `flags` gains bit 4 (`0x12`).

**If not:** `DRV2605L not found` → SDA/SCL swapped or no 3V3. `autocal FAILED (status 0xe8)`
(bit 3 = DIAG_RESULT) → motor not connected, an ERM instead of an LRA, or the rated-voltage
register is far off for your motor. The firmware default `0x3E` means ≈ 1.59 Vrms at 235 Hz
(`python3 docs/build-helpers/tuning_calc.py drv2605 --decode 0x3E 0x8C --freq 235`). For the INEED
LRA0825BC-0167F (≤ 1.25 Vrms, 240 Hz) start from `--vrms 1.25 --freq 240` → `REG_RATED_V 0x31`,
`REG_OD_CLAMP 0x6C`, edit `src/drv2605.cpp`, reflash, re-check autocal. Then set strength:
`mcring config haptic_strength 80` (0–127, RTP amplitude) and find the level that is clearly
felt through a fingertip pressed on the motor without rattling.

### 1.9 Add the LIS2DW12 (double-tap)

Wire VIN 3V3, GND, SDA, SCL, **INT1 → D8**. Reset. **Observe:** `I imu: LIS2DW12 ready at 0x18`
(or `0x19`); status `flags` bit 2 set. Tap the breadboard twice, ~150 ms apart: `I trig: double
tap` then a capture.

Tuning (there is no BLE key for the threshold yet; it is a reflash):

1. The default is `s_ths = 9` → 0.56 g per axis at ±2 g (`tuning_calc.py tap --ths 9`); the
   second tap must land inside a 560 ms window, after 20 ms of quiet, with 40 ms shock
   (`INT_DUR = 0x7A`). The firmware additionally ignores a second double-tap within 800 ms.
2. Mount the breakout on the ring position (tape it to the top of your index finger), wear it
   for an hour of normal hand use with `mcring listen` running and count unwanted `double tap`
   lines (target < 1/h, `docs/benchmarks.md`).
3. Too many false triggers → raise the threshold (`imu_set_tap_threshold(12)` ≈ 0.75 g, call it
   after `imu_init()` in `setup()`, or change the `s_ths` default) and/or shorten `LATENCY` to 5
   (400 ms). Missed deliberate taps → lower it to 7–8, or tap with the fingertip of the other
   hand on the signet rather than clapping. To read what the sensor saw, log
   `imu_read_tap_src()` in `trigger_tick()`: `0x10` = double, `0x20` = single, bits 2:0 = axis.
4. Compare with the button only (`mcring config trigger_mask 1`) and tap only (`trigger_mask 2`).

### 1.10 Voice question (long press)

Hold the button ≥ 700 ms: the ring takes the photo, then records while held, up to 5 s
(16 kHz, IMA-ADPCM ≈ 8 KB/s). Release. Run the CLI with `--wait-voice` so it waits 1.5 s for the
clip before asking.

**Observe:** `I mic: recording up to 5 s`, then two transfers: `type=1` (JPEG) and `type=2`
(ADPCM, `height` field = 160 = 16 kHz/100); the CLI saves `capture-....wav` next to the JPEG and
the answer block shows the transcript folded into the question. Transcription uses OpenAI
(`gpt-4o-mini-transcribe`), so **`OPENAI_API_KEY` must be in `backend/.env`**; without it the
backend logs nothing and simply asks the default `identify` question (transcript `null`).

**If not:** no `type=2` transfer → the press was shorter than 700 ms, or `audio_init` failed
(the Sense board carries the PDM mic; `HAS_PDM_MIC` must be 1). Silence in the WAV → PDM CLK/DATA
are 42/41 on the Sense; check the Sense board is seated. A 40 KB clip takes ~1 s on Android-class
MTU and ~4 s at iOS chunk sizes; keep questions short.

### 1.11 Battery test (100 mAh cell)

1. Solder the 100 mAh cell to the XIAO BAT+/BAT- pads (polarity!) and the 100 k/100 k divider
   from BAT+ to A0. Status now shows a real `batt=4150mV(100%)`.
2. **Unplug USB** for every measurement that matters — the USB meter measures the charger too.
   Put the current meter or the PPK2 (source-meter, 3.8 V) **in series with the battery**.
3. Record the table below. The deep-sleep number with the Sense board attached is ~3 mA by
   construction (the camera board is not power-gated on the dev kit) — measure it, then pull
   the Sense board and measure again; the difference is what the TPS22916 buys you at stage 1.

Numbers to record in `docs/benchmarks.md` (setup/date column included):

| Metric | How | Expected |
|---|---|---|
| Capture latency (button → `captured`) QVGA q12 | serial timestamps | 150–300 ms |
| JPEG size QVGA q12 / VGA q15 | `captured ... bytes` over 10 shots | 8–15 KB / 30–50 KB |
| BLE transfer, 15 KB, laptop (BlueZ/CoreBluetooth) | CLI `complete: ... kB/s` | 20–60 KB/s |
| BLE transfer, 15 KB, Android / iPhone (app) | app log | < 0.3 s / < 1 s |
| Retransmit rounds per transfer | ring `ACK complete id=N (R rounds)` | 1 (= no resend) |
| Backend latency | CLI `in NNNN ms` | 2–5 s |
| Trigger → Morse starts | stopwatch | < 6 s |
| Advertising idle current | meter, disconnected, awake | 20–40 mA (ESP32-S3 awake) |
| Connected idle current | meter, `listen` running, no transfer | 15–30 mA (slow conn params) |
| Capture peak / average over 1.5 s | PPK2 or shunt + scope | 300–370 mA / ~150 mA |
| Morse reply, 10 s, haptic+LED | meter during `mcring send` | 40–80 mA average |
| Deep sleep, Sense board attached | meter after `idle_sleep_s` elapses or `SLEEP` | ~3 mA |
| Deep sleep, Sense board removed | same | 150–250 µA as the firmware stands: XIAO ~64 µA bare + 21 µA divider + **LIS2DW12 ~90 µA** in the 400 Hz high-performance tap-wake mode that `power_deep_sleep_now()` leaves it in (+ breakout regulators/LEDs); 80–100 µA with INT1 lifted and the IMU unplugged |
| Shots on one 100 mAh charge, 30 shots/day pattern | count until `batt` < 3300 mV | model says ~500 (`hardware/power-budget.txt`) |
| Double-tap false positives per hour | §1.9 | < 1 |

**If not:** deep sleep > 300 µA with the Sense board removed → the divider is 10 k (210 µA) or a
breakout has an LED/regulator. The IMU's ~90 µA is expected: `power_deep_sleep_now()` calls `imu_wake()`
(CTRL1 `0x74` = 400 Hz, high-performance — the mode the double-tap engine is specified for), not the
~1 µA low-power ODR the firmware comment and `hardware/power-budget.txt` assume; measure with INT1
disconnected and the IMU unplugged to split it out. The fix is a firmware follow-up (§2.1 item 4), the
same one that decides the stage-1 sleep figure in §2.4.

---

## 2. Stage 1 — oversized printed ring (ESP32-S3-MINI-1U board)

Decision already taken: ESP32-S3-MINI-1U (15.4 × 15.4 × 2.4 mm), antenna end pointing **away**
from the camera, on one rigid 2-layer 0.6 mm board in a signet bay on top of the band; exact
outline in `hardware/pcb/board_params.json`, placement in `hardware/pcb/floorplan.md`,
connectivity in `hardware/electrical/out/mcring_v1.net` (ERC clean: `out/erc.md`).

### 2.1 Before ordering anything

1. Read `hardware/electrical/README.md` §6: the datasheet assumptions (16 items) that could not be
   verified from the sandbox (module pin table, IO33 free on the N4R2, FPC pin order, BQ25100 ball map,
   TPS62840 VSET code, TPS22916 ball map, WS2812B at 3.3 V, antenna outline...). Tick each against the
   datasheet you download.
2. Buy the OV2640 24-pin head **first** and buzz its pin order against §6 item 2 — a
   one-position-shifted variant exists. Confirm whether the head regulates DVDD itself (then
   U4, the 1.2 V LDO, is DNP).
3. Confirm your fab offers 0.1/0.1 mm track/space and 0.2 mm drills on 2-layer 0.6 mm. If not,
   swap both TPS22916 (0.4 mm DSBGA) for TPS22917DBV (SOT-23-5) in `hardware/electrical/mcring_v1.py`,
   regenerate, and use standard rules.
4. Known firmware gaps on `BOARD_MCRING_V1` (stage 0 is unaffected; `hardware/electrical/README.md` §7):
   * **LED rail**: `PIN_RGB_PWR` (IO33, net `LED_PWR_EN`, U9 TPS22916) is defined in `config.h` but
     `feedback.cpp` never drives it, so the WS2812 is unpowered. Patch `feedback_init()` to set it as an
     output and HIGH ≥ 1 ms before the first `neopixelWrite()`, and `power_deep_sleep_now()` to drive it
     LOW — or bridge U9's VIN–VOUT on the first board (costs 0.6–1 mA in sleep).
   * **Charging flag**: `PIN_CHG` (IO3, net `nCHG`, also TP7) is defined but `battery_charging()` returns
     `false`; `MC_FLAG_CHARGING` stays 0 until it reads the pin (active low).
   * **Deep-sleep current**: `power_deep_sleep_now()` calls `imu_wake()` = CTRL1 `0x74` (400 Hz,
     high-performance) so a double tap can wake the ring. That mode costs ~90 µA and puts the stage-1
     sleep floor at ~110 µA (`python3 docs/build-helpers/tuning_calc.py sleep`), not the 25 µA standby
     that `hardware/power-budget.txt` assumes ("IMU 1 uA"). The low-power modes of the LIS2DW12 stop at
     200 Hz, so the realistic follow-up is a wake-up/activity interrupt at 25 Hz LP1 (~2 µA) that wakes
     the ESP32-S3, which then re-arms the 400 Hz double-tap for a few seconds and goes back to sleep if
     none comes (`--imu lp-wakeup` → ~22 µA); LP1 at 200 Hz with `INT_DUR` rescaled (`--imu lp1-200`,
     ~30 µA, marginal tap timing) is the other option. §2.4 and §5 quote both figures.
5. Order with the board (now in `hardware/bom/stage1-ring.csv`): the Molex 146153-0050 flex antenna
   (34.9 × 9 mm, MHF1/u.FL pigtail — the stock 50 mm cable must be shortened or coiled, the cavity is
   2 mm deep, `hardware/cad/README.md` "Antenna"); copper foil with conductive adhesive (3M 1181 class)
   for the 4 × 5 mm lid electrode and a 3 × 4 × 3.6 mm conductive-foam block (or SMT spring finger) for
   TPAD1; two 3 × 2 mm ENIG contacts for the band (a scrap of ENIG board); 30 AWG PTFE / wire-wrap wire
   (≤ 0.7 mm OD for the Ø0.9 channels); UV-cure glue; a 0.3 mm foam or adhesive ring for the mic tube.

### 2.2 PCB order settings

| Setting | Value |
|---|---|
| Layers / thickness / material | 2 / **0.6 mm** / FR-4 TG150+, 1 oz copper |
| Min track / clearance | **0.10 / 0.10 mm** (fine), 0.15 general, 0.3 power (`hardware/electrical/README.md` §5) |
| Min via | 0.20 mm drill / 0.45 mm pad |
| Surface finish | **ENIG** (DSBGA/LGA co-planarity, charging pads) |
| Solder mask | green or black; expansion 0.05 mm (0.03 on DSBGA pads, NSMD) |
| Silkscreen | none under the module |
| Stencil | **two**, 0.10 mm (4 mil) stainless, frameless — one per side: the **bottom** carries every IC except the module, both DSBGAs, the BQ25100, the mic and all passives (64 of the 79 placed parts in `board_params.json`); the **top** only U1, FPC1, SW1, D1, R7, C3. Ask for 1:1 apertures on the DSBGA pads (the fab may want to shrink them — say no) |
| Quantity | 5–10; order 2 spare boards' worth of parts |
| Fiducials | 2 per side if there is room (the bottom is the dense side) |

Also order with the board: low-temperature SnBi58 paste (138 °C) **and/or** SAC305 paste (both if
you want the two-alloy build of §2.3), a hot plate (PCB preheater) and a hot-air station, flux gel,
Kapton tape, a USB microscope.

### 2.3 Assembly order

The board is double-sided and bottom-heavy (`hardware/pcb/floorplan.md` §2–3): the **bottom** carries
every IC except the module (U7 BQ25100, U8 TPS62840 + L1, U2/U9 TPS22916, U3/U4 XC6206, U5 DRV2605L,
U6 LIS2DW12, Q1, D2/D3, MK1 mic), all passives and all wire pads (J1 cell, PAD1w/PAD2w charging,
M1 LRA, BZ1 piezo, J2 aux); the **top** carries U1 (the module), FPC1, SW1, D1 + R7, C3, the TPAD1
copper landing and the eight test pads TP1–TP8. So: bottom first on the hot plate, prove the power
tree, then the top. Two ways to keep the bottom joints solid during the top reflow:

* **(A) one alloy** — top side by hot air with the board on the preheater at ≤ 120 °C (SnBi) / ≤ 150 °C
  (SAC305); the bottom parts hang on surface tension, which is fine for 0402s, SOT-23s and DSBGAs but
  needs a steady hand over the module.
* **(B) two alloys** — bottom in SAC305 (liquidus 217 °C), top in SnBi58 (138 °C) on the hot plate at
  165–175 °C: the bottom never re-melts. Easier for the 15.4 mm module; SnBi on the module's pads is
  fine for a prototype.

**Pass 1 — bottom side (stencil + hot plate):**

1. Kapton over the Ø0.6 mic port hole from the **top** (paste must not enter it), stencil the bottom.
   Place under the microscope: U7 BQ25100 (DSBGA-6), U2 and U9 TPS22916 (DSBGA-4), U8 TPS62840 (SOT-583)
   + L1 (2016 inductor), U3 (2.8 V) and U4 (1.2 V — DNP if the purchased head regulates DVDD itself)
   XC6206, D2 PESD5V0S1BB (bidirectional, no polarity) and D3 PMEG2005EB (cathode toward U7 / `CHG_IN`),
   Q1 AO3400A, U5 DRV2605L (VSSOP-10), U6 LIS2DW12 (LGA-12), MK1 T3902 with its port over the board hole,
   and all 0402/0603 passives. Check the reel labels for the values that set the power tree: R8/R9 1 M
   (divider), R10 9.1 k (25 mA charge), R11 11.5 k (1 mA termination), R12 267 k (3.3 V), R17/R19 100 k,
   R18 4.7 k. Nothing goes on the ten wire pads.
2. Reflow on the hot plate: SnBi peak 165–175 °C for 30 s; SAC305 peak 235–245 °C. The 0.6 mm board
   heats fast — do not exceed 60 s above liquidus.
3. Inspect: every DSBGA sits flat with no bridging visible at the perimeter balls; continuity between
   adjacent balls must be open; the mic sits flat (its port is the acoustic path).
4. Power check — every pad you need is on the still-empty top side. 4.0 V, 100 mA current limit, on
   TP8 (`VBAT`) / TP5 (`GND`): TP6 `3V3` = 3.30 ± 0.05 V (R12 = 267 k), `CAM_3V3` (at C10) and `VLED`
   (at C21) 0 V — R17/R18 hold the two load-switch enables low with no module fitted — idle current
   < 20 µA (buck IQ + divider; DRV2605L and LIS2DW12 power up in standby / power-down). Jumper R17's
   upper pad (`CAM_PWR_EN`, U2.B1) to TP6: `CAM_3V3` 3.3 V, `CAM_2V8` 2.8 V at C11, `CAM_1V2` 1.2 V at
   C12 (if U4 fitted); jumper R18's upper pad (`LED_PWR_EN`) to TP6: `VLED` 3.3 V. Charger: replace the
   bench supply by a 3.7 V cell on J1a (BAT+) / J1b (GND), put 5 V on the PAD1w pad (`CHG_PAD`) and GND
   on PAD2w: TP7 `nCHG` goes low, ≈ 25 mA flows into the cell, U7.A1 sits ~0.25 V below the pad (D3).
   Swap the 5 V: nothing conducts (D2 bidirectional + D3) — that is the reversed-cradle case.

**Pass 2 — top side:**

5. Leave the Kapton over the mic hole, stencil the top. Place U1 ESP32-S3-MINI-1U with the **u.FL end
   flush with the back edge** (x = 26.5, away from FPC1 — the antenna end points toward the back of the
   hand), FPC1 (mouth toward the front edge; bottom-contact), SW1 (plunger out of the left edge, y = 0;
   it reflows fine), D1 (DIN toward R7), R7, C3. Leave TPAD1 bare — the foam contact goes on at final
   assembly (§2.6).
6. Reflow: (B) hot plate 165–175 °C with SnBi; (A) hot air 300 °C / low flow in a slow spiral over the
   module with the board on the preheater — the shield can is the thermal mass, give it time. A gentle
   push after the paste melts seats the edge pads. Keep the FPC1 actuator open and paste-free.
7. Inspect the module perimeter; continuity U1 pads 3 / 45 / 4 → TP6 / TP2 / TP1; FPC1 pins 3 / 5 / 13
   (SIOD / SIOC / XCLK) → R5 / R6 / U1 (buzz against `floorplan.md` §7). Remove the Kapton.

**Wires (before the board goes into the bay — every wire pad is on the bottom and the wires go down
into the band):** LRA leads to M1a/M1b (≈ 15 mm, strain relief with a dab of UV glue), the two 30 AWG
charging-pad wires to PAD1w (CHG+) / PAD2w (CHG−) (≈ 25 mm, trimmed later in the rib grooves), piezo
to BZ1a/BZ1b if fitted, J2 only for the air-puff experiment. The cell leads go on **last**, in §2.6
step 4, with the cell already in its pocket. Snap the antenna's u.FL plug onto the module for the §2.4
BLE checks (press straight down until it clicks; the mated plug is the 2.9 mm tallest part).

### 2.4 Firmware on the stage-1 board

USB is on the test pads, all on the **top** side so they stay reachable with the board seated in the
bay and the lid off: a sacrificed USB cable — D− → TP3 (IO19), D+ → TP4 (IO20), GND → TP5. **Do not
connect VBUS**: the board runs from the cell on J1 or from 4.0 V on TP8/TP5; the BQ25100 cannot power
the ESP32-S3 (its output is the 25 mA charge current, `hardware/electrical/README.md` §4), and 5 V
belongs only on the charging pads. Download mode: hold TP1 (IO0) to TP5 (GND), pulse TP2 (EN) to GND,
release TP1; then:

```bash
cd firmware/ring-esp32s3
pio run -e mcring_v1 -t upload            # esp32-s3-devkitc-1 profile, qio_qspi, 4 MB default.csv
pio device monitor -b 115200
```

**Observe:** `I main: mcring fw 0.1.0 (mcring-v1)`, `I imu: LIS2DW12 ready at 0x18`, `I drv:
DRV2605L ready (LRA)` + `autocal ok`, `I cam: sensor PID=0x2640 detected`, `advertising as
mcring-XXXX`. `PIN_CAM_PWR` (IO21) behaviour: high for ~0.3 s during `camera_probe()` at boot,
then low; high again for 0.2–0.5 s per capture, low between shots — scope `CAM_3V3` while
pressing the button. There is no LED until the §2.1 item 4 patch (`PIN_RGB_PWR` is defined but not
driven); the haptic tick confirms boot instead.

**Serial checks before closing the enclosure:**

| Check | Expect |
|---|---|
| `camera_probe` | `PID=0x2640`; if `esp_camera_init failed: 0x105`, re-check FPC pin order and `CAM_3V3`/`CAM_2V8` during the probe |
| capture | `captured 320x240 JPEG` 8–15 KB; `CAM_3V3` returns to 0 V after |
| battery | `batt=` within 50 mV of the meter (R8/R9 **1 M/1 M**, `BATTERY_DIVIDER 2.0`; C23 100 nF holds the node for the 8-sample burst) |
| button | short press → capture; long press → `recording up to 5 s` |
| double tap | tap the board twice → `double tap` |
| sleep | `mcring config idle_sleep_s 20`, disconnect, wait → `I pwr: deep sleep`; battery current (PPK2 in series with the cell): **≤ 130 µA as the firmware stands** — ESP32-S3 7–8 µA + LIS2DW12 ~90 µA (400 Hz high-performance tap-wake, see §2.1 item 4) + divider 2 µA + DRV2605L standby ≤ 4 µA + mic/charger/buck/switch leakage ~6 µA ≈ 110 µA (`python3 docs/build-helpers/tuning_calc.py sleep`); **≤ 30 µA** only after the IMU low-power wake follow-up (`tuning_calc.py sleep --imu lp-wakeup` → ~22 µA). `CAM_3V3` and `VLED` read 0 V in sleep; ~3 mA means the camera rail is on (IO21 high / R17 missing). Press the button → `woke from deep sleep, cause 2`, `wake trigger -> capture`; tap → `cause 3` |
| charging | 5 V on the pads: TP7 `nCHG` low (IO3 low); `battery_charging()` still returns `false` until the §2.1 item 4 follow-up, so `MC_FLAG_CHARGING` does not change yet |

### 2.5 Enclosure print and post-processing

Files: `hardware/cad/` — `python3 hardware/cad/mcring_stage1.py` generates them from
`hardware/pcb/board_params.json` (CadQuery 2.8, ~1 min; `--no-step --no-views` for a 12 s fit check;
`--inner-d 18.3` for US 8, default 20.0 = US 10 — size table in `hardware/cad/README.md`). Three print
files: `out/mcring_stage1_shell.stl` (band + signet bay + camera pod, one part), `out/mcring_stage1_lid.stl`
(rebated lid with the detent beads, the mic tube, the LED mark and the touch dimple),
`out/mcring_stage1_key.stl` (the side-switch button); `out/mcring_stage1_assembly.step` carries every
placeholder for a viewer and `out/view_*.png` are the sanity views. `hardware/cad/fit_report.md` is the
as-built check (all intersections 0, clearances and wall probes listed). There is **no cradle model**, and
the old OpenSCAD concept with the 26 × 12 bay no longer exists — if `out/` is empty, run the script.

Numbers you will touch (`default_params()` in the script): band Ø20.0 ID × 22.4 OD × 12 wide, wall 1.2;
signet 31.5 × 21.0 mm, lid top 11.1 mm above the skin, pod roof 12.7; lens bore Ø4.6 (OV2640 barrel 4.5),
lens axis 6.25 mm above the skin; mic port Ø0.8 in the lid above a Ø1.8 tube that ends 0.3 mm above the
board; switch slot 3.4 × 1.6 through the left wall with a 4.6 × 2.8 × 0.5 counterbore inside for the key's
flange; cell pocket 10.4 × 12.4 × 3.4 and LRA pocket Ø8.4 × 2.9, both recessed into the bay floor under the
board; charging-pad windows 3 × 3 at ±25° from the bottom of the band, fed by two Ø0.9 wire channels from
the grooves on the −Y rib; lid 1.2 thick in a 0.5 rebate with 0.15 clearance, Ø0.5 detent beads, 1.0 mm
pod-roof lip over its front edge; LED: the lid stays 1.2 mm thick over D1 (an engraved Ø3 ring marks the
spot, the LED top is 2.3 mm below the lid) — no thinned window; touch dimple 4 × 5 × 0.4 (0.8 mm resin
over the lid electrode).

SLA (recommended): white or translucent **tough** resin (the detent rims and the 0.7 mm wall around the
switch counterbore do not survive a brittle one), 0.05 mm layers. **Shell**: bay opening up, finger axis
horizontal, supports under the camera pod and the signet shoulders, none in the bay, on the lid rebate or
under the pod-roof lip. **Lid**: beads up, mic tube up, light supports or flat on the plate — then sand
the elephant foot off the rebate faces, 0.15 mm is all the clearance there is. **Key**: cap down, no
supports. Wash 2 × 5 min in IPA (the second bath clean), dry, remove supports before curing, cure
10–15 min and **not longer** — over-curing yellows the resin and dims the LED through the lid. FDM
(0.4 mm nozzle, 0.12 mm layers, PETG) works for the shell only: drill the Ø0.8 mic hole, glue the lid,
and the key will not print — glue a 3.2 × 1.4 mm pin on a flange instead.

Post-processing: ream the lens bore with a 4.5 mm drill shank (print 4.6, finish to a snug fit on the
barrel); clear the Ø0.8 mic hole down through the tube with a 0.8 mm drill; slide the key through the
3.4 × 1.6 slot (0.3 mm travel at the cap); open the two 3 × 3 pad windows and pass a 0.9 mm drill through
the two wire channels (they start in the open grooves on the −Y rib and surface in the bay floor beside
the −Y wall); clear the 3 × 0.8 mm cell-lead channel. Fill the grooves with resin only after the wires are
in (§2.6).

Fit-check before assembly, against `fit_report.md`: the board drops onto its ledges with 0.3 mm play per
side (front ledges 1.0 mm wide in the gaps between the bottom parts, back ledge 3.2 mm under the test
pads; board top 0.6 mm above the ledge); the 301012 cell (3 × 10 × 12 mm) drops into the floor pocket
with 0.2 mm per side — a cell **with PCM** is longer at the tab end, check yours before the final print;
the LRA (Ø8 × 2.5) drops into its Ø8.4 pocket and ends 0.2 mm below floor level; the camera head
(8.5 × 8.5 mm, 5.8 mm tall incl. barrel) slides from the bay into the pod through the 9.2 × 9.8 opening
until the barrel sits 0.4 mm into the bore, with 0.3 mm to the floor, 0.35 to each wall and 1.0 mm above
it for the FPC fold; the lid's front edge slides under the pod-roof lip and its beads click into the
grooves. Worn with the band against the knuckle the pod front sits ~17 mm toward the PIP joint — try
the bare shell on the finger before printing in volume.

### 2.6 Mechanical assembly sequence

Pockets first, then the board, then the lid — the LRA and the cell sit **under** the board in the bay
floor and cannot go in afterwards (`hardware/cad/README.md`, "After printing — check").

1. **Key**: drop the printed key into the switch slot from inside the bay (flange in the counterbore,
   cap outside). It is loose until the board holds it.
2. **Charging wires**: thread the two 30 AWG wires already soldered to PAD1w/PAD2w (§2.3) down through the
   Ø0.9 channels that open in the bay floor beside the −Y wall — the X −1.5 channel leads to the −Y window
   (CHG−, PAD2w), the X −3.5 channel round the bottom to the +Y window (CHG+, PAD1w) — out into the rib
   grooves and to the windows. Tin each end to a 3 × 2 mm ENIG contact, press the contact into its 3 × 3
   window flush with the bore (UV glue around the edge, nothing on the face), fill the grooves with resin
   or epoxy. Both contacts flush, ≈ 8.5 mm apart (§2.8).
3. **LRA** into its pocket, face toward the finger, bonded to the pocket floor with 3M VHB or
   cyanoacrylate — rigidly coupled to the shell, never floating in foam. Its leads already run to M1a/M1b.
4. **Cell** into the floor pocket, tabs toward the −Y side in the 3 × 0.8 mm channel toward the J1 pads;
   tape it down. Now solder the leads, with the board held above the bay: J1a BAT+, J1b GND (polarity!).
5. **Camera head** from the bay into the pod until the barrel sits 0.4 mm into the bore, lens along the
   finger; its flex comes back out of the pod opening toward the bay.
6. **Board**: with the board above the bay insert the flex into FPC1 (contacts facing the board — it is
   a bottom-contact connector), close the actuator, then lower the board onto the ledges, u.FL end toward
   the back wall, FPC1 toward the pod — the flex folds 180° behind the head as the board goes down
   (≈ 11 mm of flex from the head's top edge to the contacts; measure the purchased head). Check: switch
   plunger on the key's flange, D1 under the lid's LED mark, mic port where the lid tube lands, nothing
   under the board but the cell, the LRA and the wires.
7. **Antenna**: glue the flex antenna to the inside of the back wall in the 2 mm cavity (no metal, cell
   or LRA there); the pigtail turns down behind the board edge; cable ≤ 30 mm or the excess coiled along
   the back wall — never over the module or across the FPC.
8. **Touch contact**: stick the 4 × 5 mm copper foil to the lid underside under the dimple (board
   coordinates (8.1, 5.6)); set the 3 × 4 × 3.6 mm conductive-foam block (or spring finger) on TPAD1.
   The lid compresses it to 3.2 mm.
9. **Mic seal**: a 0.3 mm foam or adhesive ring on the board around the Ø0.6 port hole at (8.1, 15.85),
   where the lid's Ø1.8 tube lands.
10. **Lid**: run the §2.4 checks once more (the test pads stay reachable), then slide the lid's front edge
    under the pod-roof lip and press the back down until the beads click into the grooves — 0.1 mm of
    engagement, a light locating click. A drop of UV glue or a strip of tape on the back edge is the real
    retention; there are no screws or bosses.

### 2.7 Sealing options

| Option | When | How |
|---|---|---|
| None | bench and indoor tests | keep it off when washing hands |
| Conformal coat | daily wear | acrylic spray on the board only; mask the test pads, the wire pads, SW1, FPC1, the mic port hole, the u.FL and TPAD1 |
| Lid seal | daily wear | a thin bead of neutral-cure silicone on the rebate faces before closing — the 0.15 mm rebate clearance leaves no room for a gasket sheet |
| Potting | long-term prototype | neutral-cure silicone (e.g. Sylgard 184) into the bay with the key/switch counterbore, the mic tube landing, the FPC fold and the LRA pocket masked; **never pot the LRA** (it must move), the switch or the mic port; potting is permanent and buries the test pads |

### 2.8 Charging via the pogo pads

Cradle (not modelled in `hardware/cad/`; a printed block): a saddle the band drops into palm-down,
indexed by the signet so the ring only fits one way; two spring pogo pins (P50-B1 / P75-E2 class,
0.68–1.0 mm tips) rise through the saddle on a ±25° V aimed at the ring axis and reach the ENIG contacts,
which sit flush with the Ø20 bore behind the 3 × 3 windows in the 1.2 mm wall. Geometry for the default
size (`python3 docs/build-helpers/tuning_calc.py pads --inner-d 20 --angle 25`): pad centres **8.45 mm
apart across the finger** (8.73 mm along the bore), each 4.23 mm off the ring's vertical mid-plane and
9.06 mm below the axis, pin axes tilted 25° from vertical; the two pads are **staggered 2.0 mm along the
finger** (CHG− at X −1.5, CHG+ at X −3.5 from the band's mid-plane toward the antenna end). A 2-pin cable
to a USB breakout: VBUS → CHG+ (PAD1/CP1), GND → CHG− (PAD2/CP2). Nothing else is in the cradle; the
BQ25100 does the regulation (25 mA, 1 mA termination, ~1.5 h from empty for the 30 mAh cell). D3 lets a
reversed ring survive, but key the saddle anyway. Check: TP7 `nCHG` low in the cradle; battery voltage
rising; the pads never see more than 5.5 V (D2). `MC_FLAG_CHARGING` stays 0 until the firmware reads
`PIN_CHG` (§2.1 item 4) — the pad voltage itself is your indicator.

### 2.9 Wearing and aiming

Index finger, signet on top, lens toward the fingertip, switch on the thumb side. Aim by
pointing the finger: the OV2640 head gives ~65° horizontal FOV, so 25–40 cm from the object
fills the frame; hold still for one beat after the trigger (power-up + 3 AEC frames ≈ 200 ms).
Daylight or room light; dim restaurants are marginal at QVGA. The `<SN>` tick tells you the shot
was taken; the Morse reply lands 2–6 s later.

### 2.10 On-finger calibration

**Touch** (`PIN_TOUCH` IO8 → R13 → TPAD1 landing → foam contact → the 4 × 5 mm foil on the lid underside,
0.8 mm of resin over it): boot prints `touch baseline N`; the pad
triggers on +25 % over a slow baseline after 150 ms of contact (`trigger.cpp`). On a finger the
adjacent finger is always near — enable touch only if a deliberate thumb press on the top face
clearly exceeds the threshold: watch `touch (V > base)` lines while resting the hand, then
`mcring config trigger_mask 7` (button + tap + touch) or leave it at `3`. A threshold change
means editing the `+25 %` in `trigger_tick()`.

**Tap**: repeat §1.9 steps 2–4 on the finished ring; the shell couples hand impacts more than
the breadboard did, so expect to end one or two threshold steps higher (10–12). Log false
positives per hour in `docs/benchmarks.md`.

---

## 3. Stage 2 path (nRF52840, Oura-size) — what to prove, in order

Nothing below needs the stage-1 ring; start it in parallel on a Seeed XIAO nRF52840 Sense.

1. **Protocol peer on nRF52840.** `west build -b xiao_ble -p auto firmware/ring-nrf52840 &&
   west flash` (nRF Connect SDK ≥ 2.7). `mcring listen` must connect and receive the synthetic
   160 × 120 frame; this proves the phone/backend side needs no change for stage 2.
2. **Bit-bang 8-bit DVP capture.** OV7670/OV7675 FPC head on 11 GPIOs of one port; capture
   QQVGA grayscale (19.2 KB) with PCLK polled, then with GPIOTE+PPI; record capture time, CPU
   load and current (PPK2). Pass: a recognisable frame in < 300 ms at < 15 mA average.
3. **Software JPEG.** Add a baseline encoder (jo_jpeg / TinyJPEG class) in `camera_hal.c`;
   measure encode time and size at 160 × 120 and 320 × 240 gray; target ≤ 20 KB → ~0.7 s on iOS.
4. **HM01B0 1-bit SPIS experiment.** Arducam HM01B0 for Pico (or the Himax lensed module):
   D0 → SPIS MOSI, PCLK → SPIS SCK, VSYNC/HSYNC → GPIOTE for frame/line framing; configure 1-bit
   serial output over I²C; try (a) SPIS + EasyDMA per line, (b) PPI-started SPIS per frame.
   Pass: 320 × 320 mono frame in < 100 ms with < 2 mW sensor power. This is unproven R&D
   (`docs/research/01-camera-modules.md` §2); budget two weekends and stop if (a) and (b)
   both fail.
5. **Per-shot energy** on the PPK2 against `hardware/power-budget.txt` (113 µAh/shot target,
   30 µA standby with a slow BLE connection).
6. **Grepow curved-cell samples** — send now; lead times are long. Template:

   > Subject: Sample request — curved Li-Po 16–24 mAh, 1C, for a smart-ring prototype
   >
   > Hello Grepow team, I am building a smart-ring prototype (electronics in an ~8 mm band,
   > ~20 mm inner diameter) and need curved Li-Po cells comparable to GRP170722 (14.5 mAh,
   > 1.7 × 6.5 × 22 mm) or your 21–24 mAh curved E-stacking cells. Requirements: 3.7 V, ≥ 1C
   > continuous discharge, PCM optional, charge at ≤ 1C with 1 mA termination (TI BQ25100).
   > Could you send: (1) datasheets and drawings of curved cells between 14 and 24 mAh,
   > (2) sample pricing and MOQ for 5–20 pieces, (3) lead time, (4) whether an NDA is required.
   > Shipping to <address>. Thank you, <name>, <project>, <phone>.

7. **Rigid-flex vendor checklist** (send to PCBWay / JLC rigid-flex / a local shop):
   stack-up 0.22 mm flex (2-layer polyimide) with 0.48 mm rigid islands; min track/space
   0.075/0.075 mm; min via 0.15 mm laser or 0.2 mm mechanical; ENIG; coverlay openings for
   WLCSP (nRF52840 0.4 mm pitch) and the OVM7692 25-ball CSP; stiffener under the cell contact
   area; bend radius ≥ 10× flex thickness at the two band folds; impedance note for the printed
   microstrip antenna; assembly quote including X-ray for the WLCSP; panel of 5–10.
8. **Haptic on-finger comparison**: VG0640001D 6 mm LRA + DRV2624 vs PowerHap 0904H014V060 +
   BOS1901, same Morse corpus, blind test of character recognition at 15/8 WPM.

---

## 4. Troubleshooting matrix

| Symptom | Likely cause | Check / fix |
|---|---|---|
| `esp_camera_init failed: 0x105` / `0x20001` | sensor not answering on SCCB; camera rail off; wrong FPC pin order | Sense board seated (stage 0); `CAM_3V3`/`CAM_2V8` present during probe, IO21 high, pull-ups on `CAM_3V3` (stage 1); buzz FPC pins vs `hardware/electrical/README.md` §6 item 2 |
| `capture failed (2)` | frame < 100 B, sensor streaming but no data | PCLK/VSYNC/HREF wiring; XCLK 20 MHz on IO10 (scope) |
| No BLE device in `mcring scan` | ring asleep (120 s idle); BlueZ down; another central already connected (1 connection max) | press the button; `bluetoothctl show`; close the phone app; `mcring config idle_sleep_s 0` for the bench |
| MTU stuck at 23 (`START ... x 16`, ~1 KB/s) | central never did the ATT MTU exchange (only the client can initiate it) | Android app: `dev.connect({ requestMTU: 517 })` in `app/src/ble/RingClient.ts` — check its `connected, MTU n` log; old BlueZ: upgrade; the ring log `MTU n -> chunk m` shows the truth |
| iOS 178-byte chunks (`MTU 185 -> chunk 178`) | normal: iOS caps ATT MTU at 185 and the connection interval at 15 ms | not a fault; expect 10–12 KB/s; keep QVGA (≤ 15 KB); never hard-code chunk size |
| `no ACK, resending END` → `giving up` (`last_error=3`) | phone not subscribed to meta/data; app blocked; ACK lost | ring log must show three `subscribe ... -> 1`; `notify dropped after retries` means controller buffers overflowed — lower `set_tx_credits_max()` or the interval is too long (`request_fast_params`) |
| Many `resend N chunks (round R)` | notifications dropped at high MTU; RF marginal | move closer; check the antenna end is clear of the cell/LRA; 2M PHY not granted by the phone is fine, resends should still converge in ≤ 2 rounds |
| Morse too fast / dots and dashes blur on the LRA | 20–40 ms LRA rise/fall vs 80 ms dots; strength too high; no Farnsworth | `--wpm 12 --overall-wpm 6` (`tuning_calc.py morse --wpm 12 --overall 6`); `haptic_strength 60–90`; confirm autocal passed (closed-loop braking is what gives crisp edges) |
| `autocal FAILED (status 0xe8)` | DIAG_RESULT set: motor missing/ERM/wrong rated voltage; motor not coupled to mass | wiring; `drv2605_init(true)`; recompute `REG_RATED_V`/`REG_OD_CLAMP` for the motor (§1.8); stick the LRA down before calibrating |
| Double-tap false triggers | threshold 0.56 g too low for hand impacts; 560 ms window too wide | §1.9: `imu_set_tap_threshold(12)`, `LATENCY 5`; compare `trigger_mask 1` vs `2`; log `TAP_SRC` |
| Double-tap never fires | INT1 not on IO7; `trigger_mask` bit 1 clear; wrong I²C address not auto-detected | `imu ready at 0x18/0x19` line; `mcring config trigger_mask 3`; `TAP_SRC` shows `0x20` singles only → taps too slow |
| ~3 mA deep-sleep current | camera board not gated (stage 0), IO21 high/floating without R17, WS2812 un-gated (0.6–1 mA, or U9 bridged), 10 k divider (stage 0) | stage 0: pull the Sense board, 100 k divider; stage 1: scope `CAM_3V3`/`VLED` in sleep, add `PIN_RGB_PWR` handling |
| ~100–130 µA deep-sleep current on stage 1 | expected as the firmware stands: `power_deep_sleep_now()` leaves the LIS2DW12 at 400 Hz high-performance (~90 µA) for tap-wake | `tuning_calc.py sleep`; confirm with INT1 lifted and the IMU powered down; the ≤ 30 µA figure needs the low-power wake mode (§2.1 item 4) |
| Ring reboots during capture on battery | 300–370 mA peak sags a small cell / thin wires | 100 µF bulk at the module (stage 1), shorter battery leads; on the 100 mAh dev cell this should not happen — check solder joints |
| Backend **401** | `MCRING_API_TOKEN` set | `mcring ... --token <t>`; app Settings → token |
| Backend **400** `an image is required` | follow-up without a session id, or session expired (30 min) | pass `--session`, or send a new photo |
| Backend **413** `image too large` | > 8 MB upload (`MCRING_MAX_UPLOAD_BYTES`) | ring images are ≤ 60 KB — this is a CLI misuse with a huge file |
| Backend **429 / 502 / 503** | provider rate-limit / API error / connection error (`retryable` in the JSON) | wait and retry; check `ANTHROPIC_API_KEY`; `MCRING_PROVIDER`; 503 with `connection error` → outbound network/proxy |
| Backend **501** | `provider=openai` without the `openai` package | `pip install openai` |
| Answer is `? NO ANSWER` | model refused (422 internally, mapped to a stock answer) | expected for people/faces/unsafe content; re-aim |
| Voice clip ignored (transcript `null`) | no `OPENAI_API_KEY` for transcription | add it to `backend/.env` (§1.10) |
| LED dark on stage 1 | `PIN_RGB_PWR` (IO33, `LED_PWR_EN`) is defined but `feedback.cpp` never drives it; R18 keeps U9 off | §2.1 item 4 (patch, or bridge U9) |
| `queue full, dropped an older capture` | > 3 captures offline | connect; raise `MAX_QUEUED_CAPTURES` only if PSRAM allows |

---

## 5. Acceptance checklist per stage (docs/01 F1–F9)

Tick each line with the evidence named; record numbers in `docs/benchmarks.md`.

### Stage 0 — bench rig

| Req | Pass criterion | Evidence |
|---|---|---|
| F1 | button, double-tap **and** touch each produce `captured ... JPEG` | serial log, §1.5/1.9/2.10 |
| F2 | 15 KB JPEG reaches the CLI in < 1 s on a laptop; < 0.3 s Android / < 1 s iPhone in the app | `complete: ... kB/s`, app log |
| F3 | `mcring listen` returns an answer with `subject`, `confidence`, `short` for a daylight photo | CLI output |
| F4 | answer spoken by the CLI (`--speak`) and by the phone app (expo-speech) | ears |
| F5 | `short` played on LED and LRA with Farnsworth spacing; a second person reads "SOS" and "R" by touch alone | §1.7/1.8 |
| F6 | long press → ADPCM clip → transcript folded into the question | §1.10, `transcript` in the response |
| F7 | `mcring ask --session <id> -q "is it edible?"` (no image argument) answers about the previous photo | CLI: same `session:` id returned, answer refers to the earlier subject |
| F8 | 3 shots taken while disconnected are delivered on reconnect, in order | `flags` bit 5 / `queued`, three transfers |
| F9 | `mcring config morse_wpm 12`, `feedback_channels 1`, `trigger_mask 2` each persist across a reset | `I cfg:` boot line |
| N2 | trigger → Morse start < 6 s on 5 consecutive shots | stopwatch |
| — | benchmarks table §1.11 filled in | `docs/benchmarks.md` |

### Stage 1 — oversized ring

| Req | Pass criterion | Evidence |
|---|---|---|
| F1 | side switch and on-finger double-tap trigger; < 1 false tap/h over a 4 h wear | §2.10 log |
| F2 | transfer numbers within 20 % of stage 0 with the ring on the finger, phone in a pocket | app log |
| F3/F4/F7 | unchanged from stage 0 (same firmware, same backend) | one full loop |
| F5 | Morse readable on the finger through the shell at 15/8 WPM with `haptic_strength` ≤ 100; LED visible through the 1.2 mm lid in daylight (after the §2.1 item 4 patch) | blind read of 5 short answers |
| F6 | voice question through the Ø0.8 lid port is transcribed correctly 4 times out of 5 at arm's length | transcripts |
| F8 | as stage 0, plus wake-from-deep-sleep by tap and by button both produce a queued capture | `woke from deep sleep, cause 2/3` |
| F9 | as stage 0 | |
| N3 | ≥ 30 shots/day for 1 day on the 30 mAh cell with `idle_sleep_s 120`; deep sleep **≤ 130 µA as the firmware stands** (≈ 110 µA modelled → 3.3 days at 30 shots/day), **≤ 30 µA** once the IMU low-power wake follow-up is in (≈ 22 µA → 4.7 days; `tuning_calc.py sleep [--imu lp-wakeup] --shots-per-day 30`; `hardware/power-budget.txt`'s 25 µA standby assumes the latter) | PPK2 log, `batt` at end of day ≥ 3600 mV |
| Mech | lid clicks under the pod lip and stays on, key actuates the switch with 0.3 mm travel, lens clear and centred in the bore, pads charge at 25 mA, 24 h worn without loose parts and without the pod binding at the PIP joint | inspection |
| Safety | cell never above 45 °C while charging; charger stops (`TP_nCHG` high) within 2 h | thermometer |

### Stage 2 — Oura-size (planning gate, not a build)

| Gate | Pass criterion |
|---|---|
| G1 | §3.1 synthetic-frame peer works with the unmodified app and CLI |
| G2 | §3.2/3.3: real QQVGA gray JPEG ≤ 20 KB captured and encoded on nRF52840 in < 500 ms total |
| G3 | §3.5: per-shot energy ≤ 150 µAh measured; standby ≤ 40 µA with BLE connected at 400 ms interval |
| G4 | a curved 16–24 mAh cell is in hand (§3.6) or the stage-1.5 flat-cell fallback is chosen explicitly |
| G5 | rigid-flex quote and stack-up accepted (§3.7); WLCSP assembly house identified |
| G6 | haptic choice made from the §3.8 comparison |

Only when G1–G5 pass does a stage-2 board get laid out; until then stage 1 is the wearable.
