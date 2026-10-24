"""ITU Morse encoder producing alternating ON/OFF unit durations.

Must stay byte-identical to firmware/ring-esp32s3/lib/mcring_morse/mcring_morse.c.
"""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass

CODES: dict[str, str] = {
    "A": ".-", "B": "-...", "C": "-.-.", "D": "-..", "E": ".", "F": "..-.", "G": "--.",
    "H": "....", "I": "..", "J": ".---", "K": "-.-", "L": ".-..", "M": "--", "N": "-.",
    "O": "---", "P": ".--.", "Q": "--.-", "R": ".-.", "S": "...", "T": "-", "U": "..-",
    "V": "...-", "W": ".--", "X": "-..-", "Y": "-.--", "Z": "--..",
    "0": "-----", "1": ".----", "2": "..---", "3": "...--", "4": "....-",
    "5": ".....", "6": "-....", "7": "--...", "8": "---..", "9": "----.",
    ".": ".-.-.-", ",": "--..--", "?": "..--..", "'": ".----.", "!": "-.-.--",
    "/": "-..-.", "(": "-.--.", ")": "-.--.-", "&": ".-...", ":": "---...",
    ";": "-.-.-.", "=": "-...-", "+": ".-.-.", "-": "-....-", "_": "..--.-",
    '"': ".-..-.", "$": "...-..-", "@": ".--.-.",
}

PROSIGNS = {"AR": ".-.-.", "SN": "...-.", "HH": "........", "BT": "-...-", "SK": "...-.-"}


@dataclass(frozen=True)
class Spacing:
    dot: int = 1
    dash: int = 3
    intra_gap: int = 1
    char_gap: int = 3
    word_gap: int = 7

    @classmethod
    def farnsworth(cls, char_wpm: int, overall_wpm: int) -> "Spacing":
        """Characters at char_wpm, overall rhythm at overall_wpm (ARRL formula).

        Mirrors mc_morse_spacing_farnsworth() in C, including rounding.
        """
        if char_wpm <= 0 or overall_wpm <= 0 or overall_wpm >= char_wpm:
            return cls()
        c, o = float(char_wpm), float(overall_wpm)
        unit_s = 1.2 / c
        extra_s = (60.0 * c - 37.2 * o) / (o * c)
        extra_units = extra_s / unit_s
        f = 1.0 + extra_units / 19.0
        cg = int(3.0 * f + 0.5)
        wg = int(7.0 * f + 0.5)
        return cls(char_gap=min(255, max(3, cg)), word_gap=min(255, max(7, wg)))


def unit_ms(wpm: int) -> int:
    """PARIS standard unit length in ms (integer division, like the C code)."""
    return 1200 // wpm if wpm else 80


def fold_ascii(text: str) -> str:
    """Fold accented Latin letters to ASCII (é→e); drop other non-ASCII."""
    out = []
    for ch in unicodedata.normalize("NFKD", text):
        if ord(ch) < 128:
            out.append(ch)
    return "".join(out)


def code_for(ch: str) -> str | None:
    return CODES.get(ch.upper())


def encode(text: str, spacing: Spacing | None = None, max_out: int = 65535) -> tuple[list[int], bool]:
    """Encode text to alternating ON/OFF unit durations (starts with ON, no trailing OFF).

    Returns (units, truncated). Unknown characters are dropped; whitespace runs become one
    word gap. Behaviour is identical to mc_morse_encode() in C.
    """
    sp = spacing or Spacing()
    text = fold_ascii(text)
    out: list[int] = []
    have_char = False
    pending_word_gap = False
    truncated = False
    for ch in text:
        if ch.isspace():
            if have_char:
                pending_word_gap = True
            continue
        code = code_for(ch)
        if code is None:
            continue
        need = (1 if have_char else 0) + len(code) + (len(code) - 1)
        if len(out) + need > max_out:
            truncated = True
            break
        if have_char:
            out.append(sp.word_gap if pending_word_gap else sp.char_gap)
        pending_word_gap = False
        for i, el in enumerate(code):
            if i:
                out.append(sp.intra_gap)
            out.append(sp.dash if el == "-" else sp.dot)
        have_char = True
    return out, truncated


def encode_prosign(name: str, spacing: Spacing | None = None) -> list[int]:
    sp = spacing or Spacing()
    code = PROSIGNS[name.upper()]
    out: list[int] = []
    for i, el in enumerate(code):
        if i:
            out.append(sp.intra_gap)
        out.append(sp.dash if el == "-" else sp.dot)
    return out


def pattern_units(units: list[int]) -> int:
    return sum(units)


def duration_ms(units: list[int], wpm: int) -> int:
    return pattern_units(units) * unit_ms(wpm)


def to_timeline(units: list[int], unit_ms_: int) -> list[tuple[bool, int]]:
    """[(on?, ms), ...] for players/visualisers."""
    return [((i % 2 == 0), u * unit_ms_) for i, u in enumerate(units)]


def to_text(units: list[int], spacing: Spacing | None = None) -> str:
    """Debug helper: render a unit pattern back to dots/dashes using the given spacing."""
    sp = spacing or Spacing()
    rev = {v: k for k, v in CODES.items()}
    words: list[str] = []
    cur_word: list[str] = []
    cur_char = ""
    for i, u in enumerate(units):
        if i % 2 == 0:
            cur_char += "-" if u >= sp.dash else "."
        else:
            if u >= sp.word_gap:
                cur_word.append(rev.get(cur_char, "#"))
                words.append("".join(cur_word))
                cur_word, cur_char = [], ""
            elif u >= sp.char_gap:
                cur_word.append(rev.get(cur_char, "#"))
                cur_char = ""
    if cur_char:
        cur_word.append(rev.get(cur_char, "#"))
    if cur_word:
        words.append("".join(cur_word))
    return " ".join(words)


def shorten_for_morse(text: str, max_chars: int = 32) -> str:
    """Normalise an LLM 'short' answer: upper-case, A-Z 0-9 space ? only, ≤ max_chars."""
    t = fold_ascii(text).upper()
    keep = []
    for ch in t:
        if ch.isalnum() or ch in " ?":
            keep.append(ch)
        elif ch in "-_/,.;:":
            keep.append(" ")
    s = " ".join("".join(keep).split())
    if len(s) <= max_chars:
        return s
    words = s.split()
    out: list[str] = []
    for w in words:
        cand = " ".join(out + [w])
        if len(cand) > max_chars:
            break
        out.append(w)
    return " ".join(out) if out else s[:max_chars].rstrip()
