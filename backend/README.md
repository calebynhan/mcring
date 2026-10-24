# mcring backend

The voice brain behind the ring. A small FastAPI service that turns a **spoken (or typed) question — with
or without a ring photo —** into:

* a spoken answer (`answer`, 1–3 sentences written to be read aloud, plus an optional `follow_up`),
* speech audio, either **mp3** for the phone / the wearer's own Bluetooth headphones or **16 kHz mcring
  ADPCM** the phone streams straight to the ring's speaker (optional server-side TTS; by default the
  phone's own TTS engine speaks `speech_text`),
* a transcription of the question when it came in as audio (ring mic clip or phone recording),
* optionally a "silent pattern" (Morse unit pattern + ring Feedback packet) — off by default.

Default model: **Claude Opus 5.5** via the Anthropic SDK with structured JSON output and server-side
refusal fallbacks (`MCRING_ANTHROPIC_FALLBACKS=1`). OpenAI ("ChatGPT") is an optional second answer
provider selected per request with `provider=openai`.

## Audio topology (what talks to what)

```
ring mic ──PDM→ADPCM (BLE)──▶ phone ──/v1/ask (audio=.adpcm)──▶ backend ──STT──▶ text ──▶ Claude
headset mic ─(phone records while the ring button is held)─▶ phone ──/v1/ask (audio=.m4a)──▶ backend
backend ──answer + mp3──▶ phone ──▶ Bluetooth headphones / phone speaker        (default output)
backend ──answer + adpcm16k──▶ phone ──BLE AUDIO_OUT (0x0008)──▶ ring speaker  (optional output)
```

The ring never pairs to headphones and never talks to the backend; the phone routes everything.

## Run

```bash
cd backend
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt           # includes openai + numpy; faster-whisper is commented out
cp .env.example .env                      # add ANTHROPIC_API_KEY (+ OPENAI_API_KEY for speech)
uvicorn app.main:app --reload --port 8000
```

Docker, built from the **repo root** (the image also needs `python/mcring_core`, which
`requirements.txt` installs with `-e ../python/mcring_core`):
`docker build -f backend/Dockerfile -t mcring-backend . && docker run -p 8000:8000 --env-file backend/.env mcring-backend`

### Speech providers

| env | values | notes |
|---|---|---|
| `MCRING_STT_PROVIDER` | `openai` (default) · `local` · `none` | speech-to-text for the question |
| `MCRING_STT_MODEL` | `gpt-4o-mini-transcribe` | OpenAI model (needs `OPENAI_API_KEY`) |
| `MCRING_WHISPER_MODEL` | `base.en` | faster-whisper model for `local` (also `small`, `medium`, `large-v3`, …) |
| `MCRING_TTS_PROVIDER` | `none` (default) · `openai` | `none` = the phone speaks; `openai` = `gpt-4o-mini-tts` on the server |
| `MCRING_TTS_VOICE` | `alloy` | default voice; per-request `voice` overrides |

**Local STT** (`MCRING_STT_PROVIDER=local`) needs the optional dependency: `pip install faster-whisper`
(or `pip install -e '.[local-stt]'`). It is imported lazily; without it the voice endpoints answer
**501** with a message that says so. faster-whisper decodes m4a/mp3/ogg uploads through PyAV, which
ships its own ffmpeg libraries, so no system ffmpeg is required. The first request downloads the model
(`base.en` ≈ 150 MB) into the Hugging Face cache; WAV and ring ADPCM clips work out of the box.

**Ring-speaker audio** (`adpcm16k`) is produced without any mp3 decoding: the TTS provider is asked for
raw PCM (OpenAI: 24 kHz 16-bit mono), which is low-passed and resampled to 16 kHz (polyphase FIR with
numpy, linear interpolation without) and encoded with `mcring_core.adpcm` — the same 132-byte / 256-sample
block format the firmware decoder plays (`AUDIO_START codec=2`, `AUDIO_DATA` blocks).

## API

All `/v1/*` endpoints except `/v1/health` require `Authorization: Bearer <MCRING_API_TOKEN>` when the
token is set. Provider problems come back as `{"detail": ..., "retryable": bool}` with the upstream's
status (429/502/503), **501** when a feature isn't configured/installed, 415 for unknown audio.

### `POST /v1/ask` — one voice turn (multipart/form-data)

| field | type | default | notes |
|---|---|---|---|
| `question` | str | "" | typed text; combined with the transcript when `audio` is also sent |
| `audio` | file | – | spoken question: WAV, m4a/mp4 (phone recording), mp3/ogg/flac/webm, or raw mcring ADPCM (`.adpcm` / `audio/x-mcring-adpcm`) |
| `image` | file | – | **optional.** JPEG/PNG/WebP from the ring. Omit for a pure voice turn; a photo already in the session stays referenced |
| `mode` | str | identify | identify · describe · read_text · translate · custom · **chat** — the prompt template for a **new** photo. Without any photo every mode behaves as `chat` (question used verbatim); a follow-up question about the session's earlier photo is used verbatim too (`custom`); a photo with no question is identified whatever the mode. The effective mode comes back in `mode` |
| `session_id` | str | new | conversation memory (last 8 turns + last photo), 30 min TTL |
| `language` | str | en | answer language |
| `want_speech` | bool | auto | default **true when a TTS provider is configured**, else false |
| `speech_format` | str | mp3 | `mp3` · `adpcm16k` · `both` |
| `voice` | str | env | TTS voice |
| `provider` | str | env | anthropic · openai |
| `want_morse` | bool | **false** | optional silent pattern; text = `subject` or the start of the answer |
| `morse_char_wpm` / `morse_overall_wpm` / `morse_channels` / `max_short_chars` | | 15 / 8 / 3 / 32 | only with `want_morse` |

Response (JSON): `answer`, `speech_text` (answer + follow_up — exactly what to say), `follow_up`,
`subject`, `confidence`, `warnings`, `mode` (effective), `had_image`, `transcript`, `transcript_error`,
`speech` (`{format:"mp3", mime:"audio/mpeg", audio_b64, voice}`), `speech_adpcm`
(`{format:"adpcm16k", mime:"audio/x-mcring-adpcm", audio_b64, sample_rate:16000, blocks, duration_ms}`),
`speech_error`, `short` + `morse` (only with `want_morse`), `provider`, `model`, `latency_ms`, `usage`,
`fallback_model`.

```bash
# voice-only turn, phone recording
curl -s -F audio=@question.m4a localhost:8000/v1/ask | jq .speech_text
# photo + ring-mic clip, answer for the ring speaker
curl -s -F image=@flower.jpg -F audio=@clip.adpcm -F speech_format=adpcm16k localhost:8000/v1/ask | jq '.answer, .speech_adpcm.blocks'
# follow-up in the same conversation (the photo stays referenced; the question is answered as asked, whatever `mode` says)
curl -s -F session_id=$SID -F question="is it edible?" localhost:8000/v1/ask | jq .answer
```

Rules: a turn needs a question (text or audio) **or** a photo; with neither → 400 (a photo alone is
identified, even with `mode=custom`/`chat`). If the recording transcribes to nothing and there is no
photo → 422. If speech-to-text fails and there is no typed question → the STT error
(e.g. 501) is returned; with a typed question the turn goes ahead and `transcript_error` is set.
Speech synthesis is best-effort: a failure sets `speech_error` and the text answer is still returned.

### `POST /v1/transcribe` — push-to-talk preview

multipart `audio` (same formats as above) + optional `language` → `{text, provider, model, audio_format, language, latency_ms}`.

### `GET|POST /v1/speech` — text to audio

`GET /v1/speech?text=...&voice=...&format=mp3|adpcm16k` or `POST {"text", "voice", "format"}`.
Returns the audio bytes (`audio/mpeg` or `audio/x-mcring-adpcm`) with `X-Mcring-Format`, `X-Mcring-Voice`
and, for ADPCM, `X-Mcring-Sample-Rate`, `X-Mcring-Blocks`, `X-Mcring-Duration-Ms` headers — the phone can
hand the body straight to the ring in `AUDIO_DATA` writes. Send `Accept: application/json` to get the
same `speech` object as `/v1/ask` (base64) instead. 501 when `MCRING_TTS_PROVIDER=none`.

### `POST /v1/morse` — optional silent pattern

`{ "text": "FOXGLOVE TOXIC", "char_wpm": 15, "overall_wpm": 8 }` → unit pattern + ring packet, no LLM.

### `GET /v1/health`

`{status, version, provider, model, tts, stt, speech_default, speech_formats}`.

## Tests

```bash
pytest           # LLM, STT and TTS providers are mocked; no API keys or network needed
```

The speech tests feed a fake TTS that returns a 440 Hz sine at 24 kHz and check that the `adpcm16k`
output decodes to the expected number of 256-sample blocks with the tone intact, with and without numpy.

The STT, LLM and TTS clients are blocking; `/v1/ask` and `/v1/transcribe` run them through Starlette's
threadpool (`run_in_threadpool`) so one slow voice turn does not stall other requests, and a test
asserts that none of the three is ever called on the event loop.
