# 4. Bluetooth Low Energy

Everything between the ring and the phone is one BLE connection, and `protocol/ble-gatt.md` is the contract. This chapter gives you the vocabulary to read that file and the two implementations of it (`firmware/ring-esp32s3/src/ble_link.cpp` on NimBLE, `firmware/ring-nrf52840/src/ble_svc.c` on Zephyr) plus the three clients (`app/src/ble/RingClient.ts`, `tools/ring-cli/mcring_cli/ring.py`, and any phone explorer app). Sections 4.1–4.2 are the model, 4.3–4.5 are throughput and reliability (where mcring's numbers come from), 4.6 is security, 4.7–4.9 are tools, stacks and phones.

Units you will meet constantly: advertising interval in 0.625 ms steps, connection interval in 1.25 ms steps, supervision timeout in 10 ms steps, ATT MTU in bytes.

## 4.1 Roles, advertising and connections

**Why it matters in mcring.** The ring is the peripheral (GATT server) and advertises as `mcring-XXXX` with the 128-bit service UUID in the packet so `RingClient.scan()` and `BleakScanner` can filter on it; `ble::init()` sets the advertising interval to 160–400 units (100–250 ms), +6 dBm TX power, one connection max, and restarts advertising from `tick()` after a disconnect. On connect the ring immediately asks for a 15–30 ms connection interval, 2M PHY and 251-byte data length; after the last transfer it asks for 200–400 ms with peripheral latency 2 to save power.

**The concepts.** BLE uses 40 channels of 2 MHz in the 2.4 GHz band: 3 for advertising (37, 38, 39) and 37 for data, hopped on every connection event. A peripheral advertises (broadcasts a packet of ≤ 31 bytes every interval); a central scans, then sends a connection request; from then on the two radios wake together every connection interval, exchange packets, and sleep. The 31-byte advertising payload is why a 16-byte custom service UUID (plus 2 bytes of header and 3 of flags) leaves only 10 bytes, not enough for `mcring-XXXX` and its 2-byte header: NimBLE puts the name in the scan response, a second 31-byte packet sent only when a scanner asks (`enableScanResponse(true)`). Connection parameters: interval (7.5 ms–4 s), peripheral latency (how many events the peripheral may skip when it has nothing to say) and supervision timeout (how long without a packet before the link is declared dead). The central owns these; a peripheral can only request (`updateConnParams(handle, 12, 24, 0, 400)` = 15–30 ms, latency 0, 4 s), and the phone may answer with its own values, so the firmware never assumes they were granted. Device addresses are 48-bit; phones use resolvable private addresses that change every few minutes, so "reconnect to the address I saw yesterday" does not work and the companions scan by service UUID instead. Power follows the schedule: a connected radio at a 30 ms interval with nothing to send costs tens of µA; at 400 ms with latency 2 it is a few µA, which is what `request_slow_params()` is for.

**Learn it.**

| Resource | Type | Time | Why this one |
|---|---|---|---|
| [Nordic DevAcademy: Bluetooth Low Energy Fundamentals](https://academy.nordicsemi.com/courses/bluetooth-low-energy-fundamentals/) | course (free, 6 lessons) | 8–10 h | the best structured path: protocol layers, advertising, connections, data exchange, security, sniffer; hands-on exercises on nRF52/nRF53 (the stage-2 family) |
| [DevAcademy lesson 2: Bluetooth LE Advertising](https://academy.nordicsemi.com/courses/bluetooth-low-energy-fundamentals/lessons/lesson-2-bluetooth-le-advertising/) | course lesson | 1.5 h | advertising types, address types, the 31-byte packet; explains the UUID-in-advert / name-in-scan-response split |
| [DevAcademy lesson 3: Bluetooth LE Connections](https://academy.nordicsemi.com/courses/bluetooth-low-energy-fundamentals/lessons/lesson-3-bluetooth-le-connections/) | course lesson | 1.5 h | connection process and parameters (interval, latency, timeout) with the power/throughput trade-off |
| [Bluetooth SIG: The Bluetooth LE Primer (PDF)](https://bluetooth.com/wp-content/uploads/2022/05/the-bluetooth-le-primer-v1.2.0.pdf) | book (free PDF) | 4 h | the official layer-by-layer study guide, physical layer to GAP; the reference to settle terminology arguments ([landing page](https://www.bluetooth.com/bluetooth-resources/the-bluetooth-low-energy-primer/)) |
| [Memfault Interrupt: Bluetooth Low Energy: A Primer](https://interrupt.memfault.com/blog/bluetooth-low-energy-a-primer) | article | 45 min | one long article through every layer with an nRF52 example; good first read before the course |
| [Adafruit: Introduction to Bluetooth Low Energy](https://learn.adafruit.com/introduction-to-bluetooth-low-energy) | guide | 30 min | the shortest correct explanation of GAP vs GATT and central vs peripheral |

**Check yourself.**

1. Convert the advertising interval `setMinInterval(160)` / `setMaxInterval(400)` and the slow connection request `updateConnParams(h, 160, 320, 2, 600)` into milliseconds and seconds.
2. Why can the ring not simply pair itself to the user's Bluetooth headphones and skip the phone?
3. The ring sets `advertiseOnDisconnect(false)` and restarts advertising from `ble::tick()`. What does that buy over the automatic restart?

<details><summary>Answers</summary>

1. Advertising 160 × 0.625 = 100 ms to 400 × 0.625 = 250 ms. Connection 160 × 1.25 = 200 ms to 320 × 1.25 = 400 ms, latency 2 (the ring may skip two events), timeout 600 × 10 ms = 6 s.
2. Headphones speak Classic Bluetooth A2DP/HFP; the ESP32-S3 and nRF52 are BLE-only and could not be an audio source even with the power to do it (`docs/04`, "Audio topology"). The phone already owns the headphones, so the ring only needs BLE.
3. The restart happens on the loop task at a point the firmware controls: after `handle_connection(false)` has stopped feedback/audio and `transfer::on_disconnect()` has parked the buffers, so no advertising begins mid-teardown.

</details>

## 4.2 GATT: services, characteristics, descriptors and properties

**Why it matters in mcring.** One service `7a3b0001-…-6d6372696e67` ("mcring" in ASCII) holds seven characteristics with deliberately chosen properties: Control and Feedback are write + write-without-response, Status is read + notify, Transfer meta/data and Events are notify only, Audio out is write-without-response only. `ble_link.cpp` creates them with `NIMBLE_PROPERTY::*` flags and sizes (517 for data), and `ble_svc.c` does the same with `BT_GATT_CHARACTERISTIC` plus an explicit `BT_GATT_CCC` descriptor for each notifying characteristic. Subscription state (`g_data_sub`, `g_events_sub`) comes from the CCCD write.

**The concepts.** GATT is a table of attributes on the server, each with a 16-bit handle, a type (UUID) and a value. A service groups characteristics; a characteristic is a value plus a declaration of what you may do with it (properties) plus optional descriptors; the one descriptor that matters is the Client Characteristic Configuration Descriptor (CCCD, UUID 0x2902), two bytes the client writes to switch on notifications (bit 0) or indications (bit 1), which is exactly the `subValue & 0x0001` test in `onSubscribe`. Operations: read (client asks, server answers), write (client sends, server acknowledges), write-without-response (client sends, no ATT acknowledgement, no waiting), notify (server pushes a value, no acknowledgement), indicate (server pushes, client must acknowledge before the next one). mcring uses notify for everything ring→phone because one indication per round trip would cut throughput several times over, and write-without-response for the audio stream so the phone can fire 60 writes a second without waiting. UUIDs: 16-bit ones are reserved for Bluetooth SIG-assigned services (0x180F battery, 0x2902 CCCD); custom services use a random 128-bit base with 16 bits free to number characteristics (0001…0008 here). The server's value for Status is also set on every change even when nobody subscribes, so a plain read returns the latest struct. ATT is the byte protocol underneath GATT; its opcodes cost 1 byte and its handle 2, which is the "3-byte ATT header" in the MTU arithmetic of 4.3.

**Learn it.**

| Resource | Type | Time | Why this one |
|---|---|---|---|
| [DevAcademy lesson 4 topic: Services and characteristics](https://academy.nordicsemi.com/courses/bluetooth-low-energy-fundamentals/lessons/lesson-4-bluetooth-le-data-exchange/topic/services-and-characteristics/) | course lesson | 1 h | attributes, handles, CCCD, notify vs indicate, with a custom-service exercise that mirrors `ble_svc.c` |
| [Novel Bits: Bluetooth GATT: How to Design Custom Services & Characteristics](https://novelbits.io/bluetooth-gatt-services-characteristics/) | article | 45 min | how to choose a 128-bit base UUID and number characteristics, which properties to give each; the reasoning behind `protocol/ble-gatt.md` |
| [Nordic DevZone: BLE Services, a beginner's tutorial](https://devzone.nordicsemi.com/nordic/short-range-guides/b/bluetooth-low-energy/posts/ble-services-a-beginners-tutorial) | tutorial (unmaintained, concepts still right) | 1 h | builds a custom service step by step; read for the attribute-table drawings |
| [Bluetooth SIG: Assigned Numbers](https://bluetooth.com/wp-content/uploads/Files/Specification/Assigned_Numbers.html) | reference | 15 min | the official 16-bit UUID tables (services, characteristics, descriptors): what 0x2902 and 0x180F mean and why custom UUIDs must avoid them |

**Check yourself.**

1. Why are Control and Feedback declared `WRITE | WRITE_NR` while Audio out is `WRITE_NR` only?
2. Events are "not queued across disconnects" and "only delivered while the phone is subscribed to 0007". Which GATT mechanism makes the second half true, and where is it checked in `ble_link.cpp`?
3. The Zephyr service table comment says "attribute indices: 0 svc, 1-2 ctrl, 3-4 status, 5 ccc …". Why does one characteristic take two attributes, and a notifying one three?

<details><summary>Answers</summary>

1. Commands like `SET_CONFIG` or `ACK_TRANSFER` benefit from an acknowledged write when the client wants confirmation, while a client in a hurry (`writeControl` in the app) may use write-without-response; both are allowed. The audio stream must never block on a response at 60+ writes/s, so it offers only the unacknowledged form.
2. The CCCD: notifications are only sent to a client that wrote 0x0001 to the characteristic's CCCD, and the subscription dies with the connection. `notify_event()` returns false unless `g_connected && g_events_sub`, flags set in `onSubscribe`.
3. A characteristic is a declaration attribute (properties, value handle, UUID) plus a value attribute; a notifying one adds the CCCD descriptor attribute so the client has something to write its subscription into.

</details>

## 4.3 MTU, connection interval, PHY, DLE: the throughput maths

**Why it matters in mcring.** The ring requests ATT MTU 517, LE 2M PHY and a 251-byte data length, then computes `chunk_len = MTU − 3 − 4` from whatever it actually got (`mc_chunk_len_for_mtu`): 178 bytes on iOS (MTU 185), up to 510 on Android (517). `protocol/ble-gatt.md` expects ~10–12 KB/s on iOS and ~50–60 KB/s on Android at a 15 ms interval; `docs/04` turns that into the "keep images ≤ 30 KB" rule, and `docs/07` §4 lists "MTU stuck at 23" and "iOS 178-byte chunks" as the two most common log lines to understand.

**The concepts.** Four knobs set the ceiling. (1) ATT MTU: the largest ATT packet; default 23 (20 bytes of payload), negotiable once per connection and only by the client. A notification carries MTU − 3 bytes of value; mcring's chunk header takes 4 more, so payload = MTU − 7. Android apps may request 517; iOS decides itself and gives 185 on current iPhones, and 185 + 4 bytes of L2CAP header = 189 fits in a single 251-byte link-layer packet, so one iOS notification is one radio packet. (2) Data Length Extension (BT 4.2): link-layer packets grow from 27 to 251 bytes of payload; without it a 182-byte notification is fragmented into 7 radio packets each with its own overhead. (3) PHY: 1M is 1 Mbit/s GFSK; 2M (BT 5) halves airtime per byte, so more packets fit in one connection event; the phone must support and grant it (`updatePhy` is a request). (4) Connection interval and packets per event: each event is a burst of packet pairs until one side runs out of data or the controller's per-event cap is hit; a shorter interval means more events per second and a higher ceiling but higher idle power. Rough arithmetic that matches the repo's measurements: at a 15 ms interval, one 182-byte notification per event is 182 / 0.015 ≈ 12 KB/s, the iOS figure; Android with 510-byte chunks (three DLE packets each) and several packets per event lands at 50–60 KB/s. For a 15 KB QVGA JPEG that is ≈ 1.3 s on iOS vs ≈ 0.3 s on Android; a 50 KB VGA frame is 4 s vs 1 s. The speaker stream needs 8.25 KB/s continuously, about 70 % of the iOS ceiling at MTU 185 (1 block per write) and ~15 % of Android's (3 blocks per write). Apple publishes what it will accept from an accessory: intervals ≥ 15 ms and in 15 ms multiples, peripheral latency ≤ 30, supervision timeout 6–18 s (R26 guidelines); requests outside that are simply answered with something else.

**Learn it.**

| Resource | Type | Time | Why this one |
|---|---|---|---|
| [Memfault Interrupt: A Practical Guide to BLE Throughput](https://interrupt.memfault.com/blog/ble-throughput-primer) | article | 1 h | the derivation from radio bit rate down to application bytes/s, 4.0 → 5.1 (DLE, 2M), and how to find which knob limits you |
| [Punch Through: Maximizing BLE Throughput on iOS and Android (Part 1)](https://punchthrough.com/maximizing-ble-throughput-on-ios-and-android/) | article | 30 min | why "1 Mbps" is not your number; iOS and Android per-event limits |
| [Punch Through: Maximizing BLE Throughput Part 2: Use Larger ATT MTU](https://punchthrough.com/maximizing-ble-throughput-part-2-use-larger-att-mtu/) | article | 20 min | MTU negotiation, who may request it, the 23→517 arithmetic (Parts 3 and 4 cover DLE and 2M PHY: [series tag](https://punchthrough.com/tag/ble-throughput)) |
| [Nordic DevZone: The ultimate guide to maximizing your BLE and Bluetooth 5 data throughput](https://devzone.nordicsemi.com/nordic/nordic-blog/b/blog/posts/the-ultimate-guide-to-maximizing-your-ble-and-blue) | article | 45 min | application-throughput formulas with measured nRF52 numbers; the stage-2 side of the same maths |
| [Apple: Accessory Design Guidelines for Apple Devices (PDF)](https://developer.apple.com/accessories/Accessory-Design-Guidelines.pdf) | spec (PDF) | 30 min (Bluetooth LE chapter) | the connection-parameter rules an iPhone enforces; check `ble_link.cpp`'s requests against them |
| [Silicon Labs: Selecting Suitable Connection Parameters for Apple Devices](https://docs.silabs.com/bluetooth/3.3/bluetooth-miscellaneous-mobile/selecting-suitable-connection-parameters-for-apple-devices) | docs | 15 min | the Apple rules restated with examples and revision history |
| [Apple Developer Forums: Request for Suggestions to Improve BLE Throughput on iOS Devices](https://developer.apple.com/forums/thread/773555) | forum thread | 15 min | what iOS developers actually see for MTU, interval and packets per event |

**Check yourself.**

1. The ring log says `MTU 23 -> chunk 16`. How many notifications does a 15 KB JPEG need, roughly how long at ~1 per 15 ms, and whose fault is it?
2. `updateConnParams(h, 12, 24, 0, 400)`: convert to ms/s and name the two values an iPhone following the R26 guidelines would not accept as-is.
3. Why does one speaker write carry 1 block on iOS and 3 on Android? Show the arithmetic from `floor((MTU − 3 − 3) / 132)`.
4. A phone grants MTU 517 but not DLE (27-byte LL payload). How many link-layer packets does one 517-byte notification take, and what does that do to throughput?

<details><summary>Answers</summary>

1. 15,000 / 16 ≈ 938 chunks ≈ 14 s. The client never did the MTU exchange (only the central can initiate it); on Android the app must call `connect({ requestMTU: 517 })`, which `RingClient.connect` does.
2. 12 × 1.25 = 15 ms min, 24 × 1.25 = 30 ms max, latency 0, 400 × 10 ms = 4 s timeout. The 4 s timeout is below Apple's 6–18 s window, and 30 ms is a multiple of 15 ms, so the interval passes, the timeout does not; iOS will pick its own values and the ring must live with them.
3. iOS: (185 − 6) / 132 = 179 / 132 → 1 block (135-byte write). Android: (517 − 6) / 132 = 511 / 132 → 3 blocks (399-byte write).
4. 517 + 4 (L2CAP) = 521 bytes → ⌈521 / 27⌉ = 20 link-layer packets, each with ~10 bytes of overhead and inter-frame spacing; throughput collapses toward the no-DLE ceiling (~a few KB/s per event), which is why the firmware asks for `setDataLen(…, 251)` as soon as it connects.

</details>

## 4.4 Flow control and the TX-credit idea

**Why it matters in mcring.** `do_notify()` in `ble_link.cpp` keeps a credit counter (`g_credits_max = 6`): each successful `notify()` spends one, the NimBLE `onStatus` callback (notification transmitted) refunds one, and if the stack never calls back a 50 ms timeout refills the pool so nothing deadlocks. When the controller's buffers are full `notify()` returns false and the sender backs off 2 ms, up to 40 times, then reports "notify dropped". `transfer::tick()` honours that back-pressure by stopping its 15 ms slice early. In the other direction the phone paces `AUDIO_DATA` writes itself (`audioStream.ts`, `audio_out.py`): burst 24 blocks, then one block per 16 ms, never more than ~40 blocks ahead, because write-without-response has no feedback at all.

**The concepts.** Between your code and the antenna sit several queues: the host stack's ATT/L2CAP buffers, the controller's link-layer TX buffers, then the air. The link layer is reliable (every data packet is acknowledged and retransmitted until the supervision timeout), but queues are finite: push faster than the connection drains and either an API call fails (`notify()` false), blocks, or the stack silently drops. Flow control is how a producer learns the consumer's pace. Credits are the classic scheme (L2CAP's own connection-oriented channels use them): the sender holds N tokens, spends one per packet, gets one back when a packet completes; N bounds how far ahead it can run, so the ring never queues more than 6 notifications and a disconnect loses at most that many. The timeout refill is a safety net for stacks that do not report completion. The write-without-response direction has no ATT feedback, so the only tools are pacing to the real-time rate the consumer is known to drain (16 ms per 256-sample block), a prebuffer on the consumer to absorb jitter, a bounded queue that drops (and counts) excess, and an application-level event (`AUDIO_UNDERRUN`) when the producer falls behind. The hard limit of pacing on a phone is timer granularity and the OS coalescing writes into connection events, which is why "3 blocks every 48 ms" is suggested rather than "1 block every 16 ms".

**Learn it.**

| Resource | Type | Time | Why this one |
|---|---|---|---|
| [NimBLE-Arduino (h2zero) on GitHub](https://github.com/h2zero/NimBLE-Arduino) | code + docs | 1 h | the library `ble_link.cpp` is written against: `NimBLECharacteristic::notify`, `onStatus`, `setDataLen`, `updatePhy`; the README links the API reference and the 1.x→2.x migration guide |
| [Apache Mynewt: NimBLE Host API](https://mynewt.apache.org/latest/network/ble_hs/ble_hs.html) | docs | 1 h | the host underneath NimBLE-Arduino: GATT server registration, `ble_gatts_notify_custom`, mbuf pools (the buffers that fill when `notify()` fails) |
| [ESP-IDF: Bluetooth LE overview (ESP32-S3)](https://docs.espressif.com/projects/esp-idf/en/latest/esp32s3/api-guides/ble/overview.html) | docs | 30 min | how controller, host (NimBLE or Bluedroid) and application tasks are layered on the ESP32-S3 |
| [Punch Through: Building a Reliable Android BLE Operation Queue](https://punchthrough.com/android-ble-operation-queue/) | article | 30 min | the phone-side version of the same problem: one operation in flight, a queue, and why unpaced writes fail on Android |

**Check yourself.**

1. With 6 credits and ~1 notification per 15 ms event on iOS, how far ahead of the air can the ring get, in ms and bytes?
2. The `onStatus` callback increments `g_credits` on the NimBLE task while `do_notify` decrements on the loop task. The README calls the callback "opportunistic". What guarantees progress if it never fires?
3. The companions are told to stay ≤ 40 blocks ahead although the queue holds 48. Why not use all 48?

<details><summary>Answers</summary>

1. 6 × 15 ms = 90 ms, 6 × 182 B ≈ 1.1 KB of notifications queued in the stack at most.
2. The 50 ms timeout in `do_notify` sets `g_credits = g_credits_max` and continues; the real back-pressure then comes from `notify()` returning false when the controller buffers are full, so throughput is safe even if credits are never refunded.
3. Margin for burstiness and for the ring's own consumption lag: the loop drains up to 8 blocks per tick, a capture can stall the loop 150–400 ms (during which the phone keeps writing), and `q_push` drops anything beyond 48. Leaving 8 blocks of headroom turns a bursty but on-time sender into zero drops.

</details>

## 4.5 Reliability on top: chunking, CRC-32, ACK and selective retransmit

**Why it matters in mcring.** Images and clips are sent as START (20-byte meta on 0004), N data chunks `{xfer_id u16, idx u16, payload}` on 0005 with no per-chunk ACK, then END; the phone answers `ACK_TRANSFER` with status 0 (complete), 1 plus a list of missing indices, or 2 (abort). `transfer.cpp` resends only the listed chunks, at most `TRANSFER_MAX_ROUNDS = 5` rounds, resends END if no ACK arrives within 3 s, keeps the buffer across a disconnect and restarts from START on reconnect. The CRC-32 in START lets `TransferAssembler.assemble()` reject a corrupt reassembly and ask for a full resend.

**The concepts.** The link layer guarantees that a radio packet either arrives intact (24-bit CRC checked, retransmitted otherwise) or the link dies; what it does not guarantee is that your notification made it through every queue on both sides: a stack can drop a notification when its buffers are full (`notify()` false on the ring, a missed callback on the phone), an app can be suspended, a connection can drop mid-image. So an application protocol adds: sequencing (`idx`) so gaps are detectable, a transfer id so a late ACK for an old transfer is ignored (`ACK for stale id`), an end marker so the receiver knows when to tally, a negative acknowledgement with a missing list so only the gaps are re-sent (selective repeat, far cheaper than go-back-N over a 10 KB/s link), bounded retries so a dead phone cannot pin the ring forever, and a checksum over the whole payload. CRC-32 (polynomial 0xEDB88320 reflected, as in `mc_crc32_update`) is polynomial division over GF(2): it detects every 1- and 2-bit error in a payload of this size, every burst error up to 32 bits long, and misses a random corruption with probability 2^−32; it is not a signature (anyone can recompute it), it is a tripwire for software bugs such as a chunk written at the wrong offset. The budget: a 15 KB JPEG is 85 chunks on iOS; one missing chunk costs one 178-byte resend and one ACK round, ~50 ms, instead of 1.3 s for a full retry.

**Learn it.**

| Resource | Type | Time | Why this one |
|---|---|---|---|
| [Ben Eater: Error detection series (checksums, CRCs, hardware CRC)](https://eater.net/crc) | video series | 2 h | "How do CRCs work?" derives polynomial division and why the generator catches burst errors, then builds it in hardware; the maths behind `mc_crc32` |
| [Memfault community thread on "A Practical Guide to BLE Throughput"](https://community.memfault.com/t/a-practical-guide-to-ble-throughput-interrupt/80) | forum thread | 15 min | the author on what the link layer does and does not guarantee (acknowledged packets, supervision timeout), i.e. why an app-level ACK still exists |
| [DevAcademy lesson 3 topic: Connection process](https://academy.nordicsemi.com/courses/bluetooth-low-energy-fundamentals/lessons/lesson-3-bluetooth-le-connections/topic/connection-process/) | course lesson | 30 min | link-layer acknowledgement, supervision timeout and what "connection lost" means at the bottom of the stack |

**Check yourself.**

1. The phone receives all chunks but the CRC fails. What does `RingClient.finish()` send, and what does the ring do with it?
2. Why is `xfer_id` in every data chunk when the phone already knows which transfer is in progress?
3. What happens if the ACK itself is lost? Trace the ring's state machine through 3 s.
4. Could the firmware drop the CRC now that each chunk arrives intact or not at all? Argue both ways in one sentence each.

<details><summary>Answers</summary>

1. `ackTransfer(xferId, [0..n−1].slice(0,200))`: status 1 with up to 200 missing indices, i.e. a full resend; `on_ack` re-queues those indices, increments `g_rounds` and goes back to `Sending`.
2. After a disconnect/reconnect or a timed-out END resend the phone may still be assembling an older transfer; chunks with a different id are ignored by `onData` (`xferId !== this.asm.start.xferId`), and stale ACKs are ignored by the ring.
3. `WaitAck` sees `millis() − g_end_sent_ms > 3000`, increments `g_rounds` and resends END; the phone's `onMeta` sees END again and re-sends its ACK (missing list empty); the ring completes. After 5 silent rounds it gives up with `last_error = 3`.
4. Drop it: the link layer's 24-bit CRC already rejects corrupted packets, so payload bytes are either right or absent. Keep it: the CRC catches *software* faults (wrong offset, stale buffer, a chunk from another transfer slipping through) on three independent implementations, at 4 bytes per image.

</details>

## 4.6 Pairing and bonding basics

**Why it matters in mcring.** The v1 firmware does not require pairing: `NimBLEDevice::setSecurityAuth(false, false, true)` means no bonding, no man-in-the-middle protection, LE Secure Connections if a central asks; `prj.conf` enables `CONFIG_BT_SMP` and `CONFIG_BT_SETTINGS` on the nRF skeleton so bonds could be stored. Anyone within range can therefore connect to an unpaired ring, read Status and trigger a capture; encryption and a bonding flow are a backlog item, and `docs/04` lists privacy as a risk. Phones add their own layer: iOS always uses private addresses, which is why both companions find the ring by service UUID rather than by MAC.

**The concepts.** Pairing creates keys; bonding stores them so the next connection is encrypted without redoing pairing. The Security Manager Protocol runs in phases: exchange capabilities (I/O: display, keyboard, none), pick a method, generate keys, distribute them. Methods: Just Works (no user step, no MITM protection: fine against eavesdropping, not against an impostor), Passkey Entry (six digits displayed on one side, typed on the other), Numeric Comparison (both show a number, user confirms), Out-of-Band. LE Legacy pairing (BT 4.0/4.1) derives keys from a short-term key and is weak against a sniffer that captures the pairing; LE Secure Connections (4.2+) uses ECDH on P-256 so a passive sniffer learns nothing. After pairing the link is AES-CCM encrypted and attributes can require it (an encrypted-only characteristic refuses reads before pairing). Privacy: a device with an Identity Resolving Key advertises resolvable private addresses that rotate every ~15 minutes; a bonded peer can resolve them, a stranger cannot track the device. For a ring with a camera and a microphone the design question is which operations may happen unpaired (Status, maybe) and which must be encrypted and bonded (capture, record, audio, config); a button-press-to-confirm on the ring would make Just Works acceptable because physical presence is the second factor.

**Learn it.**

| Resource | Type | Time | Why this one |
|---|---|---|---|
| [DevAcademy lesson 5 topic: Pairing process](https://academy.nordicsemi.com/courses/bluetooth-low-energy-fundamentals/lessons/lesson-5-bluetooth-le-security-fundamentals/topic/pairing-process/) | course lesson | 1.5 h (whole lesson) | the phases, methods, legacy vs LESC, security modes, then an exercise adding pairing, bonding and a filter accept list to a peripheral |
| [Bluetooth SIG: Bluetooth LE Security Study Guide](https://www.bluetooth.com/bluetooth-resources/le-security-study-guide/) | book (free) | 4 h | modular self-study of every LE security feature with Zephyr-based exercises; the reference for designing the ring's future pairing flow |
| [Bluetooth SIG: The Bluetooth LE Primer (PDF)](https://bluetooth.com/wp-content/uploads/2022/05/the-bluetooth-le-primer-v1.2.0.pdf) | book (free PDF) | 1 h (security chapter) | where SMP, encryption and privacy sit in the stack |

**Check yourself.**

1. Decode `setSecurityAuth(false, false, true)` argument by argument and say what a phone that insists on pairing will get.
2. Why would "connect to the MAC I saved last time" work with the desktop CLI on Linux against the ring, but a phone-side equivalent fail against an iPhone acting as peripheral?
3. Propose the minimum security change that stops a stranger triggering a capture, and name the one GATT property-level mechanism it uses.

<details><summary>Answers</summary>

1. bonding = false (keys not stored), MITM = false (Just Works allowed), SC = true (Secure Connections used if pairing happens). A phone that requests pairing gets a Just-Works LESC pairing and an encrypted link for this connection only; next time it starts from scratch.
2. The ring advertises with its public/static address, so its MAC is stable; an iPhone uses resolvable private addresses that change every few minutes, so a stored MAC is useless unless you hold its IRK (i.e. are bonded).
3. Enable bonding with MITM off (`setSecurityAuth(true, false, true)`) and mark Control, Feedback and Audio out as encryption-required (`WRITE_ENC`/`WRITE_AUTHEN` flags in NimBLE, `BT_GATT_PERM_WRITE_ENCRYPT` in Zephyr), leaving Status readable; add "hold the ring button during the first pairing" so presence gates the Just Works step.

</details>

## 4.7 Tools: nRF Connect, LightBlue, Wireshark + sniffer, bleak

**Why it matters in mcring.** Before the app exists you can drive the whole protocol by hand: subscribe to Status/Events in a phone explorer, write `01 00 00` (CAPTURE) to 0002 and watch chunks arrive on 0005; `docs/07` §1 does exactly this with `mcring` (bleak) and the ring's log side by side. When the app and the ring disagree, a sniffer trace is the only neutral witness: it shows the MTU exchange, the connection-parameter update response, the PHY update and which side went silent.

**The concepts.** A GATT explorer app is a central that discovers services and lets you read/write/subscribe raw bytes; it answers "is the ring advertising, what MTU did the phone pick, does Status notify every 30 s" without a line of app code. A BLE sniffer is a third radio that follows the hop sequence of one connection and hands every packet to Wireshark, where you can filter on ATT opcodes (`btatt.opcode == 0x1b` for notifications), see link-layer retransmissions and the exact `LL_LENGTH_RSP`/`LL_PHY_RSP`; it cannot decrypt an LESC-paired link unless it captured the pairing or you give it the LTK. A programmable central (bleak in Python) turns protocol tests into scripts; its API maps one-to-one onto GATT: `start_notify(uuid, cb)`, `write_gatt_char(uuid, data, response=False)`, and `mtu_size` for the negotiated MTU, which is why `ring.py` reads like `RingClient.ts`. Reading `btmon`/CoreBluetooth logs is the last resort for OS-side behaviour.

**Learn it.**

| Resource | Type | Time | Why this one |
|---|---|---|---|
| [nRF Connect for Mobile (Nordic)](https://www.nordicsemi.com/Products/Development-tools/nRF-Connect-for-mobile) | tool (iOS/Android) | 30 min to learn | scan, RSSI graph, connect, read/write/subscribe, log; on Android it can also request MTU and act as a GATT server to test the app |
| [LightBlue (Punch Through)](https://apps.apple.com/app/lightblue/id557428110) | tool (iOS/Android) | 20 min | the other explorer; its virtual-peripheral mode on iOS lets you fake a ring to develop the app against (also on Google Play) |
| [Nordic: nRF Sniffer for Bluetooth LE](https://docs.nordicsemi.com/r/bYkE8evbjCoV6wV0tetlaQ/tkNhkQyalEt_B1SGFLOmNw) | tool + docs | 1 h to set up | the $10-dongle sniffer with the Wireshark plugin; follows one connection, decrypts with a known LTK |
| [DevAcademy lesson 6: Bluetooth LE sniffer (exercise 3)](https://academy.nordicsemi.com/courses/bluetooth-low-energy-fundamentals/lessons/lesson-6-bluetooth-le-sniffer/topic/blefund-lesson-6-exercise-3/) | course lesson | 1 h | guided captures: advertising, a connection, a paired link; teaches the Wireshark filters you will reuse |
| [bleak documentation](https://bleak.readthedocs.io) | docs | 45 min | the cross-platform Python central the CLI is built on; read the usage page, then `tools/ring-cli/mcring_cli/ring.py` |
| [Novel Bits: Bluetooth LE Development Tools](https://novelbits.io/bluetooth-le-development-tools) | article | 20 min | a curated map of explorers, sniffers and analysers, with what each is good for |

**Check yourself.**

1. From nRF Connect on an iPhone you subscribe to 0005 and 0004 and send CAPTURE. The ring log shows `MTU 185 -> chunk 178` and `START … chunks=85 x 178`. How many bytes was the JPEG (to the nearest 100)?
2. The CLI prints `connected; MTU 517 (3 audio block(s)/write)` on Linux but the macOS run says 185. Which side chose, and is anything wrong?
3. Name three things a sniffer capture shows that neither the ring log nor the app log can.

<details><summary>Answers</summary>

1. 85 × 178 = 15,130 maximum; the last chunk may be short, so ≈ 15,000 bytes (between 14,953 and 15,130).
2. The central (BlueZ or CoreBluetooth) chose; the ring only states its 517 preference. Nothing is wrong: the firmware computes chunk and block sizes from the negotiated value, and the build guide says never to hard-code them.
3. The MTU exchange request/response values, the connection-parameter update response (what the phone actually granted), PHY/data-length negotiation, link-layer retransmissions and the empty-packet pattern that reveals how many packets per event the phone allows.

</details>

## 4.8 Stacks: NimBLE, Zephyr Bluetooth, Bluedroid

**Why it matters in mcring.** The ESP32-S3 firmware uses NimBLE-Arduino 2.x (`lib_deps`, `CONFIG_BT_NIMBLE_MAX_CONNECTIONS=1`, `CONFIG_BT_NIMBLE_ATT_PREFERRED_MTU=517`), not the Arduino core's default Bluedroid, because it is smaller and its callbacks are predictable. The nRF52840 skeleton uses Zephyr's host (`prj.conf`: `CONFIG_BT_PERIPHERAL`, `CONFIG_BT_USER_PHY_UPDATE`, `CONFIG_BT_CTLR_DATA_LENGTH_MAX=251`, `CONFIG_BT_L2CAP_TX_MTU=517`, `CONFIG_BT_CONN_TX_MAX=10`) with a `BT_GATT_SERVICE_DEFINE` table. Both implement the identical service, which is the whole point of keeping the packet codecs in `lib/`.

**The concepts.** A BLE stack is a controller (link layer and radio, often on its own core or chip) and a host (L2CAP, ATT/GATT, SMP, GAP) joined by HCI. NimBLE is Apache Mynewt's open-source host + controller, ported by Espressif to run on FreeRTOS; `NimBLE-Arduino` wraps it in C++ classes (`NimBLEServer`, `NimBLECharacteristic`) whose callbacks run on the NimBLE host task, not in `loop()`, which is why `ble_link.cpp` only sets flags or copies bytes there. Bluedroid is the larger Android-derived host Espressif also ships; it supports Classic Bluetooth, which the ESP32-S3 cannot do anyway, so NimBLE is the natural pick. Zephyr's host is written in C with static declaration macros (`BT_GATT_CHARACTERISTIC`, `BT_GATT_CCC`) that build the attribute table at compile time, Kconfig options instead of `#define`s for buffer counts and MTU, and `bt_gatt_notify` from any thread; on an nRF52840 the controller is Zephyr's own, on the same core. Knobs with the same meaning in both: preferred MTU (517), controller TX buffer count (`CONFIG_BT_CONN_TX_MAX=10` vs NimBLE mbufs, the pool that decides when `notify()` fails), data length (251), PHY update permission, max connections (1 here). What differs: NimBLE-Arduino 2.x reports notification completion via `onStatus` (the TX-credit hook), Zephyr via a per-notification callback in `bt_gatt_notify_cb`.

**Learn it.**

| Resource | Type | Time | Why this one |
|---|---|---|---|
| [NimBLE-Arduino (h2zero) on GitHub](https://github.com/h2zero/NimBLE-Arduino) | code + docs | 1 h | the exact library and version pinned in `platformio.ini`; usage tips page covers MTU, connection parameters and power settings |
| [Apache Mynewt: NimBLE Host API](https://mynewt.apache.org/latest/network/ble_hs/ble_hs.html) | docs | 1 h | the C host underneath; GAP/GATT/SMP APIs and the mbuf pool configuration |
| [ESP-IDF: Bluetooth LE overview (ESP32-S3)](https://docs.espressif.com/projects/esp-idf/en/latest/esp32s3/api-guides/ble/overview.html) | docs | 30 min | NimBLE vs Bluedroid on the ESP32-S3, controller/host split, supported versions and features |
| [Zephyr: Bluetooth API reference](https://docs.zephyrproject.org/latest/connectivity/bluetooth/api/index.html) | docs | 1 h | `bt_gatt_*`, `bt_conn_*`, `bt_le_adv_start`; the calls in `ble_svc.c` and the Kconfig symbols in `prj.conf` |
| [Nordic DevAcademy: nRF Connect SDK Fundamentals](https://academy.nordicsemi.com/?p=3700) | course (free, 8 lessons) | 8–10 h | Zephyr/nRF Connect SDK from zero: devicetree, Kconfig, threads, drivers; the prerequisite for finishing `firmware/ring-nrf52840` |
| [NordicDeveloperAcademy/bt-fund (exercise code)](https://github.com/NordicDeveloperAcademy/bt-fund) | code | 30 min | the BLE Fundamentals solutions: a custom service on Zephyr to diff against `ble_svc.c` |

**Check yourself.**

1. `AudioOutCB::onWrite` calls `audio_out_on_packet()` directly on the NimBLE task, while `CtrlCB::onWrite` hands bytes to `handle_control` which also runs there. Why is the first safe and what makes the second safe?
2. Map `CONFIG_BT_NIMBLE_ATT_PREFERRED_MTU=517` and `CONFIG_BT_CONN_TX_MAX=10` to their meaning, and say which one the phone can override.
3. The nRF skeleton predates the voice pivot: which two characteristics are missing from `ble_svc.c`, and what else must be ported with them?

<details><summary>Answers</summary>

1. `audio_out_on_packet` only pushes into a spinlock-guarded queue and sets flags, no I2S or heap work. `handle_control` runs state changes on the NimBLE task too; it works today because its targets (`transfer::on_ack`, `settings_apply`, `g_status_dirty`) are simple and `ABORT` is deferred through flags, but it is the place a future refactor should move to a queue-to-loop handoff like the audio path.
2. 517 is the ATT MTU the ring will accept; the final value is `min(ring, phone)` and the phone decides whether to ask at all. `CONFIG_BT_CONN_TX_MAX=10` is the number of link-layer TX buffers on the nRF: more buffers, more notifications in flight per event, more RAM; the phone cannot change it.
3. Events (0007, notify) and Audio out (0008, write-without-response), plus the ADPCM decoder, an I2S/PWM speaker path (not planned at stage 2) and the event emission points in the trigger/capture code.

</details>

## 4.9 BLE on phones: react-native-ble-plx, CoreBluetooth and Android quirks

**Why it matters in mcring.** `RingClient.ts` is a thin layer over `react-native-ble-plx`: `startDeviceScan([UUID_SERVICE])`, `connect({ requestMTU: 517 })`, `discoverAllServicesAndCharacteristics()`, four `monitorCharacteristicForService` subscriptions, `writeCharacteristicWithoutResponseForService` with base64 payloads, and `maxWriteForMtu = mtu − 3` to size audio writes. Because the library needs native code the app is an Expo development build (`npx expo prebuild`), not Expo Go. The CLI does the same with bleak on Linux/macOS/Windows.

**The concepts.** Phones expose BLE through an OS central API that hides the controller: iOS CoreBluetooth (`CBCentralManager` → `CBPeripheral` → services → `CBCharacteristic`), Android `BluetoothGatt`. react-native-ble-plx maps both onto one promise/callback API and ships values as base64 strings, hence `P.fromBase64` on every notification. iOS specifics: the app cannot request an MTU (iOS negotiates, currently 185) and learns the write size from `maximumWriteValueLength`; connection parameters are iOS's choice within the Accessory Design Guidelines; scanning in the background requires filtering by service UUID; the OS may coalesce notifications and deliver them in bursts; `Info.plist` needs `NSBluetoothAlwaysUsageDescription`. Android specifics: `requestMtu(517)` is explicit and may be refused; `BluetoothGatt` tolerates only one operation in flight, so reads/writes/MTU/notification-enables must be serialised (ble-plx queues per device, which is why `applyVoiceConfig` awaits three `setConfig` calls in sequence); scanning needs location (≤ Android 11) or `BLUETOOTH_SCAN` (12+) permissions; connection priority (`requestConnectionPriority`) nudges the interval toward 11.25–15 ms; write-without-response can fail when the stack's queue is full, so the audio pacer must check results; some vendors kill background BLE aggressively. Reconnection should be by scan + service UUID, never by cached address on iOS (4.6). Development builds: Expo Go cannot load custom native modules, so `expo prebuild` generates `ios/`/`android/` and `expo run:ios` needs a real iPhone (the simulator has no Bluetooth).

**Learn it.**

| Resource | Type | Time | Why this one |
|---|---|---|---|
| [react-native-ble-plx (dotintent) on GitHub](https://github.com/dotintent/react-native-ble-plx) | code + wiki | 1 h | the exact API `RingClient.ts` calls: scanning, `requestMTU`, monitors, writes, `onDeviceDisconnected`; the wiki covers Expo config-plugin setup |
| [Expo: Development builds](https://docs.expo.dev/develop/development-builds/introduction/) | docs | 30 min | why the app is not Expo Go, what `prebuild` generates, how to run on a device |
| [Apple: Core Bluetooth documentation](https://developer.apple.com/documentation/corebluetooth) | docs | 1 h | `CBCentralManager`, `CBPeripheral`, `maximumWriteValueLength`, background modes; what ble-plx wraps on iOS |
| [Punch Through: Apple's iOS Core Bluetooth: The Ultimate Guide](https://punchthrough.com/core-bluetooth-guide/) | article | 1.5 h | the delegate flow, permissions, pitfalls and the MTU/interval facts iOS imposes |
| [Android Developers: Bluetooth Low Energy overview](https://developer.android.com/develop/connectivity/bluetooth/ble/ble-overview) | docs | 1 h | GATT client flow, permissions by API level, `requestMtu`, connection priority |
| [Punch Through: Android BLE: The Ultimate Guide to Bluetooth Low Energy](https://punchthrough.com/android-ble-guide/) | article | 2 h | scanning, connecting, bonding, threading and queuing on Android, updated for API 34 |
| [Punch Through: 4 Tips to Make Android BLE Actually Work](https://punchthrough.com/android-ble-development-tips/) | article | 20 min | the short list: queue operations, request MTU early, handle 133 errors, retry connects |

**Check yourself.**

1. `RingClient.connect()` computes `writeSize = maxWriteForMtu(Math.min(mtu, 515))`. Why the 515 cap, and what write size results on iOS and Android?
2. The app subscribes to Events, and older firmware without 0007 makes the monitor error once. Why is that harmless, and what GATT step produced the error?
3. On Android the app sends `SET_CONFIG` 9, 10, 11 back-to-back with `await`. What would happen if the three writes were fired without awaiting on a stack that does not queue?
4. You want "reconnect automatically when the ring wakes". Sketch the iOS-safe approach in two sentences.

<details><summary>Answers</summary>

1. ble-plx reports the ATT MTU; the largest ATT write-without-response value is MTU − 3, and 515 − 3 = 512 keeps the payload within a 512-byte attribute-value limit while still allowing 3 audio blocks (399 bytes). iOS: 185 − 3 = 182; Android: 512.
2. Service discovery found no characteristic with UUID 0007, so enabling notifications (the CCCD write) fails for that one monitor; `onEvent` logs "events unavailable" and the app continues without button events (phone-mic mode then falls back to the in-app button).
3. On Android only one GATT operation may be outstanding; a second `writeCharacteristic` before the first callback returns false or is silently dropped, so one or two settings would never reach the ring. ble-plx serialises internally, but `await` also preserves order and surfaces errors per key.
4. Keep scanning (or rescan on disconnect) filtered by the mcring service UUID and connect to the first match whose name starts with `mcring-`, since the ring's address is stable but a cached peripheral may be stale. Never rely on the phone's own address or on a bonded identity until the firmware implements bonding.

</details>
