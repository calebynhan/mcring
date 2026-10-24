# mcring BLE protocol (v1)

The ring is a BLE **peripheral** (GATT server). The phone / desktop companion is the
**central**. All multi-byte integers are **little-endian**. All packets start with a
1-byte opcode or type.

## Service and characteristics

Base UUID: `7a3bXXXX-9c2e-4f3a-b1d4-6d6372696e67` (`6d6372696e67` is ASCII `mcring`).

| Short | UUID | Dir | Props | Purpose |
|------:|------|-----|-------|---------|
| 0001 | `7a3b0001-9c2e-4f3a-b1d4-6d6372696e67` | – | service | mcring service |
| 0002 | `7a3b0002-…` | phone→ring | write, write-no-rsp | **Control** commands |
| 0003 | `7a3b0003-…` | ring→phone | read, notify | **Status** (battery, state) |
| 0004 | `7a3b0004-…` | ring→phone | notify | **Transfer meta** (start/end of an image or audio transfer) |
| 0005 | `7a3b0005-…` | ring→phone | notify | **Transfer data** chunks |
| 0006 | `7a3b0006-…` | phone→ring | write, write-no-rsp | **Feedback** (Morse text / raw pattern / RGB) |

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
| 0x05 | `ABORT` | – | stop any transfer or feedback |
| 0x06 | `RECORD_AUDIO` | `seconds u8` | record a voice clip (if mic present), then transfer it as type `ADPCM` |
| 0x07 | `SLEEP` | – | enter deep sleep now |
| 0x08 | `GET_STATUS` | – | same as PING |

Frame sizes: `0=ring default, 1=QQVGA 160x120, 2=QVGA 320x240, 3=VGA 640x480, 4=SVGA 800x600, 5=XGA 1024x768`.

Config keys: `1=trigger_mask (bit0 button, bit1 double-tap, bit2 touch)`, `2=default_quality`,
`3=default_frame_size`, `4=idle_sleep_s`, `5=led_brightness 0..255`, `6=haptic_strength 0..127`,
`7=morse_wpm`, `8=feedback_channels (bit0 LED, bit1 haptic, bit2 buzzer)`.

## Status (0003) — ring → phone

Fixed 12-byte struct, sent on connect, on change, on PING, and every 30 s:

```
u8  version        = 1
u8  state          0 idle, 1 capturing, 2 transferring, 3 recording, 4 playing_feedback, 5 error
u16 battery_mv
u8  battery_pct    0..100 (255 = unknown)
u8  flags          bit0 charging, bit1 camera_ok, bit2 imu_ok, bit3 mic_ok, bit4 haptic_ok, bit5 queued_captures>0
u32 uptime_s
u8  last_error     0 none, 1 camera_init, 2 capture_failed, 3 transfer_timeout, 4 oom, 5 mic
u8  queued         number of captures waiting to be sent
```

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

| Opcode | Name | Payload | Notes |
|-------:|------|---------|-------|
| 0x10 | `MORSE_TEXT` | `wpm u8, channels u8, len u8, text[len]` | ring encodes ITU Morse itself. `channels` bit0 LED, bit1 haptic, bit2 buzzer, bit3 "puff"/aux |
| 0x11 | `PATTERN` | `unit_ms u8, channels u8, n u8, units u8[n]` | raw alternating ON/OFF durations in units (starts with ON). Lets the phone send arbitrary rhythms |
| 0x12 | `STOP` | – | stop playback |
| 0x13 | `RGB` | `r u8, g u8, b u8, ms u16` | one-shot colour flash (status/acks) |
| 0x14 | `MORSE_UNITS` | `unit_ms u8, channels u8, n u16, units u8[n]` | like PATTERN but 16-bit count, for long messages (written in several writes if > MTU; see below) |

Long payloads for `MORSE_UNITS` may be sent as a sequence of writes: first write carries the
header and the first bytes, subsequent writes carry opcode `0x15 MORSE_UNITS_CONT` + `offset u16` +
more units. Playback starts when `n` units have been received.

Morse timing (PARIS standard): `unit_ms = 1200 / wpm`. Dot = 1 unit on, dash = 3 on,
intra-character gap = 1 off, inter-character gap = 3 off, word gap = 7 off.
The ring default is 15 WPM with Farnsworth spacing applied by the sender (see `morse.md`).

## Errors and edge cases

* A `CAPTURE` while not idle is ignored and answered with a Status notify.
* If the phone disconnects mid-transfer, the ring keeps the buffer (up to `MAX_QUEUED=3`
  captures in PSRAM) and restarts the transfer from START on reconnect.
* On-ring triggered captures while disconnected are queued the same way; `flags.bit5` and
  `queued` tell the phone to expect transfers on connect.
