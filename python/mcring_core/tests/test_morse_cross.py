"""C firmware encoder must match the Python encoder byte-for-byte."""
import subprocess

import pytest

from mcring_core import morse

CASES = [
    ("SOS", 15, 0),
    ("FOXGLOVE TOXIC", 15, 8),
    ("? digitalis purpurea", 18, 6),
    ("  hello,   world! 123 ", 20, 0),
    ("the quick brown fox jumps over the lazy dog 0123456789", 25, 10),
    ("", 15, 0),
    ("###", 15, 0),
    ("a@b.c $5 (x) \"q\" _-+=:;/", 12, 0),
]


@pytest.mark.parametrize("text,cw,ow", CASES)
def test_c_matches_python(c_tool, text, cw, ow):
    sp = morse.Spacing.farnsworth(cw, ow) if ow else morse.Spacing()
    py_units, py_trunc = morse.encode(text, sp)
    res = subprocess.run([str(c_tool), str(cw), str(ow), text], capture_output=True, text=True, check=True)
    line, trunc = res.stdout.split("\n")[:2]
    c_units = [int(x) for x in line.split(",")] if line else []
    assert c_units == py_units
    assert int(trunc) == int(py_trunc)
