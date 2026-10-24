"""Turn an LLM short answer into a Morse pattern + ready-to-send ring packet."""
from __future__ import annotations

import base64

from mcring_core import morse, proto

from .schemas import MorseOut


def build_morse(text: str, char_wpm: int = 15, overall_wpm: int = 8, channels: int = 3,
                max_chars: int = 32) -> MorseOut:
    char_wpm = max(5, min(40, char_wpm))
    overall_wpm = max(3, min(char_wpm, overall_wpm))
    clean = morse.shorten_for_morse(text, max_chars)
    spacing = morse.Spacing.farnsworth(char_wpm, overall_wpm) if overall_wpm < char_wpm else morse.Spacing()
    units, _ = morse.encode(clean, spacing, max_out=1024)
    unit_ms = morse.unit_ms(char_wpm)
    # One MORSE_UNITS packet (the companion may re-split per its MTU; the first write carries the header).
    writes = proto.fb_morse_units(units, unit_ms, channels, max_write=65535) if units else [b""]
    return MorseOut(
        text=clean,
        unit_ms=unit_ms,
        units=units,
        duration_ms=morse.pattern_units(units) * unit_ms,
        ring_packet_b64=base64.b64encode(writes[0]).decode(),
        char_wpm=char_wpm,
        overall_wpm=overall_wpm,
    )
