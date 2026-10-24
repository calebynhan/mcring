from mcring_core import morse


def test_sos_standard():
    units, trunc = morse.encode("SOS")
    assert units == [1, 1, 1, 1, 1, 3, 3, 1, 3, 1, 3, 3, 1, 1, 1, 1, 1]
    assert not trunc


def test_word_gap_and_case_fold():
    a, _ = morse.encode("e e")
    assert a == [1, 7, 1]
    b, _ = morse.encode("E   E")
    assert a == b
    assert morse.encode("  E")[0] == [1]  # leading whitespace ignored
    assert morse.encode("E  ")[0] == [1]  # trailing whitespace ignored


def test_unknown_dropped_and_accents_folded():
    assert morse.encode("é")[0] == morse.encode("E")[0]
    assert morse.encode("E#E")[0] == [1, 3, 1]
    assert morse.encode("日本")[0] == []


def test_truncation_is_whole_characters():
    units, trunc = morse.encode("SOS", max_out=8)
    assert trunc
    assert units == [1, 1, 1, 1, 1]  # S only; O would need 3+5=8 more


def test_farnsworth_gaps_longer():
    std = morse.Spacing()
    fw = morse.Spacing.farnsworth(15, 8)
    assert fw.dot == 1 and fw.dash == 3 and fw.intra_gap == 1
    assert fw.char_gap > std.char_gap and fw.word_gap > std.word_gap
    assert morse.Spacing.farnsworth(10, 15) == std  # overall >= char -> standard


def test_unit_ms_and_duration():
    assert morse.unit_ms(15) == 80
    assert morse.unit_ms(20) == 60
    units, _ = morse.encode("E")
    assert morse.duration_ms(units, 15) == 80


def test_roundtrip_to_text():
    sp = morse.Spacing.farnsworth(15, 8)
    units, _ = morse.encode("FOXGLOVE TOXIC", sp)
    assert morse.to_text(units, sp) == "FOXGLOVE TOXIC"


def test_shorten_for_morse():
    assert morse.shorten_for_morse("This is a Foxglove, toxic!") == "THIS IS A FOXGLOVE TOXIC"
    assert morse.shorten_for_morse("Digitalis purpurea (foxglove) - toxic", 20) == "DIGITALIS PURPUREA"
    assert morse.shorten_for_morse("? maybe", 10) == "? MAYBE"
    assert len(morse.shorten_for_morse("A" * 100, 32)) == 32


def test_prosigns():
    assert morse.encode_prosign("SN") == [1, 1, 1, 1, 1, 1, 3, 1, 1]
