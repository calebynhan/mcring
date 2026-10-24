"""mcring backend — FastAPI.

POST /v1/ask        multipart: image (+ optional audio) + fields  → answer, short, morse, speech
POST /v1/morse      text → morse pattern + ring packet (no LLM)
GET  /v1/health
"""
from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Annotated

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse

from mcring_core import adpcm as adpcm_codec

from . import images
from .config import Settings, get_settings
from .llm import ModelRefused, ProviderError, get_provider
from .morse_service import build_morse
from .prompts import user_question
from .schemas import AskResponse, HealthResponse, LLMAnswer, MorseOut, MorseRequest, Usage
from .sessions import SessionStore
from .tts import synthesize, transcribe

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("mcring.api")

app = FastAPI(title="mcring backend", version="0.1.0")
sessions = SessionStore()


def require_token(settings: Annotated[Settings, Depends(get_settings)],
                  authorization: Annotated[str | None, Header()] = None) -> None:
    if not settings.api_token:
        return
    if authorization != f"Bearer {settings.api_token}":
        raise HTTPException(status_code=401, detail="invalid or missing API token")


@app.exception_handler(ProviderError)
async def provider_error_handler(_: Request, exc: ProviderError):
    return JSONResponse(status_code=exc.status, content={"detail": str(exc), "retryable": exc.retryable})


@app.get("/v1/health", response_model=HealthResponse)
def health(settings: Annotated[Settings, Depends(get_settings)]):
    model = settings.anthropic_model if settings.provider == "anthropic" else settings.openai_model
    return HealthResponse(status="ok", provider=settings.provider, model=model, tts=settings.tts_provider)


@app.post("/v1/morse", response_model=MorseOut, dependencies=[Depends(require_token)])
def morse_endpoint(req: MorseRequest):
    return build_morse(req.text, req.char_wpm, req.overall_wpm, req.channels)


@app.post("/v1/ask", response_model=AskResponse, dependencies=[Depends(require_token)])
async def ask(
    settings: Annotated[Settings, Depends(get_settings)],
    image: UploadFile | None = File(default=None),
    audio: UploadFile | None = File(default=None),
    question: str = Form(default=""),
    mode: str = Form(default="identify"),
    provider: str = Form(default=""),
    session_id: str = Form(default=""),
    want_morse: bool = Form(default=True),
    want_speech: bool = Form(default=False),
    morse_char_wpm: int = Form(default=15),
    morse_overall_wpm: int = Form(default=8),
    morse_channels: int = Form(default=3),
    max_short_chars: int = Form(default=32),
    language: str = Form(default="en"),
):
    t0 = time.time()
    sess = sessions.get_or_create(session_id or None)

    # ---- image --------------------------------------------------------------
    if image is not None:
        raw = await image.read()
        if len(raw) > settings.max_upload_bytes:
            raise HTTPException(413, "image too large")
        try:
            img_bytes, media_type, _ = images.normalise(raw, settings.max_image_edge)
        except ValueError as e:
            raise HTTPException(400, str(e)) from e
        new_image = True
    elif sess.last_image is not None:
        img_bytes, media_type, new_image = sess.last_image, sess.last_media_type, False
    else:
        raise HTTPException(400, "an image is required (or a session_id with a previous image)")

    # ---- voice question -------------------------------------------------------
    transcript = None
    if audio is not None:
        a = await audio.read()
        fname = audio.filename or "voice.bin"
        if fname.endswith(".adpcm") or (audio.content_type or "") == "audio/x-mcring-adpcm":
            a, fname = adpcm_codec.adpcm_to_wav(a, 16000), "voice.wav"
        try:
            transcript = transcribe(a, fname, settings)
        except Exception as e:  # noqa: BLE001
            log.warning("transcription failed: %s", e)
        if transcript:
            question = f"{question} {transcript}".strip()

    q_text = user_question(mode, question, language)
    if not new_image:
        q_text = f"(About the previous photo.) {q_text}"

    # ---- model ------------------------------------------------------------------
    prov = get_provider(provider, settings)
    try:
        result = prov.ask(img_bytes, media_type, q_text, sess.turns)
    except ModelRefused:
        answer = LLMAnswer(answer="I can't help with that one.", short="? NO ANSWER", subject="", confidence=0.0, warnings=[])
        result = None
    if result is not None:
        answer = result.answer

    sessions.record(sess, q_text, answer.model_dump_json(), img_bytes if new_image else None, media_type)

    morse_out = build_morse(answer.short, morse_char_wpm, morse_overall_wpm, morse_channels, max_short_chars) if want_morse else None
    speech = None
    if want_speech:
        try:
            speech = synthesize(answer.answer, settings)
        except Exception as e:  # noqa: BLE001
            log.warning("tts failed: %s", e)

    return AskResponse(
        id=uuid.uuid4().hex[:12],
        session_id=sess.id,
        answer=answer.answer,
        short=morse_out.text if morse_out else answer.short,
        subject=answer.subject,
        confidence=answer.confidence,
        warnings=answer.warnings,
        morse=morse_out,
        speech=speech,
        transcript=transcript,
        provider=result.provider if result else settings.provider,
        model=result.model if result else "",
        latency_ms=int((time.time() - t0) * 1000),
        usage=Usage(input_tokens=result.input_tokens, output_tokens=result.output_tokens) if result else Usage(),
        fallback_model=result.fallback_model if result else None,
    )


@app.get("/")
def root():
    return {"service": "mcring backend", "docs": "/docs", "schemas": "/protocol/schemas"}
