"""The published /v1/ask JSON schemas (protocol/schemas/) must stay in step with the backend.

No new dependencies: `jsonschema` and `pydantic` are only used when they happen to be installed
(they are in the backend's environment); the structural checks always run.
"""
import ast
import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[3]
SCHEMAS = ROOT / "protocol" / "schemas"
BACKEND = ROOT / "backend"


def _load(name: str) -> dict:
    return json.loads((SCHEMAS / name).read_text())


@pytest.mark.parametrize("name", ["ask_request.schema.json", "ask_response.schema.json"])
def test_schema_is_well_formed(name):
    s = _load(name)
    assert s["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert s["type"] == "object"
    props = s["properties"]
    assert set(s.get("required", [])) <= set(props), "every required field must be declared"
    for d in s.get("$defs", {}).values():
        assert set(d.get("required", [])) <= set(d["properties"])
    jsonschema = pytest.importorskip("jsonschema")
    jsonschema.Draft202012Validator.check_schema(s)


def _form_fields_of_ask() -> set[str]:
    """Names of the Form(...) parameters of `async def ask(...)` in backend/app/main.py (no import needed)."""
    tree = ast.parse((BACKEND / "app" / "main.py").read_text())
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "ask":
            args = node.args
            names: set[str] = set()
            positional = args.posonlyargs + args.args
            defaults = [None] * (len(positional) - len(args.defaults)) + list(args.defaults)
            for a, d in list(zip(positional, defaults)) + list(zip(args.kwonlyargs, args.kw_defaults)):
                if isinstance(d, ast.Call) and getattr(d.func, "id", "") == "Form":
                    names.add(a.arg)
            return names
    raise AssertionError("backend/app/main.py has no ask()")


def test_request_schema_matches_backend_form_fields():
    s = _load("ask_request.schema.json")
    assert set(s["properties"]) == _form_fields_of_ask()
    assert s["properties"]["want_morse"]["default"] is False, "Morse is optional / off by default"
    assert "chat" in s["properties"]["mode"]["enum"]
    assert set(s["properties"]["speech_format"]["enum"]) == {"mp3", "adpcm16k", "both"}


def test_response_schema_matches_pydantic_model():
    pytest.importorskip("pydantic")
    sys.path.insert(0, str(BACKEND))
    try:
        from app.schemas import AskResponse  # backend/app/schemas.py imports only pydantic
    finally:
        sys.path.pop(0)
    model = AskResponse.model_json_schema()
    s = _load("ask_response.schema.json")
    assert set(s["properties"]) == set(model["properties"])
    assert set(s["required"]) == set(model["required"])
    assert "short" not in s["required"], "`short` is null unless want_morse=true"
    for name, d in model["$defs"].items():
        assert set(s["$defs"][name]["properties"]) == set(d["properties"]), name
        assert set(s["$defs"][name].get("required", [])) == set(d.get("required", [])), name


def test_response_schema_accepts_a_default_voice_turn():
    """A speech-only answer with no Morse (what /v1/ask returns by default) validates."""
    jsonschema = pytest.importorskip("jsonschema")
    s = _load("ask_response.schema.json")
    body = {
        "id": "0123456789ab", "session_id": "s1", "answer": "It is a foxglove.",
        "speech_text": "It is a foxglove. Want to know if it is toxic?", "follow_up": "Want to know if it is toxic?",
        "subject": "Digitalis purpurea", "confidence": 0.9, "warnings": ["toxic"], "mode": "identify", "had_image": True,
        "transcript": "what is this", "transcript_error": None,
        "speech": {"format": "mp3", "mime": "audio/mpeg", "audio_b64": "AAAA", "voice": "alloy"},
        "speech_adpcm": {"format": "adpcm16k", "mime": "audio/x-mcring-adpcm", "audio_b64": "AAAA", "voice": "alloy",
                         "sample_rate": 16000, "blocks": 3, "duration_ms": 48},
        "speech_error": None, "short": None, "morse": None,
        "provider": "anthropic", "model": "claude", "latency_ms": 1200,
        "usage": {"input_tokens": 10, "output_tokens": 20}, "fallback_model": None,
    }
    jsonschema.Draft202012Validator(s).validate(body)
    # the pre-pivot shape (non-null `short`, no speech fields) must now be rejected
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(s).validate({"id": "x", "answer": "a", "short": "A", "confidence": 1,
                                                     "provider": "p", "model": "m", "latency_ms": 1})
