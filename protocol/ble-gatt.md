# mcring BLE protocol (v1)

The ring is a BLE **peripheral** (GATT server). The phone / desktop companion is the
**central**. All multi-byte integers are **little-endian**. All packets start with a
1-byte opcode or type.

mcring is **voice-first**: the user holds the ring button (or double-taps), asks a question
(optionally with a photo), and hears the answer. The ring never pairs to headphones itself
(ESP32-S3 / nRF52 have no Classic-BT A2DP/HFP and no battery budget for it). Audio topology:

```
ring ──BLE──► phone ──(normal phone audio routing)──► user's own Bluetooth headphones
 ▲              │
 │              └──HTTPS──► backend ──► Claude
 └──BLE AUDIO_OUT (optional on-ring speaker, stage-1 oversized ring only)
```

Two audio inputs, selectable in the app (`SET_CONFIG MIC_SOURCE_HINT`):
(a) **ring mic** — the ring records a PDM→ADPCM clip while the button is held and sends it
as an `ADPCM` transfer; (b) **phone / headset mic** — the phone records while the button is
held, driven by the ring's `BUTTON_DOWN` / `BUTTON_UP` events. Two audio outputs:
(a) **phone → headphones** (default; TTS on the phone or an mp3 from the server);
(b) optional **on-ring speaker** — the phone streams 16 kHz mono mcring-ADPCM to the
`AUDIO_OUT` characteristic and the ring decodes and plays it over I2S.

Haptics are short **confirmation cues** only ("listening" tick, "answer ready" double tick,
error buzz). Morse output on LED/haptic (characteristic 0006) is kept as an **optional, legacy
"silent pattern" capability**; it is off by default and no longer part of the main UX.

## Service and characteristics

Base UUID: `7a3bXXXX-9c2e-4f3a-b1d4-6d6372696e67` (`6d6372696e67` is ASCII `mcring`).

| Short | UUID | Dir | Props | Purpose |
|------:|------|-----|-------|---------|
| 0001 | `7a3b0001-9c2e-4f3a-b1d4-6d6372696e67` | – | service | mcring service |
| 0002 | `7a3b0002-…` | phone→ring | write, write-no-rsp | **Control** commands |
| 0003 | `7a3b0003-…` | ring→phone | read, notify | **Status** (battery, state) |
| 0004 | `7a3b0004-…` | ring→phone | notify | **Transfer meta** (start/end of an image or audio transfer) |
| 0005 | `7a3b0005-…` | ring→phone | notify | **Transfer data** chunks |
| 0006 | `7a3b0006-…` | phone→ring | write, write-no-rsp | **Feedback** — cues, raw patterns, RGB; Morse (legacy/optional) |
| 0007 | `7a3b0007-…` | ring→phone | notify | **Events** (button down/up, taps, capture/record lifecycle, battery, audio-out) |
| 0008 | `7a3b0008-…` | phone→ring | write-no-rsp | **Audio out** (phone → on-ring speaker, ADPCM stream) |

Advertised name: `mcring-XXXX` (last two bytes of the BLE MAC). The service UUID is
in the advertisement so the companion can filter scans.

The ring requests ATT MTU 517 and, when the stack allows it, LE 2M PHY and
Data Length Extension. The chunk payload size is computed from the negotiated MTU:
`chunk_len = MTU - 3 (ATT header) - 4 (chunk header)`. On iOS this is typically
`185 - 3 - 4 = 178` bytes; on Android up to `517 - 7 = 510`.

## Control (0002) — phone → ring

| Opcode | Name | Payload | Notes |
|-------:|------|---------|-------|
| 0x01 | `CAPTURE` | `quality u8, frame_size u8` | quality 1..63 (lower = better JPEG), frame_size see table below. `0,0` = ring defaults |
| 0x02 | `ACK_TRANSFER` | `xfer_id u16, status u8, n_missing u16, missing_idx u16[n]` | `status` 0 = complete, 1 = missing chunks listed, 2 = abort |
| 0x03 | `SET_CONFIG` | `key u8, value i32` | see config keys |
| 0x04 | `PING` | – | ring answers with a Status notify |
| 0x05 | `ABORT` | – | stop any transfer, recording, feedback or speaker playback, and end an open "ask" session |
| 0x06 | `RECORD_AUDIO` | `seconds u8` | record a voice clip of fixed length (1..8 s) with the ring mic, then transfer it as type `ADPCM` |
| 0x07 | `SLEEP` | – | enter deep sleep now |
| 0x08 | `GET_STATUS` | – | same as PING |
| 0x09 | `RECORD_START` | – | begin ring-mic recording **now**; stops on `RECORD_STOP` or after max 8 s. Emits `REC_STARTED` |
| 0x0A | `RECORD_STOP` | – | stop a running ring-mic recording and transfer it (`REC_STOPPED`, then an `ADPCM` transfer). Also ends an open phone-mic "ask" session; harmless when nothing is recording |

Frame sizes: `0=ring default, 1=QQVGA 160x120, 2=QVGA 320x240, 3=VGA 640x480, 4=SVGA 800x600, 5=XGA 1024x768`.

Config keys (`SET_CONFIG`, persisted in NVS):

| Key | Name | Range | Meaning |
|----:|------|-------|---------|
| 1 | `TRIGGER_MASK` | bits | bit0 button, bit1 double-tap, bit2 touch |
| 2 | `DEFAULT_QUALITY` | 1..63 | JPEG quality for on-ring captures |
| 3 | `DEFAULT_FRAME_SIZE` | 1..5 | frame size code |
| 4 | `IDLE_SLEEP_S` | 0..65535 | deep sleep after this long disconnected & idle (0 = never) |
| 5 | `LED_BRIGHTNESS` | 0..255 | |
| 6 | `HAPTIC_STRENGTH` | 0..127 | DRV2605 RTP amplitude |
| 7 | `MORSE_WPM` | 5..40 | legacy: default speed for `MORSE_TEXT` |
| 8 | `FEEDBACK_CHANNELS` | bits | legacy: default channels for patterns (bit0 LED, bit1 haptic, bit2 buzzer, bit3 aux) |
| 9 | `SPEAKER_VOLUME` | 0..255 | master volume of the on-ring speaker; multiplied with the per-stream `AUDIO_START.volume` (255 × 255 = unity) |
| 10 | `CUES_MASK` | bits | bit0 haptic cues, bit1 LED cues, bit2 beep cues (default haptic + LED) |
| 11 | `MIC_SOURCE_HINT` | 0..1 | 0 = ring mic (ring records on long press), 1 = phone/headset mic (ring only reports button events). Informational for the ring's own behaviour; the app owns the actual recording |

## Status (0003) — ring → phone

Fixed 12-byte struct, sent on connect, on change, on PING, and every 30 s:

```
u8  version        = 1
u8  state          0 idle, 1 capturing, 2 transferring, 3 recording, 4 playing (cue / pattern / speaker audio), 5 error
u16 battery_mv
u8  battery_pct    0..100 (255 = unknown)
u8  flags          bit0 charging, bit1 camera_ok, bit2 imu_ok, bit3 mic_ok, bit4 haptic_ok, bit5 queued_captures>0, bit6 speaker_ok
u32 uptime_s
u8  last_error     0 none, 1 camera_init, 2 capture_failed, 3 transfer_timeout, 4 oom, 5 mic
u8  queued         number of captures waiting to be sent
```

`speaker_ok` (bit6) is set when the firmware was built with I2S speaker pins configured
(`HAS_SPEAKER`); the app should only offer "play answers on the ring" when it is set.

## Events (0007) — ring → phone

Fixed 6-byte packet, one notification per event:

```
u8  event
u8  arg          event-specific (0 if unused)
u32 t_ms         ring uptime in ms when the event happened
```

| Id | Event | arg | When |
|---:|-------|-----|------|
| 1 | `BUTTON_DOWN` | 0 | button pressed (debounced); sent immediately so the phone can start recording |
| 2 | `BUTTON_UP` | held time in tenths of a second: `floor(held_ms / 100)`, capped at 255 | button released. The ring forces the value to agree with its own classification: a short press always reports `arg ≤ 6`, a long press `arg ≥ 7` (see Button semantics) |
| 3 | `DOUBLE_TAP` | 0 | IMU double tap |
| 4 | `TOUCH` | 0 | capacitive pad touched |
| 5 | `CAPTURE_STARTED` | 0 | camera capture begins (~150–400 ms) |
| 6 | `CAPTURE_DONE` | queued count (0 = capture failed) | capture finished and queued for transfer |
| 7 | `REC_STARTED` | max seconds | ring-mic recording started |
| 8 | `REC_STOPPED` | recorded tenths of a second (0 = clip discarded) | ring-mic recording stopped; an `ADPCM` transfer follows if arg > 0 |
| 9 | `LOW_BATTERY` | battery % | sent once when the battery drops below 15 % (re-armed above 20 %) |
| 10 | `AUDIO_UNDERRUN` | 0 | speaker queue ran dry mid-stream (silence inserted; phone is sending too slowly) |
| 11 | `AUDIO_DONE` | 0 = drained after `AUDIO_END`, 1 = flushed by `AUDIO_STOP`/`ABORT` | speaker playback finished |

### Button semantics (voice-first)

* **Short press** (released before 700 ms): `BUTTON_DOWN`, `BUTTON_UP(arg ≤ 6)`, then the ring
  captures a photo (`CAPTURE_STARTED`/`CAPTURE_DONE`, then a `JPEG` transfer).
* **Long press** (held ≥ 700 ms = "ask a question"): `BUTTON_DOWN` immediately. Then:
  * `MIC_SOURCE_HINT = 0` (ring mic, default): at 700 ms the ring captures a photo (this
    blocks the ring for ~150–400 ms), **then** plays the "listening" cue and starts recording
    with its own mic (`REC_STARTED`). The tick marks the real start of recording, which is
    therefore ≈ 0.85–1.1 s after `BUTTON_DOWN` — the app should tell users to **speak after
    the tick**; measure clip length from `REC_STARTED`, not from the press. Recording runs
    while the button is held (max 8 s); on release: `BUTTON_UP(arg ≥ 7)`, `REC_STOPPED`, then
    `JPEG` + `ADPCM` transfers.
  * `MIC_SOURCE_HINT = 1` (phone mic): the ring only plays the "listening" cue and reports
    `BUTTON_UP(arg ≥ 7)` on release. The phone records between `BUTTON_DOWN` and `BUTTON_UP`
    and sends `CAPTURE` itself if it wants a photo attached.
* **Double tap** is the hands-free "ask": the ring behaves as for a long press that ends
  automatically (ring mic: record up to 8 s or until `RECORD_STOP`; phone mic: the phone
  records until its own VAD/timeout). A second double tap while recording stops it.
* **`BUTTON_UP.arg`** is `floor(held_ms / 100)` and is forced to agree with the ring's own
  short/long decision (`≤ 6` short, `≥ 7` long), so companions can branch on `arg < 7`
  = "photo only" without ever disagreeing with what the ring did.
* **Phone-mic "ask" lifetime.** While an ask is open the ring reports itself busy (no deep
  sleep) and ignores a further long press / treats a further double tap as "stop". A
  phone-mic ask ends on `BUTTON_UP` (long press), on a second `DOUBLE_TAP`, on
  `RECORD_STOP` or `ABORT`, or **automatically 8.5 s after it began** if the button is no
  longer held (the companions' hands-free recording is capped at 8 s). A companion may send
  `RECORD_STOP` when its own recording ends; it is a no-op when the ring mic is idle.
* **Touch** captures a photo (as a short press).

## Audio out (0008) — phone → ring (on-ring speaker)

Write-without-response. Packets:

| Opcode | Name | Payload | Notes |
|-------:|------|---------|-------|
| 0x20 | `AUDIO_START` | `sample_rate_div100 u16 (160), codec u8 (2 = mcring ADPCM), volume u8 0..255` | resets the queue, (re)starts a stream |
| 0x21 | `AUDIO_DATA` | `seq u16, blocks[]` | one or more **whole 132-byte** mcring-ADPCM blocks (256 samples each, see `lib/mcring_adpcm`). `seq` increments per packet (wraps); used for gap logging only |
| 0x22 | `AUDIO_END` | – | no more data: the ring drains the queue and DMA, then sends `AUDIO_DONE(0)` |
| 0x23 | `AUDIO_STOP` | – | flush and stop immediately → `AUDIO_DONE(1)` |

Ring behaviour: blocks are queued (≥ 32 blocks of buffer; 48 in the ESP32-S3 firmware).
Playback starts once **24 blocks (~400 ms)** are queued, or sooner if `AUDIO_END` arrives
first. The I2S driver is only installed (and the peripheral clocked) while a stream plays; the
amplifier is only shut down between streams when its `SD` pin is wired to a GPIO
(`PIN_SPEAKER_EN`) — on the XIAO dev kit `SD` is tied high and the MAX98357A idles at ~2.4 mA.
If the queue
runs dry before `AUDIO_END`, the ring outputs silence, sends `AUDIO_UNDERRUN` and resumes
once a few blocks have accumulated again. If the queue is full, excess blocks are dropped
(logged) — the phone should stay no more than ~40 blocks (640 ms) ahead of real time:
burst the first 24–40 blocks, then pace at 1 block / 16 ms (e.g. 3 blocks every 48 ms).

Packet sizing: a write may carry `floor((MTU - 3 - 3) / 132)` blocks — 1 block (135 B) at
the iOS MTU of 185, 3 blocks (399 B) at 517. Reference splitters:
`mcring_core.proto.audio_data_writes()` and `app/src/lib/proto.ts audioDataWrites()`.

Effective gain = `AUDIO_START.volume × SPEAKER_VOLUME / 255²`; samples are scaled in the
ring before I2S. The speaker path is **mono**: the ring duplicates each sample into the
left and right I2S slots (standard Philips I2S, 16-bit, BCLK = 32 × fs), which is what a
MAX98357A expects regardless of its SD-pin channel selection.

## Transfer (0004 meta, 0005 data) — ring → phone

Images and audio clips use the same reliable transfer scheme.

**Meta START** (20 bytes) on 0004:
```
u8  type       1 = JPEG image, 2 = IMA-ADPCM audio (16 kHz mono, 4-bit, 256-sample blocks)
u16 xfer_id    increments per transfer
u32 total_len  bytes
u16 chunk_len  payload bytes per chunk (last chunk may be shorter)
u16 n_chunks
u32 crc32      IEEE CRC-32 of the full payload
u16 width      image only (0 for audio)
u16 height     image only (audio: sample_rate / 100, i.e. 160)
u8  seq_flags  bit0 = this capture was triggered on-ring (vs. requested by phone)
```

**Data chunk** on 0005:
```
u16 xfer_id
u16 idx        0-based chunk index
u8  payload[chunk_len]
```

**Meta END** (3 bytes) on 0004: `u8 type=0xFF, u16 xfer_id`.

Flow: ring sends START, then all chunks back-to-back (notifications, no per-chunk ack),
then END. The phone replies `ACK_TRANSFER`. If `status=1`, the ring re-sends only the
listed chunks and sends END again (max 5 rounds, then `last_error=3`). The ring holds the
buffer until `status=0` or abort. If no ACK arrives within 3 s of END, the ring resends END.

Throughput expectations (measured values go in `docs/benchmarks.md`):
Android, 2M PHY, 510-byte chunks, 15 ms interval → ~50–60 KB/s → a 20 KB QVGA JPEG in ≈0.4 s.
iOS, 178-byte chunks, 15 ms interval → ~10–12 KB/s → ≈2 s. VGA JPEGs (40–60 KB) take 2–3× longer.

## Feedback (0006) — phone → ring

Cues and raw patterns on the ring's LED / haptic / buzzer. The Morse opcodes are an
**optional, legacy** capability ("silent pattern" mode); they still work but nothing sends
them by default.

| Opcode | Name | Payload | Notes |
|-------:|------|---------|-------|
| 0x10 | `MORSE_TEXT` | `wpm u8, channels u8, len u8, text[len]` | *legacy.* ring encodes ITU Morse itself. `channels` bit0 LED, bit1 haptic, bit2 buzzer, bit3 "puff"/aux |
| 0x11 | `PATTERN` | `unit_ms u8, channels u8, n u8, units u8[n]` | raw alternating ON/OFF durations in units (starts with ON). Lets the phone send arbitrary rhythms |
| 0x12 | `STOP` | – | stop playback |
| 0x13 | `RGB` | `r u8, g u8, b u8, ms u16` | one-shot colour flash (status/acks) |
| 0x14 | `MORSE_UNITS` | `unit_ms u8, channels u8, n u16, units u8[n]` | *legacy.* like PATTERN but 16-bit count, for long messages (written in several writes if > MTU; see below) |
| 0x16 | `CUE` | `cue u8` | play one of the ring's built-in cues, honouring `CUES_MASK`: 1 listening (1 tick), 2 answer ready (2 ticks), 3 error (long buzz), 4 ok (1 tick) |

Long payloads for `MORSE_UNITS` may be sent as a sequence of writes: first write carries the
header and the first bytes, subsequent writes carry opcode `0x15 MORSE_UNITS_CONT` + `offset u16` +
more units. Playback starts when `n` units have been received.

Morse timing (PARIS standard): `unit_ms = 1200 / wpm`. Dot = 1 unit on, dash = 3 on,
intra-character gap = 1 off, inter-character gap = 3 off, word gap = 7 off.
The ring default is 15 WPM with Farnsworth spacing applied by the sender (see `morse.md`).

## Errors and edge cases

* A `CAPTURE` is accepted while the ring is idle, transferring or playing (a cue / pattern /
  speaker stream; a capture during speaker playback causes a ~150–400 ms `AUDIO_UNDERRUN`).
  It is ignored and answered with a Status notify while the ring is capturing or recording
  (except that a phone-mic "ask" may attach a photo with `CAPTURE` at any time).
* If the phone disconnects mid-transfer, the ring keeps the buffer (up to `MAX_QUEUED=3`
  captures in PSRAM) and restarts the transfer from START on reconnect.
* On-ring triggered captures while disconnected are queued the same way; `flags.bit5` and
  `queued` tell the phone to expect transfers on connect.
* Events are only delivered while the phone is subscribed to 0007; they are not queued
  across disconnects.
* `RECORD_START` is accepted while idle, transferring or playing (barge-in: send `AUDIO_STOP`
  and/or Feedback `STOP` first if the answer should go quiet — the ring does not silence the
  speaker itself). It is ignored (Status notify) while capturing or already recording.
* `ABORT`, `RECORD_STOP` and the disconnect are handled on the ring's BLE task; speaker
  playback is therefore stopped on the next firmware tick (≤ a few ms) and `AUDIO_DONE(1)`
  follows then.
* An `AUDIO_START` while a stream is playing aborts the old stream (no `AUDIO_DONE` for it).
