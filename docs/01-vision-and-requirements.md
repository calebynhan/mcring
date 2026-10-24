# 1. Vision and requirements

## The idea

A ring, ideally the size of an Oura ring, with a pinhole camera. You point your hand at
something, trigger a shot (button, double-tap, touch), and a few seconds later you get an
answer about what you photographed: spoken aloud by your phone or earbuds, and tapped onto your
finger as Morse code so you can "read" it without looking or listening.

Example: walking in the woods, you see an unfamiliar flower. Tap the ring. Your earbuds say
"That's a foxglove, Digitalis purpurea. All parts are toxic." Your finger feels
`F O X G L O V E  T O X I C` in Morse.

## Functional requirements

| # | Requirement | Priority |
|---|---|---|
| F1 | Capture a still image on a trigger: button, double-tap (IMU), or touch | must |
| F2 | Transfer the image to a phone over Bluetooth LE within ~1–2 s | must |
| F3 | Ask a multimodal LLM (Claude by default, OpenAI optional) a question about the image | must |
| F4 | Deliver the answer as speech (phone TTS or earbuds) | must |
| F5 | Deliver a short answer as Morse code on the ring: haptic and/or light; audible beeps optional; "air puff" as an experimental aux channel | must (haptic/LED), stretch (puff) |
| F6 | Optional spoken question captured by a microphone on the ring | should |
| F7 | Follow-up questions about the last photo ("is it edible?") | should |
| F8 | Work with no phone in reach: queue captures and send on reconnect | should |
| F9 | Configurable Morse speed (Farnsworth), channels, trigger mode | should |

## Non-functional

| # | Requirement |
|---|---|
| N1 | Stage 0 must run on off-the-shelf parts with no custom PCB |
| N2 | Phone round-trip (trigger → Morse starts) under ~6 s on a normal connection |
| N3 | A ring-sized battery (16–40 mAh) must survive a day of moderate use (≥ 30 shots) at stage 1/2 |
| N4 | The image never leaves the user's phone + chosen LLM provider; no third-party storage |
| N5 | All protocol/codec logic shared across firmware, phone, desktop and backend with byte-identical outputs and cross-tests |

## Explicitly out of scope (for now)

Continuous video, on-ring AI inference, cellular connectivity on the ring, biometric sensing.

## Staged definition of done

* **Stage 0 (bench):** XIAO ESP32S3 Sense + breadboard parts. Button → photo → phone/desktop →
  Claude → speech + Morse on an LED and an LRA. *Everything in this repo targets this today.*
* **Stage 1 (wearable, oversized):** ~30 mm OD printed ring with a custom ESP32-S3 or nRF52840
  board, flat 30–40 mAh cell, camera pod, haptic, 1-day battery.
* **Stage 2 (Oura-size):** nRF52840 WLCSP / ISP1807 on rigid-flex, 16–24 mAh curved cell,
  OVM7692-class camera in a ~4–5 mm pod, haptic Morse. Research says feasible but hard
  (see `04-feasibility-and-risks.md`).
