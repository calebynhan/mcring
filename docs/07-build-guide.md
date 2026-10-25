# 7. Build and integration guide

How to go from a box of parts to a working ring, one stage at a time, with a check at every
step. It assumes the repo as it is: `firmware/ring-esp32s3` (ESP32-S3, PlatformIO),
`backend/` (FastAPI), `tools/ring-cli` (the `mcring` desktop companion), `app/` (Expo phone
app) and the hardware files under `hardware/`. Requirements F1–F13 (voice loop, camera as
context, ring cues and the optional speaker, platform) are in `docs/01-vision-and-requirements.md`.
The loop you are building: **hold the ring → ask → the answer is spoken in your Bluetooth
headphones** (paired to the laptop/phone, never to the ring); the ring ticks once when it listens
and twice when the answer is ready, and on the oversized stage-1 ring can optionally play the
answer through its own small speaker.

Conventions: every step says what you should **observe** and what to do **if not**. Serial
log lines are quoted as the firmware prints them (`[   millis] I tag: text`, see `src/log.h`).
CLI output is quoted from `tools/ring-cli/mcring_cli/*.py`.

Files produced by other steps of the hardware pass are referenced by path; if a path does not
exist yet, that step has not been run and the guide tells you what to fall back to:

| Path | Produced by | Used in |
|---|---|---|
| `hardware/pcb/out/wiring_stage0.png` | PCB/wiring step | §1.2 |
| `hardware/pcb/out/wiring_stage0_solderless.png`, `hardware/pcb/wiring_stage0_solderless.md`, `hardware/bom/stage0-devkit-solderless.csv` | no-solder step (present) | §1.12 |
| `hardware/pcb/floorplan.md`, `hardware/pcb/board_params.json` | PCB floorplan step | §2.1, §2.6 |
| `hardware/electrical/out/mcring_v1.net`, `out/sch_*.png`, `out/erc.md` | electrical step (present) | §2.1, §2.3 |
| `hardware/cad/out/mcring_stage1_{shell,lid,key}.stl`, `hardware/cad/fit_report.md`, `hardware/cad/README.md` | enclosure CAD step (CadQuery, generated from `board_params.json`; the old OpenSCAD file is gone) | §2.5–2.8 |
| `docs/build-helpers/tuning_calc.py` | this guide (`sleep`, `pads`, `divider`, `drv2605`, `tap`, `speaker` calculators; `morse` for the optional silent mode) | §1.8, §1.9, §1.10, §1.11, §2.4, §2.8, §5 |

---

## 0. Before any hardware: prove the voice loop from the terminal (30 min)

All commands run from the **repo root** (`requirements.txt` installs `python/mcring_core` with a
relative `-e ../python/mcring_core`, so the backend install is run from `backend/`, exactly as
`backend/README.md` does):

```bash
git clone <repo> && cd mcring
python -m venv .venv && . .venv/bin/activate
(cd backend && pip install -r requirements.txt)   # backend deps + python/mcring_core (editable)
pip install -e 'tools/ring-cli[mic]'              # the mcring CLI; [mic] = sounddevice for the laptop microphone
cp backend/.env.example backend/.env              # ANTHROPIC_API_KEY (answers) + OPENAI_API_KEY (speech-to-text)
(cd backend && uvicorn app.main:app --port 8000 &)
curl -s localhost:8000/v1/health
mcring ask ~/Pictures/any-photo.jpg -q "what is this and is it dangerous?" --speak   # typed question about a photo
mcring talk --no-ring                                                                 # spoken question, laptop mic
```

(`pip install -r backend/requirements.txt` from the root fails with `../python/mcring_core is not a
valid editable requirement` — the path in the file is relative to `backend/`. Both lines above were
checked with `pip install --dry-run`.)

**Observe:** `{"status":"ok","version":…,"provider":"anthropic","model":"claude-opus-5-5","tts":"none","stt":"openai","speech_default":false,"speech_formats":[…]}`
from the health check. `mcring ask` prints `<subject>  [NN%]  via claude-opus-5-5 in NNNN ms  (photo)`,
a `claude:` line with the 1–3 sentence answer (and the follow-up offer under it), speaks it with the
OS voice, and ends with `session: <id>`. `mcring talk --no-ring` prints `no ring — laptop mic + local
speech only` and `talk — Enter: start recording · Enter: stop & ask · …`; press Enter →
`● recording… (Enter to stop)`, ask something, Enter → `■ 2.3 s — asking…`, then the same answer
block with a `you   :` line (the transcript) and the spoken answer. Pair Bluetooth headphones to
the laptop and the answer plays there — this is the routing the ring relies on (F4).

**If not:** `backend not reachable` → uvicorn is not up or the port differs (`--backend`).
HTTP 401 → `MCRING_API_TOKEN` is set in `.env` but you did not pass `--token`. 5xx → see §4.
`laptop mic unavailable (pip install 'mcring-cli[mic]')` → the `[mic]` extra is missing or no
input device; `mcring ask … -q` needs no mic. HTTP 501 on a spoken question → no `OPENAI_API_KEY`
for speech-to-text: add it, or `pip install faster-whisper` + `MCRING_STT_PROVIDER=local` in `.env`.
No sound from `--speak` → the CLI tries `afplay`, `mpg123`, `ffplay`, then `say`/`espeak-ng`;
install one, or ignore (the text is printed anyway). Tests to run once: `docs/06-getting-started.md` §C.

---

## 1. Stage 0 — bench rig (XIAO ESP32S3 Sense)

### 1.1 Order list

> **No soldering iron?** §1.12 builds the same rig from parts that plug together (pre-soldered XIAO in
> Seeed's Expansion Board Base, Grove haptic module, STEMMA QT accelerometer) — zero joints, same
> firmware (env `xiao_esp32s3_sense_base`), same §1.4–§1.7 steps. Read §1.1–§1.3 for the parts' roles, then jump there.

From `hardware/bom/stage0-devkit.csv` (≈ $40–55):

| Qty | Part | Note |
|---|---|---|
| 1 | Seeed XIAO ESP32S3 **Sense** (with the camera expansion board) | some ship with OV3660 instead of OV2640; both work |
| 1 | Adafruit DRV2605L breakout (#2305) | EN is tied high on the breakout; I²C 0x5A |
| 1 | 8 mm coin LRA, ~235 Hz (PMD C08-005, Jameco 8 mm, or INEED LRA0825BC-0167F) | the INEED part is the stage-1 motor; buy it now and tune the cues on it |
| 1 | LIS2DW12 breakout | 0x18 or 0x19, both auto-detected; double tap = hands-free ask |
| 1 | 6 × 6 mm tactile switch | the only mandatory peripheral (hold = ask, short press = photo) |
| 1 | 9–12 mm passive piezo | optional beep cues |
| 1 | **MAX98357A I2S class-D breakout** (Adafruit 3006 or clone) | **optional** — the on-ring speaker path (`AUDIO_OUT`, F12) on the bench; not in the CSV, see `docs/05` stage-0 list |
| 1 | **8 Ω 10 mm micro speaker** (PUI AS01008MR-2-R class, or any 8 Ω ≥ 0.3 W driver) | optional, with the amp above; the 10 mm part is what the stage-1 shell is designed around |
| 1 | 100 mAh LiPo (Adafruit 1570) | plugs into the XIAO BAT+/BAT- pads |
| 2 | resistors for the battery divider | **use 100 kΩ/100 kΩ**, not 10 k: 10 k/10 k drains 210 µA, ten times the sleep budget (`python3 docs/build-helpers/tuning_calc.py divider --r1k 10 --r2k 10`) |
| — | breadboard, jumpers, USB-C data cable | |
| — | Bluetooth headphones | paired to the **laptop or phone**, never to the ring — that is where the answers come out |

Tools: multimeter, a **USB inline current meter** (any $10 one) or, much better, a Nordic PPK2
(source-meter mode, 1 µA resolution, needed for the sleep numbers). A phone is optional for
stage 0; the CLI does everything the app does (push-to-talk, headphones, ring speaker).

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
| **Speaker I2S BCLK** | D7 | 44 | MAX98357A `BCLK` (optional; UART0 RX, free because logging is USB-CDC) |
| **Speaker I2S LRC** | D6 | 43 | MAX98357A `LRC` (optional; UART0 TX — the ROM banner at reset is a few inaudible frames) |
| **Speaker I2S DIN** | D10 | 9 | MAX98357A `DIN` (optional). D10 **was** the aux / air-puff enable: `PIN_AUX` is `-1` on the XIAO now, the experiment is parked on the dev kit |
| MAX98357A `SD` / `GAIN` / `VIN` | — | — | `SD` → 3V3 (amp always on; `PIN_SPEAKER_EN` is `-1` on the XIAO), `GAIN` open (9 dB) or GND (12 dB), `VIN` → 3V3 |
| Battery sense | A0 | 1 | centre of the 100 k/100 k divider from BAT+ |
| 3V3 / GND | 3V3 / GND | — | breakouts' VIN and GND |

Everything except the button is optional: missing I²C devices are detected at boot and the
matching status flags stay clear. Start with **the button only**; add parts in §1.8–1.10. The
speaker is the last thing to wire (§1.10) — the headphone path needs nothing on the ring. (If the
wiring drawing predates the speaker, the table wins: `src/config_audio.h`.)

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
[     150] I main: mcring fw 0.1.0 (xiao-esp32s3-sense) voice-first
[     152] I cfg: trig=03 q=12 fs=2 sleep=120s led=96 hap=100 wpm=15 ch=03 spk=255 cues=03 mic=ring
[     160] W imu: no IMU found at 0x18/0x19 (LIS2DW12 who=0x44, LIS3DH who=0x33; read 0xff)
[     165] W drv: DRV2605L not found (status=...)
[     420] I cam: sensor PID=0x2640 detected          (0x3660 on OV3660 units)
[     425] I spk: speaker configured (I2S1)           (the XIAO build always has the three I2S pins → SPEAKER_OK)
[     430] I trig: touch baseline 23xxx
[     900] I ble: advertising as mcring-7a3f
```

then the on-board LED (GPIO21) gives one 60 ms blink — the *ok* cue (`cues_ok()`; a haptic tick
too once the DRV2605L is wired). `spk=255 cues=03 mic=ring` are the voice settings (`SET_CONFIG`
keys 9–11): full speaker volume, haptic + LED cues, ring mic on a long press.

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
mcring events                                 # backend-free connection test: connect, print status + button events, Ctrl-C
mcring talk --backend http://localhost:8000   # the real loop (backend from §0 must be up; talk checks /v1/health
                                              # first and exits otherwise). Laptop mic by default, ring mic with --ring-mic
```

**Observe:** `scan` prints `AA:BB:CC:DD:EE:FF  mcring-7a3f  rssi=-55` (macOS shows a UUID instead
of the MAC). Both `events` and `talk` print `I mcring.ring: scanning for mcring* (10s)…`,
`connected; MTU 517 (3 audio block(s)/write)` (Linux/BlueZ; macOS reports 185 → 1 block/write) and
a `status: idle batt=0mV(255%) flags=0x4a speaker ...` line (255 % = no divider fitted; `0x4a` =
camera_ok + mic_ok + **speaker_ok**, the XIAO build always claims the PDM mic and a speaker). Press the button in `events`:
`event BUTTON_DOWN  t=12.3s`, `event BUTTON_UP held 0.2 s (photo)`, `event CAPTURE_STARTED`,
`event CAPTURE_DONE queued=1`, `transfer type=1 11234 B in 0.35 s`. `talk` prints
`talk — Enter: start recording · Enter: stop & ask · c: photo · t <text>: ask by text · q: quit` and
`ring: hold the button to ask (short press = photo); mic = this computer; answers on this computer`.
On the ring: `I ble: connected ...`, `I ble: MTU 517 -> chunk 510`, four `subscribe ... -> 1`
lines (status, meta, data, events), a short LED blink, and three `I main: set_config key=9/10/11 -> ok`
lines: `talk` and `listen` write `speaker_volume` (`--volume`, default 200), `cues_mask` (`--cues`,
default 3 = haptic + LED) and `mic_source_hint` (1 unless `--ring-mic`) to the ring's NVS on every
connect. (`morse_wpm` / `feedback_channels` are only written with `--morse`.)

**If not:** `no ring found` → the ring deep-sleeps after **120 s** disconnected and idle
(`DEFAULT_IDLE_SLEEP_S`); press the button to wake it (that press also takes a photo, which is
queued) and scan again. For bench work disable sleep once connected: `mcring config
idle_sleep_s 0` (persisted in NVS). Bleak on Linux needs BlueZ ≥ 5.43 and `bluetooth.service`
running; on macOS grant the terminal Bluetooth permission the first time.

### 1.5 First photo

With `mcring talk --no-auto-photo` running (so a lone photo is saved, not asked about yet), press the
button once (short press, < 0.7 s). **Observe** on the ring:

```
I cam: captured 320x240 JPEG, 11234 bytes (q=12)
I xfer: START id=1 type=1 len=11234 chunks=23 x 510
I xfer: ACK complete id=1 (1 rounds)
```

and in the CLI: `event BUTTON_UP held 0.3 s (photo)`, `transfer 1 start: type=1 11234 bytes in 23
chunks of 510 (320x240)`, `transfer 1 complete: 11234 bytes in 0.35s (31.3 kB/s)`,
`saved captures/capture-....jpg`. Open the JPEG. Capture latency (trigger → `captured`) should be
150–300 ms. Without `--no-auto-photo`, `talk` asks the backend about a photo that arrives alone
(`identify`) — that is the "short press = what is this?" behaviour of the app.

**If not:** `E main: capture failed (2)` → `MC_ERR_CAPTURE_FAILED`, usually a loose Sense
board or a frame < 100 bytes (sensor not streaming); re-seat and retry. `START` but no
`ACK complete` → see "transfer timeouts" in §4. `queue full, dropped an older capture` →
more than 3 captures while disconnected; connect and let them drain. A photo that is dark
or green → the 3 AEC warm-up frames were not enough in low light; add light or raise the
discard count in `camera_capture()`.

### 1.6 First voice turn (hold the button, ask, hear the answer)

Pair your Bluetooth headphones to the laptop (or just use its speakers). With `mcring talk
--backend http://localhost:8000` running — laptop mic, i.e. `mic_source_hint 1` was written to the
ring — **hold the button ≥ 0.7 s, ask a question, release**.

**Observe:** on `BUTTON_DOWN` the CLI starts recording (`● recording (release the button to ask)`);
at 0.7 s the ring plays the *listening* cue — `I fb: play 1 units @ 60 ms, ch=02 (60 ms total)` on
the LED only until the LRA is wired (§1.8), then `ch=03`. On release: `event BUTTON_UP held 2.3 s (ask)`,
`■ 2.3 s — asking…`; the CLI asks the ring for a photo if none arrived in the last 20 s (the default
`identify` mode is visual — `--mode chat` or `--no-photo` skips it), posts clip + photo to `/v1/ask`,
prints the answer block from §0 with the `you   :` transcript, sends `CUE 2` → `I fb: play 3 units @
60 ms, ch=03 (180 ms total)` = the *answer ready* double tick, and speaks the answer in your
headphones. **Button release → first spoken word should be under 6 s (N2)** — the CLI's
`in NNNN ms` is the backend's share.

Now the ring's own microphone: quit and run `mcring talk --ring-mic` (writes `mic_source_hint 0`).
Hold the button: the ring takes the photo first (blocking ~150–400 ms), **then** ticks and prints
`I mic: recording up to 8 s` — speak after the tick. Release: `event REC_STOPPED 2.3 s`, then two
transfers, `type=1` (JPEG) and `type=2` (ADPCM, `height` field = 160 = 16 kHz/100, ≈ 8 KB/s); the
CLI saves `captures/voice-….wav` next to the JPEG and asks as above. The ring's `BUTTON_UP.arg` is
forced to `≥ 7` for an ask and `≤ 6` for a photo, so the CLI never disagrees with the ring.

Transcription uses OpenAI `gpt-4o-mini-transcribe`, so **`OPENAI_API_KEY` must be in
`backend/.env`** (or `MCRING_STT_PROVIDER=local` with faster-whisper installed).

**If not:** `backend error: …` in the CLI and a long buzz / 420 ms LED flash on the ring (`CUE 3`,
`play 1 units @ 60 ms … (420 ms total)`) → the backend returned an error; read its log (§4).
`(recording discarded)` → the press was shorter than 0.7 s or the clip under 300 ms. No `type=2`
transfer in `--ring-mic` → `audio_init` failed (the Sense board carries the PDM mic; `HAS_PDM_MIC`
must be 1) or the press was short. Silence in the WAV → PDM CLK/DATA are 42/41 on the Sense; check
the Sense board is seated. `(transcription failed: …)` with a typed `-q` question → the turn went
ahead on the text; without one the backend answers 501/422 (§4). A 64 KB 8 s clip takes ~1.3 s on
Android-class MTU and ~6 s at iOS chunk sizes — keep questions short, or use the phone/laptop mic.

### 1.7 Cues on the LED and LRA (and the optional silent mode)

The ring's outputs are three **cues** — *listening* (1 tick), *answer ready* (2 ticks), *error*
(long buzz) — on the channels in `CUES_MASK` (bit 0 haptic, bit 1 LED, bit 2 beep; default 3).

```bash
mcring config cues_mask 2                        # LED only (persisted; talk/listen rewrite it from --cues on connect)
mcring talk --cues 2                             # same, for this session
mcring talk --cues 7                             # haptic + LED + piezo beep
```

**Observe:** every cue logs `I fb: play N units @ 60 ms, ch=XX (… ms total)` with `ch` = the mask
(1 unit / 60 ms = listening, 3 units / 180 ms = answer ready, 1 unit / 420 ms = error); the
listening tick must be felt/seen within ~100 ms of the press crossing 0.7 s, the double tick must
not be mistakable for it.

**If not:** nothing on the LED but the log line is there → `led_brightness` is 0 (`mcring
config led_brightness 96`). `ch=00` → the mask has no channel the firmware can drive.

*Optional silent mode (Morse, off everywhere by default):* `mcring send "SOS" --wpm 12 --channels 1`
still blinks ITU Morse on the LED (`I fb: play 17 units @ 100 ms, ch=01 (… ms total)`) and is a handy
long-pattern LED/LRA check; `mcring talk --morse --echo` requests the pattern from the backend and
plays it on the ring after the spoken answer. Timing: `protocol/morse.md`,
`tuning_calc.py morse`. Nothing else in this guide needs it.

### 1.8 Add the LRA + DRV2605L

Wire the breakout (VIN 3V3, GND, SDA D4, SCL D5; motor on the two screw/solder terminals).
Stick the LRA to something with mass (the breadboard, a coin) — a free-floating LRA cannot
auto-calibrate. Reset.

**Observe:** `I drv: DRV2605L ready (LRA)` then `I drv: autocal ok (status 0xe0)`; the boot *ok*
blink now comes with a haptic tick; in `mcring talk` the *listening* tick and the *answer ready*
double tick are felt (`mcring config cues_mask 1` for haptic only). Status `flags` gains bit 4
(`0x52` with camera + speaker).

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
tap`, `event DOUBLE_TAP` — a **hands-free ask**: with `--ring-mic` the ring captures and records up
to 8 s (a second double tap stops it); with the laptop mic `talk` starts recording and stops at the
next double tap or after 8 s. Because a false double tap now starts a recording, the tuning below
matters more than it did for a photo.

Tuning (there is no BLE key for the threshold yet; it is a reflash):

1. The default is `s_ths = 9` → 0.56 g per axis at ±2 g (`tuning_calc.py tap --ths 9`); the
   second tap must land inside a 560 ms window, after 20 ms of quiet, with 40 ms shock
   (`INT_DUR = 0x7A`). The firmware additionally ignores a second double-tap within 800 ms.
2. Mount the breakout on the ring position (tape it to the top of your index finger), wear it
   for an hour of normal hand use with `mcring events` running and count unwanted `event DOUBLE_TAP`
   lines (target < 1/h, `docs/benchmarks.md`).
3. Too many false triggers → raise the threshold (`imu_set_tap_threshold(12)` ≈ 0.75 g, call it
   after `imu_init()` in `setup()`, or change the `s_ths` default) and/or shorten `LATENCY` to 5
   (400 ms). Missed deliberate taps → lower it to 7–8, or tap with the fingertip of the other
   hand on the signet rather than clapping. To read what the sensor saw, log
   `imu_read_tap_src()` in `trigger_tick()`: `0x10` = double, `0x20` = single, bits 2:0 = axis.
4. Compare with the button only (`mcring config trigger_mask 1`) and tap only (`trigger_mask 2`).

### 1.10 Speaker bring-up (optional: MAX98357A breakout + 10 mm speaker)

This proves the `AUDIO_OUT` path (F12) that the stage-1 ring carries on its board. Nothing in the
headphone loop needs it. Power the ring down and wire the breakout:

| MAX98357A pin | XIAO | Note |
|---|---|---|
| `VIN` | 3V3 | 2.5–5.5 V; ~2.4 mA idle while `SD` is high |
| `GND` | GND | |
| `BCLK` | **D7** (GPIO44) | 512 kHz = 32 × 16 kHz |
| `LRC` | **D6** (GPIO43) | 16 kHz word clock |
| `DIN` | **D10** (GPIO9) | |
| `SD` | **3V3** | shutdown/channel select; any mode plays mono (the ring duplicates each sample into both slots) |
| `GAIN` | open (9 dB) or GND (12 dB) | the loudness ceiling; `SPEAKER_VOLUME` × stream volume scales below it |
| `+` / `−` | the 10 mm speaker | |

The ring speaker needs **server-side TTS**: `MCRING_TTS_PROVIDER=openai` (and `OPENAI_API_KEY`) in
`backend/.env`, restart uvicorn, `curl -s localhost:8000/v1/health` shows `"tts":"openai"`.

```bash
mcring say "hello from the ring" --ring-speaker --volume 160    # text → ADPCM on the server → ring speaker
mcring talk --ring-speaker                                      # answers on the laptop AND the ring speaker
mcring talk --ring-mic --ring-speaker --quiet                   # everything on the ring: its mic, its speaker
```

**Observe:** `say` prints `N blocks (x.x s)`, `speaker: N blocks (x.x s), 3 block(s)/write`
(1 block/write at MTU 185) and ends with `ring speaker: done`. On the ring: `I spk: stream start
16000 Hz, volume 255 x 160`, speech from the speaker after the ~400 ms prebuffer, `I spk: done after
N blocks (dropped 0, seq gaps 0)`, `event AUDIO_DONE (drained)`. Count `event AUDIO_UNDERRUN` lines
over a 10 s answer: ≤ 1 at MTU 185, 0 at 517 (F12). Holding the button while it plays interrupts the
answer (barge-in) and starts the next question; `s` + Enter in `talk` stops it (`AUDIO_DONE (stopped)`).
Measure loudness with a phone SPL app at 30 cm and 1 m (expect roughly 75 / 66 dB in free air).

**If not:** `AUDIO_START but no speaker on this board` → a build with `-1` I2S pins (not the XIAO).
`(ring speaker: no audio from the server: …)` → `MCRING_TTS_PROVIDER` is `none`. `stream start` and
`done after N blocks` but silence → `SD` low/floating, `GAIN` shorted wrong, `DIN`/`BCLK` swapped, or
`--volume 0`; distortion → lower `--volume` / `GAIN` open. `underrun after N blocks` → the link is
slower than real time (MTU 185 + long connection interval), or a capture ran during playback (a
`CAPTURE` blocks `loop()` for 150–400 ms — expected, see `firmware/ring-esp32s3/README.md`).
A click at reset → the ROM banner on GPIO43, harmless. Hum with the USB meter in line → measure
from the battery (§1.11).

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
| Backend latency (STT + Claude + TTS) | CLI `in NNNN ms` | 2–4 s |
| Button release → first spoken word (N2) | stopwatch, 5 turns, laptop mic and ring mic | < 6 s |
| Ring-mic clip transfer, 3 s clip (24 KB) | CLI `transfer N complete` | < 0.5 s laptop / Android, ~2 s iPhone |
| Advertising idle current | meter, disconnected, awake | 20–40 mA (ESP32-S3 awake) |
| Connected idle current | meter, `talk` running, no transfer | 15–30 mA (slow conn params) |
| Capture peak / average over 1.5 s | PPK2 or shunt + scope | 300–370 mA / ~150 mA |
| Ring-mic recording (PDM + encode + BLE) | PPK2 during `recording up to 8 s` | 40–60 mA |
| Cue (double tick, haptic + LED) | PPK2 | ~0.2 s at 40–80 mA — negligible per question |
| Speaker answer, 10 s, usable volume (§1.10) | meter during `mcring say … --ring-speaker` | **100–150 mA average** (+ ~2.4 mA amp idle while `SD` is tied high) → `tuning_calc.py speaker --ma <measured>` |
| Deep sleep, Sense board attached | meter after `idle_sleep_s` elapses or `SLEEP` | ~3 mA |
| Deep sleep, Sense board removed | same | 150–250 µA as the firmware stands: XIAO ~64 µA bare + 21 µA divider + **LIS2DW12 ~90 µA** in the 400 Hz high-performance tap-wake mode that `power_deep_sleep_now()` leaves it in (+ breakout regulators/LEDs); 80–100 µA with INT1 lifted and the IMU unplugged |
| Questions on one 100 mAh charge, 30/day pattern, answers in headphones | count until `batt` < 3300 mV | model says ~500 (`hardware/power-budget.txt`) |
| Speaker answers on one charge (10 s each) | same, `--ring-speaker` | ~2–3 photos' worth each (`tuning_calc.py speaker`) |
| Double-tap false positives per hour | §1.9 | < 1 |

**If not:** deep sleep > 300 µA with the Sense board removed → the divider is 10 k (210 µA), a
breakout has an LED/regulator, or the MAX98357A is still wired with `SD` high (2.4 mA — pull `SD`
to GND or unplug `VIN` for sleep measurements on the dev kit; the stage-1 board gates it). The IMU's ~90 µA is expected: `power_deep_sleep_now()` calls `imu_wake()`
(CTRL1 `0x74` = 400 Hz, high-performance — the mode the double-tap engine is specified for), not the
~1 µA low-power ODR the firmware comment and `hardware/power-budget.txt` assume; measure with INT1
disconnected and the IMU unplugged to split it out. The fix is a firmware follow-up (§2.1 item 4), the
same one that decides the stage-1 sleep figure in §2.4.

### 1.12 No-solder variant (XIAO in the Expansion Board Base)

**Do you have to solder for this project? Not for stage 0.** Two substitutions remove every joint:
the XIAO is bought with its headers factory-soldered (Seeed 102010635) and seated in Seeed's
**Expansion Board Base for XIAO** (103030356 / Adafruit 5033), and the two breakouts that normally
need wires — the DRV2605L's motor pads and the accelerometer's power/I²C — become a **Grove Haptic
Motor** (DRV2605L with its motor already attached) and a **LIS3DH STEMMA QT** board on a Grove→QT
cable. The base already carries the button on D1 (= `PIN_BUTTON`), a passive buzzer on A3 = D3
(= `PIN_BUZZER`) and a JST LiPo socket with a charger, so nothing from §1.2's table is wired by hand.
The firmware runs the same loop (`pio run -e xiao_esp32s3_sense_base`). The one part that keeps
unsoldered holes is the optional speaker amp (§1.12.5). Stage 1 needs no iron either: its 26.5 × 22.8 mm
board is *ordered assembled* and every off-board part plugs into it (§2, `docs/10-ordering-assembled-boards.md`;
summary at the end of this section).

Drawing: `hardware/pcb/out/wiring_stage0_solderless.png`; connection table, the `MCRING_XIAO_BASE`
build deltas and the check list: `hardware/pcb/wiring_stage0_solderless.md`. Prices are October-2026
search snippets; the research report marks what it could not verify.

#### 1.12.1 What to buy (`hardware/bom/stage0-devkit-solderless.csv`, ≈ $56–72)

| Qty | Part | Replaces (§1.1) | Note |
|---|---|---|---|
| 1 | XIAO ESP32S3 Sense, **pre-soldered** — Seeed 102010635 ($14.90–19.95) | the bare XIAO + its 14 header joints | header side **unverified** (`docs/research/04` §A1): before ordering, check on the 102010635 product photo that the pins come out of the side *opposite* the Sense board, so the camera faces up, away from the base; the photo check after seating is in §1.12.2. Fallback if out of stock: the unsoldered board + a press-fit "hammer header" (Adafruit 3662; fit in the XIAO's holes unverified) |
| 1 | Expansion Board Base for XIAO — Seeed 103030356 / Adafruit 5033 ($17.95) | breadboard, tactile switch, piezo, battery wiring | button on D1, buzzer on A3/D3, JST 2.0 LiPo + charger (≤ 460 mA), 2 × Grove I²C, Grove UART, Grove A0/D0, OLED 0x3C, RTC 0x51, microSD (CS D2) |
| 1 | Grove – Haptic Motor — Seeed 105020011 (≈ $7.50–15) | DRV2605L breakout + LRA + 2 motor joints | DRV2605L 0x5A with an **ERM** attached; the LRA feel comes back on the stage-1 board |
| 1 | LIS3DH STEMMA QT — Adafruit 2809 ($4.95) *or* SparkFun Micro LIS3DH Qwiic SEN-29529 ($5.95) | LIS2DW12 module + 4–5 wires | WHO_AM_I 0x33, detected at boot; no LIS2DW12 breakout with a QT/Qwiic plug exists (SparkFun's is retired) |
| 1 | Grove → STEMMA QT / Qwiic cable — Adafruit 4528 or SparkFun PRT-15109 ($1.95) | — | base Grove I²C #2 → LIS3DH |
| — | male-male jumpers; optionally one hammer-header strip (Adafruit 3662, $2.25) or an alligator-to-jumper set (Adafruit 3255, $7.95) | — | the LIS3DH `INT` → D8 jumper (optional; only the `_tapwake` env uses it, §1.12.4) and, with the speaker, D10 → `DIN` |
| 1 | LiPo **≥ 400 mAh**, JST-PH, with PCM — Adafruit 3898 or 1578 ($6.95–7.95) | the 100 mAh cell on the BAT pads | the base's charger is up to 460 mA: 4.6 C for the 100 mAh ring cell, so keep that cell for the soldered rig / stage 1 |
| opt. | MAX98357A breakout (Adafruit 3006, $5.95) + an 8 Ω speaker with leads (Adafruit 3923, $1.95) + a "Grove to 4-pin male jumper" cable (Seeed 110990210, ≈ $2.90): ≈ $11–13 | the same amp and speaker | see §1.12.5 — the amp's 7 header holes are the one unsoldered thing; the 10 mm PUI speaker of §1.10 has solder pads (stage-1 part) |

Not needed from §1.1: the tactile switch, the piezo, the divider resistors, the breadboard.

#### 1.12.2 Seat and flash

1. Push the XIAO into the base's socket: USB-C toward the base's USB end, `D0` at the base's `D0`
   silkscreen; the Sense board should end up on top with the camera facing away from the base. That
   header side is **unverified** for the pre-soldered board: once flashed, the first photo (§1.5) must
   show the room, not the base's PCB — if it shows the base, stop; the camera is sandwiched and this
   seating cannot work for photos. Leave the base's microSD slot empty (its CS is D2 and its SPI shares
   D8/D9/D10 with the IMU interrupt, touch and I²S DIN).
2. `cd firmware/ring-esp32s3 && pio run -e xiao_esp32s3_sense_base -t upload` (same boot/reset dance as
   §1.3 if the port is missing).

**Observe:** the §1.3 log with `mcring fw 0.1.0 (xiao-esp32s3-sense+base)` on the first line — the
`+base` means `-DMCRING_XIAO_BASE` is in: ERM haptic profile, `PIN_HAPTIC` parked (D2 is the SD chip
select), tap-source polling on, `PIN_IMU_INT` (D8) and `PIN_BATTERY_ADC` (A0) parked. Press the
base's own button: `event BUTTON_DOWN` / `BUTTON_UP` in `mcring events`, exactly as in §1.4–§1.7 — the
button and the buzzer need no wiring at all.

**If not:** the first line says `(xiao-esp32s3-sense)` without `+base` → you flashed the stock env; it
still boots but drives the ERM with the LRA profile (`autocal FAILED`) and toggles D2. A dead board →
XIAO reversed in the socket.

#### 1.12.3 Haptics: plug the Grove Haptic Motor into Grove I²C #1

Reset. **Observe:** `I drv: DRV2605L ready (ERM)` then `I drv: autocal ok (status 0xe0)`; the boot
*ok* blink comes with a buzz from the module's motor; `mcring talk` cues as in §1.7. Skip §1.8's
rated-voltage tuning (that is for the LRA); `mcring config haptic_strength 60–100` sets the level.

**If not:** `DRV2605L not found` → the module is in the UART or A0/D0 socket; move it to an I²C
socket. `autocal FAILED (status 0xe8)` → stock env flashed (see §1.12.2), or the motor is held still.

#### 1.12.4 Double tap: Grove→QT cable into Grove I²C #2, QT plug into the LIS3DH

Reset. **Observe:** `I imu: LIS3DH ready at 0x18 (double click -> INT1, latched; ths 9 = 562 mg)` (or
`0x19` for the SparkFun board), status flag bit 2 set. Tape the breakout to a finger or a coin (a
free-floating board taps itself) and tap it twice ~150 ms apart: `I trig: double tap`, `event
DOUBLE_TAP` → the hands-free ask of §1.9. **No interrupt wire is needed for this**: the build polls the
chip's latched click source every 25 ms, which adds at most 25 ms of latency.

The interrupt jumper is only for **tap-to-wake from deep sleep** (EXT1), and it takes two steps.
(1) Push a male jumper pin into the breakout's `INT` through-hole at a slight angle (friction fit), or
tap in one hammer-header pin, or use an IC-hook clip, and plug the other end into the base's breakout
header hole **D8**. (2) Flash `pio run -e xiao_esp32s3_sense_base_tapwake -t upload`
(`-DMCRING_IMU_INT_WIRED`; the boot line says `+base+tapwake`). The default `xiao_esp32s3_sense_base`
build ignores D8 on purpose: without the wire nothing drives that pin (it is also the microSD clock of
the base and the Sense board), a floating EXT1 pin would wake the ring at random, and every EXT1 wake
starts an ask. So that build powers the LIS3DH down in deep sleep and **wakes on the button only**.
Test with the tap-wake build: `mcring config idle_sleep_s 10`, disconnect, wait, double-tap →
`I pwr: woke from deep sleep, cause 3` (`ESP_SLEEP_WAKEUP_EXT1`) and `I main: wake by tap -> ask`.
Before sleeping the firmware clears the click latch, arms EXT1 only if D8 then reads low with its
pull-down on (`W pwr: IMU INT (GPIO7) high …` otherwise) and holds it low in sleep, so a jumper that
falls out does not cause random wakes; the LIS3DH stays at 400 Hz in sleep (~73 µA typ.).

Tuning is §1.9's, in the same units: the firmware keeps the tap threshold in 62.5 mg steps for both
chips (`imu_set_tap_threshold(9)` ≈ 0.56 g; the LIS3DH driver scales it ×4 into its 7-bit `CLICK_THS`),
and its 40 ms shock / 20 ms quiet / 560 ms window mirror the LIS2DW12 values (`src/imu_lis3dh.cpp`).
`imu_read_tap_src()` returns the LIS2DW12 bit layout for either chip (`0x10` = double).

**If not:** `W imu: no IMU found at 0x18/0x19 (…; read 0xff)` → the QT plug is in the breakout's socket
but the Grove end is in the UART/A0 socket, or the cable is reversed-keyed (it is not; re-seat).
`read 0x33` but no `ready` → I²C error after detection; check the Grove→QT cable. False double taps
→ raise the threshold as in §1.9 (reflash), the polling path reports exactly what the interrupt path
would.

#### 1.12.5 Battery and the optional speaker

*Battery:* plug a **≥ 400 mAh** JST-PH cell into the base's JST 2.0 socket — check red = `+` on the
base silkscreen first (a Seeed forum thread reports reversed pigtails on early units; never force a
plug) — and the base's charge LED lights while USB is in. `batt` in STATUS reads `0mV(255%)` = unknown:
the A0 divider of §1.11 is not built on this rig (the cell's `+` is only on the JST pigtail), and the
base build parks `PIN_BATTERY_ADC` so an open A0 cannot report a bogus low battery (a divider you build
on A0 is read again with `-DMCRING_BATT_DIVIDER_WIRED` added to the env's `build_flags`). For the
§1.11 current measurements put the meter in series through a JST-PH extension cable cut open; the
deep-sleep numbers are not meaningful here (OLED, RTC and charger on the base, no camera power gate).
Not verified from the base's schematic: whether its charger reaches the XIAO's BAT pads or only the
5V/VIN pin — the XIAO's own BAT pads are unused either way, and nothing goes on the 5V header pin.

*Speaker (optional, F12):* the MAX98357A breakout's speaker terminal block is pre-soldered, its
**7-pin header is not**, and no I²S amp exists with a Grove/QT plug (Grove carries two signals, I²S
needs three; the STEMMA Speaker is analog-in and the ESP32-S3 has no DAC). Honest options: (a) press
hammer-header pins (Adafruit 3662) into the amp's holes and use female jumpers; (b) five joints at a
makerspace / a friend with an iron; (c) defer — the amp is SMT on the stage-1 board. Wiring for (a) or
(b): a "Grove to 4-pin male jumper" cable in the base's **Grove UART** socket gives `BCLK` (D7),
`LRC` (D6), `VIN` (3V3) and `GND` in one plug (which Grove pin is D6 and which D7: base silkscreen —
swap `BCLK`/`LRC` if silent), a jumper from breakout header D10 to `DIN`, `SD` → `VIN`, `GAIN` open.
Speaker: Adafruit 3923 (8 Ω 1 W oval) — snip the PicoBlade plug off its leads and strip ~5 mm of each
(wire stripper, no solder) into the amp's screw terminal; the 10 mm PUI AS01008MR-2-R of §1.10 has solder
pads and stays a stage-1 part. Then §1.10 as written. Headphones need none of this.

#### 1.12.6 Which §1 steps change

| § | Soldered rig | No-solder rig |
|---|---|---|
| 1.1 / 1.2 | `stage0-devkit.csv`, `wiring_stage0.md` | `stage0-devkit-solderless.csv`, `wiring_stage0_solderless.md` |
| 1.3 | `-e xiao_esp32s3_sense` | `-e xiao_esp32s3_sense_base` (`…_base_tapwake` with the INT jumper); boot line says `+base` |
| 1.4–1.7 | tactile switch on D1 | the base's button — otherwise identical; the §1.5 photo also proves the header side |
| 1.8 | DRV2605L + LRA, rated-voltage tuning | Grove Haptic Motor (ERM): `ready (ERM)`, autocal, `haptic_strength` only |
| 1.9 | LIS2DW12 + INT1 wire | LIS3DH, polled; deep-sleep tap-wake needs the INT jumper **and** the `_tapwake` env; same thresholds/units |
| 1.10 | amp header soldered | press-fit pins, a makerspace, or defer |
| 1.11 | cell on BAT pads + divider | cell in the base's JST; no `batt` reading; no sleep figures |

*Stage 1 without an iron* is in the design (§2, `docs/10-ordering-assembled-boards.md`): the
26.5 × 22.8 mm board is ordered as **JLCPCB Standard PCBA** (Economic cannot place the 0.4 mm DSBGAs or
a double-sided board), and the cell, the charging-pad pigtail, the LRA and the optional speaker plug into
four 2-pin Molex Pico-EZmate headers on its top (J1, J3, J4, J5; `hardware/electrical/mcring_v1.py`,
`hardware/pcb/floorplan.py`). The 8 wire joints that remain are at the far ends of the pigtails (two each
on the cell, LRA and speaker, plus the two band contacts) and are made without an iron (`docs/10` §7).
The sourcing research behind it is `docs/research/04-no-solder-sourcing.md` §B–C.

---

## 2. Stage 1 — oversized printed ring (ESP32-S3-MINI-1U board)

Decision already taken: ESP32-S3-MINI-1U (15.4 × 15.4 × 2.4 mm), antenna end pointing **away**
from the camera, on one rigid 2-layer 0.6 mm board in a signet bay on top of the band; exact
outline in `hardware/pcb/board_params.json`, placement in `hardware/pcb/floorplan.md`,
connectivity in `hardware/electrical/out/mcring_v1.net` (ERC clean: `out/erc.md`).

**No soldering in this section.** The board (26.5 × 22.8 mm) is **ordered assembled** — procedure, costs and
the consigned parts in `docs/10-ordering-assembled-boards.md` — and everything off-board plugs in: the cell,
the charging-pad pigtail, the LRA and the optional speaker go into four 2-pin Molex Pico-EZmate headers on
the board's top (J1 BAT, J3 CHG, J4 LRA, J5 SPK, each with a wire notch in the board edge beside it), the
camera flex into a flip-lock ZIF (FPC1), the antenna onto the module's u.FL. The eight wire joints that
remain are at the far ends of the four pigtails (cell, LRA, speaker leads and the two band contacts) and are
made without an iron — pre-terminated harnesses (always for the cell), solder-seal sleeves on the LRA's leads,
the silver pen on the band contacts (`docs/10` §7).

### 2.1 Before ordering anything

1. Read `hardware/electrical/README.md` §6: the datasheet assumptions (16 items) that could not be
   verified from the sandbox (module pin table, IO33 free on the N4R2, FPC pin order, BQ25100 ball map,
   TPS62840 VSET code, TPS22916 ball map, WS2812B at 3.3 V, antenna outline...). Tick each against the
   datasheet you download.
2. Buy the OV2640 24-pin head **first** and buzz its pin order against §6 item 2 — a
   one-position-shifted variant exists. Confirm whether the head regulates DVDD itself (then
   U4, the 1.2 V LDO, is DNP).
3. The assembler needs 0.1/0.1 mm track/space, 0.2 mm drills and 0.35 mm-pitch BGA placement on a 2-layer
   0.6 mm ENIG board: JLCPCB **Standard** PCBA (not Economic) or PCBWay — `docs/10` §2. If you must use a
   cheaper tier, swap the three TPS22916 (0.4 mm DSBGA) for TPS22917DBV (SOT-23-5) in
   `hardware/electrical/mcring_v1.py` and regenerate; the double-sided build stays.
4. Firmware state on `BOARD_MCRING_V1` (stage 0 is unaffected; `hardware/electrical/README.md` §7):
   * **LED rail — done**: `feedback.cpp` drives `PIN_RGB_PWR` (IO33, net `LED_PWR_EN`, U9 TPS22916)
     high around every LED write (`rgb_rail()`) and `power_deep_sleep_now()` drives it low, so the
     WS2812 is powered only while a cue or flash plays. Verify on the board: `VLED` (C21) is 3.3 V
     during a cue and 0 V otherwise — never bridge U9 (0.6–1 mA in sleep).
   * **Speaker pins**: `config_audio.h` `BOARD_MCRING_V1` must carry the hardware pass's assignment —
     **IO35 `PIN_I2S_BCLK`, IO36 `PIN_I2S_LRCLK`, IO37 `PIN_I2S_DOUT`, IO34 `PIN_SPEAKER_EN`** (U11
     TPS22916 `ON`; U10's `SD_MODE` is tied to the gated rail `VAMP`, so the amp enables as the rail
     rises), IO44 spare. With `-1` placeholders the build prints
     `I spk: speaker not fitted`, `SPEAKER_OK` stays clear and `AUDIO_START` answers `AUDIO_DONE(1)`.
     `audio_out.cpp` already drives `PIN_SPEAKER_EN` high only while a stream plays and low at init,
     so the amp rail is off asleep.
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
5. Order separately from the boards (all in `hardware/bom/stage1-ring.csv`): the Molex 146153-0050 flex
   antenna (34.9 × 9 mm, MHF1/u.FL pigtail — the stock 50 mm cable must be shortened or coiled, the cavity
   is 2 mm deep, `hardware/cad/README.md` "Antenna"); the OV2640 head; the 301012 cell, the INEED LRA and
   (speaker option) the PUI AS01008MR-2-R-class 8 Ω 10 mm speaker — each **terminated with a Pico-EZmate
   plug**: two Molex 36920-0203 (300 mm) cables per ring cut in half give the four 28 AWG pigtails W1–W4
   (the charging pigtail needs ≥ 85 mm per wire, so halves of the 100 mm 36920-0201 are too short), joined to
   the parts by the cell seller, a cable shop or PCBWay's harness service to the harness table in `docs/10` §7
   — the cell **arrives terminated**: never a solder-seal sleeve, heat gun or flame on it (LiPo warning there);
   copper foil with conductive adhesive (3M 1181 class) for the 4 × 5 mm lid electrode and a 3 × 4 × 3.6 mm
   conductive-foam block (or SMT spring finger) for TPAD1; two 3 × 2 mm ENIG contacts for the band (a scrap
   of ENIG board) and the MG 842AR silver conductive pen that bonds the charging pigtail's bare ends to them;
   UV-cure glue; a 0.3 mm foam or adhesive ring for the mic tube. **Speaker option**: U10 (MAX98357A
   16-TQFN) and U11 (third TPS22916) are placed by the assembler when you leave the group populated in the
   BOM; the J5 header is populated either way, so the speaker can be added later by plugging it in. Decide
   now whether this run gets the amp group; the headphone path needs none of it.

### 2.2 PCB + assembly order settings

The full click-by-click procedure, the consigned parts and the cost of a 5-board run are in
`docs/10-ordering-assembled-boards.md`; the settings in one table:

| Setting | Value |
|---|---|
| Layers / thickness / material | 2 / **0.6 mm** / FR-4 TG150+, 1 oz copper |
| Outline | **26.5 × 22.8 mm**, r 1.5, four **2.4 × 1.1 mm wire notches** in the right (+y) edge at x = 7.65 / 12.4 / 17.1 / 21.8 (`board_params.json` → `edge_notches_mm`) |
| Min track / clearance | **0.10 / 0.10 mm** (fine), 0.15 general, 0.3 power (`hardware/electrical/README.md` §5) |
| Min via | 0.20 mm drill / 0.45 mm pad |
| Surface finish | **ENIG** (DSBGA/LGA co-planarity, charging pads) |
| Solder mask | green or black; expansion 0.05 mm (0.03 on DSBGA pads, NSMD) |
| Silkscreen | none under the module; **pin-1 marks on J1/J3/J4/J5** (the Pico-EZmate plug is polarised) |
| Assembly tier | **JLCPCB Standard PCBA, both sides** (0.35 mm BGA capability for the four 0.4 mm DSBGAs; Economic is 0.5 mm / single side) or PCBWay PCBA with X-ray on the BGAs |
| Assembly files | `hardware/pcb/out/mcring_v1_bom_jlc.csv` + `mcring_v1_cpl.csv` from `python3 hardware/pcb/export_cpl.py` (73 placed parts, 31 BOM lines, ≈ 290 joints); `mcring_v1_pcba_notes.md` lists what each line resolves to |
| Consigned parts | ESP32-S3-MINI-1U-N4R2, TPS22916CYFPR (×3), Molex 78171-0002 (×4) — not stocked by LCSC; everything else sourced |
| Stencil | made by the assembler, **two** (double-sided; 0.10 mm). Ask in the order remarks for **1:1 apertures on the DSBGA pads** (they may want to shrink them — say no) |
| Quantity | 5 boards; consigned parts with attrition (+2–5 per line) |
| DNP decisions | U4 (1.2 V LDO) DNP if the OV2640 head regulates DVDD; the speaker group U10/U11/C25/C26/R20–R24 in or out (J5 stays) |

Nothing for soldering goes on the shopping list. Tools for the rest of §2: tweezers, 0.8 / 1.1 / 4.5 mm drill
bits for the printed parts, UV-cure glue, a heat gun (no lighter) if you sleeve the LRA's leads — never the cell's (`docs/10` §7),
a multimeter, and a USB microscope is still nice for the incoming inspection.

### 2.3 Incoming inspection of the assembled boards, and the pigtails

The boards arrive populated on both sides (`hardware/pcb/floorplan.md` §2–3): the **bottom** carries every
IC except the module (U7 BQ25100 under J3, U8 TPS62840 + L1, U2/U9 TPS22916, U3/U4 XC6206, U5 DRV2605L,
U6 LIS2DW12, Q1, D2/D3, MK1 mic, and — speaker option — U10 MAX98357A + U11 TPS22916), all passives and
the two bare pad pairs (BZ1 piezo, J2 aux — unused in the ring build); the **top** carries U1 (the module),
FPC1, SW1, D1 + R7, C3, the four Pico-EZmate headers J4 / J3 / J1 / J5 in the right strip, the TPAD1 copper
landing and the eight test pads TP1–TP8. Before anything else:

1. **Look** (USB microscope or a loupe): the module's u.FL end at the board's back edge (x = 26.5, away
   from FPC1); FPC1's mouth at the front edge with its actuator closed; the four headers with their
   wire-exit end toward the board edge and the notch straight ahead of each; D1's DIN pad toward R7; D3's
   cathode toward U7; the mic flat on the bottom with the Ø0.6 port hole visible from the top; no solder
   bridging visible at the DSBGA perimeters (U2/U9/U11 next to their caps, U7 under J3). Pin-1 marks on
   the headers are what you will plug against — if the silkscreen has none, mark pin 1 (the end nearer
   the board's front for J1/J3/J4/J5 as laid out; check the layout) with a paint dot.
2. **Power check** — every pad you need is on the top side. 4.0 V, 100 mA current limit, on TP8 (`VBAT`)
   / TP5 (`GND`): TP6 `3V3` = 3.30 ± 0.05 V (R12 = 267 k), `CAM_3V3` (at C10) and `VLED` (at C21) 0 V
   between captures, idle current < 20 µA with the module held in reset (TP2 `EN` to TP5) — buck IQ +
   divider; DRV2605L and LIS2DW12 power up in standby / power-down. Release EN: the module boots (§2.4).
   Speaker option: the amp rail at U11's output (and U10 `VDD`) reads 0 V until a stream plays.
   Charger: plug a cell into **J1** through its pigtail, feed 5 V into **J3 pin 1** (`CHG_PAD`) and GND into
   J3 pin 2 through the charging pigtail's bare ends (or a spare pigtail): TP7 `nCHG` goes low, ≈ 25 mA flows
   into the cell, U7.A1 sits ~0.25 V below the pad (D3). Swap the 5 V: nothing conducts (D2 bidirectional +
   D3) — that is the reversed-cradle case. A board that fails here with everything else right has a
   DSBGA ball open (U7 or a TPS22916): that is an assembler claim, not a repair.
3. **Continuity spot-checks**: U1 pads 3 / 45 / 4 → TP6 / TP2 / TP1; FPC1 pins 3 / 5 / 13 (SIOD / SIOC /
   XCLK) → R5 / R6 / U1 (buzz against `floorplan.md` §7); J1 pin 1 → TP8; J3 pin 1 → D2.

**Pigtails (the only wire work, and none of it on the board).** Each off-board part needs a Pico-EZmate
plug on its leads: W1 cell, W2 charging contacts, W3 LRA, W4 speaker — half of a Molex 36920-0203 (300 mm)
cable each (plug one end, bare the other). Have them made (`docs/10` §7: cell seller, cable shop or PCBWay
harness service; a solder-seal sleeve with a heat gun only on the LRA — **never on the cell**, whose joint is
≈ 25 mm from the pouch); lengths: cell ≈ 25 mm from the tabs, LRA ≈ 25 mm, speaker ≈ 15 mm (polarity
irrelevant for one driver), charging pigtail **≥ 85 mm per wire** (the modelled runs through the floor groove,
the slab channels and round the band are ≈ 61 and ≈ 73.5 mm, `hardware/cad/fit_report.md`; trimmed at the
windows, and left bare — a contact soldered on beforehand cannot pass the Ø1.1 channels). J2 and BZ1 are bare pads for the bench only. Snap the
antenna's u.FL plug onto the module for the §2.4 BLE checks (press straight down until it clicks; the mated
plug is the 2.9 mm tallest part).

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

**Observe:** `I main: mcring fw 0.1.0 (mcring-v1) voice-first`, `I imu: LIS2DW12 ready at 0x18`,
`I drv: DRV2605L ready (LRA)` + `autocal ok`, `I cam: sensor PID=0x2640 detected`, `I spk: speaker
configured (I2S1)` (or `not fitted` on a build without the IO34–37 assignment, §2.1 item 4),
`advertising as mcring-XXXX`, then the boot *ok* cue: one haptic tick and one blink of D1 through the
lid (its rail `VLED` goes 3.3 V for the 60 ms of the blink and back to 0 V). `PIN_CAM_PWR` (IO21)
behaviour: high for ~0.3 s during `camera_probe()` at boot, then low; high again for 0.2–0.5 s per
capture, low between shots — scope `CAM_3V3` while pressing the button.

**Serial checks before closing the enclosure:**

| Check | Expect |
|---|---|
| `camera_probe` | `PID=0x2640`; if `esp_camera_init failed: 0x105`, re-check FPC pin order and `CAM_3V3`/`CAM_2V8` during the probe |
| capture | `captured 320x240 JPEG` 8–15 KB; `CAM_3V3` returns to 0 V after |
| battery | `batt=` within 50 mV of the meter (R8/R9 **1 M/1 M**, `BATTERY_DIVIDER 2.0`; C23 100 nF holds the node for the 8-sample burst) |
| button | short press → capture; long press (≥ 0.7 s) → photo, *listening* tick, `recording up to 8 s` (ring mic), or events only with `mic_source_hint 1`; `BUTTON_UP` arg ≥ 7 |
| double tap | tap the board twice → `double tap`, `event DOUBLE_TAP`, then the hands-free ask (recording up to 8 s) |
| cues | `mcring talk`: *listening* tick at 0.7 s, double tick with the answer, both on the LRA and on D1 through the lid (`VLED` pulses) |
| speaker (option) | `mcring say "test" --ring-speaker`: `stream start 16000 Hz`, sound from the port, `done after N blocks`, `event AUDIO_DONE (drained)`; the amp rail (U11 out) is 3.3 V only during playback, IO34 high only then; `flags` bit 6 set |
| headphones | pair Bluetooth headphones to the laptop/phone, `mcring talk` with nothing configured on the ring → the answer plays in the headphones (F4) |
| sleep | `mcring config idle_sleep_s 20`, disconnect, wait → `I pwr: deep sleep`; battery current (PPK2 in series with the cell): **≤ 130 µA as the firmware stands** — ESP32-S3 7–8 µA + LIS2DW12 ~90 µA (400 Hz high-performance tap-wake, see §2.1 item 4) + divider 2 µA + DRV2605L standby ≤ 4 µA + mic/charger/buck/switch leakage ~6 µA ≈ 110 µA (`python3 docs/build-helpers/tuning_calc.py sleep`); **≤ 30 µA** only after the IMU low-power wake follow-up (`tuning_calc.py sleep --imu lp-wakeup` → ~22 µA). `CAM_3V3`, `VLED` and the speaker rail read 0 V in sleep; ~3 mA means the camera rail is on (IO21 high / R17 missing), +2.4 mA means the amp rail is on (IO34 high). Press the button → `woke from deep sleep, cause 2`, then the trigger logic decides short press (photo) or long press (ask); tap → `cause 3`, `wake by tap -> ask` |
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
The speaker option (Ø10 × 2.5–3 mm driver and its sound port) is part of the stage-1 CAD pass — take
the pocket position, port size and post-processing step from the current `hardware/cad/README.md`
and `fit_report.md`; a shell printed from an older `out/` has no speaker pocket.

Numbers you will touch (`default_params()` in the script): band Ø20.0 ID × 22.4 OD × 12 wide, wall 1.2;
signet 31.5 × 25.8 mm (28.95 across the speaker bump), lid top 11.1 mm above the skin, pod roof 12.7; lens
bore Ø4.6 (OV2640 barrel 4.5), lens axis 6.25 mm above the skin; mic port Ø0.8 in the lid above a Ø1.8 tube
that ends 0.3 mm above the board; switch slot 3.4 × 1.6 through the left wall with a 4.6 × 2.8 × 0.5
counterbore inside for the key's flange; cell pocket 10.4 × 12.4 × 3.4 (tabs toward +y, 3 × 0.8 lead channel
to the wall under J1) and LRA pocket Ø8.4 × 2.9, both recessed into the bay floor under the board;
charging-pad windows 3 × 3 at ±25° from the bottom of the band, fed by two Ø1.1 wire channels from the
grooves on the −Y rib and a 1.2 × 0.8 groove in the bay floor that carries the two wires round to the J3 notch;
lid 1.2 thick in a 0.5 rebate with 0.15 clearance, Ø0.5 detent beads, 1.0 mm pod-roof lip over its front
edge; LED: the lid stays 1.2 mm thick over D1 (an engraved Ø3 ring marks the spot, the LED top is 2.3 mm
below the lid) — no thinned window; touch dimple 4 × 5 × 0.4 (0.8 mm resin over the lid electrode). The
signet is 4.8 mm wider than the wire-pad design of the first pass: that is the price of the plug-in headers.

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
3.4 × 1.6 slot (0.3 mm travel at the cap); open the two 3 × 3 pad windows and pass a 1.1 mm drill through
the two wire channels (they start in the open grooves on the −Y rib and surface in the bay floor beside
the −Y wall); run a scriber along the 1.2 × 0.8 floor groove (−Y edge → across at x 10.25 → +Y edge to the
J3 notch position) and the 3 × 0.8 cell-lead channel (+Y edge of the cell pocket to the wall under J1) so
no resin skin is left in them. Fill the rib grooves with resin only after the wires are in (§2.6).

Fit-check before assembly, against `fit_report.md`: the board drops onto its ledges with 0.3 mm play per
side (front ledges 1.0 mm wide outside the y 5.5–11.0 gap for the FPC-pin passives, back ledge 2.9 mm under
the u.FL strip; board top 0.6 mm above the ledge) and its four edge notches line up with the wall on the
+y side; the 301012 cell (3 × 10 × 12 mm) drops into the floor pocket
with 0.2 mm per side — a cell **with PCM** is longer at the tab end, check yours before the final print;
the LRA (Ø8 × 2.5) drops into its Ø8.4 pocket and ends 0.2 mm below floor level; the camera head
(8.5 × 8.5 mm, 5.8 mm tall incl. barrel) slides from the bay into the pod through the 9.2 × 9.8 opening
until the barrel sits 0.4 mm into the bore, with 0.3 mm to the floor, 0.35 to each wall and 1.0 mm above
it for the FPC fold; the lid's front edge slides under the pod-roof lip and its beads click into the
grooves. Worn with the band against the knuckle the pod front sits ~17 mm toward the PIP joint — try
the bare shell on the finger before printing in volume.

### 2.6 Mechanical assembly sequence (plug-in)

Pockets first, then the board, then the plugs, then the lid — the LRA and the cell sit **under** the board
in the bay floor and cannot go in afterwards (`hardware/cad/README.md`, "After printing — check"). The
rule that makes the plug-in work: **every pigtail's plug is held up out of the bay while the board goes
down, and its two wires lie in their notch position on the +y side so the descending board's notch slides
over them**. The plugs (2.6 × 3.5 mm) cannot pass through the notches; only the wires can.

1. **Key**: drop the printed key into the switch slot from inside the bay (flange in the counterbore,
   cap outside). It is loose until the board holds it.
2. **Charging pigtail (W2)**: lay its plug end outside the bay on the +y side and push each bare wire from
   the floor groove's +y end along the groove — along the +y edge to x 10.25, across the floor between the
   LRA and cell pockets, forward along the −y edge — and down the two Ø1.1 channels that open in the bay
   floor beside the −Y wall: the X −1.5 channel leads to the −Y window (CHG−, J3 pin 2), the X −3.5 channel
   round the bottom to the +Y window (CHG+, J3 pin 1). Out in the rib grooves, cut each wire so ≈ 3 mm of
   bare end reaches its window, bond it to a 3 × 2 mm ENIG contact with the silver conductive pen (a contact
   soldered on beforehand would not pass the Ø1.1 channel), press the contact into its 3 × 3 window flush with
   the bore (UV glue around the edge, nothing on the face), fill the grooves with resin or epoxy. Both
   contacts flush, ≈ 8.5 mm apart (§2.8). The wires sit in the floor groove, below everything the board
   carries; the plug waits above the J3 notch position.
3. **LRA** into its pocket, face toward the finger, bonded to the pocket floor with 3M VHB or
   cyanoacrylate — rigidly coupled to the shell, never floating in foam. Its pigtail (W3) runs +y under
   the board's edge line to the J4 notch position; plug held up.
   **Speaker** (option): the 10 mm driver into the right-wall pocket from the top with the diaphragm toward
   the grille and a ring of thin adhesive foam between its rim and the pocket floor (an unsealed front
   chamber loses most of the little output there is); its pigtail (W4) comes through the wall opening into
   the cavity and up at the J5 notch position. Clear the grille holes with a 1.0 mm drill before the driver
   goes in.
4. **Cell** into the floor pocket, **tabs toward the +Y side** in the 3 × 0.8 mm channel toward the wall
   under J1; tape it down; its pigtail (W1) comes up at the J1 notch position, plug held up.
5. **Camera head** from the bay into the pod until the barrel sits 0.4 mm into the bore, lens along the
   finger; its flex comes back out of the pod opening toward the bay.
6. **Board**: with the board above the bay insert the flex into FPC1 — contacts facing the board (it is a
   bottom-contact connector), flip the lock lever down — then lower the board onto the ledges, u.FL end
   toward the back wall, FPC1 toward the pod, the four pairs of wires guided into their notches on the +y
   edge as the board comes down; the flex folds 180° behind the head (≈ 11 mm of flex from the head's top
   edge to the contacts; measure the purchased head). Check: switch plunger on the key's flange, D1 under
   the lid's LED mark, mic port where the lid tube lands, four wire pairs in four notches, nothing under
   the board but the cell, the LRA and the wires in the groove.
7. **Plug in**: W1 → J1 (BAT+ to pin 1 — polarity!), W2 → J3 (CHG+ to pin 1), W3 → J4, W4 → J5. The
   Pico-EZmate plugs are keyed and click past the friction locks; they sit 1.55 mm high, below the module's
   shield, and come out again with tweezers for debugging. Dress the slack of each pigtail into its notch.
8. **Antenna**: glue the flex antenna to the inside of the back wall in the 2 mm cavity (no metal, cell
   or LRA there); the pigtail turns down behind the board edge; cable ≤ 30 mm or the excess coiled along
   the back wall — never over the module or across the FPC. Snap the plug onto the module's u.FL.
9. **Touch contact**: stick the 4 × 5 mm copper foil to the lid underside under the dimple (board
   coordinates (8.1, 5.6)); set the 3 × 4 × 3.6 mm conductive-foam block (or spring finger) on TPAD1.
   The lid compresses it to 3.2 mm.
10. **Mic seal**: a 0.3 mm foam or adhesive ring on the board around the Ø0.6 port hole at (8.1, 15.3),
    where the lid's Ø1.8 tube lands.
11. **Lid**: run the §2.4 checks once more (the test pads and the four plugs stay reachable), then slide
    the lid's front edge under the pod-roof lip and press the back down until the beads click into the
    grooves — 0.1 mm of engagement, a light locating click. A drop of UV glue or a strip of tape on the
    back edge is the real retention; there are no screws or bosses.

### 2.7 Sealing options

| Option | When | How |
|---|---|---|
| None | bench and indoor tests | keep it off when washing hands |
| Conformal coat | daily wear | acrylic spray on the board only; mask the test pads, the four Pico-EZmate headers, SW1, FPC1, the mic port hole, the u.FL and TPAD1 |
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
to a USB breakout: VBUS → CHG+ (J3 pin 1 / CP1), GND → CHG− (J3 pin 2 / CP2). Nothing else is in the cradle; the
BQ25100 does the regulation (25 mA, 1 mA termination, ~1.5 h from empty for the 30 mAh cell). D3 lets a
reversed ring survive, but key the saddle anyway. Check: TP7 `nCHG` low in the cradle; battery voltage
rising; the pads never see more than 5.5 V (D2). `MC_FLAG_CHARGING` stays 0 until the firmware reads
`PIN_CHG` (§2.1 item 4) — the pad voltage itself is your indicator.

### 2.9 Wearing and aiming

Index finger, signet on top, lens toward the fingertip, switch on the thumb side. Aim by
pointing the finger: the OV2640 head gives ~65° horizontal FOV, so 25–40 cm from the object
fills the frame; hold still for one beat after the trigger (power-up + 3 AEC frames ≈ 200 ms).
Daylight or room light; dim restaurants are marginal at QVGA. Hold the switch, wait for the
*listening* tick (the shot is taken just before it in ring-mic mode), ask, release; the double tick
and the answer in your headphones — or from the ring speaker — land 2–6 s later. A short press is a
photo only; a double tap asks hands-free.

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
   west flash` (nRF Connect SDK ≥ 2.7). `mcring talk` must connect and receive the synthetic
   160 × 120 frame; this proves the phone/backend side needs no change for stage 2. The skeleton
   predates the voice pivot: `EVENTS`, `RECORD_START/STOP` and the cues still have to be ported
   (`docs/05`); `AUDIO_OUT` never will be — stage 2 has no speaker, answers are phone/headphones only.
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
   BOS1901, same three cues (60 ms tick, double tick, 420 ms buzz), blind identification of the cue
   on the finger while walking; the Morse corpus at 15/8 WPM only if the optional silent mode is
   wanted at stage 2.

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
| Listening tick and answer-ready double tick feel alike | 60 ms ticks at the LRA's 20–40 ms rise/fall; strength too high (rattle) | `haptic_strength 60–90`; confirm autocal passed (closed-loop braking is what gives crisp edges); the double tick's 60 ms gap must be felt — raise `CUE_TICK_MS` in `config_audio.h` if not |
| No cue at all although `I fb: play …` is logged | `CUES_MASK` has no drivable channel; `led_brightness 0`; DRV2605L not found | `mcring config cues_mask 3`, `led_brightness 96`; `I drv: DRV2605L ready` must be in the boot log |
| `AUDIO_START but no speaker on this board` | build with `-1` I2S pins (`BOARD_MCRING_V1` before the IO34–37 assignment) | §2.1 item 4; `flags` bit 6 clear tells the companion not to offer the ring speaker |
| `(ring speaker: no audio from the server…)` | `MCRING_TTS_PROVIDER=none` — the phone's own voice cannot reach the ring | `MCRING_TTS_PROVIDER=openai` + `OPENAI_API_KEY` in `backend/.env` (§1.10) |
| `stream start` … `done after N blocks` but silence | MAX98357A `SD` low/floating, `GAIN` miswired, `DIN`/`BCLK` swapped, volume 0 | §1.10 table; `mcring say … --volume 200`; on stage 1 scope IO34 high and the amp rail 3.3 V during playback |
| `event AUDIO_UNDERRUN` / `underrun after N blocks` | link slower than real time (MTU 185 → 1 block/write + long interval), or a capture during playback | expected ≤ 1 at MTU 185; avoid `CAPTURE` while streaming; the companion bursts 24 blocks then paces at 1 block / 16 ms |
| Morse too fast / dots and dashes blur on the LRA (optional silent mode only) | 20–40 ms LRA rise/fall vs 80 ms dots; strength too high; no Farnsworth | `--wpm 12 --overall-wpm 6` (`tuning_calc.py morse --wpm 12 --overall 6`); `haptic_strength 60–90` |
| `autocal FAILED (status 0xe8)` | DIAG_RESULT set: motor missing/ERM/wrong rated voltage; motor not coupled to mass | wiring; `drv2605_init(true)`; recompute `REG_RATED_V`/`REG_OD_CLAMP` for the motor (§1.8); stick the LRA down before calibrating |
| Double-tap false triggers | threshold 0.56 g too low for hand impacts; 560 ms window too wide | §1.9: `imu_set_tap_threshold(12)`, `LATENCY 5`; compare `trigger_mask 1` vs `2`; log `TAP_SRC` |
| Double-tap never fires | INT1 not on IO7; `trigger_mask` bit 1 clear; wrong I²C address not auto-detected | `imu ready at 0x18/0x19` line; `mcring config trigger_mask 3`; `TAP_SRC` shows `0x20` singles only → taps too slow |
| ~3 mA deep-sleep current | camera board not gated (stage 0), IO21 high/floating without R17, WS2812 un-gated (U9 bridged, 0.6–1 mA), MAX98357A `SD` tied high (2.4 mA, stage 0 or IO34 stuck high), 10 k divider (stage 0) | stage 0: pull the Sense board, 100 k divider, `SD` to GND for sleep tests; stage 1: scope `CAM_3V3`/`VLED`/the amp rail in sleep (all 0 V) |
| ~100–130 µA deep-sleep current on stage 1 | expected as the firmware stands: `power_deep_sleep_now()` leaves the LIS2DW12 at 400 Hz high-performance (~90 µA) for tap-wake | `tuning_calc.py sleep`; confirm with INT1 lifted and the IMU powered down; the ≤ 30 µA figure needs the low-power wake mode (§2.1 item 4) |
| Ring reboots during capture on battery | 300–370 mA peak sags a small cell / thin wires | 100 µF bulk at the module (stage 1), shorter battery leads; on the 100 mAh dev cell this should not happen — check solder joints |
| Backend **401** | `MCRING_API_TOKEN` set | `mcring ... --token <t>`; app Settings → token |
| Backend **400** `say or type a question, or attach a photo` | the turn carried neither audio nor text nor image (e.g. `--mode chat` with a discarded recording) | ask again; a follow-up needs `--session <id>` only to reference the earlier photo |
| Backend **422** `I didn't catch that — the recording came back empty` | the clip transcribed to nothing and there was no photo: too quiet, too short, spoke before the tick (ring mic) | speak after the *listening* tick, closer to the ring; check the WAV in `captures/` |
| Backend **413** `… too large` | > 8 MB upload (`MCRING_MAX_UPLOAD_BYTES`) | ring images are ≤ 60 KB and clips ≤ 64 KB — this is a CLI misuse with a huge file |
| Backend **429 / 502 / 503** | provider rate-limit / API error / connection error (`retryable` in the JSON) | wait and retry; check `ANTHROPIC_API_KEY`; `MCRING_PROVIDER`; 503 with `connection error` → outbound network/proxy |
| Backend **501** | a speech feature is not configured: no `OPENAI_API_KEY` for speech-to-text, `MCRING_STT_PROVIDER=local` without `faster-whisper`, `MCRING_TTS_PROVIDER=none` with `--server-tts` / `--ring-speaker`, or `provider=openai` without `OPENAI_API_KEY` | the 501 message says which; `backend/README.md` "Speech providers" |
| Answer is `I can't help with that one.` | model refused (stock `REFUSAL_ANSWER`) | expected for people/faces/unsafe content; re-aim or rephrase |
| `(transcription failed: …)` in the CLI, answer based on the typed text only | speech-to-text failed but a `-q` question was present | fix the STT provider (501 row); without a typed question the same failure is returned as the error |
| LED dark on stage 1 | `VLED` never rises: R18 missing / U9 dead, D1 reversed, `led_brightness 0`, or a firmware build that predates `rgb_rail()` | scope `VLED` (C21) during a cue — it must pulse to 3.3 V; `mcring config led_brightness 96` |
| `queue full, dropped an older capture` | > 3 captures offline | connect; raise `MAX_QUEUED_CAPTURES` only if PSRAM allows |

---

## 5. Acceptance checklist per stage (docs/01 F1–F13)

Tick each line with the evidence named; record numbers in `docs/benchmarks.md`. IDs are
`docs/01`'s: F5 means *cues* (Morse is optional and off), F10–F13 are the phone-mic, voice-only,
ring-speaker and audio-routing requirements of the voice-first pivot.

### Stage 0 — bench rig

| Req | Pass criterion | Evidence |
|---|---|---|
| F1 | short press, double-tap (as the start of an ask), touch and the companion's `c` / *Take photo* each produce `CAPTURE_STARTED`, `CAPTURE_DONE queued=1` and a `captured ... JPEG` | serial log + `event` lines, §1.5/1.9/2.10 |
| F2 | 15 KB JPEG reaches the CLI in < 1 s on a laptop; < 0.3 s Android / < 1 s iPhone in the app; a 3 s ring-mic clip (24 KB) in < 0.5 s / ~2 s | `complete: ... kB/s`, app log |
| F3 / F11 | a spoken question **with** a photo returns `(photo)`, a `subject` and a 1–3 sentence `claude:` answer without lists or markup; the **same question with no photo** (`--mode chat`, or no ring in reach) is answered as plain chat and the CLI shows no `(photo)` (`mode = chat`, `had_image = false`) | CLI output, §1.6 |
| F4 | with Bluetooth headphones paired to the laptop/phone and **nothing configured on the ring**, the answer is heard in the headphones; with none paired, on the laptop/phone speaker; the phone app does the same with *Phone voice* and *Server voice* | ears, §0/§1.6 |
| F5 | the *listening* tick lands within ~100 ms of the press crossing 0.7 s, the double tick arrives with the answer, a backend error gives the long buzz; `cues_mask 2` moves all three to the LED only; with default settings **no Morse is ever played** | §1.7/1.8, `I fb: play` lines |
| F6 | hold ≥ 0.7 s with `--ring-mic` → `REC_STARTED`, on release `BUTTON_UP (ask)` + `REC_STOPPED` with a length matching the hold ± 0.3 s, an ADPCM transfer, and the `you   :` transcript contains the spoken words | §1.6, `transcript` in the response |
| F10 | laptop/phone mic (`mic_source_hint 1`): `BUTTON_DOWN` arrives before the first word is finished, `BUTTON_UP held N s` matches the stopwatch ± 0.1 s, the recording transcribes correctly 4 times out of 5 | `event` lines, §1.6 |
| F7 | a follow-up in the same session with no new photo (`mcring ask --session <id> -q "is it edible?"`, or just the next question in `talk`) answers about the earlier photo | CLI: same `session:` id, answer refers to the earlier subject |
| F8 | 3 asks (photo + clip) made while disconnected are delivered on reconnect, in order | `flags` bit 5 / `queued`, transfers |
| F9 | `mcring config speaker_volume 200`, `cues_mask 1`, `mic_source_hint 1`, `trigger_mask 2` each persist across a reset | `I cfg:` boot line (`spk=200 cues=01 mic=phone`) |
| F12 | with the §1.10 breakout: a 10 s answer streamed as `adpcm16k` plays end to end with ≤ 1 `AUDIO_UNDERRUN` at MTU 185 and 0 at 517, ends with `AUDIO_DONE (drained)`; `s` / `AUDIO_STOP` silences it within 100 ms → `AUDIO_DONE (stopped)`; `flags` bit 6 (`SPEAKER_OK`) is set | §1.10, `event` lines |
| F13 | CLI: `--ring-mic` / laptop mic, `--server-tts` / OS voice, `--ring-speaker` each switch the path; app: *Voice in*, *Speak answers* and *Ring speaker* do the same, and *Ring speaker* is offered **only** when the status shows `SPEAKER_OK` | §1.6/1.10, app Settings |
| N2 | button release → first spoken word < 6 s on 5 consecutive turns (laptop mic and ring mic) | stopwatch; CLI `in NNNN ms` for the backend share |
| — | benchmarks table §1.11 filled in | `docs/benchmarks.md` |

### Stage 1 — oversized ring

| Req | Pass criterion | Evidence |
|---|---|---|
| F1 | side switch (short = photo, hold = ask) and on-finger double-tap (hands-free ask) trigger; < 1 false tap/h over a 4 h wear | §2.10 log |
| F2 | transfer numbers within 20 % of stage 0 with the ring on the finger, phone in a pocket | app log |
| F3/F4/F7/F10/F11/F13 | unchanged from stage 0 (same firmware, same backend, same companions) | one full loop each way (ring mic, phone mic, headphones) |
| F5 | all three cues felt through the shell on the finger at `haptic_strength` ≤ 100 and seen on D1 through the 1.2 mm lid in daylight; a second person tells *listening* from *answer ready* blind 5 times out of 5 | blind cue test |
| F6 | voice question through the Ø0.8 lid port is transcribed correctly 4 times out of 5 at arm's length | transcripts |
| F8 | as stage 0, plus wake-from-deep-sleep by button (→ short/long press decided after wake) and by tap (→ `wake by tap -> ask`, delivered on reconnect) | `woke from deep sleep, cause 2/3` |
| F9 | as stage 0 | |
| F12 (if the speaker option is built) | `SPEAKER_OK` set; a 10 s answer plays through the sound port end to end (same underrun limits as stage 0); loudness ≥ 60 dB at 30 cm (phone SPL app); the amp rail is 3.3 V only during playback and 0 V in sleep (IO34); `mcring config speaker_volume` scales it | §2.4 speaker row, PPK2 |
| N3 | ≥ 30 questions/day for 1 day on the 30 mAh cell with the answers in headphones and `idle_sleep_s 120`; deep sleep **≤ 130 µA as the firmware stands** (≈ 110 µA modelled → 3.3 days at 30 questions/day), **≤ 30 µA** once the IMU low-power wake follow-up is in (≈ 22 µA → 4.7 days; `tuning_calc.py sleep [--imu lp-wakeup] --shots-per-day 30`; `hardware/power-budget.txt`'s 25 µA standby assumes the latter). With the speaker option, separately count how many 10 s speaker answers the cell affords (`tuning_calc.py speaker --ma <measured>`; the speaker is allowed to cost battery) | PPK2 log, `batt` at end of day ≥ 3600 mV |
| Mech | lid clicks under the pod lip and stays on, key actuates the switch with 0.3 mm travel, lens clear and centred in the bore, pads charge at 25 mA, 24 h worn without loose parts and without the pod binding at the PIP joint; speaker port clear and the driver sealed to it (option) | inspection |
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
| G7 | `EVENTS` / `RECORD_START/STOP` / cues ported to the nRF52840 firmware and the phone-mic loop (F10 + F4) runs against it — stage 2 has **no speaker**, answers are phone/headphones only |

Only when G1–G5 pass does a stage-2 board get laid out; until then stage 1 is the wearable.
