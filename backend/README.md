# mcring backend

A small FastAPI service that turns a ring photo (+ optional typed or spoken question) into:

* a spoken answer (`answer`, 1–3 sentences),
* a Morse-friendly `short` answer (≤ 32 chars, A–Z 0–9),
* the exact Morse unit pattern and a ready-to-write ring Feedback packet,
* optionally server-side speech (phone-side TTS is the default).

Default model: **Claude Opus 5.5** via the Anthropic SDK with structured JSON output and
server-side refusal fallbacks enabled (`MCRING_ANTHROPIC_FALLBACKS=1`). OpenAI ("ChatGPT") is
an optional second provider selected per request with `provider=openai`.

## Run

```bash
cd backend
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # add ANTHROPIC_API_KEY
uvicorn app.main:app --reload --port 8000
```

Docker (from the repo root): `docker build -f backend/Dockerfile -t mcring-backend . && docker run -p 8000:8000 --env-file backend/.env mcring-backend`

## API

`POST /v1/ask` — multipart/form-data

| field | type | default | notes |
|---|---|---|---|
| `image` | file | – | JPEG/PNG/WebP. Optional if `session_id` has a previous image |
| `audio` | file | – | voice question: WAV, or raw mcring ADPCM (`.adpcm`) |
| `question` | str | "" | free text |
| `mode` | str | identify | identify · describe · read_text · translate · custom |
| `provider` | str | env | anthropic · openai |
| `session_id` | str | new | follow-up questions reuse the last image |
| `want_morse` | bool | true | |
| `want_speech` | bool | false | server TTS (needs `MCRING_TTS_PROVIDER=openai`) |
| `morse_char_wpm` / `morse_overall_wpm` | int | 15 / 8 | Farnsworth timing |
| `morse_channels` | int | 3 | bit0 LED, bit1 haptic, bit2 buzzer, bit3 aux |
| `max_short_chars` | int | 32 | |
| `language` | str | en | spoken answer language |

Response: see `protocol/schemas/ask_response.schema.json`.

```bash
curl -s -F image=@flower.jpg -F question="is it safe to touch?" localhost:8000/v1/ask | jq .
```

`POST /v1/morse` `{ "text": "FOXGLOVE TOXIC", "char_wpm": 15, "overall_wpm": 8 }` → pattern only.

`GET /v1/health`

Set `MCRING_API_TOKEN` to require `Authorization: Bearer <token>` from the companion.

## Tests

```bash
pytest           # provider calls are mocked; no API key needed
```
