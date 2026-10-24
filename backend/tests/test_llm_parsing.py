import pytest

from app import llm
from app.prompts import SYSTEM_PROMPT, user_question
from app.schemas import LLMAnswer


def test_parse_answer_plain_and_embedded():
    a = llm._parse_answer('{"answer":"x","subject":"","confidence":0.5,"warnings":[],"follow_up":""}')
    assert a.answer == "x" and a.follow_up == ""
    b = llm._parse_answer('Sure: {"answer":"x","subject":"s","confidence":1,"warnings":["w"],"follow_up":"More?"} done')
    assert b.warnings == ["w"] and b.follow_up == "More?"
    with pytest.raises(llm.ProviderError):
        llm._parse_answer("no json here")


def test_parse_answer_tolerates_missing_optional_and_out_of_range():
    a = llm._parse_answer('{"answer":"x","confidence":1.7}')
    assert a.confidence == 1.0 and a.subject == "" and a.warnings == [] and a.follow_up == ""
    b = llm._parse_answer('{"answer":"x","subject":null,"follow_up":null,"confidence":"0.3","warnings":[]}')
    assert b.subject == "" and b.follow_up == "" and b.confidence == 0.3


def test_schema_has_no_morse_field_and_no_numeric_bounds():
    props = llm.ANSWER_SCHEMA["properties"]
    assert "short" not in props
    assert set(llm.ANSWER_SCHEMA["required"]) == {"answer", "subject", "confidence", "warnings", "follow_up"}
    assert set(props) == set(llm.ANSWER_SCHEMA["required"])
    assert "minimum" not in props["confidence"] and "maximum" not in props["confidence"]
    assert llm.ANSWER_SCHEMA["additionalProperties"] is False
    # the pydantic model agrees with the wire schema
    assert set(LLMAnswer.model_fields) == set(props)


def test_prompt_is_voice_first():
    low = SYSTEM_PROMPT.lower()
    assert "read aloud" in low and "follow_up" in SYSTEM_PROMPT
    assert "morse" not in low and "`short`" not in SYSTEM_PROMPT


def test_speech_text_joins_follow_up():
    a = LLMAnswer(answer=" Red oak. ", follow_up=" Want the leaf shape? ")
    assert a.speech_text == "Red oak. Want the leaf shape?"
    assert LLMAnswer(answer="Red oak.").speech_text == "Red oak."


def test_user_question_modes():
    assert user_question("identify", "").startswith("What is this?")
    assert user_question("custom", "how many?") == "how many?"
    assert user_question("chat", "capital of France?") == "capital of France?"
    assert user_question("chat", "") == ""                       # caller rejects empty chat turns
    assert user_question("bogus", "") .startswith("What is this?")
    assert user_question("bogus", "hey") == "hey"
    q = user_question("read_text", "then translate", "de")
    assert "Read the text" in q and "then translate" in q and q.endswith("Answer in de.")
    assert "short" not in q


def test_history_blocks_trimmed():
    hist = [{"question": f"q{i}", "answer_json": "{}"} for i in range(10)]
    blocks = llm._history_blocks(hist)
    assert len(blocks) == 12 and blocks[0]["content"] == "q4"
