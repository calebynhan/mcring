# 6. Getting started (today, with or without hardware)

The loop is: hold the ring → ask → hear Claude. Everything below gets you to that loop with
progressively more hardware. You need an `ANTHROPIC_API_KEY` for the answers and, for spoken
questions, either an `OPENAI_API_KEY` (speech-to-text default, `gpt-4o-mini-transcribe`) or a
local faster-whisper (`MCRING_STT_PROVIDER=local`). Typed questions need only the Anthropic key.

## A. No hardware: talk to Claude from the terminal

```bash
git clone <this repo> && cd mcring
python -m venv .venv && . .venv/bin/activate
(cd backend && pip install -r requirements.txt)   # backend deps + python/mcring_core (editable; run from backend/ so ../python resolves)
pip install -e 'tools/ring-cli[mic]'              # the mcring CLI; [mic] = sounddevice for the laptop microphone
cp backend/.env.example backend/.env                               # put ANTHROPIC_API_KEY and OPENAI_API_KEY in it
(cd backend && uvicorn app.main:app --port 8000 &)
curl -s localhost:8000/v1/health                                   # {"status":"ok",...,"stt":"openai","tts":"none",...}

mcring talk --no-ring                     # Enter → speak → Enter → the answer is spoken by your OS voice
mcring talk --no-ring --image ~/Pictures/plant.jpg     # same, with a photo attached to the first question
mcring ask ~/Pictures/plant.jpg -q "what is this and is it dangerous?" --speak   # typed question, no mic
mcring ask --audio question.wav --mode chat            # a recorded question, no photo
```

Pair Bluetooth headphones to the laptop and the answer plays there — the same routing the phone
app relies on. `--server-tts` plays the backend's mp3 voice instead of the OS voice (needs
`MCRING_TTS_PROVIDER=openai` in `.env`); `--mode chat` never attaches a photo; the conversation
continues in the same session until you quit.

No `OPENAI_API_KEY`? Either `pip install faster-whisper` and set `MCRING_STT_PROVIDER=local`
(first run downloads the `base.en` model, ≈ 150 MB), or stick to typed questions
(`mcring ask … -q`) — voice uploads then answer 501 with a message that says why.

## B. Stage-0 bench rig

**No soldering iron?** Order `hardware/bom/stage0-devkit-solderless.csv` instead: a pre-soldered XIAO in Seeed's expansion base with plug-in haptic and accelerometer boards. Build it with `pio run -e xiao_esp32s3_sense_base -t upload` and follow `docs/07-build-guide.md` §1.12 and `hardware/pcb/out/wiring_stage0_solderless.png`. Only the optional speaker amp still needs its header pins fitted (press-fit hammer headers avoid solder).

1. Order `hardware/bom/stage0-devkit.csv`. For the ring-speaker path add an Adafruit-style
   MAX98357A I2S breakout and an 8 Ω 10 mm speaker (optional; the headphone path needs nothing).
2. Wire per `firmware/ring-esp32s3/README.md` — the button on D1 is enough to start; the speaker
   goes on D6 (LRC) / D7 (BCLK) / D10 (DIN).
3. `pip install platformio && cd firmware/ring-esp32s3 && pio run -e xiao_esp32s3_sense -t upload`
4. `mcring scan`, then:

   ```bash
   mcring talk                               # hold the ring button, ask, release → answer in your headphones
   mcring talk --ring-mic                    # record with the ring's PDM mic instead of the laptop's
   mcring talk --ring-mic --ring-speaker     # answer on the ring speaker (needs the MAX98357A wired)
   mcring say "hello from the ring" --ring-speaker --volume 160    # speaker test, no AI
   mcring events                             # watch BUTTON_DOWN / BUTTON_UP / REC_* / AUDIO_* arrive
   mcring listen                             # unattended bridge: ring photos and clips → backend → spoken answer + cues
   ```

   A short press is a photo only; holding ≥ 0.7 s is an "ask"; a double tap is a hands-free ask.
   The ring ticks once when it starts listening and twice when the answer arrives.
5. Or build the phone app: `cd app && npm install && npx expo prebuild && npx expo run:android`
   (or `run:ios`), set *Backend URL* in Settings, pick *Voice in* (ring mic or phone/headset mic)
   and *Speak answers* (phone voice or server voice). Pair your headphones to the phone as usual.
   Turn on *Ring speaker* only after the ring reports `SPEAKER_OK` (speaker pins configured).

## C. Tests

```bash
(cd python/mcring_core && pytest)   # codecs + C cross-check incl. events / audio-out (needs a C compiler)   → 36 passed
(cd backend && pytest)              # API with mocked LLM, STT and TTS providers                             → 77 passed
(cd tools/ring-cli && pytest)       # push-to-talk, pacing, BLE client logic with fake transports            → 24 passed
(cd app && npm test && npm run typecheck)   # jest (5 suites, 33 tests) + tsc --noEmit
(cd firmware/ring-esp32s3 && pio test -e native)   # Unity host tests: packets, events, audio-out, CRC, ADPCM, Morse
```

## D. Optional: the silent pattern (Morse)

Morse is off everywhere by default. To see the legacy output anyway:

```bash
mcring ask ~/Pictures/plant.jpg -q "what is this?" --morse --echo --beep   # request the pattern and show/beep it
mcring listen --morse                                                      # also play it on the ring's LED/haptic
mcring morse "FOXGLOVE TOXIC" --beep                                       # local encoder, no backend
```

Spec and timing: `protocol/morse.md`.
