# 1. Vision and requirements

## The idea

A ring, ideally the size of an Oura ring, that you can talk to. You hold its button (or
double-tap it), ask a question out loud, and a few seconds later Claude answers in your own
Bluetooth headphones. The ring has a pinhole camera, so the question can be about whatever your
hand is pointing at — "what is this flower?", "read me this label", "what does this sign say?" —
but it does not have to be: "what's the capital of Mongolia?" works just as well with no photo.
The ring itself only confirms with short haptic ticks; the phone does speech, internet and AI.

Example: walking in the woods you see an unfamiliar flower. Hold the ring and ask "what's this?".
Your earbuds say: "That's a foxglove, Digitalis purpurea. Every part of it is toxic, so don't
touch your mouth after handling it. Want to know what it's used for?" You say "yes" and the
conversation continues about the same plant.

**Audio topology.** ring ↔ phone over BLE; phone ↔ the user's own Bluetooth headphones through
the phone's normal audio routing (the ring never pairs to headphones — ESP32-S3/nRF52 have no
Classic-Bluetooth A2DP/HFP and no battery for it); phone ↔ backend ↔ Claude. Two audio inputs,
selectable in the app: the ring's mic (PDM → ADPCM over BLE) or the headset/phone mic (the phone
records while the ring button is held). Two audio outputs: phone → headphones (default) or, on
the oversized stage-1 ring only, an on-ring speaker fed by the phone over BLE.

## Functional requirements

IDs are stable so that `docs/07-build-guide.md` §5 (per-stage acceptance checklist) keeps
pointing at the right rows; **F5 changed meaning** in the voice-first pivot (ring output is now
*cues*, Morse is optional) and F10–F13 are new.

| # | Requirement | Priority |
|---|---|---|
| **Voice loop** | | |
| F6 | Ask by voice with the ring's own microphone: hold the button (or double-tap) → the ring records (≤ 8 s, 16 kHz ADPCM) and sends the clip over BLE | must |
| F10 | Ask by voice with the headset/phone microphone: the ring reports `BUTTON_DOWN` / `BUTTON_UP` (and `DOUBLE_TAP`) events so the phone can record for exactly as long as the button is held | must |
| F4 | Deliver the answer as speech through the phone's audio output — i.e. the user's Bluetooth headphones or the phone speaker — via on-device TTS or server TTS (mp3) | must |
| F3 | Ask a multimodal LLM (Claude by default, OpenAI optional) and get a read-aloud answer (1–3 sentences, optional follow-up offer), with or without a photo | must |
| F11 | Voice-only turns: a question with no photo is answered as plain chat; a photo already in the session stays referenced for follow-ups | must |
| F7 | Follow-up questions in the same session ("is it edible?") about the last photo / previous answers | must |
| **Camera as context** | | |
| F1 | Capture a still image on a trigger: short button press, touch, phone request, or automatically at the start of a ring-mic "ask" | must |
| F2 | Transfer the image (and the voice clip) to the phone over BLE within ~1–2 s, reliably (CRC + selective retransmit) | must |
| **Ring outputs** | | |
| F5 | Confirmation cues on the ring: *listening* (1 tick), *answer ready* (2 ticks), *error* (long buzz) on haptic and/or LED, beep optional; selectable with `CUES_MASK`. Morse "silent pattern" output stays available but **off by default** (see appendix) | must (cues) / optional (Morse) |
| F12 | On-ring speaker (stage-1 oversized ring): the phone streams the answer as 16 kHz mono mcring-ADPCM over the `AUDIO_OUT` characteristic; the ring buffers ≥ 24 blocks (~400 ms), decodes and plays over I2S (MAX98357A + 10 mm speaker), reporting `AUDIO_UNDERRUN` / `AUDIO_DONE` | should (stage 1) |
| **Platform** | | |
| F8 | Work with no phone in reach: queue captures/clips and send on reconnect | should |
| F9 | Configurable from the app and persisted on the ring: trigger mask, mic source hint, speaker volume, cues mask, image quality/size, idle sleep | should |
| F13 | Audio source and sink selectable in the companion: *Ring mic* / *Phone-headset mic*; *Phone voice* / *Server voice*; *Ring speaker* on/off (only offered when the ring reports `SPEAKER_OK`) | should |

## Non-functional

| # | Requirement |
|---|---|
| N1 | Stage 0 must run on off-the-shelf parts with no custom PCB |
| N2 | Round trip from releasing the button to the first spoken word under ~6 s on a normal connection (BLE clip transfer ≤ 1 s, STT + LLM + TTS ≤ 5 s) |
| N3 | A ring-sized battery (16–40 mAh) must survive a day of moderate use (≥ 30 questions) at stage 1/2; the speaker is a stage-1 option that is allowed to cost battery |
| N4 | Audio and images go only to the providers the user configures (Claude for answers; OpenAI or a local faster-whisper for speech-to-text, OpenAI for optional server TTS); no other third-party storage. Backend sessions are in-memory with a 30-minute TTL |
| N5 | All protocol/codec logic shared across firmware, phone, desktop and backend with byte-identical outputs and cross-tests |
| N6 | The ring never needs to pair with anything but the phone; headphones are the phone's business |
| N7 | The ring must stay usable with the phone's mic/speaker alone — no ring mic or speaker is required for the core loop (F10 + F4) |

## Explicitly out of scope (for now)

Continuous video, always-on listening / wake word, on-ring AI inference, cellular connectivity on
the ring, biometric sensing, Classic-Bluetooth audio from the ring. Projection from the ring is a
**v2 idea**, analysed in `08-projection-v2.md` and tracked on the roadmap — not a v1 requirement.

## Staged definition of done

* **Stage 0 (bench):** XIAO ESP32S3 Sense + breadboard parts. Hold the button → ask → the laptop
  CLI or the phone app transcribes, asks Claude and speaks the answer in headphones; LED + LRA
  cues; optional MAX98357A + speaker on the bench to prove the `AUDIO_OUT` path. *Everything in
  this repo targets this today.*
* **Stage 1 (wearable, oversized):** ~30 mm OD printed ring with a custom ESP32-S3 or nRF52840
  board, flat 30–40 mAh cell, camera pod, PDM mic port, haptic, optional 10 mm speaker + I2S amp,
  1-day battery.
* **Stage 2 (Oura-size):** nRF52840 WLCSP / ISP1807 on rigid-flex, 16–24 mAh curved cell,
  OVM7692-class camera in a ~4–5 mm pod, mic + haptic cues, **no speaker** — answers come from
  the phone/headphones only. Research says feasible but hard (see `04-feasibility-and-risks.md`).

## Acceptance criteria (voice loop)

Testable statements behind the must/should rows above; the per-stage hardware checklist with
evidence columns lives in `07-build-guide.md` §5.

| Req | Pass criterion |
|---|---|
| F6 | Holding the ring button ≥ 0.7 s yields `REC_STARTED`, then on release `BUTTON_UP(held)` and `REC_STOPPED(tenths > 0)` followed by an `ADPCM` transfer whose length matches the held time ± 0.3 s; the backend's `transcript` contains the spoken words |
| F10 | With `MIC_SOURCE_HINT = 1`, `BUTTON_DOWN` arrives before the user finishes the first word and `BUTTON_UP.arg` equals the held time in tenths ± 1; the phone recording (`.m4a`) transcribes correctly 4 times out of 5 |
| F4 | With Bluetooth headphones paired to the phone and nothing configured on the ring, the answer is heard in the headphones; with none paired, on the phone speaker |
| F3 / F11 | A spoken question with no photo returns `mode = "chat"`, `had_image = false`, and a `speech_text` of 1–3 sentences without lists or markup; the same question with a photo returns `had_image = true` and a `subject` |
| F7 | A follow-up in the same `session_id` with no new image answers about the earlier photo |
| F1 / F2 | Short press, touch and the app's *Take photo* each produce `CAPTURE_STARTED`, `CAPTURE_DONE(queued ≥ 1)` and a complete JPEG at the companion; a 15 KB JPEG arrives in < 1 s on a laptop / Android, < 2 s on iPhone |
| F5 | The listening tick is felt within ~100 ms of the press crossing 0.7 s; the double tick arrives with the answer; a backend/provider error produces the long buzz; `CUES_MASK = 2` moves all three to the LED only; with default settings no Morse is ever played |
| F12 | A 10 s answer streamed as `adpcm16k` plays on the ring speaker end to end with ≤ 1 `AUDIO_UNDERRUN` at MTU 185 and 0 at MTU 517, ends with `AUDIO_DONE(0)`; `AUDIO_STOP` silences it within 100 ms and yields `AUDIO_DONE(1)`; on a board without speaker pins `AUDIO_START` answers `AUDIO_DONE(1)` and the status flag `SPEAKER_OK` is clear |
| F8 | Three asks made while disconnected are delivered on reconnect in order (`flags.bit5`, `queued`) |
| F9 / F13 | `SET_CONFIG` keys 9–11 written from Settings survive a ring reset; the app offers *Ring speaker* only when `SPEAKER_OK` is set |
| N2 | Button release → first spoken word < 6 s on five consecutive turns (stopwatch; log `latency_ms`) |

## Appendix: the optional silent pattern (Morse)

The project began as a haptic-Morse ring and that output is preserved as a capability, not a
feature: the ITU Morse encoder, the ring's pattern player and the `MORSE_TEXT` / `MORSE_UNITS`
feedback opcodes still work and are still cross-tested, but the default app flow, the default LLM
prompt and the default CLI produce no Morse. Request it explicitly (`want_morse=true` on
`/v1/ask`, `--morse` in the CLI) for situations where audio is impossible — a silent room, a
hearing impairment, discreet use. Specification: `protocol/morse.md`.
