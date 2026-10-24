"""mcring backend — FastAPI. Voice-first: ask by voice (with or without a photo), hear the answer.

POST /v1/ask         multipart: question (text and/or audio) + optional image → answer (+ speech)
POST /v1/transcribe  multipart: audio → text (push-to-talk preview)
GET/POST /v1/speech  text → mp3 (phone/headphones) or 16 kHz mcring ADPCM (ring speaker)
POST /v1/morse       text → silent pattern + ring packet (optional feature, no LLM)
GET  /v1/health
"""
from __future__ import annotations

import logging
import time
import uuid
from typing import Annotated

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Query, Request, UploadFile
from fastapi.responses import JSONResponse, Response
from starlette.concurrency import run_in_threadpool

from . import images, stt, tts
from .config import Settings, get_settings
from .errors import ModelRefused, ProviderError
from .llm import get_provider
from .morse_service import build_morse, morse_text_for
from .prompts import PREVIOUS_PHOTO_NOTE, user_question
from .schemas import (ASK_SPEECH_FORMATS, MODES, SPEECH_FORMATS, AskResponse, HealthResponse, LLMAnswer,
                      MorseOut, MorseRequest, SpeechRequest, TranscribeResponse, Usage)
from .sessions import SessionStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("mcring.api")

VERSION = "0.2.0"
app = FastAPI(title="mcring backend", version=VERSION)
sessions = SessionStore()

REFUSAL_ANSWER = LLMAnswer(answer="I can't help with that one.", subject="", confidence=0.0, warnings=[], follow_up="")


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
    return HealthResponse(status="ok", version=VERSION, provider=settings.provider, model=model,
                          tts=settings.tts_provider, stt=settings.stt_provider, speech_default=settings.tts_enabled)


# ---------------------------------------------------------------------------
# /v1/ask — the main voice turn
# ---------------------------------------------------------------------------
# The STT, LLM and TTS clients are synchronous (blocking HTTP, or a local model). The handlers below
# are async so the multipart uploads stream without a worker thread, but every provider round trip
# goes through run_in_threadpool so one slow voice turn does not stall the event loop for everyone.
async def _read_upload(f: UploadFile | None, limit: int, what: str) -> bytes | None:
    if f is None:
        return None
    data = await f.read()
    if not data:
        return None
    if len(data) > limit:
        raise HTTPException(413, f"{what} too large")
    return data


def _answer(provider: str, settings: Settings, img: bytes | None, media_type: str | None, q_text: str, history: list[dict]):
    """Blocking: provider construction (first call only) + the model round trip. Run in the threadpool."""
    return get_provider(provider, settings).ask(img, media_type, q_text, history)


def _effective_mode(mode: str, question: str, has_image: bool, new_image: bool) -> str:
    """Which prompt template a turn gets.

    - no photo anywhere            -> chat      (the question is used verbatim)
    - follow-up about the session's photo, with a question
                                   -> custom    (answer the question itself; do not re-identify the photo)
    - a photo and nothing asked    -> identify  (whatever mode the client sent; chat/custom have no template)
    - otherwise                    -> the requested mode (new photo: identify/describe/read_text/translate/custom)
    """
    if not has_image:
        return "chat"
    if question and not new_image:
        return "custom"
    if not question and mode in ("chat", "custom"):
        return "identify"
    return mode


@app.post("/v1/ask", response_model=AskResponse, dependencies=[Depends(require_token)])
async def ask(
    settings: Annotated[Settings, Depends(get_settings)],
    image: UploadFile | None = File(default=None),
    audio: UploadFile | None = File(default=None),
    question: str = Form(default=""),
    mode: str = Form(default="identify"),
    provider: str = Form(default=""),
    session_id: str = Form(default=""),
    language: str = Form(default="en"),
    # speech out: default = server TTS when one is configured (else the phone speaks `speech_text` itself)
    want_speech: bool | None = Form(default=None),
    speech_format: str = Form(default="mp3"),          # mp3 | adpcm16k | both
    voice: str = Form(default=""),
    # optional silent pattern (off by default)
    want_morse: bool = Form(default=False),
    morse_char_wpm: int = Form(default=15),
    morse_overall_wpm: int = Form(default=8),
    morse_channels: int = Form(default=3),
    max_short_chars: int = Form(default=32),
):
    t0 = time.time()
    if speech_format not in ASK_SPEECH_FORMATS:
        raise HTTPException(400, f"speech_format must be one of {', '.join(ASK_SPEECH_FORMATS)}")
    if mode not in MODES:
        raise HTTPException(400, f"mode must be one of {', '.join(MODES)}")
    sess = sessions.get_or_create(session_id or None)

    # ---- photo (optional) --------------------------------------------------------
    img_bytes: bytes | None = None
    media_type: str | None = None
    new_image = False
    raw = await _read_upload(image, settings.max_upload_bytes, "image")
    if raw is not None:
        try:
            img_bytes, media_type, _ = images.normalise(raw, settings.max_image_edge)
        except ValueError as e:
            raise HTTPException(400, str(e)) from e
        new_image = True
    elif sess.last_image is not None:
        img_bytes, media_type = sess.last_image, sess.last_media_type   # the session's photo stays referenced

    # ---- spoken question (optional) ----------------------------------------------
    transcript: str | None = None
    transcript_error: str | None = None
    a = await _read_upload(audio, settings.max_upload_bytes, "audio")
    if a is not None:
        try:
            tr = await run_in_threadpool(stt.transcribe, a, audio.filename or "", audio.content_type or "", settings, language)
            transcript = tr.text
        except ProviderError as e:
            if not question.strip():
                raise                      # nothing else to answer: surface the STT problem
            transcript_error = str(e)
            log.warning("transcription failed: %s", e)
        if transcript:
            question = f"{question} {transcript}".strip()

    # ---- build the turn ------------------------------------------------------------
    has_image = img_bytes is not None
    question = question.strip()
    eff_mode = _effective_mode(mode, question, has_image, new_image)
    q_text = user_question(eff_mode, question, language)
    if not q_text.strip():                       # only possible without any photo (a photo alone is identified)
        if a is not None and not transcript:
            raise HTTPException(422, "I didn't catch that — the recording came back empty")
        raise HTTPException(400, "say or type a question, or attach a photo")
    if has_image and not new_image:
        q_text = f"{PREVIOUS_PHOTO_NOTE} {q_text}"

    result = None
    try:
        result = await run_in_threadpool(_answer, provider, settings, img_bytes, media_type, q_text, sess.turns)
        answer = result.answer
    except ModelRefused:
        answer = REFUSAL_ANSWER
    sessions.record(sess, q_text, answer.model_dump_json(), img_bytes if new_image else None, media_type or "image/jpeg")

    # ---- outputs -------------------------------------------------------------------
    speech_text = answer.speech_text
    morse_out: MorseOut | None = None
    if want_morse:
        morse_out = build_morse(morse_text_for(answer, max_short_chars), morse_char_wpm, morse_overall_wpm,
                                morse_channels, max_short_chars)

    speech = speech_adpcm = None
    speech_error = None
    if want_speech is None:
        want_speech = settings.tts_enabled
    if want_speech:
        try:
            if speech_format in ("mp3", "both"):
                res = await run_in_threadpool(tts.synthesize, speech_text, settings, voice=voice, fmt="mp3")
                speech = res.to_speech_out()
            if speech_format in ("adpcm16k", "both"):
                res = await run_in_threadpool(tts.synthesize, speech_text, settings, voice=voice, fmt="adpcm16k")
                speech_adpcm = res.to_speech_out()
        except ProviderError as e:
            speech_error = str(e)
            log.warning("tts failed: %s", e)
        except Exception as e:  # noqa: BLE001 - speech is best-effort; the text answer still goes out
            speech_error = f"tts failed: {e}"
            log.exception("tts failed")

    return AskResponse(
        id=uuid.uuid4().hex[:12],
        session_id=sess.id,
        answer=answer.answer,
        speech_text=speech_text,
        follow_up=answer.follow_up or None,
        subject=answer.subject,
        confidence=answer.confidence,
        warnings=answer.warnings,
        mode=eff_mode,
        had_image=has_image,
        transcript=transcript,
        transcript_error=transcript_error,
        speech=speech,
        speech_adpcm=speech_adpcm,
        speech_error=speech_error,
        short=morse_out.text if morse_out else None,
        morse=morse_out,
        provider=result.provider if result else (provider or settings.provider),
        model=result.model if result else "",
        latency_ms=int((time.time() - t0) * 1000),
        usage=Usage(input_tokens=result.input_tokens, output_tokens=result.output_tokens) if result else Usage(),
        fallback_model=result.fallback_model if result else None,
    )


# ---------------------------------------------------------------------------
# /v1/transcribe — push-to-talk preview
# ---------------------------------------------------------------------------
@app.post("/v1/transcribe", response_model=TranscribeResponse, dependencies=[Depends(require_token)])
async def transcribe_endpoint(
    settings: Annotated[Settings, Depends(get_settings)],
    audio: UploadFile = File(...),
    language: str = Form(default=""),
):
    t0 = time.time()
    data = await _read_upload(audio, settings.max_upload_bytes, "audio")
    if data is None:
        raise HTTPException(400, "empty audio upload")
    tr = await run_in_threadpool(stt.transcribe, data, audio.filename or "", audio.content_type or "", settings, language)
    return TranscribeResponse(text=tr.text, provider=tr.provider, model=tr.model, audio_format=tr.audio_format,
                              language=tr.language, latency_ms=int((time.time() - t0) * 1000))


# ---------------------------------------------------------------------------
# /v1/speech — text to audio
# ---------------------------------------------------------------------------
def _speech_response(text: str, voice: str, fmt: str, settings: Settings, accept: str) -> Response:
    if fmt not in SPEECH_FORMATS:
        raise HTTPException(400, f"format must be one of {', '.join(SPEECH_FORMATS)}")
    res = tts.synthesize(text, settings, voice=voice, fmt=fmt)
    if "application/json" in (accept or "") and "*/*" not in accept:
        return JSONResponse(res.to_speech_out().model_dump(), headers=res.headers())
    return Response(content=res.data, media_type=res.mime, headers=res.headers())


@app.get("/v1/speech", dependencies=[Depends(require_token)],
         responses={200: {"content": {"audio/mpeg": {}, "audio/x-mcring-adpcm": {}, "application/json": {}}}})
def speech_get(
    settings: Annotated[Settings, Depends(get_settings)],
    text: Annotated[str, Query(min_length=1, max_length=4000)],
    voice: str = "",
    format: str = "mp3",
    accept: Annotated[str | None, Header()] = None,
):
    """Audio bytes by default (mp3, or 16 kHz mcring ADPCM with format=adpcm16k); JSON with Accept: application/json."""
    return _speech_response(text, voice, format, settings, accept or "")


@app.post("/v1/speech", dependencies=[Depends(require_token)],
          responses={200: {"content": {"audio/mpeg": {}, "audio/x-mcring-adpcm": {}, "application/json": {}}}})
def speech_post(
    settings: Annotated[Settings, Depends(get_settings)],
    req: SpeechRequest,
    accept: Annotated[str | None, Header()] = None,
):
    return _speech_response(req.text, req.voice, req.format, settings, accept or "")


# ---------------------------------------------------------------------------
# /v1/morse — optional silent pattern (no LLM)
# ---------------------------------------------------------------------------
@app.post("/v1/morse", response_model=MorseOut, dependencies=[Depends(require_token)])
def morse_endpoint(req: MorseRequest):
    return build_morse(req.text, req.char_wpm, req.overall_wpm, req.channels)


@app.get("/")
def root():
    return {"service": "mcring backend", "version": VERSION, "docs": "/docs",
            "endpoints": ["/v1/ask", "/v1/transcribe", "/v1/speech", "/v1/morse", "/v1/health"]}
