"""Local Morse playback for testing without a ring: terminal flashes and optional beeps."""
from __future__ import annotations

import math
import struct
import sys
import time

from mcring_core import morse


def _tone(ms: int, freq: float = 700.0, sr: int = 22050) -> bytes:
    n = int(sr * ms / 1000)
    return struct.pack(f"<{n}h", *(int(12000 * math.sin(2 * math.pi * freq * i / sr)) for i in range(n)))


def play_units(units: list[int], unit_ms: int, beep: bool = False, label: str = "") -> None:
    """Blocking playback: prints a bar for ON, spaces for OFF; beeps if simpleaudio is available."""
    sa = None
    if beep:
        try:
            import simpleaudio  # type: ignore

            sa = simpleaudio
        except ImportError:
            print("(pip install simpleaudio for beeps)", file=sys.stderr)
    text = morse.to_text(units)
    print(f"▶ {label or text}  ({morse.pattern_units(units) * unit_ms / 1000:.1f}s)")
    for i, u in enumerate(units):
        ms = u * unit_ms
        on = i % 2 == 0
        if on:
            sys.stdout.write("█" * u)
            sys.stdout.flush()
            if sa:
                sa.play_buffer(_tone(ms), 1, 2, 22050)
        else:
            sys.stdout.write(" " * u)
            sys.stdout.flush()
        time.sleep(ms / 1000)
    print()
