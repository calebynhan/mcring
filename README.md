# mcring — a camera ring that answers questions in speech and Morse

Point your hand at something, tap the ring, and a few seconds later your phone speaks the
answer while your finger feels it in Morse code. This repository is the complete plan and
the complete software for building it, in three hardware stages:

| Stage | Form factor | Brain | Status |
|---|---|---|---|
| **0 — bench** | Seeed XIAO ESP32S3 Sense + breadboard | ESP32-S3 | **software complete, ready to flash** |
| **1 — oversized ring** | 30 mm OD printed ring, custom board, 30–40 mAh | ESP32-S3-MINI-1U (or nRF52840) | BOM, schematic notes, enclosure model, same firmware |
| **2 — Oura-size** | 8 mm band ≤ 3 mm + 4–5 mm camera pod, 16–24 mAh curved cell | nRF52840 WLCSP / ISP1807 | research-backed spec, Zephyr skeleton with stubbed camera |

```
ring ──BLE──▶ phone app / desktop CLI ──HTTPS──▶ backend ──▶ Claude (or OpenAI)
 ▲                                                   │
 └──────────── Morse pattern (LED · haptic · beep) ◀─┘ + spoken answer via phone/earbuds
```

## What's in the box

| Path | Contents |
|---|---|
| `docs/` | vision & requirements, architecture, **hardware spec**, **feasibility & risks**, roadmap, getting started; `docs/research/` three deep sourcing reports (cameras · MCU/radio/power · actuators/triggers) |
| `protocol/` | BLE GATT spec, Morse timing spec, packet layouts, JSON schemas |
| `firmware/ring-esp32s3/` | PlatformIO firmware (stage 0/1): capture, reliable chunked transfer, button/double-tap/touch triggers, Morse player on LED/haptic/buzzer/aux, voice clip (ADPCM), deep sleep |
| `firmware/ring-nrf52840/` | Zephyr skeleton (stage 2): same GATT service/transfer/feedback, camera HAL stub |
| `python/mcring_core/` | shared codecs (packets, CRC, Morse, ADPCM) — cross-tested byte-for-byte against the C libs |
| `backend/` | FastAPI: image + question → Claude Opus 5.5 (structured JSON, refusal fallbacks) → spoken answer + Morse units + ring packet (+ optional TTS); sessions for follow-ups |
| `app/` | React Native / Expo companion: BLE, reassembly, TTS, Morse write-back, settings |
| `tools/ring-cli/` | Python desktop companion (bleak) + no-hardware `mcring ask photo.jpg` |
| `hardware/` | BOMs with sources for all three stages, pin maps, schematic notes, power budget, Mermaid diagrams, OpenSCAD enclosure |

## Quick start (no hardware)

```bash
pip install -r backend/requirements.txt -e tools/ring-cli
export ANTHROPIC_API_KEY=sk-ant-...
(cd backend && uvicorn app.main:app --port 8000 &)
mcring ask your-photo.jpg -q "what is this?" --speak --beep
```

Full instructions: `docs/06-getting-started.md`. Flash the ring: `firmware/ring-esp32s3/README.md`.

## Key engineering conclusions (details in `docs/03` and `docs/04`)

1. **Battery and peak current, not chip size, decide the ring.** Real rings carry 16–22 mAh
   at ~1C; an ESP32-S3 camera board peaks at 300+ mA. ESP32-S3 is the right stage-0/1 part
   and the wrong stage-2 part; nRF52840-class is the stage-2 part.
2. **No digital camera a hobbyist can buy fits inside a 3 mm band.** The best stage-2 option
   is the OmniVision OVM7692 (2.8 × 3.2 × 2.6 mm, DVP, in stock) in a ~4–5 mm pod. The famous
   0.65 mm OVM6948 is analog and needs a 6 × 6 mm bridge chip — skip it.
3. **Haptic Morse is the one output that works at every size.** Speech from the ring is not
   realistic; the phone speaks. **Air puff** is possible only as a 20 × 20 mm signet experiment
   on the stage-1 ring (Murata MZB1001T02); it is physically out at Oura size.
4. **Keep images ≤ 30 KB** so the BLE leg stays under ~1 s on iPhone (~350 kbps) — QVGA JPEG
   or 160×120 grayscale is plenty for identification.

## Test status

| Suite | Result |
|---|---|
| `python/mcring_core` (codecs + C cross-check) | 29 passed |
| `backend` | 13 passed (providers mocked) |
| `tools/ring-cli` | 3 passed |
| `app` jest + `tsc --noEmit` | 16 passed, typecheck clean |
| `firmware/ring-esp32s3` | C libraries compiled & tested on host; application syntax-checked against API stubs — **not yet compiled with the ESP32 toolchain** (network-restricted build sandbox); run `pio run` locally |
| `firmware/ring-nrf52840` | reviewed, uncompiled skeleton |

## License

MIT — see `LICENSE`.
