# Morse output spec (optional / legacy "silent pattern" mode)

> **Status: optional, off by default.** mcring is voice-first: answers are spoken to the user
> through the phone (and their own Bluetooth headphones) or, on the stage-1 ring, an on-ring
> speaker — see `ble-gatt.md`. The Morse path below is kept as a *silent pattern* capability
> for situations where audio is impossible (quiet room, hearing impairment, discreet use). The
> codecs (`python/mcring_core/mcring_core/morse.py`, `firmware/.../lib/mcring_morse`) and the
> `MORSE_TEXT` / `MORSE_UNITS` feedback opcodes still work and are still cross-tested, but
> nothing in the default app flow or the default LLM prompt produces Morse any more. Haptics
> in the default UX are only the short cues listed in `ble-gatt.md` (`CUE` opcode).

When enabled, mcring delivers short answers as International (ITU) Morse code on one or more
physical channels: LED (light), haptic (vibration), buzzer (sound), or an auxiliary channel
(reserved for an air-puff / thermal actuator if one is ever fitted).

## Timing

PARIS standard: one *unit* = `1200 / wpm` ms.

| Element | ON/OFF | Units |
|---------|--------|------:|
| dot | on | 1 |
| dash | on | 3 |
| gap inside a character | off | 1 |
| gap between characters | off | 3 |
| gap between words | off | 7 |

**Farnsworth** spacing (recommended for haptics): characters are sent at `char_wpm` (e.g. 18),
but gaps between characters and words are stretched to an effective `overall_wpm` (e.g. 8).
Haptic Morse is much easier to read with a fast character and long gaps. The sender
(phone / backend) does the stretching and ships a `MORSE_UNITS` pattern, or ships
`MORSE_TEXT` and lets the ring use its default spacing.

Default profile: `char_wpm = 15`, `overall_wpm = 8`, haptic + LED.

## Alphabet

A–Z, 0–9 and `. , ? ' ! / ( ) & : ; = + - _ " $ @` per ITU-R M.1677-1. Lower-case is
upper-cased. Unknown characters are dropped. Accented Latin letters are folded to ASCII
(é→E). Non-Latin scripts are dropped.

Prosigns used by mcring:

| Prosign | Meaning | Code |
|---------|---------|------|
| `<AR>` | end of message | `.-.-.` |
| `<SN>` | understood / ready | `...-.` |
| `<HH>` | error | `........` |
| `<BT>` | break / new section | `-...-` |

Legacy firmware played `<SN>` when a capture succeeded and `<HH>` on failure; the voice-first
firmware uses the shorter non-Morse cues instead (`feedback_signal_*` remain available).

## Short-answer rules (only when Morse mode is enabled)

When the app has Morse mode on, the LLM is asked for two answers: a spoken/long one and a
Morse-friendly `short` one:

* ≤ 6 words, ≤ 32 characters, upper-case A–Z 0–9 and spaces only.
* Nouns first, no articles, no filler ("FOXGLOVE TOXIC" not "This is a foxglove, which is toxic").
* Numbers as digits.
* Standard Morse abbreviations are allowed: `R`=received/yes, `N`=no, `?`=unknown, `TU`=thank you,
  `WX`=weather, `NR`=number.
* Confidence ≤ 60 % → prefix `?` (e.g. `? FOXGLOVE`).

At 15/8 WPM Farnsworth, "FOXGLOVE TOXIC" takes ≈ 11 s on the wrist; "? FOXGLOVE" ≈ 8 s.

## Wire pattern format

A pattern is an array of bytes, alternating ON, OFF, ON, OFF… durations **in units**,
always starting with ON. A trailing OFF is omitted. Example `"SOS"` at tight spacing:

```
S: 1 1 1 1 1          ... (dot gap dot gap dot)
   3                  letter gap
O: 3 1 3 1 3
   3
S: 1 1 1 1 1
→ [1,1,1,1,1,3,3,1,3,1,3,3,1,1,1,1,1]
```

The reference encoder lives in `python/mcring_core/mcring_core/morse.py` and
`firmware/ring-esp32s3/lib/mcring_morse/`. Both must produce byte-identical output for the
same text and spacing; `python/mcring_core/tests/test_morse_cross.py` checks this against the C
implementation.
