import pytest

from app import llm
from app.prompts import user_question


def test_parse_answer_plain_and_embedded():
    a = llm._parse_answer('{"answer":"x","short":"X","subject":"","confidence":0.5,"warnings":[]}')
    assert a.short == "X"
    b = llm._parse_answer('Sure: {"answer":"x","short":"X","subject":"s","confidence":1,"warnings":["w"]} done')
    assert b.warnings == ["w"]
    with pytest.raises(llm.ProviderError):
        llm._parse_answer("no json here")


def test_user_question_modes():
    assert user_question("identify", "") .startswith("What is this?")
    assert user_question("custom", "how many?") == "how many?"
    q = user_question("read_text", "then translate", "de")
    assert "Read the text" in q and "then translate" in q and "Answer in de" in q


def test_history_blocks_trimmed():
    hist = [{"question": f"q{i}", "answer_json": "{}"} for i in range(10)]
    blocks = llm._history_blocks(hist)
    assert len(blocks) == 12 and blocks[0]["content"] == "q4"
