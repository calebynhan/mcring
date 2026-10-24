# mcring desktop companion (`mcring` CLI)

A Python stand-in for the phone app, **voice-first**. It talks BLE to the ring with
[bleak](https://github.com/hbldh/bleak) (macOS / Linux / Windows), records your question (laptop
mic or the ring's mic), sends it with the latest photo to the backend and speaks the answer on the
computer — or on the ring's own speaker. It also lets you exercise the whole AI loop with **no
hardware at all** (`mcring ask photo.jpg --audio question.wav`).

```bash
cd tools/ring-cli
pip install -e ../../python/mcring_core -e '.[mic]'        # [mic] = sounddevice for the laptop microphone

mcring talk --backend http://localhost:8000                 # Enter: record · Enter: stop & ask · hear the answer
mcring talk --ring-mic --ring-speaker                       # record with the ring mic, answer on the ring speaker
mcring talk --no-ring --image ~/Pictures/plant.jpg          # no ring: laptop mic + a photo file
mcring listen --backend http://localhost:8000               # the real loop: press / hold the ring button
mcring ask ~/Pictures/any-photo.jpg -q "is it safe to touch?" --speak   # no ring, no mic
mcring ask --audio question.wav --mode chat                 # a voice clip, no photo
mcring say "hello from the ring" --ring-speaker --volume 160  # test the ring speaker
mcring events                                               # print button / tap / record / audio events
mcring scan                                                 # find the ring
mcring config speaker_volume 200                            # SET_CONFIG (also cues_mask, mic_source_hint, trigger_mask, …)
```

## `mcring talk` — push-to-talk

Terminals have no key-up events, so: **Enter** starts recording, **Enter** again stops and asks.
With a ring connected, **holding the ring button** does the same (a short press is a photo); with
`--ring-mic` the ring records (`RECORD_START` / `RECORD_STOP`) and sends a 16 kHz ADPCM clip,
otherwise the laptop mic records 16 kHz WAV between `BUTTON_DOWN` and `BUTTON_UP`. The question
goes to `/v1/ask` with the latest photo if one arrived in the last 20 s (visual modes ask the ring
for one if none is fresh; `--mode chat` never attaches a photo). The answer is spoken with the OS
voice (`say`, `espeak-ng`, …) or the server's mp3 (`--server-tts`, played with `afplay` / `mpg123`
/ `ffplay`), and with `--ring-speaker` streamed to the ring as 16 kHz ADPCM, paced in bursts so the
ring's ~400 ms buffer never overruns. Ring events are printed as they arrive; the ring gets short
cues only ("listening" tick, "answer ready" double tick, error buzz).

Inside `talk` / `listen`: `c` captures a photo, `t <text>` asks by text, `r` toggles a ring-mic
recording (`listen`), `s` stops ring audio, `q` quits.

## Legacy silent pattern

Morse output is no longer on by default anywhere. `--morse` on `ask` / `listen` / `talk` requests
the pattern from the backend and plays it on the ring (and in the terminal with `--echo` / `--beep`);
`mcring morse` and `mcring send` still play Morse locally / on the ring.

Tests: `pytest` (BLE and HTTP are mocked; the laptop mic is optional and mocked out).
